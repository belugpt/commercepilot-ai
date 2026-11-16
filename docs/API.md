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

Production registration/OIDC, key rotation API, collection pagination, webhook ingestion, scheduling and worker endpoints are pending. API docs are not an assertion of full MVP completion.
