# ADR 0001: modular backend and explicit provider ports

Accepted 2026-11-16. Source folder had only product/handoff documents and no code to preserve. Choose Python/FastAPI for typed API contracts; separate domain, services, policy, persistence and integration ports. SQLite enables immediate isolated local tests. PostgreSQL and durable workers are production gates rather than untested infrastructure claims.

Consequence: contributors can run the core without provider accounts and add implementations behind stable contracts. Full SaaS identity, production migrations, async scheduling and dashboard remain explicit follow-up milestones. Avoid microservice deployment complexity until operational evidence warrants splitting modules.
