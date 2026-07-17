"""
Device registry data access.

slot_id is the permanent human-facing label (e.g. "TV1-01"). mac_address is
the permanent hardware identity — the pair (slot_id <-> mac_address) is the
stable mapping. last_known_ip / network / last_seen_timestamp are transient
"live" fields meant to be refreshed by a network scan (see
device_control/mac_lookup.py), not treated as long-term truth, since
devices get physically moved between networks over time. Manual entry via
seed_devices.py remains the stopgap until the scan feature exists.
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


def get_device_by_mac(mac_address):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM devices WHERE mac_address = ?", (mac_address,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def upsert_device(slot_id, device_type, last_known_ip, network,
                   friendly_name=None, platform=None, roku_app_id=None,
                   mac_address=None, touch_last_seen=True):
    """Create or update a device by slot_id. Used by manual seeding today
    and by the scan/assign flow later.

    roku_app_id is per-device: privately-distributed Roku channels (like
    aha) can be assigned a different app ID on each Roku unit, so this
    can't live in the global platform config.

    mac_address is optional here since manual seeding predates having real
    fleet MAC data — once that lands, registration should key off MAC via
    the scan/assign flow rather than this function."""
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
                       mac_address = COALESCE(?, mac_address),
                       last_seen_timestamp = COALESCE(?, last_seen_timestamp)
                   WHERE slot_id = ?""",
                (device_type, last_known_ip, network, friendly_name, platform,
                 roku_app_id, mac_address, last_seen, slot_id),
            )
        else:
            conn.execute(
                """INSERT INTO devices
                   (slot_id, device_type, last_known_ip, network,
                    friendly_name, platform, roku_app_id, mac_address,
                    last_seen_timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slot_id, device_type, last_known_ip, network,
                 friendly_name, platform, roku_app_id, mac_address, last_seen),
            )
        conn.commit()
        return get_device_by_slot(slot_id)
    finally:
        conn.close()


def update_live_location(mac_address, last_known_ip, network):
    """Refresh the transient IP/network/last_seen fields for the device
    identified by its permanent MAC address. Used by the (future) scan
    feature — IP/network are never the source of truth for device identity,
    only where a known device currently happens to be.

    Returns the updated device dict, or None if no registered device has
    this MAC yet (caller should treat that as an "unregistered device
    found" case rather than silently creating a slot)."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT slot_id FROM devices WHERE mac_address = ?", (mac_address,)
        ).fetchone()
        if not existing:
            return None
        conn.execute(
            "UPDATE devices SET last_known_ip = ?, network = ?, last_seen_timestamp = ? WHERE mac_address = ?",
            (last_known_ip, network, datetime.now(timezone.utc).isoformat(), mac_address),
        )
        conn.commit()
        return get_device_by_mac(mac_address)
    finally:
        conn.close()


def clear_live_location(mac_address):
    """Clear IP/network for a device that was previously on a network but
    wasn't found there in the most recent scan of that network. Does NOT
    touch last_seen_timestamp — the device wasn't seen, so that field
    should keep reflecting when it actually last was, not this scan."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE devices SET last_known_ip = NULL, network = NULL WHERE mac_address = ?",
            (mac_address,),
        )
        conn.commit()
        return get_device_by_mac(mac_address)
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
