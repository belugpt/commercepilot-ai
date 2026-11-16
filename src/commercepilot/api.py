"""Versioned API; bearer keys resolve tenants server-side."""
import os
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from commercepilot.database import Database
from commercepilot.domain import FinancialInput, PolicyInput, ProductInput, TaskInput, financial_report
from commercepilot.integrations import PROVIDERS
from commercepilot.services import Conflict, Missing, Services


def create_app(db_path: str | None = None, adapters=None) -> FastAPI:
    service = Services(Database(db_path or os.getenv("COMMERCEPILOT_DB", "commercepilot.db")), adapters)
    app = FastAPI(title="CommercePilot AI", version="0.1.0")
    app.state.services = service
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

    @app.get("/health", tags=["operations"])
    def health():
        return {"status": "ok", "version": "0.1.0"}

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

    return app
