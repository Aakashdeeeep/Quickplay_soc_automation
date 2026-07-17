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
    device_type TEXT NOT NULL,
    last_known_ip TEXT,
    network TEXT,
    last_seen_timestamp TEXT,
    friendly_name TEXT,
    platform TEXT,
    roku_app_id TEXT
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
