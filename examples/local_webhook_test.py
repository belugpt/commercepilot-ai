"""Real loopback HTTP + separate CLI worker; temporary data, no Meta requests."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time

import httpx
import uvicorn
from commercepilot.api import create_app
from commercepilot.domain import Action, PolicyInput
from commercepilot.planners import CommandPlanner


def main():
    secret, verify_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with TemporaryDirectory(prefix="commercepilot-local-") as directory:
        db_path = str(Path(directory) / "local.db")
        app = create_app(db_path, planner=CommandPlanner(), whatsapp_secret=secret, whatsapp_verify_token=verify_token)
        services = app.state.services
        merchant, bearer = services.provision("Local test shop")
        services.policy(merchant, PolicyInput(enabled=True,
            actions=frozenset({Action.PROFILE, Action.CREATE_PRODUCT}),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        # Deliberate fixtures: actual Meta account IDs and phone numbers aren't used.
        app.state.whatsapp.bind(merchant, "111", "222", "phone:2348000000000")
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        # Pass an already-bound loopback socket; no race for an available port.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(16)
        port = sock.getsockname()[1]
        thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Local server did not start")
                time.sleep(0.05)
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False) as client:
                assert client.get("/health").status_code == 200
                print("PASS: real HTTP server is reachable on loopback")
                handshake = client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": verify_token, "hub.challenge": "local-challenge"})
                assert handshake.status_code == 200 and handshake.text == "local-challenge"
                print("PASS: webhook subscription challenge")

                def message(mid, body):
                    event = {"object": "whatsapp_business_account", "entry": [{"id": "111", "changes": [{"field": "messages", "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "222"}, "messages": [{"id": mid, "from": "2348000000000", "type": "text", "timestamp": str(int(time.time())), "text": {"body": body}}]}}]}]}
                    raw = json.dumps(event).encode()
                    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
                    return raw, {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}

                def work():
                    env = {**os.environ, "COMMERCEPILOT_PLANNER": "offline"}
                    completed = subprocess.run([sys.executable, "-m", "commercepilot.cli", "--db", db_path, "whatsapp-work", "--once"],
                                               capture_output=True, text=True, timeout=20, env=env)
                    if completed.returncode:
                        raise RuntimeError("Local worker process failed")
                    outcome = json.loads(completed.stdout)
                    assert outcome["state"] == "completed" and outcome["delivery"] == "draft_only"

                profile = {"business_name": "Local test shop", "sector": "clothing", "currency": "NGN", "timezone": "Africa/Lagos", "capabilities": ["catalogue", "content", "economics"]}
                raw, headers = message("local-onboarding", "/profile " + json.dumps(profile))
                assert client.post("/webhooks/whatsapp", content=raw, headers=headers).json()["accepted"] == 1
                work()
                print("PASS: signed onboarding processed by a separate worker process")

                product = {"title": "Local test dress", "sku": "LOCAL-001", "currency": "NGN", "price_minor": 450000}
                raw, headers = message("local-product", "/product " + json.dumps(product))
                assert client.post("/webhooks/whatsapp", content=raw, headers=headers).json()["accepted"] == 1
                work()
                print("PASS: signed product creation processed")
                assert client.post("/webhooks/whatsapp", content=raw, headers=headers).json()["duplicates"] == 1
                assert client.post("/webhooks/whatsapp", content=raw + b" ", headers=headers).status_code == 401
                print("PASS: duplicate rejected and altered-body signature denied")

                auth = {"Authorization": f"Bearer {bearer}"}
                inbox = client.get("/v1/whatsapp/inbox", headers=auth).json()
                outbox = client.get("/v1/whatsapp/outbox", headers=auth).json()
                assert len(inbox) == 2 and all(x["state"] == "completed" for x in inbox)
                assert len(outbox) == 2 and all(x["state"] == "draft" for x in outbox)
                run = client.get("/v1/agent/runs/" + inbox[0]["run_id"], headers=auth).json()
                assert run["state"] == "completed"
                pid = run["result"]["product"]["id"]
                stored = client.get("/v1/products/" + pid, headers=auth).json()
                assert stored["sku"] == "LOCAL-001"
                print("PASS: product read-back, persisted results and two reply drafts")
                print("LOCAL TEST PASSED: no public endpoint, no Meta requests, no WhatsApp sends.")
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
            if thread.is_alive():
                raise RuntimeError("Local server did not stop cleanly")


if __name__ == "__main__":
    main()
