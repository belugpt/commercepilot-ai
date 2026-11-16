# Roadmap and acceptance gates

1. Backend foundation: tenant-scoped catalogue, keys, policy, tasks, verification ports, finance and API tests. Current release.
2. Production infrastructure: PostgreSQL migrations/forced RLS, membership/OIDC, vault, leased outbox worker, telemetry, Docker deployment and restore exercise. Gate: cross-tenant SQL/API and concurrent/crash recovery tests.
3. WhatsApp onboarding/profile/capabilities and canonical media ingestion. Gate: signed sandbox messages, replay rejection, tenant-bound sender mapping and quarantined uploads.
4. Product facts and structured AI content. Gate: schema validation, no unsupported claims, prompt-injection tests and model-independent authorization.
5. Bumpa/Shopify adapters and Meta publishing. Gate: official scope/access verification, sandbox contract tests, independent reads, policy schedules, uncertain reconciliation and duplicate prevention.
6. Order ingestion, provenance-rich expenses, costs and daily reporting. Gate: dedup/conflicts, cancellations/refunds, period/timezone and provider-total reconciliation; missing expenses visible.
7. Dashboard, policies/approvals, reports, task/exception operations and full MVP merchant journey. Gate: all master-spec acceptance criteria and operational/security readiness.
8. Versioned plans, budgets and statistical forecasts after validated history. Gate: explainable assumptions and backtesting against simple baselines.

No production completion dates until account access, hosting and team capacity are known.
