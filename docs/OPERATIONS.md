# Local runtime and deployment preparation

## Windows runtime

`python -m commercepilot.cli serve` runs the private dashboard on 127.0.0.1:8000, a webhook-only listener on 127.0.0.1:8002, and the durable inbox/reply workers. The listeners share one database. Both access logs are disabled so the subscription verification query is not logged. The public surface has no dashboard, bearer APIs, documentation or upload endpoint.

For a Windows background run use `scripts/start-local.ps1 -WithTunnel` after placing the official utility at `.local/tools/cloudflared.exe`. Both processes start hidden, with logs/PIDs under ignored `.local`. The launcher refuses an occupied dashboard port. `scripts/stop-local.ps1` stops only process command lines/executables matching this project and tunnel target. The user must renew the callback after a new tunnel URL is assigned. Background processes survive tool-session loss, but a computer restart or provider tunnel/token expiry still interrupts the service.

Set each credential locally with `python -m commercepilot.cli set-secret WHATSAPP_APP_SECRET` (and the other names in `.env.example`). Values are entered invisibly and protected by Windows user-scoped DPAPI in ignored `.local/secrets.dpapi`. Environment variables take precedence. `COMMERCEPILOT_SECRET_FILE` selects another protected file. This file is tied to the Windows account; it is not a portable production vault. Non-Windows hosts must inject environment secrets instead. Do not send secrets in WhatsApp or commit them.

`python -m commercepilot.cli doctor` prints presence flags, planner mode and enablement only. Presence is not provider verification. To check a scoped Meta test token and phone ID, run `python examples/whatsapp_live_probe.py`. Add `--send-hello-world <verified-recipient-digits>` only when you deliberately want a test template sent. This operator test claims one submission in ignored `.local/live-hello-world.json`; it will not blindly repeat an uncertain send.

The default installed planner remains account-free. Supported shortcuts include `/products`, `show my products`, `/expenses`, `sales today`, `sales yesterday`, `/sales`, `/add Product title | SKU | NGN 5000.00`, and `/caption SKU`. These are deterministic commands, not unrestricted language understanding. JSON tools remain available. An explicitly configured model is necessary for open-ended requests; no API credits are included.

## HTTPS test tunnel

Install the official Cloudflare utility and point it only at port 8002:

```powershell
cloudflared tunnel --url http://127.0.0.1:8002 --no-autoupdate
```

Register `https://<assigned-host>.trycloudflare.com/webhooks/whatsapp` in Meta with the local verification token. Subscribe the `messages` field, then separately subscribe the app to the intended WABA using the official `/{WABA-ID}/subscribed_apps` API. Account subscription and callback configuration are distinct. Do not point a tunnel at the private dashboard port. The URL changes when the tunnel restarts and works only while the processes/computer stay running. Quick Tunnels provide no production uptime guarantee.

If an approved test tunnel is replaced, the explicit operator command `python -m commercepilot.cli whatsapp-subscribe <WABA-ID> --callback https://<new-host>/webhooks/whatsapp` sets a WABA-specific alternate callback and asks Meta to verify it. It does not change the app dashboard's default callback or grant a new app/account access. Omit `--callback` only when deliberately restoring the app default; that removes the account override. This uses Meta's supported subscription contract ([official Python SDK](https://github.com/meta/facebook-python-business-sdk/blob/main/facebook_business/adobjects/whatsappbusinessaccount.py)). Token expiry must be resolved first; Meta code 190/subcode 463 was observed for the expired temporary token during local testing. A temporary tunnel/token cannot provide an always-on production service.

After configuration, send an actual WhatsApp message from an operator-verified bound identity. Inspect the persisted inbox, agent run, outbox and delivery status. Signature verification and identity binding remain mandatory. A delivery callback is stronger evidence than an accepted send response. Test-account access does not imply the app is approved to serve arbitrary production users. Follow the current account-specific publication/business/phone requirements shown by Meta.

References: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [Meta WABA subscriptions](https://www.postman.com/meta/whatsapp-business-platform/request/c1ai24q/subscribe-to-your-waba).

## Containers

`Dockerfile` and `compose.yaml` prepare a non-root Python runtime with a persistent data volume. Populate ignored `.env` with environment secrets and keep `WHATSAPP_SEND_ENABLED=false` until the binding, grant and provider validation are ready. Run `docker compose up --build`; optionally add `--profile tunnel` to start a webhook-only tunnel sidecar. Only the private dashboard port is mapped, on host loopback. Provision a tenant inside the app container using the CLI; existing Windows DPAPI files cannot be decrypted inside Linux containers. The application and tunnel share a network namespace so the gateway stays on loopback.

Docker is unavailable on the development computer; these container files have not been build/run validated. They are deployment preparation, not a production deployment. A managed PostgreSQL/RLS store, federated identity, object scanning/storage, TLS/stable ingress, tenancy/load testing, backup/restore, retention controls and operational monitoring are still release gates.

## Forecasts and plan variance

WhatsApp attachment capture is separately enabled with `WHATSAPP_MEDIA_ENABLED=true` and requires a current `media.capture` grant plus the content capability. It accepts supported image/PDF/audio/video types up to 8 MB, checks the provider account, destination, content size and hash, and stores source-linked quarantine bytes. It never interprets attachments, follows instructions in captions or creates financial/product facts from unreviewed media. Redirects are rejected to prevent forwarding credentials to a different host. Official contract: [Retrieve Media URL](https://www.postman.com/meta/whatsapp-business-platform/request/ptjyi84/retrieve-media-url). Retrieval and security gates are fixture-tested; live attachment receipt remains a separate acceptance check.

`POST /v1/forecasts` accepts `ends_on`, `currency`, `history_days` (28–180) and `horizon_days` (1–30). Every historical day must have explicit order history. Missing days return `insufficient_history`; they are never silently filled with zero. A seven-day holdout compares mean and weekly naive methods using MAE and WAPE. The chosen method produces base/downside/optimistic sales scenarios from empirical holdout error, not calibrated confidence bounds. These are recorded booked-sales estimates, not guarantees, cash forecasts or inventory commitments. Zero-denominator WAPE is unknown.

`GET /v1/plans/{id}/variance` compares recorded net sales and complete expenses with that exact plan's target/budget. Positive revenue variance is above target; positive expense variance is above budget. Missing days/cost coverage remain unknown. Periods are bounded to 366 days. The agent exposes `/forecast <JSON>` and `/variance {"plan_id":"..."}` under economics capability and `sales.report.daily` permission. Daily WhatsApp reports now render actual amounts and missing fields.

## Recovery

Inbox processing retries bounded recoverable local failures. Delivery submission is claimed before contacting Meta; accepted/delivered/read/failed/uncertain states are persisted separately from drafts. A network ambiguity or crash after claiming is never automatically resubmitted. Inspect the provider and the stored reference before operator intervention. Expired windows and revoked grants/bindings cannot be bypassed by the worker. Revoke a key with the existing CLI, revoke a binding through the owner API, or disable the autonomy policy to stop new authorized effects.
