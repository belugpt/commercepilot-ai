"""A separate listener exposes only the signed WhatsApp webhook, never the dashboard."""
import os
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool
from commercepilot.api import create_app
from commercepilot.whatsapp import WebhookError, MAX_BODY_BYTES


def webhook_app(whatsapp):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(WebhookError)
    async def error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.code})

    @app.get("/health")
    def health():
        return {"status": "ok", "surface": "signed_whatsapp_webhook"}

    @app.get("/webhooks/whatsapp")
    def verify(mode: str | None = Query(None, alias="hub.mode"), token: str | None = Query(None, alias="hub.verify_token"), challenge: str | None = Query(None, alias="hub.challenge")):
        return PlainTextResponse(whatsapp.verify_subscription(mode, token, challenge))

    @app.post("/webhooks/whatsapp")
    async def receive(request: Request, x_hub_signature_256: str | None = Header(None)):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                raise WebhookError(413, "payload_too_large")
            body.extend(chunk)
        return await run_in_threadpool(whatsapp.ingest, bytes(body), x_hub_signature_256)

    return app


def create_gateway():
    from commercepilot.secrets import load_environment
    load_environment(os.getenv("COMMERCEPILOT_SECRET_FILE", ".local/secrets.dpapi"))
    return webhook_app(create_app().state.whatsapp)
