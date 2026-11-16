"""Stable extension ports. Implementations must be explicitly installed by host code."""
from dataclasses import dataclass
from typing import Protocol
from commercepilot.domain import Action


@dataclass(frozen=True)
class ExecutionContext:
    merchant_id: str
    task_id: str
    idempotency_key: str
    action: Action
    product: dict


class Adapter(Protocol):
    def submit(self, context: ExecutionContext) -> str:
        """Return provider reference; never equate acceptance with success."""
        ...

    def verify(self, context: ExecutionContext, reference: str) -> dict | None:
        """Return independently read evidence, or None if outcome is uncertain."""
        ...


class Planner(Protocol):
    def propose(self, message: str, facts: dict) -> dict:
        """Return untrusted TaskInput data. Host validates and enforces policy."""
        ...


PROVIDERS = [
    {"id": "bumpa", "state": "documentation_identified_access_unverified",
     "docs": "https://docs.bumpa.io/", "enabled": False},
    {"id": "shopify", "state": "credentials_required", "enabled": False},
    {"id": "meta", "state": "app_review_and_credentials_required", "enabled": False},
    {"id": "whatsapp", "state": "business_account_required", "enabled": False},
]
