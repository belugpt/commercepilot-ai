# WhatsApp text intake and worker — 0.3

This release implements inbound HTTP contracts and durable local processing. It has **not** been tested against a live Meta account. No message-sending client is included: every outbound record is a draft, never sent/delivered.

## Architecture

Meta POST → bounded raw bytes → HMAC-SHA256 verification → validated event batch → account/number/sender mapping → transactional inbox → HTTP acknowledgement. A separate CLI worker claims queued text, invokes the policy-checked agent and commits a draft reply. HTTP acknowledgement confirms persistence, not business execution or delivery.

The subscription GET validates hub.mode and hub.verify_token using constant-time comparison and returns hub.challenge as plain text. The POST validates X-Hub-Signature-256 over the original bytes using the app secret, before parsing. Missing configuration returns 503; bad signatures 401; malformed signed events 422; oversized requests 413. Webhook requests do not need a bearer key, because the Meta signature is the transport authentication. Owner inspection/revocation/retry routes do require bearer authorization.

## Configuration

Inject WHATSAPP_APP_SECRET and WHATSAPP_VERIFY_TOKEN through your shell or secret manager. Do not commit actual values. Start the API with the instructions in README. Callback path: `/webhooks/whatsapp`. A public TLS endpoint, correct Meta app/WABA subscription, permissions and approved business setup are needed before live validation. Keep development on loopback until deployment protections are ready. Configure access logs/proxies to omit the subscription verification query token; do not log webhook bodies.

Before allowing a WhatsApp sender to operate a merchant account, an operator must verify the merchant's identity, control of the sender identity and intended access. Create the binding using actual provider identifiers, not the visible phone display name:

```powershell
.venv\Scripts\python -m commercepilot.cli whatsapp-bind <merchant_id> <waba_id> <phone_number_id> phone:2348012345678
# For users identified by a business-scoped ID instead:
.venv\Scripts\python -m commercepilot.cli whatsapp-bind <merchant_id> <waba_id> <phone_number_id> bsuid:US.example
```

Binding ownership is operator-attested, not OAuth/provider-verified. No public endpoint can self-bind a sender. The binding creates a persistent conversation. Set the required autonomy grants using PUT /v1/policy, as in TRY_THE_AGENT.md. Mapping a sender does not enable automation grants or business capabilities.

Incoming routing requires an enabled binding for WABA ID, receiving phone_number_id and either sender phone identity or business-scoped from_user_id. A contact display name never authorizes access. BSUID-only messages are supported. When both identities resolve to different merchants, the message is ignored rather than choosing a tenant. Two independently created aliases for one merchant have separate conversations; alias linking/reassignment is not yet implemented. Revocation is permanent in the current API; reactivation requires a future reviewed operator workflow.

## Worker

Run this against the same COMMERCEPILOT_DB as the API, with the same planner configuration:

```powershell
.venv\Scripts\python -m commercepilot.cli whatsapp-work --once
# Or continuously; Ctrl+C stops the worker:
.venv\Scripts\python -m commercepilot.cli whatsapp-work
```

Workers atomically claim with a random lease token and 120-second expiry. Processing of a conversation preserves inbox arrival order. Another conversation can proceed independently. Expired claims can be reclaimed. The agent execution guard rechecks the binding and current lease inside the local-effect transaction; an expired/revoked worker cannot mutate business records. Model calls use the configured 30-second transport timeout, below the lease window; long-running custom planners may require a redesigned heartbeat protocol.

Agent idempotency is bound to the inbox ID. If a worker dies after the agent committed and before the reply draft, recovery reads the same run and does not repeat its effect. A worker dying during planning may leave an abandoned run: retries wait and eventually dead-letter, rather than launch duplicate planning. Inspect/cancel the agent run before retrying. Cancellation is terminal for that run; it cannot automatically replay the original business intent. A new signed message is required to request a new action.

Automatic transient retries use bounded exponential delay, at most five claims per retry cycle. Exhausted items become dead letters. Owner-initiated retry resets the cycle only for recoverable worker/busy/planning reasons with an enabled binding. Unsupported media, stale timestamps and revoked channels cannot be bypassed by retry. Errors store safe reason codes, not provider exception text.

## Inspection and recovery

- GET /v1/whatsapp/bindings: tenant mappings.
- GET /v1/whatsapp/inbox: pending/processing/completed/dead, attempt counts, reasons and linked runs.
- GET /v1/whatsapp/outbox: draft text and linked runs; there is no send route.
- GET /v1/whatsapp/conflicts: conflicting payload digests for reused provider IDs.
- POST /v1/whatsapp/bindings/{id}/revoke: disable sender access, including queued work and effects not yet committed.
- POST /v1/whatsapp/inbox/{id}/retry: requeue an eligible dead letter after review.
- Existing /v1/agent/runs routes inspect/cancel abandoned planning.

Records are tenant-filtered and bounded to 100 per collection. A completed inbox means the agent produced a terminal result (including blocked/failed/clarification), not that its business action succeeded. The linked run is authoritative for that distinction. Once an action has committed, subsequent binding revocation cannot undo it.

## Intake rules and limitations

- Deduplicate on WABA/phone/provider-message ID. Changed payload reuse records a conflict digest and preserves the first source; it does not overwrite or repeat the original action.
- Require the signed timestamp to be no older than seven days or more than five minutes ahead at admission. This is a local safety policy, not a promised Meta delivery SLA.
- Cap requests at 1 MB and parsed message batches at 100. Validate the entire batch before committing any messages.
- Unknown or ambiguous senders are acknowledged and ignored without creating merchant conversations or storing their text.
- Bound non-text messages are retained as unsupported dead letters; there is no media download, transcription or OCR. Delivery-status callbacks are acknowledged but not stored or treated as inbound commands.
- Only normalized message fields are persisted, not full raw webhook envelopes or unsupported media metadata. Sender/message IDs and conversation content are sensitive business data; production encryption, retention and deletion procedures remain pending.
- API traffic throttling, production PostgreSQL queueing, queue metrics/alerts, media support, business account onboarding, sender reactivation, outbound templates/windows/consent and independently verified delivery are future work.

## Official references checked 2026-11-16

- https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview — current message envelope, WABA/phone IDs, sender BSUIDs and permissions.
- https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/ — Meta's archived SDK reference corroborates verification challenge and raw-body signature checks; the archived SDK is not a dependency.
- The current text-specific reference returned HTTP 429 during research; recheck it with actual account access before live certification. No live-account or compliance claim is made.
