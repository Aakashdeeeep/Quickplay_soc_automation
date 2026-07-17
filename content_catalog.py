"""
Content assignment catalog: what platform/title/type is supposed to be
showing at a given physical slot. This is independent of the device
registry — it describes an assignment, not which device currently
occupies that position, so a device swap doesn't require re-entering
the content assignment.

slot_id is the join key back to devices.slot_id (models.py).
"""

from db import get_connection


def list_catalog():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM content_catalog ORDER BY slot_id").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_by_slot(slot_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM content_catalog WHERE slot_id = ?", (slot_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_by_slots(slot_ids):
    """Bulk lookup for rendering a device grid without one query per tile."""
    if not slot_ids:
        return {}
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in slot_ids)
        rows = conn.execute(
            f"SELECT * FROM content_catalog WHERE slot_id IN ({placeholders})",
            list(slot_ids),
        ).fetchall()
        return {row["slot_id"]: dict(row) for row in rows}
    finally:
        conn.close()


def upsert_entry(slot_id, tv_id, channel, device_type, platform, content_title,
                  content_type, content_id=None, verified=False, notes=None):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM content_catalog WHERE slot_id = ?", (slot_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE content_catalog
                   SET tv_id = ?, channel = ?, device_type = ?, platform = ?,
                       content_title = ?, content_type = ?, content_id = ?,
                       verified = ?, notes = ?
                   WHERE slot_id = ?""",
                (tv_id, channel, device_type, platform, content_title,
                 content_type, content_id, int(verified), notes, slot_id),
            )
        else:
            conn.execute(
                """INSERT INTO content_catalog
                   (slot_id, tv_id, channel, device_type, platform,
                    content_title, content_type, content_id, verified, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slot_id, tv_id, channel, device_type, platform, content_title,
                 content_type, content_id, int(verified), notes),
            )
        conn.commit()
        return get_by_slot(slot_id)
    finally:
        conn.close()


def delete_entry(slot_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM content_catalog WHERE slot_id = ?", (slot_id,))
        conn.commit()
    finally:
        conn.close()
