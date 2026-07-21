"""
Roku control via ECP (External Control Protocol). No pairing required —
just direct HTTP calls to the device's IP.
"""

import requests

from config import ROKU_ECP_PORT, ROKU_REQUEST_TIMEOUT, DEFAULT_MEDIA_TYPE


class RokuError(Exception):
    pass


def launch_content(ip, app_id, content_id, media_type=DEFAULT_MEDIA_TYPE):
    """Launch a Roku channel, optionally deep-linking to a specific content
    ID. content_id may be blank/None — ECP's /launch endpoint supports
    opening a channel to its own home screen with no contentId at all,
    for cases where we don't have a working deep-link target yet.

    Returns (True, message) on success, (False, message) on failure.
    Raises nothing — callers get a clean status tuple for UI feedback.
    """
    if not app_id:
        return False, "No Roku app ID configured for this platform."

    url = f"http://{ip}:{ROKU_ECP_PORT}/launch/{app_id}"
    params = {"contentId": content_id, "mediaType": media_type} if content_id else {}

    try:
        resp = requests.post(url, params=params, timeout=ROKU_REQUEST_TIMEOUT)
    except requests.exceptions.ConnectTimeout:
        return False, f"Timed out connecting to Roku at {ip} — device may be offline."
    except requests.exceptions.ConnectionError:
        return False, f"Could not reach Roku at {ip} — device may be offline or on a different network."
    except requests.exceptions.RequestException as exc:
        return False, f"Roku request failed: {exc}"

    if resp.status_code == 200:
        label = content_id if content_id else "channel home"
        return True, f"Launched {label} on Roku at {ip}."
    return False, f"Roku at {ip} returned HTTP {resp.status_code}."


def query_device_info(ip):
    """Used by status checks / scan confirmation — cheap way to verify a
    Roku is actually a Roku and is reachable."""
    url = f"http://{ip}:{ROKU_ECP_PORT}/query/device-info"
    try:
        resp = requests.get(url, timeout=ROKU_REQUEST_TIMEOUT)
        return resp.status_code == 200 and "<device-info>" in resp.text
    except requests.exceptions.RequestException:
        return False
