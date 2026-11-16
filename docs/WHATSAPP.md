# WhatsApp intake, media and delivery — 0.5

Signed text intake, the durable worker, automatic text replies and delivered-status callbacks were validated against the owner's live Meta test account in 0.5. New installations keep external access disabled until configured. Attachment retrieval into quarantine is implemented and fixture-tested; transcription/OCR are not performed. See [operations](OPERATIONS.md) for the integrated runtime, protected settings and tunnel setup, and [the completion matrix](REQUIREMENTS_MATRIX.md) for remaining production gates.

## Architecture

Meta POST → bounded raw bytes → HMAC-SHA256 verification → validated event batch → account/number/sender mapping → transactional inbox → HTTP acknowledgement. A worker claims queued text, invokes the policy-checked agent and commits a draft reply. The separately authorized delivery worker claims eligible drafts before submission and reconciles signed statuses. HTTP acknowledgement confirms persistence, not business execution or delivery.

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
# To also drain eligible replies with configured sending and merchant grants:
.venv\Scripts\python -m commercepilot.cli whatsapp-work --send
# Or run both listeners and workers together:
.venv\Scripts\python -m commercepilot.cli serve
```

Workers atomically claim with a random lease token and 120-second expiry. Processing of a conversation preserves inbox arrival order. Another conversation can proceed independently. Expired claims can be reclaimed. The agent execution guard rechecks the binding and current lease inside the local-effect transaction; an expired/revoked worker cannot mutate business records. Model calls use the configured 30-second transport timeout, below the lease window; long-running custom planners may require a redesigned heartbeat protocol.

Agent idempotency is bound to the inbox ID. If a worker dies after the agent committed and before the reply draft, recovery reads the same run and does not repeat its effect. A worker dying during planning may leave an abandoned run: retries wait and eventually dead-letter, rather than launch duplicate planning. Inspect/cancel the agent run before retrying. Cancellation is terminal for that run; it cannot automatically replay the original business intent. A new signed message is required to request a new action.

Automatic transient retries use bounded exponential delay, at most five claims per retry cycle. Exhausted items become dead letters. Owner-initiated retry resets the cycle only for recoverable worker/busy/planning reasons with an enabled binding. Unsupported media, stale timestamps and revoked channels cannot be bypassed by retry. Errors store safe reason codes, not provider exception text.

## Inspection and recovery

- GET /v1/whatsapp/bindings: tenant mappings.
- GET /v1/whatsapp/inbox: pending/processing/completed/dead, attempt counts, reasons and linked runs.
- GET /v1/whatsapp/outbox: draft text and linked runs.
- POST /v1/whatsapp/outbox/{id}/send: owner submission with current reply grant, binding and reply-window checks.
- GET /v1/whatsapp/deliveries: submitting/accepted/sent/delivered/read/failed/uncertain evidence.
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
- With WHATSAPP_MEDIA_ENABLED=true, configured provider credentials, media.capture grant and content capability, bound image/document/audio/video attachments are retrieved through Meta's account-scoped media lookup. Downloads are restricted to HTTPS lookaside.fbsbx.com, reject redirects and verify size and SHA-256 against provider and webhook claims. Up to 8 MB is stored in tenant quarantine with its source message. Captions are retained as untrusted data and never executed as commands. No transcription, OCR, scanning or financial extraction occurs. Unsupported or unconfigured media remains a dead letter. Signed delivery statuses are stored and matched by account, phone, recipient and provider reference; they never invoke the agent.
- Only normalized message fields are persisted, not full raw webhook envelopes or unsupported media metadata. Sender/message IDs and conversation content are sensitive business data; production encryption, retention and deletion procedures remain pending.
- API throttling, production PostgreSQL queueing, metrics/alerts, interpreted media, self-serve business onboarding, sender reactivation and general approved-template campaigns remain future work. Text replies enforce a 24-hour inbound window and do not silently fall back to a template. The explicit operator Hello World utility is a test-account probe, separate from merchant reply automation.

## Official references checked 2026-11-16

- https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview — current message envelope, WABA/phone IDs, sender BSUIDs and permissions.
- https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/ — Meta's archived SDK reference corroborates verification challenge and raw-body signature checks; the archived SDK is not a dependency.
- The current text-specific reference returned HTTP 429 during research; recheck it with actual account access before live certification. No live-account or compliance claim is made.
