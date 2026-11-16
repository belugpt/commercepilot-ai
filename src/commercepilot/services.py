import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from commercepilot.database import Database
from commercepilot.domain import Action, PolicyInput, ProductInput, TaskInput
from commercepilot.integrations import Adapter, ExecutionContext
from commercepilot.policy import authorize


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


class Conflict(Exception):
    pass


class Missing(Exception):
    pass


class Services:
    def __init__(self, db: Database, adapters: dict[Action, Adapter] | None = None):
        self.db, self.adapters = db, dict(adapters or {})

    def provision(self, name: str) -> tuple[str, str]:
        if not name.strip():
            raise ValueError("merchant name required")
        merchant, token = str(uuid4()), secrets.token_urlsafe(32)
        with self.db.connect() as c:
            c.execute("INSERT INTO merchants VALUES(?,?)", (merchant, name))
            c.execute("INSERT INTO api_keys(digest,merchant_id,role) VALUES(?,?,?)", (digest(token), merchant, "owner"))
            self.audit(c, merchant, "merchant.provisioned", merchant)
        return merchant, token

    @staticmethod
    def audit(c, merchant, event, object_id):
        c.execute("INSERT INTO audit(merchant_id,event,object_id,occurred_at) VALUES(?,?,?,?)",
                  (merchant, event, object_id, now()))

    def identity(self, token):
        with self.db.connect() as c:
            row = c.execute("SELECT merchant_id,role FROM api_keys WHERE digest=? AND revoked=0", (digest(token),)).fetchone()
            return dict(row) if row else None

    def create_product(self, merchant, data: ProductInput):
        product_id = str(uuid4())
        with self.db.connect() as c:
            try:
                c.execute("INSERT INTO products VALUES(?,?,?,?)", (product_id, merchant, data.sku, data.model_dump_json()))
            except sqlite3.IntegrityError as e:
                raise Conflict("SKU already exists") from e
            self.audit(c, merchant, "product.created", product_id)
        return {"id": product_id, **data.model_dump()}

    def product(self, merchant, product_id):
        with self.db.connect() as c:
            row = c.execute("SELECT body FROM products WHERE merchant_id=? AND id=?", (merchant, product_id)).fetchone()
        if not row:
            raise Missing("product not found")
        return {"id": product_id, **json.loads(row["body"])}

    def policy(self, merchant, data: PolicyInput):
        if data.expires_at.tzinfo is None:
            raise ValueError("timezone required")
        with self.db.connect() as c:
            c.execute("INSERT INTO policies VALUES(?,1,?) ON CONFLICT(merchant_id) DO UPDATE SET version=version+1,body=excluded.body",
                      (merchant, data.model_dump_json()))
            self.audit(c, merchant, "policy.changed", merchant)

    def submit(self, merchant, key: str, data: TaskInput):
        self.product(merchant, data.product_id)
        body = data.model_dump_json()
        task_id = str(uuid4())
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            previous = c.execute("SELECT * FROM tasks WHERE merchant_id=? AND idempotency_key=?", (merchant, key)).fetchone()
            if previous:
                if previous["payload_hash"] != digest(body):
                    raise Conflict("idempotency key reused with different payload")
                return self.task(merchant, previous["id"])
            c.execute("INSERT INTO tasks VALUES(?,?,?,?,?,'pending',NULL,?)", (task_id, merchant, key, digest(body), body, now()))
            self.audit(c, merchant, "task.queued", task_id)
        return self.task(merchant, task_id)

    def task(self, merchant, task_id):
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM tasks WHERE merchant_id=? AND id=?", (merchant, task_id)).fetchone()
        if not row:
            raise Missing("task not found")
        return {"id": row["id"], "state": row["state"], "command": json.loads(row["body"]),
                "evidence": json.loads(row["evidence"]) if row["evidence"] else None,
                "created_at": row["created_at"]}

    def finish(self, merchant, task_id, state, evidence=None, reason=None):
        with self.db.connect() as c:
            c.execute("UPDATE tasks SET state=?,evidence=? WHERE merchant_id=? AND id=?",
                      (state, json.dumps(evidence) if evidence else None, merchant, task_id))
            if reason:
                c.execute("INSERT OR REPLACE INTO exceptions VALUES(?,?,?)", (task_id, merchant, reason))
            self.audit(c, merchant, "task." + state, task_id)
        return self.task(merchant, task_id)

    def run(self, merchant, task_id):
        # Claim atomically so concurrent workers cannot submit the same task twice.
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM tasks WHERE merchant_id=? AND id=?", (merchant, task_id)).fetchone()
            if not row:
                raise Missing("task not found")
            if row["state"] != "pending":
                return self.task(merchant, task_id)
            command = TaskInput.model_validate_json(row["body"])
            stored = c.execute("SELECT body FROM policies WHERE merchant_id=?", (merchant,)).fetchone()
            reason = authorize(command.action, PolicyInput.model_validate_json(stored["body"]) if stored else None)
            if reason:
                c.execute("UPDATE tasks SET state='blocked' WHERE id=?", (task_id,))
                c.execute("INSERT INTO exceptions VALUES(?,?,?)", (task_id, merchant, reason))
                self.audit(c, merchant, "task.blocked", task_id)
            else:
                c.execute("UPDATE tasks SET state='running' WHERE id=?", (task_id,))
                self.audit(c, merchant, "task.claimed", task_id)
        if reason:
            return self.task(merchant, task_id)
        adapter = self.adapters.get(command.action)
        if adapter is None:
            return self.finish(merchant, task_id, "blocked", reason="adapter_not_configured")
        context = ExecutionContext(merchant, task_id, task_id, command.action, self.product(merchant, command.product_id))
        try:
            reference = adapter.submit(context)
            if not reference:
                raise ValueError("provider reference missing")
            # Persist reference before verification for operator reconciliation.
            self.finish(merchant, task_id, "running", {"reference": reference})
            evidence = adapter.verify(context, reference)
            if not evidence:
                return self.finish(merchant, task_id, "uncertain", {"reference": reference}, "verification_unconfirmed")
            return self.finish(merchant, task_id, "succeeded", {"reference": reference, "verification": evidence})
        except Exception:
            # Never persist provider exception strings: they may contain tokens.
            return self.finish(merchant, task_id, "uncertain", self.task(merchant, task_id)["evidence"], "adapter_outcome_unknown")

    def history(self, merchant, table):
        if table not in {"audit", "exceptions"}:
            raise ValueError("unsupported history")
        with self.db.connect() as c:
            return [dict(row) for row in c.execute(f"SELECT * FROM {table} WHERE merchant_id=? LIMIT 200", (merchant,))]
