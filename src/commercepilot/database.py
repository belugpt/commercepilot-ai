"""Local transactional storage. Production PostgreSQL/RLS is a separate gate."""
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS merchants(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS api_keys(
 digest TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 role TEXT NOT NULL CHECK(role IN ('owner','staff')), revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS products(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 sku TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(merchant_id,sku), UNIQUE(merchant_id,id));
CREATE TABLE IF NOT EXISTS policies(
 merchant_id TEXT PRIMARY KEY REFERENCES merchants(id), version INTEGER NOT NULL,
 body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(
 id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 idempotency_key TEXT NOT NULL, payload_hash TEXT NOT NULL, body TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','running','succeeded','blocked','uncertain','failed')),
 evidence TEXT, created_at TEXT NOT NULL,
 UNIQUE(merchant_id,idempotency_key), UNIQUE(merchant_id,id));
CREATE TABLE IF NOT EXISTS audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT NOT NULL REFERENCES merchants(id),
 event TEXT NOT NULL, object_id TEXT NOT NULL, occurred_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exceptions(
 task_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, reason TEXT NOT NULL,
 FOREIGN KEY(merchant_id,task_id) REFERENCES tasks(merchant_id,id));
INSERT OR IGNORE INTO schema_versions VALUES(1);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
