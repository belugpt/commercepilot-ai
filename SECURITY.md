# Security and disclosure

This is a development foundation. Bind to loopback. Bearer keys are generated using secure randomness, stored only as hashes and revocable through the operator CLI. Key provisioning is not public. Tenant IDs derive from credentials, not request bodies. Owner permissions guard mutations; staff is read-only. No provider secrets are stored or returned.

Before production: TLS, OIDC membership lifecycle, key rotation/expiry, rate limits/body limits, PostgreSQL forced row security, encrypted storage/vault, webhook signatures/replay protection, media quarantine, outbound allowlists, redacted traces, backup/restore, audit immutability, retention/export/deletion and incident response. No legal compliance claim is made. Assess applicable Nigerian privacy requirements before serving merchants.

Adapters are trusted server code. Verification evidence must be curated to avoid secrets. Audit logs intentionally omit request/provider payloads. Running tasks do not auto-retry after a crash; reconcile their outcome first. Do not publish vulnerabilities or credentials in public issues; a private disclosure contact must be configured before a public production release.
