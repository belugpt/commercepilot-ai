"""Persistent one-tool agent turns with validation, policy and atomic local effects."""
import json
import sqlite3
from datetime import timezone
from uuid import uuid4
from pydantic import ValidationError
from commercepilot.agent_schema import TOOL_SCHEMAS, ProfileInput
from commercepilot.domain import Action, PolicyInput, financial_report
from commercepilot.policy import authorize
from commercepilot.services import Conflict, Missing, digest, now


TOOL_ACTIONS = {
    "profile_save": Action.PROFILE, "product_create": Action.CREATE_PRODUCT,
    "catalogue_list": Action.READ_CATALOGUE, "caption_prepare": Action.CAPTION,
    "expense_capture": Action.EXPENSE, "expenses_list": Action.READ_EXPENSES,
    "report_calculate": Action.CALCULATE,
    "daily_report": Action.SALES_REPORT,
}
TOOL_CAPABILITIES = {
    "product_create": "catalogue", "catalogue_list": "catalogue",
    "caption_prepare": "content", "expense_capture": "economics",
    "expenses_list": "economics", "report_calculate": "economics",
    "daily_report": "economics",
}


class Agent:
    def __init__(self, services, planner):
        self.services, self.db, self.planner = services, services.db, planner

    def conversation(self, merchant):
        conversation_id = str(uuid4())
        with self.db.connect() as c:
            c.execute("INSERT INTO conversations VALUES(?,?,?)", (conversation_id, merchant, now()))
            self.services.audit(c, merchant, "conversation.created", conversation_id)
        return {"id": conversation_id, "planner_mode": self.planner.mode}

    @staticmethod
    def require_conversation(c, merchant, conversation):
        if not c.execute("SELECT 1 FROM conversations WHERE merchant_id=? AND id=?", (merchant, conversation)).fetchone():
            raise Missing("conversation not found")

    def context(self, merchant, conversation):
        with self.db.connect() as c:
            self.require_conversation(c, merchant, conversation)
            profile = c.execute("SELECT body FROM business_profiles WHERE merchant_id=?", (merchant,)).fetchone()
            products = c.execute("SELECT id,body FROM products WHERE merchant_id=? ORDER BY id LIMIT 50", (merchant,)).fetchall()
            history = c.execute("SELECT role,body FROM messages WHERE merchant_id=? AND conversation_id=? ORDER BY id DESC LIMIT 6", (merchant, conversation)).fetchall()
        return {"profile": json.loads(profile["body"]) if profile else None,
                "products": [{"id": p["id"], **json.loads(p["body"])} for p in products],
                "recent_messages": [{"role": r["role"], "body": r["body"][:2000]} for r in reversed(history)]}

    def history(self, merchant, conversation):
        with self.db.connect() as c:
            self.require_conversation(c, merchant, conversation)
            rows = c.execute("SELECT role,body,run_id,created_at FROM messages WHERE merchant_id=? AND conversation_id=? ORDER BY id LIMIT 200", (merchant, conversation)).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, merchant, run_id):
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM agent_runs WHERE merchant_id=? AND id=?", (merchant, run_id)).fetchone()
        if not row:
            raise Missing("agent run not found")
        return {"id": row["id"], "conversation_id": row["conversation_id"], "state": row["state"],
                "tool": row["tool"], "result": json.loads(row["result"]) if row["result"] else None}

    def runs(self, merchant):
        with self.db.connect() as c:
            ids = c.execute("SELECT id FROM agent_runs WHERE merchant_id=? ORDER BY created_at DESC LIMIT 100", (merchant,)).fetchall()
        return [self.get_run(merchant, row["id"]) for row in ids]

    def cancel(self, merchant, run_id):
        """Cancel an abandoned planning turn. A late planner cannot execute it."""
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT conversation_id,state FROM agent_runs WHERE merchant_id=? AND id=?", (merchant, run_id)).fetchone()
            if not row:
                raise Missing("agent run not found")
            if row["state"] == "planning":
                self.persist_completion(c, merchant, row["conversation_id"], run_id, "failed",
                                        {"message": "Planning cancelled; no local action executed.", "reason": "cancelled_by_owner"})
        return self.get_run(merchant, run_id)

    def turn(self, merchant, conversation, key, message, execution_guard=None):
        run_id = str(uuid4())
        # Reserve before planning: duplicate deliveries never spend model tokens twice.
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            self.require_conversation(c, merchant, conversation)
            old = c.execute("SELECT id,payload_hash FROM agent_runs WHERE merchant_id=? AND conversation_id=? AND idempotency_key=?", (merchant, conversation, key)).fetchone()
            if old:
                if old["payload_hash"] != digest(message):
                    raise Conflict("message key reused with different content")
                return self.get_run(merchant, old["id"])
            if c.execute("SELECT 1 FROM agent_runs WHERE merchant_id=? AND conversation_id=? AND state='planning'", (merchant, conversation)).fetchone():
                raise Conflict("conversation has an active turn; inspect its run before retrying")
            c.execute("INSERT INTO agent_runs VALUES(?,?,?, ?,?,'planning',NULL,NULL,NULL,?)", (run_id, merchant, conversation, key, digest(message), now()))
            c.execute("INSERT INTO messages(merchant_id,conversation_id,run_id,role,body,created_at) VALUES(?,?,?,'user',?,?)", (merchant, conversation, run_id, message, now()))
            self.services.audit(c, merchant, "agent.planning", run_id)
        try:
            decision = self.planner.propose(message, self.context(merchant, conversation))
            if not isinstance(decision, dict) or set(decision) != {"tool", "arguments"}:
                raise ValueError("invalid plan")
            tool = decision["tool"]
            if not isinstance(tool, str) or tool not in TOOL_SCHEMAS:
                raise ValueError("unknown tool")
            args = TOOL_SCHEMAS[tool].model_validate(decision["arguments"])
        except ValidationError:
            return self.complete(merchant, conversation, run_id, "clarification",
                                 {"message": "Required tool details are missing or invalid. Check the tool schema and supply the requested facts.", "reason": "invalid_tool_arguments"})
        except Exception:
            return self.complete(merchant, conversation, run_id, "failed",
                                 {"message": "Planning failed; no action was executed.", "reason": "planner_unavailable_or_invalid_output"})
        try:
            with self.db.connect() as c:
                c.execute("BEGIN IMMEDIATE")
                state_row = c.execute("SELECT state FROM agent_runs WHERE merchant_id=? AND id=?", (merchant, run_id)).fetchone()
                if state_row["state"] != "planning":
                    return self.get_run(merchant, run_id)
                c.execute("UPDATE agent_runs SET tool=?,arguments=? WHERE merchant_id=? AND id=?", (tool, args.model_dump_json(), merchant, run_id))
                if execution_guard is not None and not execution_guard(c):
                    state, result = "blocked", {"message": "The channel authorization or worker lease is no longer valid; no action was executed.", "reason": "channel_authorization_revoked"}
                elif tool == "clarify":
                    state, result = "clarification", {"message": args.question}
                else:
                    policy_row = c.execute("SELECT version,body FROM policies WHERE merchant_id=?", (merchant,)).fetchone()
                    policy = PolicyInput.model_validate_json(policy_row["body"]) if policy_row else None
                    action = Action(args.action) if tool == "external_request" else TOOL_ACTIONS[tool]
                    reason = authorize(action, policy)
                    if reason:
                        state, result = "blocked", {"message": "This action is outside the current automation permissions.", "reason": reason}
                    else:
                        state, result = self.execute(c, merchant, run_id, tool, args)
                    if policy_row:
                        result["policy_version"] = policy_row["version"]
                self.persist_completion(c, merchant, conversation, run_id, state, result)
        except (Missing, ValueError, sqlite3.IntegrityError):
            return self.complete(merchant, conversation, run_id, "clarification",
                                 {"message": "The referenced record is unavailable, the SKU already exists, or the financial inputs conflict. No changes were made.", "reason": "tool_validation_failed"})
        except Exception:
            return self.complete(merchant, conversation, run_id, "failed",
                                 {"message": "Execution failed; local changes were rolled back.", "reason": "tool_execution_failed"})
        return self.get_run(merchant, run_id)

    def persist_completion(self, c, merchant, conversation, run_id, state, result):
        body = json.dumps(result)
        c.execute("UPDATE agent_runs SET state=?,result=? WHERE merchant_id=? AND id=?", (state, body, merchant, run_id))
        c.execute("INSERT INTO messages(merchant_id,conversation_id,run_id,role,body,created_at) VALUES(?,?,?,'assistant',?,?)", (merchant, conversation, run_id, body, now()))
        self.services.audit(c, merchant, "agent." + state, run_id)

    def complete(self, merchant, conversation, run_id, state, result):
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute("SELECT state FROM agent_runs WHERE merchant_id=? AND id=?", (merchant, run_id)).fetchone()
            if current and current["state"] == "planning":
                self.persist_completion(c, merchant, conversation, run_id, state, result)
        return self.get_run(merchant, run_id)

    def execute(self, c, merchant, run_id, tool, args):
        """Local effects and result/audit commit together; no model prose proves success."""
        if tool == "profile_save":
            c.execute("INSERT INTO business_profiles VALUES(?,?,?) ON CONFLICT(merchant_id) DO UPDATE SET body=excluded.body,updated_at=excluded.updated_at", (merchant, args.model_dump_json(), now()))
            self.services.audit(c, merchant, "profile.saved", merchant)
            return "completed", {"message": "Business profile saved.", "profile": args.model_dump(mode="json")}
        profile = c.execute("SELECT body FROM business_profiles WHERE merchant_id=?", (merchant,)).fetchone()
        if not profile:
            return "clarification", {"message": "Please provide your business name, sector, currency, timezone and required capabilities to set up your profile.", "reason": "profile_required"}
        profile = ProfileInput.model_validate_json(profile["body"])
        if TOOL_CAPABILITIES.get(tool) not in profile.capabilities:
            return "blocked", {"message": "This business capability is disabled in your profile.", "reason": "capability_disabled"}
        if tool == "product_create":
            product_id = str(uuid4())
            c.execute("INSERT INTO products VALUES(?,?,?,?)", (product_id, merchant, args.sku, args.model_dump_json()))
            self.services.audit(c, merchant, "product.created", product_id)
            # Read the stored record before reporting completion.
            row = c.execute("SELECT body FROM products WHERE merchant_id=? AND id=?", (merchant, product_id)).fetchone()
            return "completed", {"message": "Product created in your catalogue.", "product": {"id": product_id, **json.loads(row["body"])}}
        if tool == "catalogue_list":
            rows = c.execute("SELECT id,body FROM products WHERE merchant_id=? ORDER BY id LIMIT 100", (merchant,)).fetchall()
            return "completed", {"message": "Catalogue records retrieved (up to 100).", "products": [{"id": r["id"], **json.loads(r["body"])} for r in rows]}
        if tool == "caption_prepare":
            row = c.execute("SELECT body FROM products WHERE merchant_id=? AND id=?", (merchant, args.product_id)).fetchone()
            if not row:
                raise Missing("product not found")
            p = json.loads(row["body"])
            # Deliberately use a factual template, not free model claims or guessed availability.
            caption = f"{p['title']}\nSKU: {p['sku']}"
            # Initial market is Nigeria. Other currency scales require an explicit
            # registry; omit their price rather than guessing a display amount.
            if p["currency"] == "NGN":
                naira, kobo = divmod(p["price_minor"], 100)
                caption += f"\nNGN {naira:,}.{kobo:02d}"
            return "completed", {"message": "A factual caption draft is ready. It has not been published.", "caption": caption,
                                 "source_product_id": args.product_id, "generation_method": "verified_catalogue_template"}
        if tool == "expense_capture":
            expense_id = str(uuid4())
            body = {**args.model_dump(mode="json"), "occurred_at": args.occurred_at.astimezone(timezone.utc).isoformat(),
                    "source_type": "merchant_conversation", "source_system": "commercepilot",
                    "source_record_id": run_id, "evidence_reference": run_id,
                    "verification_status": "merchant_reported", "confidence_score": None,
                    "reconciliation_status": "unreconciled", "recorded_at": now()}
            c.execute("INSERT INTO expenses VALUES(?,?,?,?,?,?,?)", (expense_id, merchant, run_id, args.amount_minor, args.currency, json.dumps(body), body["recorded_at"]))
            self.services.audit(c, merchant, "expense.captured", expense_id)
            return "completed", {"message": "Expense recorded as merchant-reported and unreconciled.", "expense": {"id": expense_id, **body}}
        if tool == "expenses_list":
            rows = c.execute("SELECT id,body FROM expenses WHERE merchant_id=? ORDER BY recorded_at DESC LIMIT 100", (merchant,)).fetchall()
            return "completed", {"message": "Expense records retrieved (up to 100); no currencies have been combined.", "expenses": [{"id": r["id"], **json.loads(r["body"])} for r in rows]}
        if tool == "report_calculate":
            return "completed", {"message": "Calculated from supplied aggregates; missing costs remain unknown. These inputs have not been reconciled with orders.", "report": financial_report(args)}
        if tool == "daily_report":
            from commercepilot.business import Business
            return "completed", {"message": "Daily report prepared from recorded source data. Review missing fields and coverage before using profit figures.",
                                 "report": Business(self.services).daily(merchant, args.day, args.currency)}
        raise ValueError("unsupported tool")
