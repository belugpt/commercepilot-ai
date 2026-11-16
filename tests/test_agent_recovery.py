from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from fastapi.testclient import TestClient
from commercepilot.api import create_app
from commercepilot.domain import Action, PolicyInput
from commercepilot.planners import CommandPlanner
from test_agent import PROFILE, PRODUCT, onboard, command


def test_cancel_late_planner_and_continue_conversation(tmp_path):
    entered, release = Event(), Event()
    class SlowPlanner:
        mode = "test"
        def propose(self, message, context):
            entered.set()
            assert release.wait(10)
            return {"tool": "profile_save", "arguments": PROFILE}
    app = create_app(str(tmp_path / "test.db"), planner=SlowPlanner())
    s, agent = app.state.services, app.state.agent
    merchant, _ = s.provision("Test")
    s.policy(merchant, PolicyInput(enabled=True, actions=frozenset(Action), expires_at="2099-01-01T00:00:00Z"))
    conv = agent.conversation(merchant)["id"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(agent.turn, merchant, conv, "one", "setup")
        assert entered.wait(5)
        run = agent.runs(merchant)[0]
        # Duplicate delivery returns current run without starting another planner.
        assert agent.turn(merchant, conv, "one", "setup")["id"] == run["id"]
        assert agent.cancel(merchant, run["id"])["state"] == "failed"
        release.set()
        assert future.result(timeout=10)["result"]["reason"] == "cancelled_by_owner"
    with s.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM business_profiles").fetchone()[0] == 0
    agent.planner = CommandPlanner()
    assert agent.turn(merchant, conv, "two", "/products")["state"] == "clarification"


def test_effect_and_result_rollback_together(tmp_path):
    app = create_app(str(tmp_path / "test.db"), planner=CommandPlanner())
    c, s = TestClient(app), app.state.services
    _, key = s.provision("Test")
    h = {"Authorization": f"Bearer {key}"}
    c.put("/v1/policy", headers=h, json={"enabled": True, "actions": [a.value for a in Action], "expires_at": "2099-01-01T00:00:00Z"})
    conv = c.post("/v1/conversations", headers=h).json()["id"]
    onboard(c, h, conv)
    original = s.audit
    def broken_audit(conn, merchant, event, object_id):
        if event == "product.created":
            raise RuntimeError("simulated storage failure")
        return original(conn, merchant, event, object_id)
    s.audit = broken_audit
    assert command(c, h, conv, "/product", PRODUCT)["state"] == "failed"
    with s.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def test_staff_cannot_start_agent_or_change_profile(tmp_path):
    from commercepilot.services import digest
    app = create_app(str(tmp_path / "test.db"), planner=CommandPlanner())
    c, s = TestClient(app), app.state.services
    _, token = s.provision("staff")
    with s.db.connect() as conn:
        conn.execute("UPDATE api_keys SET role='staff' WHERE digest=?", (digest(token),))
    h = {"Authorization": f"Bearer {token}"}
    assert c.post("/v1/conversations", headers=h).status_code == 403
    assert c.get("/v1/agent/runs", headers=h).status_code == 403


def test_context_and_history_survive_restart(tmp_path):
    path = str(tmp_path / "test.db")
    app = create_app(path, planner=CommandPlanner())
    c, s = TestClient(app), app.state.services
    merchant, token = s.provision("Test")
    h = {"Authorization": f"Bearer {token}"}
    c.put("/v1/policy", headers=h, json={"enabled": True, "actions": [a.value for a in Action], "expires_at": "2099-01-01T00:00:00Z"})
    conv = c.post("/v1/conversations", headers=h).json()["id"]
    onboard(c, h, conv)
    command(c, h, conv, "/product", PRODUCT)
    other = create_app(path, planner=CommandPlanner())
    context = other.state.agent.context(merchant, conv)
    assert context["profile"]["business_name"] == PROFILE["business_name"]
    assert context["products"][0]["sku"] == PRODUCT["sku"]
    assert len(other.state.agent.history(merchant, conv)) == 4


def test_policy_revoked_during_planning_is_rechecked(tmp_path):
    app = create_app(str(tmp_path / "test.db"), planner=CommandPlanner())
    s, agent = app.state.services, app.state.agent
    merchant, _ = s.provision("Test")
    granted = PolicyInput(enabled=True, actions=frozenset(Action), expires_at="2099-01-01T00:00:00Z")
    s.policy(merchant, granted)
    class RevokingPlanner:
        mode = "test"
        def propose(self, message, context):
            s.policy(merchant, granted.model_copy(update={"enabled": False}))
            return {"tool": "profile_save", "arguments": PROFILE}
    agent.planner = RevokingPlanner()
    conv = agent.conversation(merchant)["id"]
    result = agent.turn(merchant, conv, "one", "save profile")
    assert result["state"] == "blocked"
    assert result["result"]["policy_version"] == 2
    with s.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM business_profiles").fetchone()[0] == 0
