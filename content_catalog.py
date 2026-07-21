"""
Content assignment catalog: what platform/title/type is supposed to be
showing at a given physical slot. This is independent of the device
registry — it describes an assignment, not which device currently
occupies that position, so a device swap doesn't require re-entering
the content assignment.

slot_id is the join key back to devices.slot_id (models.py).
"""

import random

from db import get_connection
from config import resolve_platform_key


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
                  content_type, content_id=None, nav_sequence=None, verified=False, notes=None):
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
                       nav_sequence = ?, verified = ?, notes = ?
                   WHERE slot_id = ?""",
                (tv_id, channel, device_type, platform, content_title,
                 content_type, content_id, nav_sequence, int(verified), notes, slot_id),
            )
        else:
            conn.execute(
                """INSERT INTO content_catalog
                   (slot_id, tv_id, channel, device_type, platform,
                    content_title, content_type, content_id, nav_sequence, verified, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slot_id, tv_id, channel, device_type, platform, content_title,
                 content_type, content_id, nav_sequence, int(verified), notes),
            )
        conn.commit()
        return get_by_slot(slot_id)
    finally:
        conn.close()


def list_by_platform_and_type(platform, content_type):
    """All catalog entries (across any slot) matching a platform + content
    type, compared via the same platform-key normalization the launcher
    uses (so "aha Telugu" matches a search for "aha"). A row is only
    eligible if it has a real content_id (a deep-linkable slug) or a
    nav_sequence (a remote-simulation path) — a human title alone isn't a
    safe launchable target."""
    target_key = resolve_platform_key(platform)
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM content_catalog
               WHERE content_type = ? AND (content_id IS NOT NULL OR nav_sequence IS NOT NULL)""",
            (content_type,),
        ).fetchall()
        return [dict(r) for r in rows if resolve_platform_key(r["platform"]) == target_key]
    finally:
        conn.close()


def find_title_for_launch(slot_id, platform, content_type):
    """Resolve what to actually launch for slot_id + chosen app + Live/VOD:
    1. If this slot's own catalog entry matches the chosen platform+type
       (and has a content_id or nav_sequence), use it — deterministic, the
       "assigned" case.
    2. Otherwise, randomly pick a matching entry from anywhere else in the
       catalog for that platform+type — the "no specific title assigned
       here, but we know of one elsewhere" fallback.
    3. If nothing matches at all, return None.

    Returns a dict with an added "source" key ("assigned" or
    "catalog-random"), or None.
    """
    target_key = resolve_platform_key(platform)

    own = get_by_slot(slot_id)
    if (own and (own["content_id"] or own["nav_sequence"]) and own["content_type"] == content_type
            and resolve_platform_key(own["platform"]) == target_key):
        return {**own, "source": "assigned"}

    candidates = list_by_platform_and_type(platform, content_type)
    if not candidates:
        return None
    return {**random.choice(candidates), "source": "catalog-random"}


def delete_entry(slot_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM content_catalog WHERE slot_id = ?", (slot_id,))
        conn.commit()
    finally:
        conn.close()
