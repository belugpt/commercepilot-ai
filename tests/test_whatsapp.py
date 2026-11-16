from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from commercepilot.api import create_app
from commercepilot.domain import Action
from commercepilot.planners import CommandPlanner
from commercepilot.whatsapp import LEASE_SECONDS, MAX_ATTEMPTS
from test_agent import PROFILE, PRODUCT

SECRET = "fixture-app-secret"
VERIFY = "fixture-verification-token"


class Clock:
    def __init__(self):
        self.time = 1800000000.0
    def __call__(self):
        return self.time


@pytest.fixture
def wa_setup(tmp_path):
    clock = Clock()
    app = create_app(str(tmp_path / "wa.db"), planner=CommandPlanner(), whatsapp_secret=SECRET, whatsapp_verify_token=VERIFY, clock=clock)
    c, s, wa = TestClient(app), app.state.services, app.state.whatsapp
    merchant, key = s.provision("Ada")
    h = {"Authorization": f"Bearer {key}"}
    c.put("/v1/policy", headers=h, json={"enabled": True, "actions": [a.value for a in Action], "expires_at": "2099-01-01T00:00:00Z"})
    binding = wa.bind(merchant, "111", "222", "phone:2348012345678")
    return app, c, h, merchant, binding, clock


def payload(text="/products", mid="wamid.fixture", sender="2348012345678", timestamp="1800000000", **extra):
    message = {"id": mid, "from": sender, "timestamp": timestamp, "type": "text", "text": {"body": text}}
    message.update(extra)
    if message["type"] != "text":
        message.pop("text", None)
    if sender is None:
        del message["from"]
    return {"object": "whatsapp_business_account", "entry": [{"id": "111", "changes": [{"field": "messages", "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "222"}, "messages": [message]}}]}]}


def post(c, data, secret=SECRET):
    raw = json.dumps(data).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return c.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"})


def onboard(c, wa):
    assert post(c, payload("/profile " + json.dumps(PROFILE), mid="onboard")).status_code == 200
    assert wa.process_one()["state"] == "completed"


def test_verification_handshake_and_signature_checks(wa_setup):
    app, c, h, m, b, clock = wa_setup
    url = "/webhooks/whatsapp"
    assert c.get(url, params={"hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "12345"}).text == "12345"
    assert c.get(url, params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"}).status_code == 403
    assert post(c, payload(), secret="wrong").status_code == 401
    assert c.post(url, content=b"not json").status_code == 401
    assert c.post(url, content=b"x" * 1_000_001).status_code == 413
    assert post(c, {"object": "wrong"}).status_code == 422
    assert c.get("/v1/whatsapp/inbox", headers=h).json() == []


def test_unconfigured_routes_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)
    c = TestClient(create_app(str(tmp_path / "off.db"), planner=CommandPlanner()))
    assert post(c, payload()).status_code == 503
    assert c.get("/webhooks/whatsapp").status_code == 503


def test_webhook_is_queue_only_then_worker_executes_and_drafts(wa_setup):
    app, c, h, merchant, binding, clock = wa_setup
    wa = app.state.whatsapp
    onboard(c, wa)
    data = payload("/product " + json.dumps(PRODUCT))
    assert post(c, data).json()["accepted"] == 1
    with wa.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    result = wa.process_one()
    assert result["delivery"] == "draft_only"
    with wa.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    assert post(c, data).json()["duplicates"] == 1
    assert wa.process_one() is None
    drafts = c.get("/v1/whatsapp/outbox", headers=h).json()
    assert len(drafts) == 2
    assert all(d["state"] == "draft" for d in drafts)
    assert "Cotton dress" in drafts[-1]["body"] or "Cotton dress" in drafts[0]["body"]


def test_unknown_sender_and_wrong_account_cannot_route(wa_setup):
    app, c, h, _, _, _ = wa_setup
    assert post(c, payload(sender="2348099999999")).json()["ignored"] == 1
    data = payload()
    data["entry"][0]["id"] = "999"
    assert post(c, data).json()["ignored"] == 1
    assert app.state.whatsapp.process_one() is None


def test_bsuid_only_sender_routes_and_conflicting_alias_does_not(wa_setup):
    app, c, h, merchant, _, _ = wa_setup
    wa = app.state.whatsapp
    wa.bind(merchant, "111", "222", "bsuid:US.fixture")
    assert post(c, payload(sender=None, from_user_id="US.fixture")).json()["accepted"] == 1
    assert wa.process_one()["state"] == "completed"
    other, _ = app.state.services.provision("Other")
    wa.bind(other, "111", "222", "bsuid:US.other")
    assert post(c, payload(mid="ambiguous", from_user_id="US.other")).json()["ignored"] == 1


def test_source_id_conflict_preserves_original_and_surfaces_issue(wa_setup):
    app, c, h, _, _, _ = wa_setup
    assert post(c, payload()).json()["accepted"] == 1
    assert post(c, payload("/profile {}")).json()["conflicts"] == 1
    conflicts = c.get("/v1/whatsapp/conflicts", headers=h).json()
    assert len(conflicts) == 1
    with app.state.whatsapp.db.connect() as conn:
        assert json.loads(conn.execute("SELECT body FROM whatsapp_inbox").fetchone()[0])["text"]["body"] == "/products"


@pytest.mark.parametrize("changes,reason", [
    ({"type": "image", "text": None}, "unsupported_message_type"),
    ({"timestamp": "1"}, "message_timestamp_outside_admission_window"),
    ({"timestamp": "1999999999"}, "message_timestamp_outside_admission_window"),
])
def test_unsupported_or_stale_events_dead_letter(wa_setup, changes, reason):
    app, c, h, _, _, _ = wa_setup
    assert post(c, payload(**changes)).json()["accepted"] == 1
    assert app.state.whatsapp.process_one() is None
    row = c.get("/v1/whatsapp/inbox", headers=h).json()[0]
    assert row["state"] == "dead" and row["reason"] == reason


def test_binding_revocation_blocks_queued_work_and_tenant_reads(wa_setup):
    app, c, h, merchant, binding, _ = wa_setup
    post(c, payload("/profile " + json.dumps(PROFILE)))
    other, key = app.state.services.provision("Other")
    h2 = {"Authorization": f"Bearer {key}"}
    assert c.get("/v1/whatsapp/inbox", headers=h2).json() == []
    url = f"/v1/whatsapp/bindings/{binding['id']}/revoke"
    assert c.post(url, headers=h2).status_code == 404
    assert c.post(url, headers=h).status_code == 200
    assert app.state.whatsapp.process_one()["state"] == "dead"
    with app.state.whatsapp.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM business_profiles").fetchone()[0] == 0


def test_revocation_during_planning_prevents_local_effect(wa_setup):
    app, c, h, merchant, binding, _ = wa_setup
    wa = app.state.whatsapp
    class RevokingPlanner:
        mode = "test"
        def propose(self, message, context):
            wa.revoke(merchant, binding["id"])
            return {"tool": "profile_save", "arguments": PROFILE}
    app.state.agent.planner = RevokingPlanner()
    post(c, payload("setup"))
    result = wa.process_one()
    assert app.state.agent.get_run(merchant, result["run_id"])["state"] == "blocked"
    with wa.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM business_profiles").fetchone()[0] == 0


def test_concurrent_workers_have_one_claim(wa_setup):
    app, c, h, _, _, _ = wa_setup
    wa = app.state.whatsapp
    post(c, payload())
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: wa.claim(), range(4)))
    assert sum(x is not None for x in claims) == 1


def test_crash_after_agent_commit_recovers_without_duplicate_effect(wa_setup):
    app, c, h, merchant, _, clock = wa_setup
    wa = app.state.whatsapp
    onboard(c, wa)
    post(c, payload("/product " + json.dumps(PRODUCT)))
    item = wa.claim()
    # Emulate a worker dying after the agent committed but before inbox finalization.
    run = wa.agent.turn(merchant, item["conversation_id"], "whatsapp:" + item["id"], "/product " + json.dumps(PRODUCT), execution_guard=lambda conn: wa._guard(conn, item))
    assert run["state"] == "completed"
    clock.time += LEASE_SECONDS + 1
    assert wa.process_one()["state"] == "completed"
    with wa.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM whatsapp_outbox WHERE inbox_id=?", (item["id"],)).fetchone()[0] == 1


def test_fenced_lease_cannot_execute_late_effect(wa_setup):
    app, c, h, merchant, _, clock = wa_setup
    wa = app.state.whatsapp
    post(c, payload("/profile " + json.dumps(PROFILE)))
    old = wa.claim()
    clock.time += LEASE_SECONDS + 1
    new = wa.claim()
    assert old["lease_token"] != new["lease_token"]
    run = wa.agent.turn(merchant, old["conversation_id"], "whatsapp:" + old["id"], "/profile " + json.dumps(PROFILE), execution_guard=lambda conn: wa._guard(conn, old))
    assert run["state"] == "blocked"
    with wa.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM business_profiles").fetchone()[0] == 0


def test_bounded_retry_and_restart_persistence(wa_setup):
    app, c, h, _, _, clock = wa_setup
    wa = app.state.whatsapp
    post(c, payload())
    with patch.object(wa.agent, "turn", side_effect=RuntimeError("sensitive provider error")):
        for _ in range(MAX_ATTEMPTS):
            wa.process_one()
            clock.time += 301
    row = c.get("/v1/whatsapp/inbox", headers=h).json()[0]
    assert row["state"] == "dead" and row["attempts"] == MAX_ATTEMPTS
    assert "sensitive" not in json.dumps(row)
    assert wa.process_one() is None
    from commercepilot.database import Database
    Database(wa.db.path)
    with wa.db.connect() as conn:
        assert conn.execute("SELECT state FROM whatsapp_inbox").fetchone()[0] == "dead"


def test_status_callback_is_acknowledged_without_agent_or_reply(wa_setup):
    app, c, h, _, _, _ = wa_setup
    data = payload()
    value = data["entry"][0]["changes"][0]["value"]
    del value["messages"]
    value["statuses"] = [{"id": "wamid.outbound", "status": "delivered"}]
    assert post(c, data).json()["accepted"] == 0
    assert app.state.whatsapp.process_one() is None
    assert c.get("/v1/whatsapp/outbox", headers=h).json() == []


def test_dead_letter_retry_is_audited_and_bounded_by_eligibility(wa_setup):
    app, c, h, _, _, clock = wa_setup
    wa = app.state.whatsapp
    post(c, payload())
    with patch.object(wa.agent, "turn", side_effect=RuntimeError("worker stopped")):
        for _ in range(MAX_ATTEMPTS):
            wa.process_one()
            clock.time += 301
    item = c.get("/v1/whatsapp/inbox", headers=h).json()[0]
    assert c.post(f"/v1/whatsapp/inbox/{item['id']}/retry", headers=h).status_code == 200
    assert wa.process_one()["state"] == "completed"
    post(c, payload(mid="old-event", timestamp="1"))
    item = c.get("/v1/whatsapp/inbox", headers=h).json()[0]
    assert c.post(f"/v1/whatsapp/inbox/{item['id']}/retry", headers=h).status_code == 409


def test_per_conversation_order_survives_worker_claim_and_expiry(wa_setup):
    app, c, h, _, _, clock = wa_setup
    wa = app.state.whatsapp
    post(c, payload(mid="first"))
    post(c, payload(mid="second"))
    first = wa.claim()
    assert first["provider_message_id"] == "first"
    assert wa.claim() is None
    clock.time += LEASE_SECONDS + 1
    recovered = wa.claim()
    assert recovered["id"] == first["id"]


def test_atomic_batch_rejects_invalid_tail_without_partial_acceptance(wa_setup):
    app, c, h, _, _, _ = wa_setup
    data = payload()
    data["entry"][0]["changes"][0]["value"]["messages"].append({"id": "invalid"})
    assert post(c, data).status_code == 422
    assert c.get("/v1/whatsapp/inbox", headers=h).json() == []
