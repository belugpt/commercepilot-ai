"""Versioned API; bearer keys resolve tenants server-side."""
import os
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from commercepilot.database import Database
from commercepilot.domain import FinancialInput, PolicyInput, ProductInput, TaskInput, financial_report
from commercepilot.integrations import PROVIDERS
from commercepilot.services import Conflict, Missing, Services
from commercepilot.agent import Agent
from commercepilot.agent_schema import MessageInput
from commercepilot.planners import configured_planner
from commercepilot.whatsapp import WhatsApp, WebhookError, MAX_BODY_BYTES
from commercepilot.business_api import business_router
from commercepilot.delivery import Delivery, configured_sender
from commercepilot.media import configured_media


def create_app(db_path: str | None = None, adapters=None, planner=None,
               whatsapp_secret=None, whatsapp_verify_token=None, clock=None, sender=None) -> FastAPI:
    service = Services(Database(db_path or os.getenv("COMMERCEPILOT_DB", "commercepilot.db")), adapters)
    app = FastAPI(title="CommercePilot AI", version="0.6.0")
    app.state.services = service
    agent = Agent(service, planner if planner is not None else configured_planner())
    app.state.agent = agent
    whatsapp = WhatsApp(service, agent, whatsapp_secret or os.getenv("WHATSAPP_APP_SECRET"),
                        whatsapp_verify_token or os.getenv("WHATSAPP_VERIFY_TOKEN"), clock, configured_media())
    app.state.whatsapp = whatsapp
    delivery = Delivery(service, sender if sender is not None else configured_sender(), clock)
    app.state.delivery = delivery
    security = HTTPBearer(auto_error=False)

    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
        user = service.identity(credentials.credentials) if credentials else None
        if not user:
            raise HTTPException(401, "invalid or revoked credentials", headers={"WWW-Authenticate": "Bearer"})
        return user

    def owner(user=Depends(identity)):
        if user["role"] != "owner":
            raise HTTPException(403, "owner required")
        return user

    @app.exception_handler(Missing)
    async def missing_handler(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(WebhookError)
    async def webhook_error_handler(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.code})

    @app.get("/webhooks/whatsapp", tags=["whatsapp"])
    def verify_whatsapp(hub_mode: str | None = Query(default=None, alias="hub.mode"),
                        hub_token: str | None = Query(default=None, alias="hub.verify_token"),
                        hub_challenge: str | None = Query(default=None, alias="hub.challenge")):
        return PlainTextResponse(whatsapp.verify_subscription(hub_mode, hub_token, hub_challenge))

    @app.post("/webhooks/whatsapp", tags=["whatsapp"])
    async def receive_whatsapp(request: Request, x_hub_signature_256: str | None = Header(default=None)):
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_BODY_BYTES:
                raise WebhookError(413, "payload_too_large")
            raw.extend(chunk)
        return await run_in_threadpool(whatsapp.ingest, bytes(raw), x_hub_signature_256)

    @app.get("/health", tags=["operations"])
    def health():
        return {"status": "ok", "version": "0.6.0"}

    @app.get("/v1/runtime", tags=["operations"])
    def runtime_status(user=Depends(owner)):
        return {"planner": agent.planner.mode,
                "whatsapp_signature_configured": bool(whatsapp._secret),
                "whatsapp_verification_configured": bool(whatsapp._verify_token),
                "whatsapp_sender_configured": delivery.sender is not None,
                "whatsapp_media_configured": whatsapp.media_loader is not None,
                "account_validation": "Configuration alone does not prove provider access or app publication."}

    @app.post("/v1/products", status_code=201, tags=["catalogue"])
    def create_product(data: ProductInput, user=Depends(owner)):
        return service.create_product(user["merchant_id"], data)

    @app.get("/v1/products/{product_id}", tags=["catalogue"])
    def get_product(product_id: str, user=Depends(identity)):
        return service.product(user["merchant_id"], product_id)

    @app.put("/v1/policy", tags=["autonomy"])
    def set_policy(data: PolicyInput, user=Depends(owner)):
        if data.expires_at.tzinfo is None:
            raise HTTPException(422, "expires_at must include timezone")
        service.policy(user["merchant_id"], data)
        return {"saved": True}

    @app.post("/v1/tasks", status_code=202, tags=["execution"])
    def submit_task(data: TaskInput, idempotency_key: str = Header(min_length=1, max_length=200), user=Depends(owner)):
        return service.submit(user["merchant_id"], idempotency_key, data)

    @app.get("/v1/tasks/{task_id}", tags=["execution"])
    def get_task(task_id: str, user=Depends(identity)):
        return service.task(user["merchant_id"], task_id)

    @app.post("/v1/tasks/{task_id}/run", tags=["execution"])
    def run_task(task_id: str, user=Depends(owner)):
        return service.run(user["merchant_id"], task_id)

    @app.get("/v1/audit", tags=["operations"])
    def audit(user=Depends(owner)):
        return service.history(user["merchant_id"], "audit")

    @app.get("/v1/exceptions", tags=["operations"])
    def exceptions(user=Depends(owner)):
        return service.history(user["merchant_id"], "exceptions")

    @app.get("/v1/integrations", tags=["integrations"])
    def integrations(user=Depends(identity)):
        return PROVIDERS

    @app.post("/v1/reports/calculate", tags=["economics"])
    def calculate(data: FinancialInput, user=Depends(identity)):
        try:
            return financial_report(data)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.post("/v1/conversations", status_code=201, tags=["agent"])
    def create_conversation(user=Depends(owner)):
        return agent.conversation(user["merchant_id"])

    @app.post("/v1/conversations/{conversation_id}/messages", tags=["agent"])
    def agent_message(conversation_id: str, data: MessageInput,
                      idempotency_key: str = Header(min_length=1, max_length=200), user=Depends(owner)):
        return agent.turn(user["merchant_id"], conversation_id, idempotency_key, data.message)

    @app.get("/v1/conversations/{conversation_id}/messages", tags=["agent"])
    def conversation_messages(conversation_id: str, user=Depends(owner)):
        return agent.history(user["merchant_id"], conversation_id)

    @app.get("/v1/agent/runs/{run_id}", tags=["agent"])
    def agent_run(run_id: str, user=Depends(owner)):
        return agent.get_run(user["merchant_id"], run_id)

    @app.get("/v1/agent/runs", tags=["agent"])
    def agent_runs(user=Depends(owner)):
        return agent.runs(user["merchant_id"])

    @app.post("/v1/agent/runs/{run_id}/cancel", tags=["agent"])
    def cancel_agent_run(run_id: str, user=Depends(owner)):
        return agent.cancel(user["merchant_id"], run_id)

    @app.get("/v1/whatsapp/{collection}", tags=["whatsapp"])
    def whatsapp_records(collection: str, user=Depends(owner)):
        if collection == "deliveries":
            return delivery.records(user["merchant_id"])
        if collection not in {"bindings", "inbox", "outbox", "conflicts"}:
            raise HTTPException(404, "collection not found")
        return whatsapp.list_records(user["merchant_id"], collection)

    @app.post("/v1/whatsapp/bindings/{binding_id}/revoke", tags=["whatsapp"])
    def revoke_whatsapp(binding_id: str, user=Depends(owner)):
        return whatsapp.revoke(user["merchant_id"], binding_id)

    @app.post("/v1/whatsapp/inbox/{inbox_id}/retry", tags=["whatsapp"])
    def retry_whatsapp(inbox_id: str, user=Depends(owner)):
        return whatsapp.requeue(user["merchant_id"], inbox_id)

    @app.post("/v1/whatsapp/outbox/{outbox_id}/send", tags=["whatsapp"])
    def send_reply(outbox_id: str, user=Depends(owner)):
        return delivery.send(user["merchant_id"],outbox_id)

    app.include_router(business_router(service, owner, identity))
    return app
