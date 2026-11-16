# Implementation status

2026-11-16: New standalone Git repository created and published publicly at https://github.com/belugpt/commercepilot-ai under the user-selected MIT license. Source master specification preserved under docs.

Implemented: installable Python package, FastAPI/OpenAPI, operator provisioning, hashed revocable keys, tenant/owner boundaries, validated catalogue, versioned autonomy settings, payload-bound idempotent durable tasks, atomic claims, adapter submit/read-back separation, audit/exceptions and exact financial calculator. Integration/planner protocols and contributor/architecture/roadmap/security documents are included.

Verification: 15 acceptance tests passed on Python 3.15 (2026-11-16), including API tenant isolation, credential revocation, strict inputs, policy expiry/kill switch, sensitive-action denial, idempotency conflicts, concurrent claims, unknown outcomes and exact financial totals. Sandbox Windows loopback restrictions hung the API test client; the same suite passed outside the sandbox in 3.28 seconds. One upstream Starlette/httpx deprecation warning remains. CI configuration is included but has not yet been executed on GitHub.

Not implemented: complete MVP, WhatsApp/media/model client, provider accounts/connectors, scheduled durable worker/retries/reconciliation UI, approval execution, ingestion/provenance ledger, dashboard, PostgreSQL/RLS, production identity/vault/deployment, planning and forecasts. All providers disabled; test adapters are fixtures only.

Bumpa documentation location corrected to bumpa.io → docs.bumpa.io. API availability is documented; merchant access and detailed contracts remain unverified. User will create provider accounts later. Hosting is undecided.
