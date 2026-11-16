"""Strict transport-independent commands; money is expressed in minor units."""
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, StrictInt


class Action(StrEnum):
    DESCRIBE = "content.describe"
    PUBLISH = "social.publish"
    SYNC = "catalogue.sync"
    REFUND = "payments.refund"
    DELETE = "catalogue.delete"


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProductInput(Command):
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    sku: str = Field(min_length=1, max_length=100, pattern=r"\S")
    price_minor: StrictInt = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class TaskInput(Command):
    action: Action
    product_id: str = Field(min_length=1, max_length=100)


class PolicyInput(Command):
    enabled: bool
    actions: frozenset[Action]
    expires_at: datetime


class FinancialInput(Command):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    gross_minor: StrictInt = Field(ge=0, le=10**15)
    discounts_minor: StrictInt = Field(ge=0, le=10**15)
    refunds_minor: StrictInt = Field(ge=0, le=10**15)
    cogs_minor: StrictInt | None = Field(default=None, ge=0, le=10**15)
    expenses_minor: StrictInt | None = Field(default=None, ge=0, le=10**15)
    cash_collected_minor: StrictInt | None = Field(default=None, ge=0, le=10**15)


def financial_report(data: FinancialInput) -> dict:
    if data.discounts_minor > data.gross_minor:
        raise ValueError("discounts exceed gross sales")
    net = data.gross_minor - data.discounts_minor
    if data.refunds_minor > net:
        raise ValueError("refunds exceed net sales")
    after_refunds = net - data.refunds_minor
    gross_profit = None if data.cogs_minor is None else after_refunds - data.cogs_minor
    operating = None if gross_profit is None or data.expenses_minor is None else gross_profit - data.expenses_minor
    return {**data.model_dump(), "net_sales_minor": net,
            "sales_after_refunds_minor": after_refunds, "gross_profit_minor": gross_profit,
            "operating_profit_minor": operating,
            "missing": [name for name in ("cogs_minor", "expenses_minor", "cash_collected_minor")
                        if getattr(data, name) is None],
            "calculation_version": "1", "basis": "caller_supplied_unverified_aggregates"}
