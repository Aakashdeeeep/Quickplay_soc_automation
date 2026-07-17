"""
Device registry data access.

slot_id is the permanent label (e.g. "TV1-01"); everything else about a
device (IP, network) can change over time as devices get physically moved,
so those fields get overwritten in place rather than versioned.
"""

from datetime import datetime, timezone

from db import get_connection


def _row_to_dict(row):
    return dict(row) if row else None


def list_devices(network=None):
    conn = get_connection()
    try:
        if network:
            rows = conn.execute(
                "SELECT * FROM devices WHERE network = ? ORDER BY slot_id",
                (network,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM devices ORDER BY slot_id").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_device_by_slot(slot_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM devices WHERE slot_id = ?", (slot_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_device_by_id(device_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM devices WHERE id = ?", (device_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def upsert_device(slot_id, device_type, last_known_ip, network,
                   friendly_name=None, platform=None, roku_app_id=None,
                   touch_last_seen=True):
    """Create or update a device by slot_id. Used by manual seeding today
    and by the scan/assign flow later.

    roku_app_id is per-device: privately-distributed Roku channels (like
    aha) can be assigned a different app ID on each Roku unit, so this
    can't live in the global platform config."""
    conn = get_connection()
    try:
        last_seen = datetime.now(timezone.utc).isoformat() if touch_last_seen else None
        existing = conn.execute(
            "SELECT id FROM devices WHERE slot_id = ?", (slot_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE devices
                   SET device_type = ?, last_known_ip = ?, network = ?,
                       friendly_name = COALESCE(?, friendly_name),
                       platform = COALESCE(?, platform),
                       roku_app_id = COALESCE(?, roku_app_id),
                       last_seen_timestamp = COALESCE(?, last_seen_timestamp)
                   WHERE slot_id = ?""",
                (device_type, last_known_ip, network, friendly_name, platform,
                 roku_app_id, last_seen, slot_id),
            )
        else:
            conn.execute(
                """INSERT INTO devices
                   (slot_id, device_type, last_known_ip, network,
                    friendly_name, platform, roku_app_id, last_seen_timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (slot_id, device_type, last_known_ip, network,
                 friendly_name, platform, roku_app_id, last_seen),
            )
        conn.commit()
        return get_device_by_slot(slot_id)
    finally:
        conn.close()


def touch_last_seen(slot_id):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE devices SET last_seen_timestamp = ? WHERE slot_id = ?",
            (datetime.now(timezone.utc).isoformat(), slot_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_device(slot_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM devices WHERE slot_id = ?", (slot_id,))
        conn.commit()
    finally:
        conn.close()
