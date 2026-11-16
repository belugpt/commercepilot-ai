# Security and disclosure

This is a development foundation. Bind to loopback. Bearer keys are generated using secure randomness, stored only as hashes and revocable through the operator CLI. Key provisioning is not public. Tenant IDs derive from credentials, not request bodies. Owner permissions guard mutations; staff is read-only. No provider secrets are stored or returned.

WhatsApp intake now verifies raw-body HMAC signatures before parsing, caps body/batch size, deduplicates provider IDs, applies a timestamp admission window and requires an operator-attested sender mapping. Owner revocation and worker lease checks guard local effects after planning. Unknown customers cannot act as merchant owners. There is no outbound sending client. Protect the subscription verification token from query/access logs; do not log webhook payloads or message contents. See docs/WHATSAPP.md for recovery and identity limits.

Before production: TLS, OIDC membership lifecycle, key rotation/expiry, traffic throttling, PostgreSQL forced row security, encrypted storage/vault, validation for additional provider webhooks, media quarantine, outbound allowlists, redacted traces, backup/restore, audit immutability, retention/export/deletion and incident response. No legal compliance claim is made. Assess applicable Nigerian privacy requirements before serving merchants.

Adapters are trusted server code. Verification evidence must be curated to avoid secrets. Audit logs intentionally omit request/provider payloads. Running tasks do not auto-retry after a crash; reconcile their outcome first. Do not publish vulnerabilities or credentials in public issues; a private disclosure contact must be configured before a public production release.
