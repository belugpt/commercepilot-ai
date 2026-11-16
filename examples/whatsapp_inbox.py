"""Exercise signed intake, actual local agent work and draft output without network."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from commercepilot.agent import Agent
from commercepilot.database import Database
from commercepilot.domain import Action, PolicyInput
from commercepilot.planners import CommandPlanner
from commercepilot.services import Services
from commercepilot.whatsapp import WhatsApp


def main():
    with TemporaryDirectory() as directory:
        services = Services(Database(str(Path(directory) / "demo.db")))
        merchant, _ = services.provision("Demo")
        services.policy(merchant, PolicyInput(enabled=True, actions=frozenset({Action.PROFILE}), expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        wa = WhatsApp(services, Agent(services, CommandPlanner()), app_secret="local-fixture-only")
        wa.bind(merchant, "111", "222", "phone:2348012345678")
        profile = {"business_name": "Demo", "sector": "clothing", "currency": "NGN", "timezone": "Africa/Lagos", "capabilities": ["catalogue", "content", "economics"]}
        message = {"from": "2348012345678", "id": "wamid.local-demo", "timestamp": str(int(time.time())), "type": "text", "text": {"body": "/profile " + json.dumps(profile)}}
        payload = {"object": "whatsapp_business_account", "entry": [{"id": "111", "changes": [{"field": "messages", "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "222"}, "messages": [message]}}]}]}
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(b"local-fixture-only", raw, hashlib.sha256).hexdigest()
        print("Intake:", wa.ingest(raw, signature))
        print("Worker:", wa.process_one())
        print("Reply drafts:", json.dumps(wa.list_records(merchant, "outbox"), indent=2))
        print("Replay:", wa.ingest(raw, signature))
        print("No WhatsApp messages were sent.")


if __name__ == "__main__":
    main()
