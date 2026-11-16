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
    args = parser.parse_args()
    db = Database(args.db)
    if args.command == "create-merchant":
        merchant, token = Services(db).provision(args.name)
        print(f"Merchant: {merchant}\nBearer key (shown once): {token}")
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
