# Implementation status

## 0.4 — merchant workspace and business ledger, 2026-11-16

Implemented a responsive local dashboard for reports, agent chat, catalogue, canonical order imports, expenses/coverage, plans, quarantined files, runs/audit and autonomy settings. Added append-only source revisions/conflict detection, timezone/currency-separated daily calculations with unknown-value gates, immutable exact-hash plan approval, and tenant-protected quarantine storage. Added opt-in text reply transport, claimed submission records and signed delivery-status reconciliation; ambiguous sends are never replayed automatically. Migrations 004/005 upgrade existing stores.

Verification: 66 tests passed on Python 3.15, including concurrent reply submission, early/out-of-order/wrong-recipient status callbacks, disabled/expired/revoked channels, uncertain outcomes, source corrections/conflicts, financial missing values, tenant isolation, plan approval and upload boundaries. Browser verified connected sample records, correct sales/profit/unknown operating profit, navigation and an agent catalogue response. A labelled temporary demo is runnable with examples/dashboard_demo.py. One upstream Starlette/httpx warning remains.

Still incomplete: provider-backed catalogue/order connectors, live backend WhatsApp send/inbound validation and public HTTPS deployment, receipt OCR/scanning, forecasts, multi-step autonomous scheduling, production identity/PostgreSQL/RLS/secret management and the remaining full product spec. No live credentials were added. Local sending remains disabled by default. Earlier milestone entries below describe their historical scope.

## Local connection validation — 2026-11-16

User confirmed receipt of the Meta dashboard Hello World test at their verified recipient number. Test-account token authorization and recipient verification were completed through Meta. This validates the Meta dashboard send path, not the CommercePilot backend. No provider tokens have been committed to this repository.

User selected a local test before hosting. The actual loopback HTTP + separate CLI-worker smoke test passed locally: subscription challenge, signed onboarding/product creation, duplicate rejection, altered-signature denial, product read-back and two persisted reply drafts. Ephemeral secrets/data were used, the server shut down cleanly and no Meta calls or WhatsApp sends occurred. The smoke test is included in CI. Hosting, public HTTPS callback registration and backend live inbound verification remain pending. Outbound backend replies remain drafts.

## 0.3 — WhatsApp intake and worker, 2026-11-16

Implemented signed webhook verification/intake, raw-body and batch limits, explicit operator-attested WABA/number/sender mapping, phone and business-scoped sender IDs, persistent conversations, transactional inbox/replay dedup/conflict records, leased worker with conversation ordering, bounded retries/dead letters, owner recovery/revocation/inspection and draft-only reply outbox. Agent execution rechecks channel binding and worker lease. Migration 003 upgrades existing databases. CLI and signed offline demonstration are documented in docs/WHATSAPP.md.

Verification: 51 tests passed locally on Python 3.15, including signed intake/limits/atomic batches, phone/BSUID tenant routing, revocation during planning, dedup/conflicts, concurrent claims, ordering, lease fencing, crash recovery and bounded retry/dead-letter recovery. The signed offline example and CLI command discovery also passed. GitHub CI for milestone commit 0a682f7 succeeded on Python 3.11, 3.13 and 3.15: https://github.com/belugpt/commercepilot-ai/actions/runs/43850098312. No live Meta account, credentials, outbound sends or delivery verification exist. Sender ownership is operator-attested, not provider/OAuth-verified. One upstream Starlette/httpx warning remains.

Remaining: live account validation, outbound transport/templates/windows/consent and delivery receipts, sender reactivation, media processing, production infrastructure, provider adapters and the remaining MVP. Next milestone: outbound delivery contract and status reconciliation after confirming account/API access; media ingestion can progress independently.

## 0.2 — agent runtime, 2026-11-16

Implemented persistent tenant conversations/messages/runs; business profiles and capabilities; strict tool schemas; default offline command planner and optional OpenAI Responses function-call planner; atomic local execution/result/audit; source-linked merchant-reported expense records; factual caption drafts; exact supplied-aggregate report tool; idempotent delivery; cancellation of abandoned planning with late-execution prevention. Migration 002 upgrades the foundation schema without losing existing merchants. Agent API and local demonstration are documented.

Verified: 32 tests passed locally on Python 3.15, including the full offline profile→product→caption→expense→report journey, tenant boundaries, duplicate deliveries, hostile planner output, grant/capability denial, model errors, cancellation, rollback, restart persistence and policy revocation during planning. The editable package installation and runnable offline merchant example also passed. Optional model transport is fixture-contract tested only; no live AI/provider credentials or network effects were used. GitHub CI for runtime commit 025fec0 succeeded on Python 3.11, 3.13 and 3.15: https://github.com/belugpt/commercepilot-ai/actions/runs/43847860163. One upstream Starlette/httpx warning remains.

Limits: one tool per synchronous turn; no autonomous multi-step chaining, background scheduling or WhatsApp transport yet. Content uses verified-fact templates. External publishing/refunds/sync/deletion remain blocked. Imported orders, receipt OCR, reconciled profit, production PostgreSQL/identity/vault, dashboard and advanced planning/forecasting are pending. Next: signed WhatsApp text inbox and durable worker, then approved provider adapters.

## 0.1 — foundation

2026-11-16: New standalone Git repository created and published publicly at https://github.com/belugpt/commercepilot-ai under the user-selected MIT license. Source master specification preserved under docs.

Implemented: installable Python package, FastAPI/OpenAPI, operator provisioning, hashed revocable keys, tenant/owner boundaries, validated catalogue, versioned autonomy settings, payload-bound idempotent durable tasks, atomic claims, adapter submit/read-back separation, audit/exceptions and exact financial calculator. Integration/planner protocols and contributor/architecture/roadmap/security documents are included.

Verification: 15 acceptance tests passed on Python 3.15 (2026-11-16), including API tenant isolation, credential revocation, strict inputs, policy expiry/kill switch, sensitive-action denial, idempotency conflicts, concurrent claims, unknown outcomes and exact financial totals. Sandbox Windows loopback restrictions hung the API test client; the same suite passed outside the sandbox in 3.28 seconds. One upstream Starlette/httpx deprecation warning remains. CI configuration is included but has not yet been executed on GitHub.

Not implemented: complete MVP, WhatsApp/media/model client, provider accounts/connectors, scheduled durable worker/retries/reconciliation UI, approval execution, ingestion/provenance ledger, dashboard, PostgreSQL/RLS, production identity/vault/deployment, planning and forecasts. All providers disabled; test adapters are fixtures only.

Bumpa documentation location corrected to bumpa.io → docs.bumpa.io. API availability is documented; merchant access and detailed contracts remain unverified. User will create provider accounts later. Hosting is undecided.
