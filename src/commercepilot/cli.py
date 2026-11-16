"""Operator-only provisioning; no unauthenticated registration endpoint."""
import argparse
import os
from commercepilot.database import Database
from commercepilot.services import Services, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.getenv("COMMERCEPILOT_DB", "commercepilot.db"))
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-merchant")
    create.add_argument("name")
    commands.add_parser("revoke-key")
    bind = commands.add_parser("whatsapp-bind", help="Bind an operator-verified merchant sender")
    bind.add_argument("merchant_id")
    bind.add_argument("waba_id")
    bind.add_argument("phone_number_id")
    bind.add_argument("sender_key", help="phone:<digits> or bsuid:<id>")
    work = commands.add_parser("whatsapp-work", help="Process durable inbox; no WhatsApp sends")
    work.add_argument("--once", action="store_true")
    work.add_argument("--send", action="store_true", help="Drain replies when sender and current merchant grants permit")
    runtime = commands.add_parser("serve", help="Run private dashboard, webhook listener and workers")
    runtime.add_argument("--port", type=int, default=8000)
    runtime.add_argument("--webhook-port", type=int, default=8002)
    secret = commands.add_parser("set-secret", help="Store a setting with Windows user-scoped DPAPI")
    from commercepilot.secrets import ALLOWED
    secret.add_argument("name", choices=sorted(ALLOWED))
    commands.add_parser("doctor", help="Show configuration readiness without exposing secret values")
    subscription = commands.add_parser('whatsapp-subscribe', help='Operator-only WABA subscription/callback renewal')
    subscription.add_argument('waba_id')
    subscription.add_argument('--callback',help='Explicit HTTPS alternate callback; omit to use the app default')
    args = parser.parse_args()
    if args.command == "set-secret":
        import getpass
        from commercepilot.secrets import save_secrets
        save_secrets(os.getenv("COMMERCEPILOT_SECRET_FILE", ".local/secrets.dpapi"), {args.name: getpass.getpass("Value (hidden): ")})
        print("Stored using Windows user-scoped protection.")
        return
    if args.command == "serve":
        from commercepilot.runtime import main as serve
        serve(args.db, args.port, args.webhook_port)
        return
    from commercepilot.secrets import load_environment
    load_environment(os.getenv("COMMERCEPILOT_SECRET_FILE", ".local/secrets.dpapi"))
    if args.command == 'whatsapp-subscribe':
        import json
        from commercepilot.whatsapp_setup import subscribe
        print(json.dumps(subscribe(args.waba_id,args.callback)))
        return
    if args.command == "doctor":
        import json
        required = ["WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_GRAPH_VERSION", "WHATSAPP_PHONE_NUMBER_ID"]
        print(json.dumps({"settings": {key: bool(os.getenv(key)) for key in required}, "sending_enabled": os.getenv("WHATSAPP_SEND_ENABLED", "false") == "true", "planner": os.getenv("COMMERCEPILOT_PLANNER", "offline"), "model_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("COMMERCEPILOT_MODEL")), "live_account_validation": "run separately; configuration is not provider verification"}, indent=2))
        return
    db = Database(args.db)
    if args.command == "create-merchant":
        merchant, token = Services(db).provision(args.name)
        print(f"Merchant: {merchant}\nBearer key (shown once): {token}")
    elif args.command in {"whatsapp-bind", "whatsapp-work"}:
        import json
        import time
        from commercepilot.agent import Agent
        from commercepilot.planners import CommandPlanner, configured_planner
        from commercepilot.whatsapp import WhatsApp
        services = Services(db)
        planner = CommandPlanner() if args.command == "whatsapp-bind" else configured_planner()
        from commercepilot.media import configured_media
        whatsapp = WhatsApp(services, Agent(services, planner), media_loader=configured_media() if args.command == 'whatsapp-work' else None)
        from commercepilot.delivery import Delivery, configured_sender
        delivery = Delivery(services, configured_sender()) if args.command == "whatsapp-work" and args.send else None
        if args.command == "whatsapp-bind":
            print(json.dumps(whatsapp.bind(args.merchant_id, args.waba_id, args.phone_number_id, args.sender_key)))
        else:
            try:
                while True:
                    result = whatsapp.process_one()
                    if result:
                        print(json.dumps(result), flush=True)
                    sent = delivery.process_one() if delivery else None
                    if sent:
                        print(json.dumps(sent), flush=True)
                    if args.once:
                        break
                    if result is None:
                        time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        import getpass
        token = getpass.getpass("Key to revoke: ")
        with db.connect() as c:
            row = c.execute("SELECT merchant_id FROM api_keys WHERE digest=?", (digest(token),)).fetchone()
            if not row:
                parser.error("key not found")
            c.execute("UPDATE api_keys SET revoked=1 WHERE digest=?", (digest(token),))
            Services.audit(c, row["merchant_id"], "credential.revoked", "api_key")
        print("Key revoked")


if __name__ == "__main__":
    main()
