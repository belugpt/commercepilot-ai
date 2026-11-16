"""Business APIs share the existing identity/owner dependencies."""
from datetime import date
import hashlib
from importlib.resources import files
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from commercepilot.business import Business, OrderInput, FinancialRecordInput, CoverageInput, PlanInput, ApprovePlanInput
from commercepilot.services import now
from commercepilot.analytics import Analytics, ForecastInput


def business_router(services, owner, identity):
    router = APIRouter()
    business = Business(services)
    analytics = Analytics(services)

    @router.post("/v1/forecasts", tags=["planning"])
    def forecast(data: ForecastInput, user=Depends(identity)):
        try:
            return analytics.forecast(user["merchant_id"], data)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @router.get("/v1/plans/{plan_id}/variance", tags=["planning"])
    def plan_variance(plan_id: str, user=Depends(identity)):
        try:
            return analytics.variance(user["merchant_id"], plan_id)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard():
        html = files("commercepilot").joinpath("static/dashboard.html").read_text(encoding="utf-8")
        return HTMLResponse(html, headers={"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'", "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    @router.get("/assets/{filename}", include_in_schema=False)
    def asset(filename: str):
        types = {"dashboard.js": "text/javascript", "dashboard.css": "text/css"}
        if filename not in types:
            raise HTTPException(404, "asset not found")
        return Response(files("commercepilot").joinpath("static/" + filename).read_bytes(), media_type=types[filename], headers={"X-Content-Type-Options": "nosniff"})

    @router.get("/v1/me", tags=["merchant"])
    def me(user=Depends(identity)):
        with services.db.connect() as c:
            merchant = c.execute("SELECT name FROM merchants WHERE id=?", (user["merchant_id"],)).fetchone()
            policy = c.execute("SELECT version,body FROM policies WHERE merchant_id=?", (user["merchant_id"],)).fetchone()
            products = c.execute("SELECT id,body FROM products WHERE merchant_id=? ORDER BY sku LIMIT 200", (user["merchant_id"],)).fetchall()
            profile = c.execute("SELECT body FROM business_profiles WHERE merchant_id=?", (user["merchant_id"],)).fetchone()
        import json
        return {"merchant_id": user["merchant_id"], "name": merchant["name"], "role": user["role"],
                "profile": json.loads(profile["body"]) if profile else None,
                "policy": {"version": policy["version"], **json.loads(policy["body"])} if policy else None,
                "products": [{"id": p["id"], **json.loads(p["body"])} for p in products]}

    @router.post("/v1/orders/ingest", tags=["sales"])
    def ingest_order(data: OrderInput, user=Depends(owner)):
        return business.ingest(user["merchant_id"], data, "order")

    @router.get("/v1/orders", tags=["sales"])
    def orders(user=Depends(identity)):
        return business.latest(user["merchant_id"], "orders")

    @router.post("/v1/financial-records", tags=["economics"])
    def expense(data: FinancialRecordInput, user=Depends(owner)):
        return business.ingest(user["merchant_id"], data, "expense")

    @router.get("/v1/financial-records", tags=["economics"])
    def expenses(user=Depends(identity)):
        return business.latest(user["merchant_id"], "expenses")

    @router.put("/v1/reports/expense-coverage", tags=["economics"])
    def coverage(data: CoverageInput, user=Depends(owner)):
        return business.declare_coverage(user["merchant_id"], data)

    @router.get("/v1/reports/daily", tags=["sales"])
    def daily(day: date, currency: str = Query(pattern=r"^[A-Z]{3}$"), user=Depends(identity)):
        try:
            return business.daily(user["merchant_id"], day, currency)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @router.get("/v1/data-quality", tags=["economics"])
    def quality(user=Depends(owner)):
        return business.issues(user["merchant_id"])

    @router.post("/v1/plans", status_code=201, tags=["planning"])
    def create_plan(data: PlanInput, user=Depends(owner)):
        return business.create_plan(user["merchant_id"], data)

    @router.get("/v1/plans/{plan_id}", tags=["planning"])
    def get_plan(plan_id: str, user=Depends(identity)):
        return business.plan(user["merchant_id"], plan_id)

    @router.post("/v1/plans/{plan_id}/approve", tags=["planning"])
    def approve_plan(plan_id: str, data: ApprovePlanInput, user=Depends(owner)):
        return business.approve_plan(user["merchant_id"], plan_id, data)

    @router.get("/v1/plans", tags=["planning"])
    def plans(user=Depends(identity)):
        with services.db.connect() as c:
            ids = c.execute("SELECT id FROM business_plans WHERE merchant_id=? ORDER BY created_at DESC LIMIT 100", (user["merchant_id"],)).fetchall()
        return [business.plan(user["merchant_id"], r["id"]) for r in ids]

    @router.post("/v1/media", status_code=201, tags=["media"])
    async def upload(request: Request, user=Depends(owner)):
        mime = request.headers.get("content-type", "").split(";")[0].lower()
        signatures = {"application/pdf": (b"%PDF-",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/jpeg": (b"\xff\xd8\xff",)}
        if mime not in signatures:
            raise HTTPException(415, "only PDF, PNG and JPEG are accepted into quarantine")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8_000_000:
                raise HTTPException(413, "media limit is 8 MB")
            body.extend(chunk)
        if not any(body.startswith(sig) for sig in signatures[mime]):
            raise HTTPException(422, "content does not match the declared media type")
        fingerprint, media_id = hashlib.sha256(body).hexdigest(), str(uuid4())
        with services.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT id FROM media_uploads WHERE merchant_id=? AND content_hash=?", (user["merchant_id"], fingerprint)).fetchone()
            if row:
                media_id = row["id"]
            else:
                c.execute("INSERT INTO media_uploads VALUES(?,?,?,?,?,?,'quarantined',?)", (media_id, user["merchant_id"], fingerprint, mime, len(body), bytes(body), now()))
                services.audit(c, user["merchant_id"], "media.quarantined", media_id)
        return {"id": media_id, "state": "quarantined", "sha256": fingerprint, "bytes": len(body), "extraction": "not_performed"}

    @router.get("/v1/media", tags=["media"])
    def media(user=Depends(owner)):
        with services.db.connect() as c:
            return [dict(r) for r in c.execute("SELECT id,mime_type,byte_length,state,created_at FROM media_uploads WHERE merchant_id=? ORDER BY created_at DESC LIMIT 100", (user["merchant_id"],))]

    @router.get("/v1/media/{media_id}", tags=["media"])
    def download(media_id: str, user=Depends(owner)):
        with services.db.connect() as c:
            row = c.execute("SELECT body FROM media_uploads WHERE merchant_id=? AND id=?", (user["merchant_id"], media_id)).fetchone()
        if not row:
            raise HTTPException(404, "media not found")
        return Response(row["body"], media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="quarantined-upload.bin"', "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    return router
