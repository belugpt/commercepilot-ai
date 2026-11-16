"""Bounded agent tool schemas; models never supply identity or permissions."""
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import Field, StrictInt, field_validator
from commercepilot.domain import Command, FinancialInput, ProductInput


class MessageInput(Command):
    message: str = Field(min_length=1, max_length=8000, pattern=r"\S")


class ProfileInput(Command):
    business_name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    sector: str = Field(min_length=1, max_length=100)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str = Field(min_length=1, max_length=100)
    capabilities: frozenset[Literal["catalogue", "content", "economics"]]

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError("valid IANA timezone required") from e
        return value


class EmptyInput(Command):
    pass


class CaptionInput(Command):
    product_id: str = Field(min_length=1, max_length=100)


class ExpenseInput(Command):
    amount_minor: StrictInt = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    category: Literal["packaging", "delivery", "fees", "advertising", "rent", "utilities", "payroll", "other"]
    occurred_at: datetime
    note: str = Field(max_length=1000)

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        return value


class ClarifyInput(Command):
    question: str = Field(min_length=1, max_length=500)


class DailySalesInput(Command):
    day: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class ExternalInput(Command):
    action: Literal["social.publish", "catalogue.sync", "payments.refund", "catalogue.delete"]
    product_id: str = Field(min_length=1, max_length=100)


# Tool registry is static trusted code. Extra arguments (tenant IDs, SQL, URLs,
# permissions) are rejected before execution. All tool arguments are facts/data.
TOOL_SCHEMAS = {
    "profile_save": ProfileInput,
    "product_create": ProductInput,
    "catalogue_list": EmptyInput,
    "caption_prepare": CaptionInput,
    "expense_capture": ExpenseInput,
    "expenses_list": EmptyInput,
    "report_calculate": FinancialInput,
    "daily_report": DailySalesInput,
    "external_request": ExternalInput,
    "clarify": ClarifyInput,
}
