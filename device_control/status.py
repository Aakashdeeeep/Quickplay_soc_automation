"""
Lightweight online/offline probes for the device grid view.

Deliberately cheap (raw TCP connect, no app-level handshake) so a full
grid of 56 tiles can refresh status without hammering every device with
a launch-equivalent request.
"""

import socket

from config import ROKU_ECP_PORT, ADB_PORT, STATUS_CHECK_TIMEOUT, ADB_DEVICE_TYPES
from device_control import adb as adb_control


def _port_open(ip, port, timeout=STATUS_CHECK_TIMEOUT):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_status(device_type, ip):
    """Return a dict: {'online': bool, 'detail': str}.

    For ADB devices this also surfaces the authorization state, since
    "port open but unauthorized" is a distinct, actionable condition the
    UI should show rather than lumping in with plain offline.
    """
    if not ip:
        return {"online": False, "detail": "No IP on record — needs scan/assign."}

    if device_type == "roku":
        online = _port_open(ip, ROKU_ECP_PORT)
        return {"online": online, "detail": "reachable" if online else "unreachable"}

    if device_type in ADB_DEVICE_TYPES:
        if not _port_open(ip, ADB_PORT):
            return {"online": False, "detail": "unreachable"}
        state = adb_control.get_device_state(ip)
        if state == "device":
            return {"online": True, "detail": "authorized"}
        if state == "unauthorized":
            return {"online": True, "detail": "unauthorized — needs pairing accepted on-device"}
        return {"online": True, "detail": f"port open, adb state: {state}"}

    if device_type == "appletv":
        return {"online": False, "detail": "AppleTV control not yet implemented"}

    return {"online": False, "detail": f"unknown device_type '{device_type}'"}
