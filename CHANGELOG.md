# Changelog

## Local smoke-test addition — 2026-11-16
- Added real loopback HTTP testing with a separate CLI worker, temporary data, signed intake, replay/tamper checks and product read-back.
- Added the smoke test to the Python CI matrix and documented the distinction between Meta dashboard testing and backend connection validation.

## 0.3.0 — 2026-11-16
- Added signed WhatsApp subscription/intake contracts with bounded parsing, sender bindings and phone/BSUID routing.
- Added durable inbox, conversation-ordered leased worker, replay/conflict detection, audited retries/dead letters and draft-only outbox.
- Added channel revocation/lease checks at agent execution, crash recovery and owner inspection/retry routes.
- Added migration 003, operator CLI commands, signed-intake demonstration and security/recovery documentation. Live delivery remains disabled.

## 0.2.0 — 2026-11-16
- Added persistent agent turns, profile/capability context, policy-checked validated tools and source-linked expenses.
- Added optional Responses function-call planning and explicit offline command mode.
- Added idempotent conversation delivery, atomic tool effects, cancellation/recovery, migration 002 and adversarial/end-to-end tests.
- Added a runnable offline merchant example and agent setup documentation.

## 0.1.0 — 2026-11-16
- Created MIT-licensed extensible backend foundation, API, tenant/auth/policy/task/finance modules and tests.
- Documented architecture, canonical data direction, provider evidence, extension contracts and production gates.
