"""Canonical source snapshots, deterministic reporting and explicit plan approval."""
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo
import json
from pydantic import Field, StrictInt, field_validator, model_validator
from commercepilot.domain import Command
from commercepilot.services import Conflict, Missing, digest, now


class Provenance(Command):
    source_system: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    source_id: str = Field(min_length=1, max_length=200)
    revision: StrictInt = Field(ge=1, le=2**31-1)
    occurred_at: datetime
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    verification_status: Literal["merchant_reported", "provider_imported", "reconciled"]
    evidence_reference: str = Field(min_length=1, max_length=500)

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("timezone required")
        return value


class OrderLine(Command):
    sku: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    quantity: StrictInt = Field(ge=1, le=10**6)
    unit_price_minor: StrictInt = Field(ge=0, le=10**15)
    # Total recognized cost for this line, already adjusted for returned goods.
    cogs_minor: StrictInt | None = Field(default=None, ge=0, le=10**15)


class OrderInput(Provenance):
    status: Literal["open", "fulfilled", "cancelled"]
    payment_status: Literal["pending", "paid", "partially_refunded", "refunded"]
    channel: str = Field(min_length=1, max_length=80)
    lines: list[OrderLine] = Field(min_length=1, max_length=500)
    discounts_minor: StrictInt = Field(ge=0, le=10**15)
    refunds_minor: StrictInt = Field(ge=0, le=10**15)
    cash_collected_minor: StrictInt | None = Field(default=None, ge=0, le=10**15)

    @model_validator(mode="after")
    def totals(self):
        gross = sum(x.quantity * x.unit_price_minor for x in self.lines)
        if self.discounts_minor > gross or self.refunds_minor > gross - self.discounts_minor:
            raise ValueError("discounts/refunds exceed order value")
        return self


class FinancialRecordInput(Provenance):
    category: Literal["packaging", "delivery", "fees", "advertising", "rent", "utilities", "payroll", "other"]
    amount_minor: StrictInt = Field(ge=0, le=10**15)
    note: str = Field(max_length=1000)


class CoverageInput(Command):
    day: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    complete: bool


class PlanInput(Command):
    title: str = Field(min_length=1, max_length=200)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    starts_on: date
    ends_on: date
    revenue_target_minor: StrictInt = Field(ge=0, le=10**15)
    expense_budget_minor: StrictInt = Field(ge=0, le=10**15)
    assumptions: str = Field(max_length=3000)

    @model_validator(mode="after")
    def dates(self):
        if self.ends_on < self.starts_on:
            raise ValueError("end date precedes start")
        return self


class ApprovePlanInput(Command):
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class Business:
    def __init__(self, services):
        self.services, self.db = services, services.db

    def ingest(self, merchant, data, kind):
        table = {"order": "order_events", "expense": "financial_events"}[kind]
        body = data.model_dump_json()
        fingerprint = digest(body)
        mismatch = False
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            previous = c.execute(f"SELECT id,payload_hash,body FROM {table} WHERE merchant_id=? AND source_system=? AND source_id=? AND revision=?", (merchant, data.source_system, data.source_id, data.revision)).fetchone()
            if previous:
                if previous["payload_hash"] != fingerprint:
                    mismatch = True
                    c.execute("INSERT INTO data_quality_issues(merchant_id,kind,source_reference,details,created_at) VALUES(?,?,?,?,?)", (merchant, "conflicting_source_revision", previous["id"], "A source revision was reused with changed values; original preserved.", now()))
                    self.services.audit(c, merchant, "data.conflict_detected", previous["id"])
                else:
                    return {"id": previous["id"], "duplicate": True, "record": json.loads(previous["body"])}
            else:
                record_id = str(uuid4())
                c.execute(f"INSERT INTO {table} VALUES(?,?,?,?,?,?,?,?,?,?)", (record_id, merchant, data.source_system, data.source_id, data.revision, fingerprint, body, data.occurred_at.astimezone(timezone.utc).isoformat(), now(), data.currency))
                self.services.audit(c, merchant, kind + ".ingested", record_id)
        if mismatch:
            raise Conflict("source revision conflicts with existing record; original preserved")
        return {"id": record_id, "duplicate": False, "record": data.model_dump(mode="json")}

    def latest(self, merchant, kind):
        table = {"orders": "order_events", "expenses": "financial_events"}[kind]
        with self.db.connect() as c:
            rows = c.execute(f"""SELECT a.* FROM {table} a WHERE a.merchant_id=?
                AND NOT EXISTS(SELECT 1 FROM {table} b WHERE b.merchant_id=a.merchant_id
                  AND b.source_system=a.source_system AND b.source_id=a.source_id AND b.revision>a.revision)
                ORDER BY a.occurred_at DESC LIMIT 10001""", (merchant,)).fetchall()
        if len(rows) > 10000:
            raise ValueError("report capacity exceeded; use a paginated production store")
        return [{"id": r["id"], "recorded_at": r["recorded_at"], **json.loads(r["body"])} for r in rows]

    def profile(self, merchant):
        with self.db.connect() as c:
            row = c.execute("SELECT body FROM business_profiles WHERE merchant_id=?", (merchant,)).fetchone()
        if not row:
            raise ValueError("business profile required")
        return json.loads(row["body"])

    def declare_coverage(self, merchant, data):
        with self.db.connect() as c:
            c.execute("INSERT INTO expense_coverage VALUES(?,?,?,?,?) ON CONFLICT(merchant_id,day,currency) DO UPDATE SET complete=excluded.complete,declared_at=excluded.declared_at", (merchant, data.day.isoformat(), data.currency, int(data.complete), now()))
            self.services.audit(c, merchant, "expenses.coverage_declared", data.day.isoformat())
        return data.model_dump(mode="json")

    def daily(self, merchant, day, currency):
        profile = self.profile(merchant)
        tz = ZoneInfo(profile["timezone"])
        start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
        end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
        in_period = lambda r: r["currency"] == currency and start <= datetime.fromisoformat(r["occurred_at"]) < end
        orders = [r for r in self.latest(merchant, "orders") if in_period(r)]
        expense_records = [r for r in self.latest(merchant, "expenses") if in_period(r)]
        with self.db.connect() as c:
            coverage = c.execute("SELECT complete,declared_at FROM expense_coverage WHERE merchant_id=? AND day=? AND currency=?", (merchant, day.isoformat(), currency)).fetchone()
            conversational = [dict(r) for r in c.execute("SELECT id,body FROM expenses WHERE merchant_id=? AND currency=?", (merchant, currency))]
        captured = [{"id": r["id"], **json.loads(r["body"])} for r in conversational]
        captured = [r for r in captured if in_period(r)]
        active = [r for r in orders if r["status"] != "cancelled"]
        gross = sum(sum(x["quantity"] * x["unit_price_minor"] for x in r["lines"]) for r in active)
        discounts = sum(r["discounts_minor"] for r in active)
        refunds = sum(r["refunds_minor"] for r in active)
        cogs_known = bool(orders) and all(x["cogs_minor"] is not None for r in active for x in r["lines"])
        cogs = sum(x["cogs_minor"] for r in active for x in r["lines"]) if cogs_known else None
        cash_known = bool(orders) and all(r["cash_collected_minor"] is not None for r in orders)
        # Cash is gross receipts; refunds on cancelled orders still affect cash.
        cash = sum(r["cash_collected_minor"] - r["refunds_minor"] for r in orders) if cash_known else None
        reported_expenses = sum(r["amount_minor"] for r in expense_records + captured)
        complete = bool(coverage and coverage["complete"])
        expenses = reported_expenses if complete else None
        gross_profit = gross - discounts - refunds - cogs if cogs is not None else None
        operating = gross_profit - expenses if gross_profit is not None and expenses is not None else None
        top = {}
        channels = {}
        for order in active:
            channel = channels.setdefault(order["channel"], {"orders": 0, "net_sales_minor": 0})
            channel["orders"] += 1
            channel["net_sales_minor"] += sum(x["quantity"] * x["unit_price_minor"] for x in order["lines"]) - order["discounts_minor"]
            for line in order["lines"]:
                product = top.setdefault(line["sku"], {"sku": line["sku"], "units_ordered": 0, "gross_minor": 0})
                product["units_ordered"] += line["quantity"]
                product["gross_minor"] += line["quantity"] * line["unit_price_minor"]
        missing = ([] if orders else ["order_history"]) + ([] if cogs_known else ["cogs"]) + ([] if complete else ["expense_coverage"]) + ([] if cash_known else ["cash_receipts"])
        return {"day": day.isoformat(), "currency": currency, "timezone": profile["timezone"],
                "period_start": start.isoformat(), "period_end_exclusive": end.isoformat(),
                "orders": len(orders), "cancelled_orders": len(orders)-len(active),
                "pending_payment_orders": sum(r["payment_status"] == "pending" for r in active),
                "gross_sales_minor": gross if orders else None, "discounts_minor": discounts if orders else None, "net_sales_minor": gross-discounts if orders else None,
                "refunds_minor": refunds if orders else None, "sales_after_refunds_minor": gross-discounts-refunds if orders else None,
                "cash_after_refunds_minor": cash, "cogs_minor": cogs,
                "reported_expenses_minor": reported_expenses, "expenses_minor": expenses,
                "gross_profit_minor": gross_profit, "operating_profit_minor": operating,
                "missing": missing, "source_ids": [r["id"] for r in orders+expense_records+captured],
                "channels": channels, "top_products": sorted(top.values(), key=lambda p:p["gross_minor"], reverse=True)[:10],
                "calculation_version": "ledger-v1", "coverage": "recorded_data_only",
                "verification": "source_claims_not_independently_reconciled",
                "basis": "booked orders excluding cancellations; line COGS must include return adjustments"}

    def create_plan(self, merchant, data):
        plan_id, body = str(uuid4()), data.model_dump_json()
        with self.db.connect() as c:
            c.execute("INSERT INTO business_plans VALUES(?,?,?,?,?,'draft',?,NULL)", (plan_id, merchant, data.title, body, digest(body), now()))
            self.services.audit(c, merchant, "plan.drafted", plan_id)
        return self.plan(merchant, plan_id)

    def plan(self, merchant, plan_id):
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM business_plans WHERE merchant_id=? AND id=?", (merchant, plan_id)).fetchone()
        if not row:
            raise Missing("plan not found")
        return {"id": row["id"], "state": row["state"], "payload_hash": row["payload_hash"],
                "created_at": row["created_at"], "approved_at": row["approved_at"], "plan": json.loads(row["body"])}

    def approve_plan(self, merchant, plan_id, data):
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT payload_hash FROM business_plans WHERE merchant_id=? AND id=?", (merchant, plan_id)).fetchone()
            if not row:
                raise Missing("plan not found")
            if row["payload_hash"] != data.payload_hash:
                raise Conflict("approval does not match the exact plan")
            changed = c.execute("UPDATE business_plans SET state='approved',approved_at=? WHERE merchant_id=? AND id=? AND state='draft'", (now(), merchant, plan_id))
            if changed.rowcount:
                self.services.audit(c, merchant, "plan.approved", plan_id)
        return self.plan(merchant, plan_id)

    def issues(self, merchant):
        with self.db.connect() as c:
            return [dict(r) for r in c.execute("SELECT id,kind,source_reference,details,created_at FROM data_quality_issues WHERE merchant_id=? ORDER BY id DESC LIMIT 200", (merchant,))]
