# Local webhook test

Run from the repository after `pip install -e ".[dev]"`:

```powershell
.venv\Scripts\python examples/local_webhook_test.py
```

This starts a real HTTP server on a randomly assigned 127.0.0.1 port, verifies the subscription challenge, submits signed profile/product messages, processes each through a separate CLI worker process, verifies product persistence and reply drafts, and checks replay/signature rejection. The server shuts down and temporary database is removed afterward. No public listener, tunnel, provider credentials, real recipient phone number or Meta API calls are used. HTTP proxy environment settings are ignored for loopback requests; access logging is disabled to protect the verification token.

This verifies the local transport and worker flow. It does not establish that Meta can reach your backend. Actual inbound WhatsApp messages still require a public HTTPS callback URL, the Meta app secret and verification token configured privately, the messages subscription, and an explicit merchant sender binding. Outbound replies remain drafts until a sending adapter is implemented.

Docker is not installed on the current workstation, so this test runs directly in Python. Container deployment is not required for this local milestone.
