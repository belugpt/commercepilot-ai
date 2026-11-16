from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from commercepilot.api import create_app
from commercepilot.domain import Action, FinancialInput, financial_report


class FixtureAdapter:
    def __init__(self):
        self.calls, self.verified, self.raises = 0, True, False

    def submit(self, context):
        self.calls += 1
        if self.raises:
            raise TimeoutError("secret token must not be persisted")
        return "fixture-reference"

    def verify(self, context, reference):
        return {"fixture_only": True, "id": reference} if self.verified else None


@pytest.fixture
def setup(tmp_path):
    adapter = FixtureAdapter()
    app = create_app(str(tmp_path / "test.db"), {Action.DESCRIBE: adapter})
    service = app.state.services
    _, t1 = service.provision("merchant one")
    _, t2 = service.provision("merchant two")
    return TestClient(app), service, adapter, {"Authorization": f"Bearer {t1}"}, {"Authorization": f"Bearer {t2}"}


def product(client, headers):
    r = client.post("/v1/products", headers=headers, json={"title": "Dress", "sku": "D1", "price_minor": 125000, "currency": "NGN"})
    assert r.status_code == 201
    return r.json()["id"]


def grant(client, headers, **changes):
    body = {"enabled": True, "actions": ["content.describe"], "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    body.update(changes)
    return client.put("/v1/policy", headers=headers, json=body)


def task(client, headers, pid, action="content.describe", key="one"):
    return client.post("/v1/tasks", headers={**headers, "Idempotency-Key": key}, json={"action": action, "product_id": pid})


def test_tenant_isolation_auth_and_unique_sku(setup):
    c, s, a, h1, h2 = setup
    pid = product(c, h1)
    assert c.get(f"/v1/products/{pid}", headers=h2).status_code == 404
    assert task(c, h2, pid).status_code == 404
    assert c.get(f"/v1/products/{pid}").status_code == 401
    assert c.post("/v1/products", headers=h1, json={"title": "Other", "sku": "D1", "price_minor": 0, "currency": "NGN"}).status_code == 409
    product(c, h2)


def test_idempotency_and_verified_execution(setup):
    c, s, a, h, other = setup
    pid = product(c, h)
    grant(c, h)
    t = task(c, h, pid).json()
    assert task(c, h, pid).json()["id"] == t["id"]
    assert task(c, h, pid, action="catalogue.delete").status_code == 409
    assert c.get(f"/v1/tasks/{t['id']}", headers=other).status_code == 404
    url = f"/v1/tasks/{t['id']}/run"
    assert c.post(url, headers=h).json()["state"] == "succeeded"
    assert c.post(url, headers=h).json()["state"] == "succeeded"
    assert a.calls == 1


@pytest.mark.parametrize("change", [{"enabled": False}, {"actions": []}, {"expires_at": "2000-01-01T00:00:00Z"}])
def test_policy_blocks(setup, change):
    c, s, a, h, _ = setup
    t = task(c, h, product(c, h)).json()
    grant(c, h, **change)
    assert c.post(f"/v1/tasks/{t['id']}/run", headers=h).json()["state"] == "blocked"
    assert a.calls == 0
    assert len(c.get("/v1/exceptions", headers=h).json()) == 1


@pytest.mark.parametrize("action", ["payments.refund", "catalogue.delete", "social.publish", "catalogue.sync"])
def test_sensitive_and_unimplemented_rules_block(setup, action):
    c, s, a, h, _ = setup
    pid = product(c, h)
    grant(c, h, actions=[action])
    t = task(c, h, pid, action=action).json()
    assert c.post(f"/v1/tasks/{t['id']}/run", headers=h).json()["state"] == "blocked"
    assert a.calls == 0


@pytest.mark.parametrize("raises", [False, True])
def test_uncertain_never_resubmits_or_leaks_errors(setup, raises):
    c, s, a, h, _ = setup
    a.verified, a.raises = False, raises
    grant(c, h)
    t = task(c, h, product(c, h)).json()
    url = f"/v1/tasks/{t['id']}/run"
    assert c.post(url, headers=h).json()["state"] == "uncertain"
    c.post(url, headers=h)
    assert a.calls == 1
    assert "secret" not in c.get("/v1/exceptions", headers=h).text


def test_concurrent_claims_submit_once(setup):
    c, s, a, h, _ = setup
    grant(c, h)
    t = task(c, h, product(c, h)).json()
    merchant = s.identity(h["Authorization"].split()[1])["merchant_id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: s.run(merchant, t["id"]), range(4)))
    assert a.calls == 1


def test_money_unknown_and_exact():
    d = FinancialInput(currency="NGN", gross_minor=10000, discounts_minor=1000, refunds_minor=500)
    r = financial_report(d)
    assert r["net_sales_minor"] == 9000
    assert r["sales_after_refunds_minor"] == 8500
    assert r["operating_profit_minor"] is None
    assert r["cash_collected_minor"] is None
    r = financial_report(d.model_copy(update={"cogs_minor": 3000, "expenses_minor": 1000}))
    assert r["operating_profit_minor"] == 4500


def test_validation(setup):
    c, s, a, h, _ = setup
    body = {"title": "Dress", "sku": "D", "price_minor": 1.1, "currency": "NGN", "merchant_id": "other"}
    assert c.post("/v1/products", headers=h, json=body).status_code == 422
    assert grant(c, h, expires_at="2027-01-01T00:00:00").status_code == 422
    assert c.post("/v1/reports/calculate", headers=h, json={"currency": "NGN", "gross_minor": 1, "discounts_minor": 2, "refunds_minor": 0}).status_code == 422


def test_missing_adapter_and_key_revocation(setup):
    c, s, a, h, _ = setup
    grant(c, h)
    s.adapters.clear()
    t = task(c, h, product(c, h)).json()
    assert c.post(f"/v1/tasks/{t['id']}/run", headers=h).json()["state"] == "blocked"
    from commercepilot.services import digest
    with s.db.connect() as conn:
        conn.execute("UPDATE api_keys SET revoked=1 WHERE digest=?", (digest(h["Authorization"].split()[1]),))
    assert c.get("/v1/audit", headers=h).status_code == 401
