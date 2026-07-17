"""
Single dispatch point for launching content on a device, regardless of
underlying protocol. This is the seam that keeps routes/UI code ignorant
of Roku-vs-ADB-vs-(future)AppleTV details — adding a new device_type means
adding a branch here and a control module, nothing else changes.
"""

from config import PLATFORMS, DEFAULT_MEDIA_TYPE
from device_control import roku, adb


class LaunchError(Exception):
    pass


def launch_content(device, content_id, platform_key):
    """device: a dict from models.py (must have device_type, last_known_ip).
    content_id: platform-specific slug/ID, either a preset or operator-pasted.
    platform_key: which OTT platform config to use (e.g. "aha").

    Returns (success: bool, message: str) — never raises for expected
    failure modes (offline, unauthorized, etc.), so routes can surface the
    message directly to the UI.
    """
    device_type = device.get("device_type")
    ip = device.get("last_known_ip")

    if not ip:
        return False, f"{device.get('slot_id', 'device')} has no known IP — scan/assign first."

    platform = PLATFORMS.get(platform_key)
    if not platform:
        return False, f"Unknown platform '{platform_key}'."

    if device_type == "roku":
        # Privately-distributed channels (like aha) can have a different
        # app ID per Roku unit, so a per-device value wins over the
        # platform-wide default in config.py.
        app_id = device.get("roku_app_id") or platform.get("roku_app_id")
        return roku.launch_content(ip, app_id, content_id, DEFAULT_MEDIA_TYPE)

    if device_type in ("firetv", "androidtv", "chromecast-gtv"):
        package = platform.get("android_package")
        if not package:
            return False, f"No Android package configured for platform '{platform_key}'."
        template = platform.get("deep_link_template")
        deep_link_url = template.format(content_id=content_id) if template else None
        return adb.launch_content(ip, package, deep_link_url)

    if device_type == "appletv":
        return False, "AppleTV control is not implemented yet."

    return False, f"Unsupported device_type '{device_type}'."
