# CommercePilot AI

An MIT-licensed backend for WhatsApp-first merchant operations. Built for developers to extend through typed integration and planner contracts.

**Status: working backend foundation; full MVP and production deployment are still in development.** No WhatsApp, Shopify, Meta, Bumpa or AI credentials are bundled. No external connector is enabled.

## Run locally

Python 3.11+ is required. From this repository:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m commercepilot.cli create-merchant "My shop"
.venv\Scripts\python -m uvicorn commercepilot.api:create_app --factory --host 127.0.0.1
```

The CLI prints a bearer key once. Store it securely; use `Authorization: Bearer <key>` in the interactive API documentation at http://127.0.0.1:8000/docs. The database defaults to commercepilot.db; set COMMERCEPILOT_DB to change it. Revoke keys with `python -m commercepilot.cli revoke-key`. Keep the server on loopback until the production security gates are complete.

```powershell
.venv\Scripts\python -m pytest -q
```

## Implemented

- Tenant identity from hashed, revocable bearer keys; owner/staff authorization boundary.
- Tenant-scoped product creation and retrieval with SKU uniqueness and strict input validation.
- Default-deny, expiring autonomy grants and kill switch.
- Durable task submission, payload-bound idempotency, atomic worker claims, independent verification states, audit and exceptions.
- Exact financial calculations with explicit unknown costs/cash and declared unverified inputs.
- OpenAPI contract and typed integration/planner extension ports.

Publishing, syncing, refunds and deletion are deliberately blocked until their required approval/rule implementations exist. The default application contains no executing adapter. Successful test adapters are fixtures only.

## Build on it

Read [architecture](docs/ARCHITECTURE.md), [extension guide](docs/EXTENDING.md), [API guide](docs/API.md), [database design](docs/DATABASE.md), [integration evidence](docs/INTEGRATIONS.md), [roadmap](docs/ROADMAP.md), [status](IMPLEMENTATION_STATUS.md), [contribution guide](CONTRIBUTING.md) and [security](SECURITY.md). The original [master specification](docs/MASTER_PRODUCT_SPECIFICATION.md) remains authoritative.

Public repository: https://github.com/belugpt/commercepilot-ai.
