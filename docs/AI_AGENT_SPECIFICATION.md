# Agent runtime — 0.2

## Implemented flow

Authenticate owner → resolve tenant/conversation → reserve idempotent run → load bounded merchant context → propose exactly one tool → reject unknown tools/extra arguments → validate typed fields → recheck current autonomy policy and business capability → execute local service transaction → persist actual result, assistant message and audit → respond.

The model only selects tools and supplies data; it cannot grant permissions, choose a tenant, run SQL or assert execution success. Completion messages for executed tools are rendered by trusted handlers. Model clarification questions are untrusted language and are explicitly marked clarification, never completed. Profile and expense fields remain merchant-reported, not externally verified.

## Modes

- Default `offline_commands`: explicit slash commands/JSON plus a bounded set of read aliases and typed shortcuts (`/add title | SKU | NGN 5000.00`, `/caption SKU`, `sales today`). This is a deterministic parser, not unrestricted natural-language AI. Relative dates use the stored merchant timezone.
- Optional `openai_responses`: Responses API function selection from the same strict tool registry. Set COMMERCEPILOT_PLANNER=openai, COMMERCEPILOT_MODEL to an account-supported model, and OPENAI_API_KEY through the shell/secret manager. There is no hardcoded model, included credential or live-provider verification. Startup fails if configuration is incomplete. Do not silently fall back after a model error.
- Extensions implement AgentPlanner.propose(message, context), expose a mode string and return only `{tool, arguments}`. The older integrations.Planner protocol describes the initial generic port; the agent runtime uses AgentPlanner.

Official implementation references: https://developers.openai.com/api/docs/guides/function-calling and https://developers.openai.com/api/reference/resources/responses/methods/create (checked 2026-11-16). The model request disables provider response storage, restricts selection to one function, caps output tokens and times out after 30 seconds. Account retention and privacy terms must be reviewed separately. No provider call is made in offline mode or fixture tests.

## Tools

| Tool | Permission | Business capability | Behavior |
|---|---|---|---|
| profile_save | merchant.profile.update | none | Save name/sector/currency/timezone/capabilities |
| product_create | catalogue.create | catalogue | Create canonical product and read back |
| catalogue_list | catalogue.read | catalogue | List up to 100 tenant products |
| caption_prepare | content.caption | content | Factual catalogue template; no publication |
| expense_capture | economics.expense.capture | economics | Record unreconciled merchant-reported cost with source |
| expenses_list | economics.expense.read | economics | List separate currency-preserving records |
| report_calculate | economics.calculate | economics | Exact explicitly supplied aggregates; unknowns retained |
| daily_report | sales.report.daily | economics | Source-linked timezone/currency daily calculations |
| forecast_prepare | sales.report.daily | economics | History gates, evaluated statistical baselines and descriptive scenarios |
| plan_variance | sales.report.daily | economics | Compare exact plan targets with recorded actuals; preserve unknowns |
| external_request | external action policy | unavailable | Refund/delete escalated; publish/sync remain blocked |
| clarify | no mutation | none | Ask for missing facts |

No tool can change autonomy permissions. The authenticated owner configures grants through PUT /v1/policy. Profiles and grants are distinct: enabling economics does not authorize expenses without a grant.

## Persistence and recovery

Business profiles, conversations, user/assistant messages, runs and expenses use migration 002. A local tool effect, result, assistant message and audit commit together. Concurrent deliveries with the same key share a run; changed content conflicts. A conversation accepts only one planning turn at a time. Up to six recent messages (2000 characters each), profile and 50 products form planning context; larger catalogue pagination/retrieval is pending.

Run states: planning, completed, clarification, blocked, failed. A process crash before commit leaves planning with no local tool effects. Inspect GET /v1/agent/runs and cancel abandoned planning runs using POST /v1/agent/runs/{id}/cancel. A late planner rechecks state and cannot execute after cancellation. Cancellation cannot reverse an already committed action or undo provider token usage. New intent uses a new idempotency key.

Planning and local execution remain synchronous for direct API calls. WhatsApp routes signed text through a durable inbox and leased worker; the integrated runtime also drains eligible authorized replies and records delivery evidence. This remains one tool per turn, not multi-step chaining. Attachments use a trusted quarantine handler, never caption-driven tool execution. External task execution stays in the separate subsystem; social scheduling remains incomplete.

## Integrity and limits

Every expense preserves raw message/validated arguments through its run, normalized UTC occurrence, recording timestamp, currency/minor amount, source/evidence ID, merchant-reported verification and unreconciled status. Confidence is unknown rather than invented. Duplicate message delivery cannot duplicate an expense; separately worded duplicate receipts are not yet detected. Imported order/expense revisions and daily ledger reporting are implemented; independent provider reconciliation and receipt interpretation remain incomplete.

Caption drafts show Nigerian naira prices with two decimal places. Other currencies retain their source values in the catalogue, but caption prices are omitted until a supported currency-scale registry is added. No exchange conversion occurs.

Model outputs are schema-validated but may still contain semantically incorrect facts. Merchant inputs and catalogue strings are untrusted. Never provide secrets in conversation: raw messages and results are persisted locally, and bounded context is sent to the configured model provider when enabled. Storage encryption, retention, consent and production incident procedures remain release gates.
