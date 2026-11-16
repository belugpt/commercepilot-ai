"""Explicitly enabled text replies; acceptance and signed delivery evidence stay distinct."""
import json
import os
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from commercepilot.domain import Action, PolicyInput
from commercepilot.policy import authorize
from commercepilot.services import Conflict, Missing, now


class ProviderRejected(Exception):
    pass


class MetaTextSender:
    def __init__(self, access_token, version, phone_number_id, transport=None):
        if not re.fullmatch(r"v[0-9]+\.0", version) or not re.fullmatch(r"[0-9]{1,100}", phone_number_id):
            raise ValueError("explicit valid Meta version and phone number ID required")
        self._token, self.version, self.phone_number_id = access_token, version, phone_number_id
        self.transport = transport or self._post

    def _post(self, phone_id, payload):
        req = Request(f"https://graph.facebook.com/{self.version}/{phone_id}/messages", data=json.dumps(payload).encode(), headers={"Authorization": "Bearer "+self._token, "Content-Type":"application/json"})
        try:
            with urlopen(req, timeout=20) as response:
                return json.loads(response.read(1_000_000))
        except HTTPError as e:
            # 5xx could follow an accepted mutation. Never retry ambiguous effects.
            if 400 <= e.code < 500:
                raise ProviderRejected("provider_rejected") from None
            raise RuntimeError("provider_outcome_unknown") from None

    def send(self, phone_id, recipient, text):
        if phone_id != self.phone_number_id:
            raise ProviderRejected("phone_not_configured")
        result = self.transport(phone_id, {"messaging_product":"whatsapp", "recipient_type":"individual", "to":recipient, "type":"text", "text":{"body":text,"preview_url":False}})
        reference = result["messages"][0]["id"]
        if not isinstance(reference,str) or not reference or len(reference)>512:
            raise RuntimeError("invalid_provider_reference")
        return reference


def configured_sender():
    if os.getenv("WHATSAPP_SEND_ENABLED", "false").lower() != "true":
        return None
    values = [os.getenv(k) for k in ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_GRAPH_VERSION", "WHATSAPP_PHONE_NUMBER_ID")]
    if not all(values):
        raise ValueError("sending requires access token, explicit Graph version and phone number ID")
    return MetaTextSender(*values)


class Delivery:
    def __init__(self, services, sender=None, clock=None):
        self.services, self.db, self.sender = services, services.db, sender
        self.clock = clock or time.time

    def records(self, merchant):
        with self.db.connect() as c:
            return [dict(r) for r in c.execute("SELECT outbox_id,state,provider_message_id,reason,created_at,updated_at FROM whatsapp_deliveries WHERE merchant_id=? ORDER BY created_at DESC LIMIT 100", (merchant,))]

    @staticmethod
    def reconcile(c, provider_id):
        delivery = c.execute("SELECT * FROM whatsapp_deliveries WHERE provider_message_id=?", (provider_id,)).fetchone()
        if not delivery:
            return
        receipts = c.execute("SELECT status,body FROM whatsapp_status_receipts WHERE provider_message_id=? AND waba_id=? AND phone_number_id=?", (provider_id, delivery["waba_id"], delivery["phone_number_id"])).fetchall()
        ranks={"submitting":0,"uncertain":0,"accepted":1,"failed":1,"sent":2,"delivered":3,"read":4}
        current=delivery["state"]
        for receipt in receipts:
            event=json.loads(receipt["body"])
            if event.get("recipient_id") != delivery["recipient"]:
                continue
            state=receipt["status"]
            if state=="failed" and current in {"accepted","submitting","uncertain","failed"}:
                current="failed"
            elif state in ranks and ranks[state]>ranks[current]:
                current=state
        c.execute("UPDATE whatsapp_deliveries SET state=?,updated_at=? WHERE outbox_id=?",(current,now(),delivery["outbox_id"]))

    def send(self, merchant, outbox_id):
        if self.sender is None:
            raise Conflict("outbound sending is disabled; configure a scoped provider account first")
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("""SELECT o.*,b.sender_key,b.enabled,i.phone_number_id,i.waba_id,i.body AS inbound_body
                FROM whatsapp_outbox o JOIN whatsapp_inbox i ON i.id=o.inbox_id AND i.merchant_id=o.merchant_id
                JOIN whatsapp_bindings b ON b.id=i.binding_id AND b.merchant_id=i.merchant_id
                WHERE o.merchant_id=? AND o.id=?""",(merchant,outbox_id)).fetchone()
            if not row:
                raise Missing("reply draft not found")
            previous=c.execute("SELECT state FROM whatsapp_deliveries WHERE merchant_id=? AND outbox_id=?",(merchant,outbox_id)).fetchone()
            if previous:
                # A timed-out/crashed submission is never automatically replayed.
                return {"outbox_id":outbox_id,"state":previous["state"],"resubmitted":False}
            policy=c.execute("SELECT body FROM policies WHERE merchant_id=?",(merchant,)).fetchone()
            reason=authorize(Action.REPLY,PolicyInput.model_validate_json(policy["body"]) if policy else None)
            if reason or not row["enabled"]:
                raise Conflict("reply is outside the current autonomy or channel permissions")
            if not row["sender_key"].startswith("phone:"):
                raise Conflict("BSUID outbound support requires provider validation; reply not sent")
            timestamp=int(json.loads(row["inbound_body"])["timestamp"])
            if not 0 <= self.clock()-timestamp < 24*3600:
                raise Conflict("the verified inbound message is outside the text-reply window; use an approved template")
            recipient=row["sender_key"].split(":",1)[1]
            c.execute("INSERT INTO whatsapp_deliveries VALUES(?,?,?,?,?,'submitting',NULL,NULL,?,?)",(outbox_id,merchant,row["phone_number_id"],row["waba_id"],recipient,now(),now()))
            self.services.audit(c,merchant,"whatsapp.reply_submitting",outbox_id)
        try:
            reference=self.sender.send(row["phone_number_id"],recipient,row["body"])
            state,reason="accepted",None
        except ProviderRejected:
            reference,state,reason=None,"failed","provider_rejected"
        except Exception:
            reference,state,reason=None,"uncertain","provider_outcome_unknown"
        with self.db.connect() as c:
            c.execute("UPDATE whatsapp_deliveries SET state=?,provider_message_id=?,reason=?,updated_at=? WHERE merchant_id=? AND outbox_id=?",(state,reference,reason,now(),merchant,outbox_id))
            if reference:
                self.reconcile(c,reference)
            self.services.audit(c,merchant,"whatsapp.reply_"+state,outbox_id)
        return next(r for r in self.records(merchant) if r["outbox_id"]==outbox_id)
