# Master-spec completion matrix — 2026-11-16

This distinguishes implemented behavior from fixtures, live verification and remaining work. The full master specification is not complete.

| Module | Implemented evidence | Remaining acceptance work |
|---|---|---|
| WhatsApp text | Live test-account signed inbound, durable worker, automatic replies and signed delivered callbacks | Production business number, publication/access requirements, stable hosting, credential lifecycle |
| WhatsApp attachments | Opt-in hash/size/account-checked media retrieval and source-linked quarantine; fixture-tested security/recovery | Live attachment validation, malware scanning, OCR, voice transcription and interpreted-data confirmation |
| Onboarding | Persisted profile/capabilities, verified sender binding, user-provided Belu clothing-business profile | Progressive natural-language onboarding, self-serve OAuth/account linking |
| Catalogue | Typed products/SKUs/prices, deterministic text/JSON creation, read-back, factual captions | Variants, inventory/media associations, rich metadata, bulk approval rules |
| AI runtime | One validated tool per persisted turn, strict optional Responses planner, policy/capability enforcement | User has no funded model API account; live model validation, bounded multi-step orchestration and spend controls |
| Content/publishing | Grounded caption drafts and generic mutation/verification extension ports | Brand variation, publishing calendar, official Facebook/Instagram execution adapters and live authorized accounts |
| Commerce | Canonical revisioned source import, duplicates/conflicts, order history | Shopify/Bumpa account access and verified adapter schemas/scopes, sync, pagination, reconciliation against provider totals |
| Sales/economics | Deterministic currency/timezone reports, cost/cash unknowns, provenance, expenses/coverage | Settlement journal, cross-source matching, allocation/unit economics, complete costs and independent reconciliation |
| Planning | Immutable approved target/budget plans and recorded actual variance | Inventory/purchasing/marketing/staffing plans, commitment execution and richer version lineage |
| Forecasting | Evaluated mean/weekly sales baselines, 7-day holdout, MAE/WAPE and descriptive scenarios; history gates | Validated real history, demand/inventory/cash/profit forecasting, calibrated intervals and monitoring |
| Dashboard | Connected owner workflows, activity/outbox/delivery inspection, permissions, reports/plans/files/forecast | Staff-oriented UX, publishing calendar, full accessibility/responsive acceptance and large-data pagination |
| Reliability | Idempotent local effects, inbox leases/fencing/recovery, outbox submission claims, no blind ambiguous retries | Reconciliation operator workflow, scheduling, queue metrics/alerts and production load/chaos testing |
| Identity/security | Hashed revocable owner/staff bearer boundary, tenant filters, expiring grants, local DPAPI secrets | Managed user/membership identity, PostgreSQL forced RLS, portable vault, retention/export/deletion and independent security review |
| Infrastructure | Working local runtime/HTTPS test tunnel, non-root container/Compose preparation | Docker runtime validation (Docker unavailable locally), permanent hosting, stable ingress, backups/restore, monitoring and production readiness |

Provider-dependent items cannot be declared complete from fixture tests or a temporary test phone. OpenAI billing/key setup, commerce/social credentials, business publication/production-number decisions and hosting are external dependencies. Existing implementation work remains reusable through typed tool and adapter contracts.
