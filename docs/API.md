# API

Run the app and inspect /docs or /openapi.json. Generated OpenAPI is the authoritative transport contract. All /v1 routes require bearer authentication; the merchant is resolved from the hashed key. Unknown/missing credentials return 401; insufficient role 403; missing or foreign object 404; duplicate SKU/key payload conflicts 409; invalid schema 422.

| Route | Access | Behavior |
|---|---|---|
| GET /health | public | Liveness/version only |
| POST /v1/products | owner | Strict product creation |
| GET /v1/products/{id} | member | Tenant-bound read |
| PUT /v1/policy | owner | Replace grants and increment policy version |
| POST /v1/tasks | owner | Queue command; Idempotency-Key required |
| GET /v1/tasks/{id} | member | Task/evidence state |
| POST /v1/tasks/{id}/run | owner | Claim and execute once; development runner |
| GET /v1/audit | owner | Up to 200 tenant audit records |
| GET /v1/exceptions | owner | Up to 200 tenant exceptions |
| GET /v1/integrations | member | Disabled provider statuses |
| POST /v1/reports/calculate | member | Calculate unverified aggregate inputs |

Product body: title, sku, price_minor (nonnegative integer), currency (uppercase three-letter code). Currency format is validated; supported-currency/scale registry is pending. Task body: action and product_id. Policy body: enabled, actions and timezone-aware expires_at. No API accepts merchant_id overrides. Financial endpoint accepts one currency per report, no conversions. Net sales excludes discounts; refunds are a separate deduction. Cash is separately supplied and never inferred.

## Agent routes (0.2)

## WhatsApp routes (0.3)

GET /webhooks/whatsapp handles subscription verification; POST on the same path verifies the raw-body signature and persists intake without running the agent. GET /v1/whatsapp/{bindings|inbox|outbox|conflicts} requires owner access. POST /v1/whatsapp/bindings/{id}/revoke disables a sender; POST /v1/whatsapp/inbox/{id}/retry requeues eligible reviewed dead letters. See WHATSAPP.md for status semantics, limits, configuration and the separate worker command. No outbound send endpoint is exposed.

### Agent operations

All require owner access. POST /v1/conversations creates a tenant-bound conversation. POST /v1/conversations/{id}/messages accepts `{message}` plus Idempotency-Key and returns a persisted agent run. GET on the same messages path returns up to 200 messages. GET /v1/agent/runs lists up to 100 recent runs, GET /v1/agent/runs/{id} reads one, and POST /v1/agent/runs/{id}/cancel fails an abandoned planning run without executing its tool. Current processing is synchronous. See AI_AGENT_SPECIFICATION.md for grants, capabilities, modes and recovery limits.

Production registration/OIDC, key rotation API, collection pagination, webhook ingestion, scheduling and worker endpoints are pending. API docs are not an assertion of full MVP completion.
