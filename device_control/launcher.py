"""
Single dispatch point for launching content on a device, regardless of
underlying protocol. This is the seam that keeps routes/UI code ignorant
of Roku-vs-ADB-vs-(future)AppleTV details — adding a new device_type means
adding a branch here and a control module, nothing else changes.
"""

from config import (
    PLATFORMS,
    DEFAULT_MEDIA_TYPE,
    ADB_DEVICE_TYPES,
    is_ops_restricted_platform,
    resolve_platform_key,
)
from device_control import roku, adb


class LaunchError(Exception):
    pass


def launch_content(device, content_id, platform_label, nav_sequence=None):
    """device: a dict from models.py (must have device_type, last_known_ip,
    network).
    content_id: platform-specific slug/ID, either a preset or operator-pasted.
    Blank/None is valid — it means "just open the app/channel", for
    platforms where we don't have a working deep-link format yet.
    platform_label: free-text platform name — either a PLATFORMS config key
    (e.g. "aha") from manual entry, or a raw content_catalog platform string
    (e.g. "aha Telugu") from the assigned-title dropdown.
    nav_sequence: comma-separated Android keyevent names (e.g.
    "DPAD_LEFT,DPAD_DOWN,DPAD_CENTER") simulating remote-control button
    presses to reach specific content — for platforms where playback needs
    a real backend/DRM handshake a URL can't trigger (confirmed on Unifi
    TV). Takes priority over content_id/deep-linking when present, and
    only applies to ADB-controlled devices.

    Returns (success: bool, message: str) — never raises for expected
    failure modes (offline, unauthorized, restricted, etc.), so routes can
    surface the message directly to the UI.
    """
    device_type = device.get("device_type")
    ip = device.get("last_known_ip")
    network = device.get("network")

    if not ip:
        return False, f"{device.get('slot_id', 'device')} has no known IP — scan/assign first."

    # Hard compliance check — runs before any config lookup so it still
    # blocks even for platforms we haven't wired launch config for yet.
    # Always uses the device's current network from the live registry, not
    # any assumption, since devices get moved between networks over time.
    if is_ops_restricted_platform(platform_label) and network != "OPS":
        return False, (
            f"'{platform_label}' is restricted to the OPS network — "
            f"{device.get('slot_id', 'this device')} is currently on "
            f"{network or 'an unknown'} network."
        )

    platform_key = resolve_platform_key(platform_label)
    platform = PLATFORMS.get(platform_key)
    if not platform:
        return False, f"No launch configuration yet for platform '{platform_label}'."

    if device_type == "roku":
        # Privately-distributed channels (like aha) can have a different
        # app ID per Roku unit, so a per-device value wins over the
        # platform-wide default in config.py.
        app_id = device.get("roku_app_id") or platform.get("roku_app_id")
        return roku.launch_content(ip, app_id, content_id, DEFAULT_MEDIA_TYPE)

    if device_type in ADB_DEVICE_TYPES:
        package = platform.get("android_package")
        if not package:
            return False, f"No Android package configured for platform '{platform_key}'."

        adb_port = device.get("adb_port")  # per-device: Wireless Debugging uses a random port

        if nav_sequence:
            keys = [k.strip() for k in nav_sequence.split(",") if k.strip()]
            return adb.send_key_sequence(ip, package, keys, port=adb_port)

        template = platform.get("deep_link_template")
        # Blank content_id means "just open the app" (e.g. no working
        # deep-link format known yet for this platform) - only build a
        # deep link URL when there's an actual ID to put in it.
        deep_link_url = template.format(content_id=content_id) if template and content_id else None
        return adb.launch_content(ip, package, deep_link_url, port=adb_port)

    if device_type == "appletv":
        return False, "AppleTV control is not implemented yet."

    return False, f"Unsupported device_type '{device_type}'."
