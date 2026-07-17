"""
SQLite connection handling and schema initialization.
"""

import sqlite3
import os

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id TEXT UNIQUE NOT NULL,
    mac_address TEXT,
    device_type TEXT NOT NULL,
    last_known_ip TEXT,
    network TEXT,
    last_seen_timestamp TEXT,
    friendly_name TEXT,
    platform TEXT,
    roku_app_id TEXT
);

CREATE TABLE IF NOT EXISTS content_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id TEXT UNIQUE NOT NULL,
    tv_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    device_type TEXT,
    platform TEXT NOT NULL,
    content_title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT,
    verified INTEGER DEFAULT 0,
    notes TEXT
);
"""


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    """Add columns introduced after the initial schema, for DBs created
    before this field existed. SQLite has no IF NOT EXISTS for ADD COLUMN,
    so check pragma first."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(devices)")}
    if "roku_app_id" not in existing_columns:
        conn.execute("ALTER TABLE devices ADD COLUMN roku_app_id TEXT")
    if "mac_address" not in existing_columns:
        conn.execute("ALTER TABLE devices ADD COLUMN mac_address TEXT")

    # Permanent hardware identity — unique when set, but many rows will
    # have no MAC yet (pending real fleet data), so this must tolerate
    # multiple NULLs. SQLite unique indexes already treat NULL as distinct
    # from other NULLs, so this doesn't need to be a partial index.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_mac_address ON devices(mac_address)")


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {DB_PATH}")
