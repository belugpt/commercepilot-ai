"""No credentials, no network, temporary data: demonstrate real local tool execution."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta, timezone
from commercepilot.agent import Agent
from commercepilot.database import Database
from commercepilot.domain import Action, PolicyInput
from commercepilot.planners import CommandPlanner
from commercepilot.services import Services


def main():
    with TemporaryDirectory() as directory:
        services = Services(Database(str(Path(directory) / "demo.db")))
        merchant, _ = services.provision("Demo shop")
        services.policy(merchant, PolicyInput(enabled=True, actions=frozenset({Action.PROFILE, Action.CREATE_PRODUCT, Action.CAPTION, Action.EXPENSE}), expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        agent = Agent(services, CommandPlanner())
        conversation = agent.conversation(merchant)["id"]
        messages = [
            '/profile {"business_name":"Demo shop","sector":"clothing","currency":"NGN","timezone":"Africa/Lagos","capabilities":["catalogue","content","economics"]}',
            '/product {"title":"Cotton dress","sku":"DEMO-1","price_minor":450000,"currency":"NGN"}',
        ]
        for index, message in enumerate(messages):
            run = agent.turn(merchant, conversation, str(index), message)
            print(json.dumps(run, indent=2))
        product_id = run["result"]["product"]["id"]
        run = agent.turn(merchant, conversation, "caption", '/caption ' + json.dumps({"product_id": product_id}))
        print(json.dumps(run, indent=2))


if __name__ == "__main__":
    main()
