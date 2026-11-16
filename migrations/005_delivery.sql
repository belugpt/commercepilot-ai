CREATE UNIQUE INDEX IF NOT EXISTS whatsapp_outbox_tenant_id ON whatsapp_outbox(merchant_id,id);
CREATE TABLE IF NOT EXISTS whatsapp_deliveries(
 outbox_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL,
 phone_number_id TEXT NOT NULL, waba_id TEXT NOT NULL, recipient TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('submitting','accepted','sent','delivered','read','failed','uncertain')),
 provider_message_id TEXT UNIQUE, reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(merchant_id,outbox_id) REFERENCES whatsapp_outbox(merchant_id,id));
CREATE TABLE IF NOT EXISTS whatsapp_status_receipts(
 fingerprint TEXT PRIMARY KEY, waba_id TEXT NOT NULL, phone_number_id TEXT NOT NULL,
 provider_message_id TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL,
 received_at TEXT NOT NULL);
INSERT OR IGNORE INTO schema_versions VALUES(5);
