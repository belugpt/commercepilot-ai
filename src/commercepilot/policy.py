"""Deterministic policy: models and plugins cannot authorize themselves."""
from datetime import datetime, timezone
from commercepilot.domain import Action, PolicyInput


def authorize(action: Action, policy: PolicyInput | None) -> str | None:
    if action in {Action.REFUND, Action.DELETE}:
        return "explicit_approval_required"
    if action in {Action.PUBLISH, Action.SYNC}:
        return "schedule_and_channel_rules_not_implemented"
    if policy is None or not policy.enabled:
        return "automation_disabled"
    if policy.expires_at.tzinfo is None or policy.expires_at <= datetime.now(timezone.utc):
        return "permission_expired"
    if action not in policy.actions:
        return "action_not_granted"
    return None
