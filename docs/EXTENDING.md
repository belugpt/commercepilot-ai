# Extension guide

## Add an integration

1. Record official documentation, auth/scopes, sandbox access, limits and supported capabilities in INTEGRATIONS.md.
2. Implement `Adapter.submit(ExecutionContext) -> str` and `verify(context, reference) -> dict | None` in a new provider module. Resolve credentials through a host-provided vault, keyed by authenticated merchant. Never accept arbitrary callback/base URLs from model output.
3. Submit using context.idempotency_key where supported. Handle rate limits and ambiguous outcomes without duplicate mutations. Verification must make an independent provider read and return evidence bound to tenant, object and provider reference.
4. Register explicitly in trusted bootstrap code through `create_app(adapters={Action.DESCRIBE: adapter})`. Do not enable publication/sync by weakening policy; first add versioned schedule/channel rules and acceptance tests.
5. Add fixture contracts and separately gated sandbox tests. Document whether functionality is fixture-tested, sandbox-tested or production-verified.

The existing protocol is synchronous. Async or long-running adapters should be introduced with a durable worker, not by spawning an untracked thread from HTTP.

## Add a planner

Implement Planner.propose using only approved merchant facts. Validate output with TaskInput.model_validate; resolve identity from the authenticated service, and submit through Services. Never pass database handles, API keys, arbitrary shell tools or authorization decisions to the model. Treat documents, descriptions and inbound messages as untrusted data.

## Add a module

Keep domain calculations independent of HTTP and provider SDKs. Add tenant constraints/migrations before routes, explicit owner/staff permissions, auditable writes, OpenAPI schemas, cross-tenant failure tests and docs. Do not extend Action without updating policy and tests. Changes to extension contracts follow semantic versioning; before 1.0 minor releases may break contracts with migration notes.
