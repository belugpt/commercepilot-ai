# Try the agent locally

Install dependencies from README, provision a merchant, start the backend, open /docs, and use its Authorize button with the printed bearer key.

First configure PUT /v1/policy. Use a future, timezone-aware expiry suitable for your environment:

```json
{
  "enabled": true,
  "actions": ["merchant.profile.update", "catalogue.create", "catalogue.read", "content.caption", "economics.expense.capture", "economics.expense.read", "economics.calculate"],
  "expires_at": "2026-12-16T23:59:59+01:00"
}
```

Create a conversation with POST /v1/conversations. Send messages to POST /v1/conversations/{id}/messages with a distinct Idempotency-Key for each new intent. For example, the message body for profile setup is:

```json
{"message":"/profile {\"business_name\":\"Ada Shop\",\"sector\":\"clothing\",\"currency\":\"NGN\",\"timezone\":\"Africa/Lagos\",\"capabilities\":[\"catalogue\",\"content\",\"economics\"]}"}
```

Then send these message strings through the same endpoint:

```text
/product {"title":"Cotton dress","sku":"AD-1","price_minor":450000,"currency":"NGN"}
/products
/caption {"product_id":"<id returned by product creation>"}
/expense {"amount_minor":20000,"currency":"NGN","category":"packaging","occurred_at":"2026-11-16T10:00:00+01:00","note":"boxes"}
/expenses
/calculate {"currency":"NGN","gross_minor":100000,"discounts_minor":5000,"refunds_minor":1000}
```

Repeat the same message and key to retrieve the existing run. Reusing its key for changed content returns 409. The financial report leaves operating profit unknown until required costs are supplied. Captions remain drafts; no social account is contacted.

GET conversation messages returns history; GET /v1/agent/runs returns recent results, including failed/blocked runs. Cancel an abandoned planning run before continuing its conversation. The runtime validates each tool's required fields; malformed commands ask for clarification.

For a self-contained demonstration with a temporary database and no credentials:

```powershell
.venv\Scripts\python examples/local_merchant.py
```

For natural-language planning, explicitly configure the model mode described in AI_AGENT_SPECIFICATION.md. Live AI requests consume your provider account usage; the offline demonstration makes none. WhatsApp delivery is not implemented in this release.
