CREATE UNIQUE INDEX IF NOT EXISTS media_uploads_tenant_id ON media_uploads(merchant_id,id);
CREATE TABLE IF NOT EXISTS media_sources(
 merchant_id TEXT NOT NULL, inbox_id TEXT NOT NULL UNIQUE,
 media_id TEXT NOT NULL, provider_media_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
 FOREIGN KEY(merchant_id,inbox_id) REFERENCES whatsapp_inbox(merchant_id,id),
 FOREIGN KEY(merchant_id,media_id) REFERENCES media_uploads(merchant_id,id));
INSERT OR IGNORE INTO schema_versions VALUES(6);
