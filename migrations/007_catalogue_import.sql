CREATE TABLE IF NOT EXISTS catalogue_imports(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 payload_hash TEXT NOT NULL, source_origin TEXT NOT NULL, body TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('preview','committed')), created_at TEXT NOT NULL, committed_at TEXT,
 UNIQUE(merchant_id,payload_hash));
CREATE TABLE IF NOT EXISTS catalogue_sources(
 merchant_id TEXT NOT NULL, source_system TEXT NOT NULL, source_id TEXT NOT NULL,
 product_id TEXT NOT NULL, payload_hash TEXT NOT NULL, body TEXT NOT NULL, recorded_at TEXT NOT NULL,
 PRIMARY KEY(merchant_id,source_system,source_id), UNIQUE(merchant_id,product_id),
 FOREIGN KEY(merchant_id,product_id) REFERENCES products(merchant_id,id));
INSERT OR IGNORE INTO schema_versions VALUES(7);
