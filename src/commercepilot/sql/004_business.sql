CREATE TABLE IF NOT EXISTS order_events(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 source_system TEXT NOT NULL, source_id TEXT NOT NULL, revision INTEGER NOT NULL,
 payload_hash TEXT NOT NULL, body TEXT NOT NULL, occurred_at TEXT NOT NULL,
 recorded_at TEXT NOT NULL, currency TEXT NOT NULL,
 UNIQUE(merchant_id,source_system,source_id,revision));
CREATE INDEX IF NOT EXISTS order_events_tenant ON order_events(merchant_id,currency,source_system,source_id,revision);
CREATE TABLE IF NOT EXISTS financial_events(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 source_system TEXT NOT NULL, source_id TEXT NOT NULL, revision INTEGER NOT NULL,
 payload_hash TEXT NOT NULL, body TEXT NOT NULL, occurred_at TEXT NOT NULL,
 recorded_at TEXT NOT NULL, currency TEXT NOT NULL,
 UNIQUE(merchant_id,source_system,source_id,revision));
CREATE TABLE IF NOT EXISTS data_quality_issues(
 id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 kind TEXT NOT NULL, source_reference TEXT NOT NULL, details TEXT NOT NULL,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS expense_coverage(
 merchant_id TEXT NOT NULL REFERENCES merchants(id), day TEXT NOT NULL,
 currency TEXT NOT NULL, complete INTEGER NOT NULL, declared_at TEXT NOT NULL,
 PRIMARY KEY(merchant_id,day,currency));
CREATE TABLE IF NOT EXISTS business_plans(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 title TEXT NOT NULL, body TEXT NOT NULL, payload_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('draft','approved')),
 created_at TEXT NOT NULL, approved_at TEXT, UNIQUE(merchant_id,id));
CREATE TABLE IF NOT EXISTS media_uploads(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 content_hash TEXT NOT NULL, mime_type TEXT NOT NULL, byte_length INTEGER NOT NULL,
 body BLOB NOT NULL, state TEXT NOT NULL DEFAULT 'quarantined' CHECK(state='quarantined'),
 created_at TEXT NOT NULL, UNIQUE(merchant_id,content_hash));
INSERT OR IGNORE INTO schema_versions VALUES(4);
