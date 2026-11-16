# User stories and current acceptance

- As a merchant, I can save business context once and reuse it across messages/restarts. Implemented and tested through the local agent API; WhatsApp onboarding is pending.
- As a merchant, I can create catalogue records and request factual caption drafts within grants. Implemented and tested; media extraction and social publication are pending.
- As a merchant, I can record expenses with evidence and see missing costs in calculations. Implemented for explicitly supplied records/aggregates; source reconciliation is pending.
- As an owner, I can revoke automation and inspect or cancel abandoned agent runs. Implemented with checks after planning; cancelling a completed effect is not supported.
- As a merchant, my objects, conversations and runs are hidden from other tenants. Tested at service/API and composite relationship boundaries; production PostgreSQL row security is pending.
- As a contributor, I can add planners/adapters without granting them authority. Typed ports, validation and extension guide are implemented; plugins remain trusted host code, not a sandbox.
- As a merchant, I can connect WhatsApp/commerce/social accounts, schedule approved workflows, receive reconciled daily reports and manage everything through a dashboard. Remaining MVP work, subject to account access and production infrastructure.
