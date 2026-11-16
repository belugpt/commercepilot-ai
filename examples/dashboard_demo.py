"""Launch an isolated, temporary local dashboard with labelled sample records."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import uvicorn
from commercepilot.api import create_app
from commercepilot.business import Business, OrderInput
from commercepilot.domain import Action, PolicyInput
from commercepilot.planners import CommandPlanner


def main():
    with TemporaryDirectory(prefix="commercepilot-demo-") as directory:
        app = create_app(str(Path(directory) / "demo.db"), planner=CommandPlanner())
        services = app.state.services
        merchant, token = services.provision("Demo shop · sample data")
        actions = frozenset(a for a in Action if a != Action.REPLY)
        services.policy(merchant, PolicyInput(enabled=True, actions=actions, expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        agent = app.state.agent
        conversation = agent.conversation(merchant)["id"]
        agent.turn(merchant, conversation, "profile", '/profile {"business_name":"Demo shop","sector":"clothing","currency":"NGN","timezone":"Africa/Lagos","capabilities":["catalogue","content","economics"]}')
        agent.turn(merchant, conversation, "product", '/product {"title":"Cotton dress","sku":"DEMO-1","price_minor":450000,"currency":"NGN"}')
        Business(services).ingest(merchant, OrderInput(source_system="demo",source_id="sample-order",revision=1,occurred_at=datetime.now(timezone.utc),currency="NGN",verification_status="merchant_reported",evidence_reference="illustrative demo record",status="fulfilled",payment_status="paid",channel="whatsapp",lines=[{"sku":"DEMO-1","title":"Cotton dress","quantity":2,"unit_price_minor":450000,"cogs_minor":500000}],discounts_minor=0,refunds_minor=0,cash_collected_minor=900000), "order")
        print("Temporary sample workspace: http://127.0.0.1:8001", flush=True)
        print("Access key (expires with this demo database): " + token, flush=True)
        uvicorn.run(app, host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
