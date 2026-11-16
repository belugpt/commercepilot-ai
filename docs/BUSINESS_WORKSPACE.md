# Merchant workspace and business ledger

Run the usual API server and open http://127.0.0.1:8000/. Paste the owner key issued by the provisioning CLI. The key lives only in tab memory. API documentation remains at `/docs`. A fresh workspace starts empty: grant the profile permission in Settings, then save the business profile and select the tools you want enabled.

For an isolated sample workspace run `python examples/dashboard_demo.py`, open http://127.0.0.1:8001 and use the temporary key printed in your terminal. The workspace is explicitly labelled sample data and its database is removed on a clean exit. It never enables outbound replies.

## Surfaces

Overview shows daily booked sales, order counts, known gross profit, operating profit only with declared expense coverage, source completeness and top SKUs. Other views provide agent conversations, product creation, canonical order import, expense entry, expense coverage, immutable budget/target drafts with exact-payload approval, quarantined uploads, agent runs, cancellation, audit and source conflicts. Settings controls business capabilities and expiring autonomy grants. API owner/staff checks remain authoritative; owner workflows are the intended dashboard experience.

## Source contracts

`POST /v1/orders/ingest` and `POST /v1/financial-records` accept typed canonical records, not arbitrary provider payloads. OpenAPI contains the full schemas. Every record has source system, source ID, monotonically increasing revision, aware occurrence timestamp, currency, verification claim and evidence reference. Identical source revisions deduplicate. Reusing a revision with changed values returns 409, preserves the original and commits a data-quality issue. New revisions append history; the maximum revision is current even when imports arrive out of order.

Verification labels are importer assertions; independent reconciliation has not been implemented. Conversational expenses and imported expenses use distinct sources: importing the same expense twice through both paths can double-count it. Review source references before declaring coverage complete. There is no automatic matching or deduplication across sources.

Daily reports use merchant timezone boundaries, retain currency separation, exclude cancelled booked orders and keep cancellation cash/refund effects. Cash means gross receipts minus refunds, independent of booked sales. Line COGS is a total recognized cost already adjusted for returns. Missing COGS, cash receipts and expense coverage remain unknown. Empty order history remains unknown. Reports describe latest recorded order snapshots grouped by order occurrence date; they are not a cash accounting journal and do not allocate later refunds to their settlement date. Lists/report aggregation have an explicit 10,000 current-record local capacity limit.

`PUT /v1/reports/expense-coverage` is an owner declaration for one local day/currency. It permits using recorded expenses in operating profit, without upgrading reconciliation evidence. `/sales {"day":"2026-11-16","currency":"NGN"}` invokes the same daily calculator through the agent and requires `sales.report.daily` plus economics capability.

## Plans and files

Plans contain date bounds, currency, target revenue, expense budget and assumptions. Approval matches the exact stored SHA-256 payload. It does not reserve or spend money, trigger provider changes, or produce a forecast. Plans are immutable; create a new draft for changes.

Media accepts raw PDF/PNG/JPEG bytes up to 8 MB, checks the declared signature, hashes/deduplicates within a tenant and stores bytes in quarantine. Downloads require owner authentication and force an opaque attachment. Signature validation is not malware scanning. OCR, receipt interpretation, image processing and posting are not implemented; uploads never alter business figures.

## WhatsApp replies

The separate inbox worker continues producing drafts. `POST /v1/whatsapp/outbox/{id}/send` explicitly submits one draft and requires owner access, the current `whatsapp.reply.send` autonomy grant, an enabled binding, an inbound phone identity within the 24-hour reply window and an explicitly configured sender. Configure `WHATSAPP_SEND_ENABLED=true`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_GRAPH_VERSION`, and `WHATSAPP_PHONE_NUMBER_ID` through the environment. Intake independently needs the app secret and verification token.

`GET /v1/whatsapp/deliveries` exposes submitting, accepted, sent, delivered, read, failed and uncertain states. Signed status callbacks must match provider reference, WABA, phone number ID and recipient before advancing evidence. A successful HTTP submission is only accepted. Delivery evidence may arrive before the submit response and is reconciled afterward; older statuses cannot downgrade delivered/read.

Submission is claimed before contacting Meta. Concurrent or repeated calls never replay it. An ambiguous timeout remains uncertain; a process crash after claiming can leave submitting. Both require operator/provider investigation, with no automatic retry. There is no template fallback, BSUID outbound support, unsolicited campaign sending or automatic outbox drain. The transport and callback contract are fixture-tested, not live-account verified. Keep sending disabled until account-specific validation is complete.

## Operational boundary

SQLite, local bearer-key provisioning and quarantined BLOB storage are development infrastructure. Production needs managed identity, secrets, PostgreSQL/RLS migration, media scanning/object storage, capacity controls, backups, monitoring, retention and deployed HTTPS webhook validation. Bumpa/Shopify synchronization, social publishing, OCR, forecasting, multi-step agents and scheduled campaigns remain separate work.
