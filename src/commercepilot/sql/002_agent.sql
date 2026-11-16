CREATE TABLE IF NOT EXISTS business_profiles(
 merchant_id TEXT PRIMARY KEY REFERENCES merchants(id), body TEXT NOT NULL,
 updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 created_at TEXT NOT NULL, UNIQUE(merchant_id,id));
CREATE TABLE IF NOT EXISTS agent_runs(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 idempotency_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('planning','completed','clarification','blocked','failed')),
 tool TEXT, arguments TEXT, result TEXT, created_at TEXT NOT NULL,
 UNIQUE(merchant_id,conversation_id,idempotency_key), UNIQUE(merchant_id,id),
 FOREIGN KEY(merchant_id,conversation_id) REFERENCES conversations(merchant_id,id));
CREATE TABLE IF NOT EXISTS messages(
 id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT NOT NULL,
 conversation_id TEXT NOT NULL, run_id TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')), body TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(merchant_id,conversation_id) REFERENCES conversations(merchant_id,id),
 FOREIGN KEY(merchant_id,run_id) REFERENCES agent_runs(merchant_id,id));
CREATE TABLE IF NOT EXISTS expenses(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 run_id TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK(amount_minor>=0),
 currency TEXT NOT NULL, body TEXT NOT NULL, recorded_at TEXT NOT NULL,
 UNIQUE(merchant_id,run_id),
 FOREIGN KEY(merchant_id,run_id) REFERENCES agent_runs(merchant_id,id));
CREATE INDEX IF NOT EXISTS messages_tenant_conversation ON messages(merchant_id,conversation_id,id);
INSERT OR IGNORE INTO schema_versions VALUES(2);
