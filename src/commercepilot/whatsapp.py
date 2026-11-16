"""Signed WhatsApp intake and durable local processing; delivery is a separate worker."""
import hashlib
import hmac
import json
import re
import time
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from commercepilot.services import Conflict, Missing, digest, now

MAX_BODY_BYTES = 1_000_000
MAX_ATTEMPTS = 5
LEASE_SECONDS = 120
MAX_EVENT_AGE = 7 * 24 * 3600  # local admission policy, not a Meta guarantee


class WebhookError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


class Text(BaseModel):
    body: str = Field(min_length=1, max_length=8000, pattern=r"\S")


class Attachment(BaseModel):
    id: str = Field(pattern=r"^[0-9]{1,100}$")
    mime_type: str | None = Field(default=None,max_length=100)
    sha256: str | None = Field(default=None,max_length=100)
    caption: str | None = Field(default=None,max_length=8000)


class Incoming(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(min_length=1, max_length=512)
    sender: str | None = Field(default=None, alias="from", max_length=100)
    from_user_id: str | None = Field(default=None, max_length=200)
    timestamp: str = Field(pattern=r"^\d{1,12}$")
    type: str = Field(min_length=1, max_length=50)
    text: Text | None = None
    image: Attachment | None = None
    document: Attachment | None = None
    audio: Attachment | None = None
    video: Attachment | None = None

    def sender_keys(self):
        keys = []
        if self.from_user_id:
            keys.append("bsuid:" + self.from_user_id)
        if self.sender and re.fullmatch(r"[0-9]{5,20}", self.sender):
            keys.append("phone:" + self.sender)
        return keys


class WhatsApp:
    def __init__(self, services, agent, app_secret=None, verify_token=None, clock=None, media_loader=None):
        self.services, self.db, self.agent = services, services.db, agent
        self._secret, self._verify_token = app_secret, verify_token
        self.clock = clock or time.time
        self.media_loader = media_loader

    def verify_subscription(self, mode, token, challenge):
        if not self._verify_token:
            raise WebhookError(503, "whatsapp_not_configured")
        if mode != "subscribe" or not token or not hmac.compare_digest(token.encode(), self._verify_token.encode()):
            raise WebhookError(403, "verification_failed")
        if not challenge or len(challenge) > 1000:
            raise WebhookError(400, "invalid_challenge")
        return challenge

    def bind(self, merchant, waba_id, phone_number_id, sender_key):
        # Only the operator CLI may establish ownership mappings, after checking
        # the merchant identity. Provider contacts alone never grant authority.
        if not re.fullmatch(r"[0-9]{1,100}", waba_id) or not re.fullmatch(r"[0-9]{1,100}", phone_number_id):
            raise ValueError("numeric provider account identifiers required")
        if not re.fullmatch(r"(?:phone:[0-9]{5,20}|bsuid:[A-Za-z0-9._-]{1,200})", sender_key):
            raise ValueError("sender must be phone:<digits> or bsuid:<business-scoped-id>")
        binding, conversation = str(uuid4()), str(uuid4())
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if not c.execute("SELECT 1 FROM merchants WHERE id=?", (merchant,)).fetchone():
                raise Missing("merchant not found")
            if c.execute("SELECT 1 FROM whatsapp_bindings WHERE waba_id=? AND phone_number_id=? AND sender_key=?", (waba_id, phone_number_id, sender_key)).fetchone():
                raise Conflict("sender is already bound; inspect or revoke the existing binding")
            c.execute("INSERT INTO conversations VALUES(?,?,?)", (conversation, merchant, now()))
            c.execute("INSERT INTO whatsapp_bindings VALUES(?,?,?,?,?,?,1)", (binding, merchant, waba_id, phone_number_id, sender_key, conversation))
            self.services.audit(c, merchant, "whatsapp.sender_bound", binding)
        return {"id": binding, "conversation_id": conversation, "ownership_verification": "operator_attested"}

    def revoke(self, merchant, binding):
        with self.db.connect() as c:
            changed = c.execute("UPDATE whatsapp_bindings SET enabled=0 WHERE merchant_id=? AND id=?", (merchant, binding))
            if not changed.rowcount:
                raise Missing("binding not found")
            self.services.audit(c, merchant, "whatsapp.binding_revoked", binding)
        return {"revoked": True}

    def requeue(self, merchant, inbox_id):
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT i.*,b.enabled FROM whatsapp_inbox i JOIN whatsapp_bindings b ON b.id=i.binding_id WHERE i.merchant_id=? AND i.id=?", (merchant, inbox_id)).fetchone()
            if not row:
                raise Missing("inbox record not found")
            allowed = {"worker_error", "conversation_busy", "agent_planning_requires_review", "maximum_attempts_exceeded"}
            if row["state"] != "dead" or not row["enabled"] or row["reason"] not in allowed:
                raise Conflict("record cannot be retried; inspect the reason and channel authorization")
            if row["run_id"]:
                run = c.execute("SELECT state FROM agent_runs WHERE merchant_id=? AND id=?", (merchant, row["run_id"])).fetchone()
                if run and run["state"] == "planning":
                    raise Conflict("inspect or cancel the abandoned agent run before requeuing")
            c.execute("UPDATE whatsapp_inbox SET state='pending',attempts=0,available_at=?,reason=NULL,lease_token=NULL,lease_until=NULL WHERE id=?", (self.clock(), inbox_id))
            self.services.audit(c, merchant, "whatsapp.inbox_requeued", inbox_id)
        return {"id": inbox_id, "state": "pending"}

    def ingest(self, raw, signature):
        if not self._secret:
            raise WebhookError(503, "whatsapp_not_configured")
        if len(raw) > MAX_BODY_BYTES:
            raise WebhookError(413, "payload_too_large")
        expected = "sha256=" + hmac.new(self._secret.encode(), raw, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature.encode(), expected.encode()):
            raise WebhookError(401, "invalid_signature")
        try:
            payload = json.loads(raw)
            if payload["object"] != "whatsapp_business_account":
                raise ValueError("unsupported object")
            events = []
            statuses = []
            for entry in payload["entry"]:
                waba_id = entry["id"]
                if not isinstance(waba_id, str) or not re.fullmatch(r"[0-9]{1,100}", waba_id):
                    raise ValueError("invalid account")
                for change in entry["changes"]:
                    if change["field"] != "messages":
                        continue
                    value = change["value"]
                    if value.get("messaging_product") != "whatsapp":
                        raise ValueError("invalid product")
                    phone_id = value["metadata"]["phone_number_id"]
                    if not isinstance(phone_id, str) or not re.fullmatch(r"[0-9]{1,100}", phone_id):
                        raise ValueError("invalid number")
                    for message in value.get("messages", []):
                        incoming = Incoming.model_validate(message)
                        if incoming.type == "text" and incoming.text is None:
                            raise ValueError("missing text")
                        events.append((waba_id, phone_id, incoming))
                        if len(events) > 100:
                            raise ValueError("batch too large")
                    for status in value.get("statuses", []):
                        if not isinstance(status,dict) or not isinstance(status.get("id"),str) or len(status["id"])>512 or status.get("status") not in {"sent","delivered","read","failed"}:
                            raise ValueError("invalid delivery status")
                        if not isinstance(status.get("recipient_id"),str) or not re.fullmatch(r"[0-9]{5,20}",status["recipient_id"]):
                            # Status-only notifications without a phone recipient
                            # are not sufficient proof for this phone-only sender.
                            continue
                        statuses.append((waba_id,phone_id,status))
                        if len(statuses)>100:
                            raise ValueError("status batch too large")
        except (ValueError, TypeError, KeyError, AttributeError, ValidationError, RecursionError):
            raise WebhookError(422, "invalid_webhook_payload") from None
        counts = {"accepted": 0, "duplicates": 0, "ignored": 0, "conflicts": 0}
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            from commercepilot.delivery import Delivery
            for waba_id,phone_id,status in statuses:
                # Do not retain statuses for accounts this host does not map.
                if not c.execute("SELECT 1 FROM whatsapp_bindings WHERE waba_id=? AND phone_number_id=?",(waba_id,phone_id)).fetchone():
                    continue
                body=json.dumps(status,sort_keys=True)
                c.execute("INSERT OR IGNORE INTO whatsapp_status_receipts VALUES(?,?,?,?,?,?,?)",(digest(waba_id+":"+phone_id+":"+body),waba_id,phone_id,status["id"],status["status"],body,now()))
                Delivery.reconcile(c,status["id"])
            for waba_id, phone_id, message in events:
                candidates = []
                for sender in message.sender_keys():
                    row = c.execute("SELECT * FROM whatsapp_bindings WHERE waba_id=? AND phone_number_id=? AND sender_key=? AND enabled=1", (waba_id, phone_id, sender)).fetchone()
                    if row:
                        candidates.append(row)
                # Ambiguous phone/BSUID ownership cannot choose a tenant safely.
                if not candidates or len({r["merchant_id"] for r in candidates}) != 1:
                    counts["ignored"] += 1
                    continue
                binding = candidates[0]
                merchant = binding["merchant_id"]
                # Preserve pre-media normalized text hashes across upgrades.
                absent_media={name for name in {'image','document','audio','video'} if getattr(message,name) is None}
                body = message.model_dump_json(by_alias=True,exclude=absent_media)
                old = c.execute("SELECT id,merchant_id,payload_hash FROM whatsapp_inbox WHERE waba_id=? AND phone_number_id=? AND provider_message_id=?", (waba_id, phone_id, message.id)).fetchone()
                if old:
                    if old["payload_hash"] != digest(body):
                        c.execute("INSERT OR IGNORE INTO whatsapp_conflicts(merchant_id,inbox_id,incoming_hash,occurred_at) VALUES(?,?,?,?)", (old["merchant_id"], old["id"], digest(body), now()))
                        counts["conflicts"] += 1
                    else:
                        counts["duplicates"] += 1
                    continue
                reason = None
                if not message.sender_keys():
                    reason = "unsupported_sender_identity"
                elif message.type != "text" and not (self.media_loader and message.type in {'image','document','audio','video'} and getattr(message,message.type,None)):
                    reason = "unsupported_message_type"
                elif not self.clock() - MAX_EVENT_AGE <= int(message.timestamp) <= self.clock() + 300:
                    reason = "message_timestamp_outside_admission_window"
                inbox_id = str(uuid4())
                c.execute("INSERT INTO whatsapp_inbox(id,merchant_id,binding_id,provider_message_id,waba_id,phone_number_id,payload_hash,body,state,available_at,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                          (inbox_id, merchant, binding["id"], message.id, waba_id, phone_id, digest(body), body, "dead" if reason else "pending", self.clock(), reason, now()))
                self.services.audit(c, merchant, "whatsapp.inbox_accepted", inbox_id)
                counts["accepted"] += 1
        return counts

    def list_records(self, merchant, kind):
        queries = {
            "bindings": "SELECT id,waba_id,phone_number_id,sender_key,conversation_id,enabled FROM whatsapp_bindings WHERE merchant_id=? LIMIT 100",
            "inbox": "SELECT id,provider_message_id,state,attempts,run_id,reason,created_at FROM whatsapp_inbox WHERE merchant_id=? ORDER BY seq DESC LIMIT 100",
            "outbox": "SELECT id,inbox_id,run_id,body,state,created_at FROM whatsapp_outbox WHERE merchant_id=? ORDER BY created_at DESC LIMIT 100",
            "conflicts": "SELECT inbox_id,incoming_hash,occurred_at FROM whatsapp_conflicts WHERE merchant_id=? ORDER BY id DESC LIMIT 100",
        }
        if kind not in queries:
            raise ValueError("unknown collection")
        with self.db.connect() as c:
            return [dict(r) for r in c.execute(queries[kind], (merchant,))]

    def claim(self):
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("""SELECT i.*,b.conversation_id FROM whatsapp_inbox i
                JOIN whatsapp_bindings b ON b.id=i.binding_id AND b.merchant_id=i.merchant_id
                WHERE ((i.state='pending' AND i.available_at<=?) OR
                       (i.state='processing' AND i.lease_until<=?))
                AND NOT EXISTS(SELECT 1 FROM whatsapp_inbox earlier
                    JOIN whatsapp_bindings eb ON eb.id=earlier.binding_id
                    WHERE eb.conversation_id=b.conversation_id AND earlier.seq<i.seq
                    AND earlier.state IN ('pending','processing'))
                ORDER BY i.seq LIMIT 1""", (self.clock(), self.clock())).fetchone()
            if not row:
                return None
            token = str(uuid4())
            c.execute("UPDATE whatsapp_inbox SET state='processing',attempts=attempts+1,lease_token=?,lease_until=? WHERE id=?", (token, self.clock() + LEASE_SECONDS, row["id"]))
            self.services.audit(c, row["merchant_id"], "whatsapp.inbox_claimed", row["id"])
            return {**dict(row), "lease_token": token, "attempts": row["attempts"] + 1}

    def _guard(self, c, item):
        return bool(c.execute("""SELECT 1 FROM whatsapp_inbox i JOIN whatsapp_bindings b
            ON b.id=i.binding_id AND b.merchant_id=i.merchant_id
            WHERE i.id=? AND i.lease_token=? AND i.state='processing'
            AND i.lease_until>? AND b.enabled=1""", (item["id"], item["lease_token"], self.clock())).fetchone())

    def _retry(self, item, reason):
        with self.db.connect() as c:
            changed = c.execute("UPDATE whatsapp_inbox SET state=?,reason=?,available_at=?,lease_token=NULL,lease_until=NULL WHERE id=? AND lease_token=?",
                      ("dead" if item["attempts"] >= MAX_ATTEMPTS else "pending", reason,
                       self.clock() + min(300, 2 ** item["attempts"]), item["id"], item["lease_token"]))
            if changed.rowcount:
                event = "whatsapp.inbox_dead" if item["attempts"] >= MAX_ATTEMPTS else "whatsapp.inbox_retry_scheduled"
                self.services.audit(c, item["merchant_id"], event, item["id"])

    def process_one(self):
        item = self.claim()
        if not item:
            return None
        if item["attempts"] > MAX_ATTEMPTS:
            self._retry(item, "maximum_attempts_exceeded")
            return {"id": item["id"], "state": "dead"}
        try:
            with self.db.connect() as c:
                authorized = self._guard(c, item)
            if not authorized:
                self._retry({**item, "attempts": MAX_ATTEMPTS}, "binding_revoked_or_lease_lost")
                return {"id": item["id"], "state": "dead"}
            message = Incoming.model_validate_json(item["body"])
            if message.type == 'text':
                run = self.agent.turn(item["merchant_id"], item["conversation_id"], "whatsapp:" + item["id"], message.text.body,
                                      execution_guard=lambda c: self._guard(c, item))
            else:
                from commercepilot.media import capture
                run = capture(self,item,message)
            with self.db.connect() as c:
                c.execute("UPDATE whatsapp_inbox SET run_id=? WHERE id=? AND lease_token=?", (run["id"], item["id"], item["lease_token"]))
            if run["state"] == "planning":
                self._retry(item, "agent_planning_requires_review")
                return {"id": item["id"], "state": "waiting"}
            reply = self.render_reply(run)
            with self.db.connect() as c:
                c.execute("BEGIN IMMEDIATE")
                # Fencing prevents an expired worker from finalizing a new claim.
                owned = c.execute("SELECT 1 FROM whatsapp_inbox WHERE id=? AND lease_token=? AND lease_until>?", (item["id"], item["lease_token"], self.clock())).fetchone()
                if not owned:
                    return {"id": item["id"], "state": "lease_lost"}
                c.execute("UPDATE whatsapp_inbox SET state='completed',run_id=?,lease_token=NULL,lease_until=NULL,reason=NULL WHERE id=? AND lease_token=?", (run["id"], item["id"], item["lease_token"]))
                c.execute("INSERT OR IGNORE INTO whatsapp_outbox(id,merchant_id,inbox_id,run_id,body,created_at) VALUES(?,?,?,?,?,?)", (str(uuid4()), item["merchant_id"], item["id"], run["id"], reply, now()))
                self.services.audit(c, item["merchant_id"], "whatsapp.reply_drafted", item["id"])
            return {"id": item["id"], "state": "completed", "run_id": run["id"], "delivery": "draft_only"}
        except Conflict:
            self._retry(item, "conversation_busy")
        except Exception:
            self._retry(item, "worker_error")
        return {"id": item["id"], "state": "retry_or_dead"}

    @staticmethod
    def render_reply(run):
        result = run.get("result") or {}
        text = result.get("message", "This request needs review.")
        if result.get("caption"):
            text += "\n\n" + result["caption"]
        elif result.get("product"):
            text += "\n" + result["product"]["title"] + " (" + result["product"]["sku"] + ")"
        elif "products" in result:
            text += "\n" + ("\n".join(p["title"] + " (" + p["sku"] + ")" for p in result["products"][:20]) or "No products yet. Use /add Product title | SKU | NGN 5000.00 with your actual product details.")
        elif result.get("report"):
            report = result["report"]
            def amount(value):
                if value is None:
                    return "Unknown"
                currency = report.get("currency", "")
                if currency == "NGN":
                    major, minor = divmod(abs(value), 100)
                    return f"NGN {'-' if value < 0 else ''}{major:,}.{minor:02d}"
                return f"{value} minor units ({currency})"
            text += "\n" + str(report.get("day", "Supplied aggregates"))
            for key, label in [("net_sales_minor", "Net sales"), ("cash_after_refunds_minor", "Cash after refunds"), ("gross_profit_minor", "Gross profit"), ("operating_profit_minor", "Operating profit")]:
                text += "\n" + label + ": " + amount(report.get(key))
            if report.get("missing"):
                text += "\nMissing: " + ", ".join(report["missing"])
        elif result.get("expenses"):
            text += "\n" + "\n".join(f"{e['category']}: {e['amount_minor']} minor units ({e['currency']})" for e in result["expenses"][:20])
        elif result.get("forecast"):
            forecast=result["forecast"]
            text += "\nState: " + forecast["state"]
            if forecast["state"]=="insufficient_history":
                text += "\n" + forecast["required"]
            else:
                text += "\nMethod: " + forecast["method"]
                text += "\n" + "\n".join(f"{p['day']}: {p['base_minor']} minor units ({forecast['currency']})" for p in forecast["daily"])
                text += "\nEstimate only; scenarios and assumptions are available in the dashboard."
        elif result.get("variance"):
            variance=result["variance"]
            text += f"\nRevenue variance: {variance['revenue_variance_minor']} minor units\nExpense variance: {variance['expense_variance_minor']} minor units"
            text = text.replace('None minor units','Unknown')
        return text[:3500]
