CREATE TABLE IF NOT EXISTS whatsapp_bindings(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 waba_id TEXT NOT NULL, phone_number_id TEXT NOT NULL, sender_key TEXT NOT NULL,
 conversation_id TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
 UNIQUE(waba_id,phone_number_id,sender_key), UNIQUE(merchant_id,id),
 FOREIGN KEY(merchant_id,conversation_id) REFERENCES conversations(merchant_id,id));
CREATE TABLE IF NOT EXISTS whatsapp_inbox(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 merchant_id TEXT NOT NULL, binding_id TEXT NOT NULL,
 provider_message_id TEXT NOT NULL, waba_id TEXT NOT NULL, phone_number_id TEXT NOT NULL,
 payload_hash TEXT NOT NULL, body TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','processing','completed','dead')),
 attempts INTEGER NOT NULL DEFAULT 0, available_at REAL NOT NULL,
 lease_token TEXT, lease_until REAL, run_id TEXT, reason TEXT, created_at TEXT NOT NULL,
 UNIQUE(waba_id,phone_number_id,provider_message_id), UNIQUE(merchant_id,id),
 FOREIGN KEY(merchant_id,binding_id) REFERENCES whatsapp_bindings(merchant_id,id),
 FOREIGN KEY(merchant_id,run_id) REFERENCES agent_runs(merchant_id,id));
CREATE TABLE IF NOT EXISTS whatsapp_conflicts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT NOT NULL,
 inbox_id TEXT NOT NULL, incoming_hash TEXT NOT NULL, occurred_at TEXT NOT NULL,
 UNIQUE(inbox_id,incoming_hash),
 FOREIGN KEY(merchant_id,inbox_id) REFERENCES whatsapp_inbox(merchant_id,id));
CREATE TABLE IF NOT EXISTS whatsapp_outbox(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, inbox_id TEXT NOT NULL UNIQUE,
 run_id TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'draft' CHECK(state='draft'),
 created_at TEXT NOT NULL,
 FOREIGN KEY(merchant_id,inbox_id) REFERENCES whatsapp_inbox(merchant_id,id),
 FOREIGN KEY(merchant_id,run_id) REFERENCES agent_runs(merchant_id,id));
CREATE INDEX IF NOT EXISTS whatsapp_inbox_ready ON whatsapp_inbox(state,available_at,lease_until);
INSERT OR IGNORE INTO schema_versions VALUES(3);
