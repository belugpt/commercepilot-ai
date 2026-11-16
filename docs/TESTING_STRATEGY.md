# Testing strategy

Run `python -m pytest -q`. Current suite covers tenant-isolated APIs/objects, owner enforcement, revoked credentials, strict data fields, policy expiry/kill switch/version checks, duplicate tasks/messages, atomic concurrent claims, provider verification/unknown outcomes, profile→product→caption→expense→report journey, hostile planner outputs, model failure redaction, cancellation with late output, atomic rollback, restart context and version-1 migration.

Optional model planning uses a transport fixture to inspect the request and validate function-call selection/refusal behavior. It is not a live model evaluation. Offline examples execute actual local database effects in temporary storage without network or credentials. Windows sandbox loopback restrictions require API tests to run outside that sandbox; Linux CI runs the same suite on Python 3.11, 3.13 and 3.15.

Next gates: signed WhatsApp webhook and replay tests, durable inbox/worker crash recovery, sandbox provider contract tests, semantic tool accuracy and prompt-injection evaluations, production PostgreSQL row security/concurrency, authenticated membership lifecycle, reconciled sales/expense fixtures, media quarantine, restore/export/deletion and complete merchant journey acceptance.
