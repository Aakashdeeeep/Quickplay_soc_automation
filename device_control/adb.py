"""
Control for Android-based devices (Fire TV, Android TV / Google TV boxes,
Chromecast with Google TV) via wireless ADB.

Pairing is one-time per device: `adb connect <ip>:5555` then the operator
accepts the "Allow debugging" prompt on-screen via remote. After that ADB
remembers the device as authorized indefinitely (until factory reset or the
device revokes it), so `adb devices` reporting "device" (not "unauthorized")
is what we key off of for status.
"""

import subprocess

from config import ADB_PORT, ADB_COMMAND_TIMEOUT


class AdbError(Exception):
    pass


def _run(args, timeout=ADB_COMMAND_TIMEOUT):
    """Run an adb command, return (returncode, stdout, stderr).
    Never raises on non-zero exit — callers interpret the result."""
    try:
        result = subprocess.run(
            ["adb"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        raise AdbError("adb executable not found — is Android platform-tools on PATH?")
    except subprocess.TimeoutExpired:
        return None, "", "adb command timed out"


def _serial(ip):
    return f"{ip}:{ADB_PORT}"


def get_device_state(ip):
    """Return one of: 'device' (authorized, ready), 'unauthorized'
    (pairing prompt not yet accepted), 'offline' (adb knows it but can't
    reach it), or 'not_connected' (no adb session established yet)."""
    serial = _serial(ip)
    _, stdout, _ = _run(["devices"])
    for line in stdout.splitlines()[1:]:  # skip "List of devices attached" header
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] == serial:
            return parts[1]  # "device", "unauthorized", "offline", etc.
    return "not_connected"


def ensure_connected(ip):
    """Attempt `adb connect` if not already tracked, then report state.
    Safe to call repeatedly — adb connect is idempotent."""
    state = get_device_state(ip)
    if state == "device":
        return state

    returncode, stdout, stderr = _run(["connect", _serial(ip)], timeout=5)
    if returncode is None:
        return "offline"  # timed out reaching the device

    return get_device_state(ip)


def launch_content(ip, package_name, deep_link_url=None):
    """Launch an app, optionally deep-linking to a specific content URL.

    Returns (True, message) on success, (False, message) with a specific
    reason (offline / unauthorized / etc.) on failure.
    """
    state = ensure_connected(ip)

    if state == "unauthorized":
        return False, (
            f"Device at {ip} is not authorized yet — accept the 'Allow debugging' "
            "prompt on the device screen, then try again."
        )
    if state in ("offline", "not_connected"):
        return False, f"Could not reach ADB device at {ip} — device may be off or unreachable."

    serial = _serial(ip)

    if deep_link_url:
        args = [
            "-s", serial, "shell", "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", deep_link_url,
            package_name,
        ]
    else:
        args = [
            "-s", serial, "shell", "monkey",
            "-p", package_name,
            "-c", "android.intent.category.LAUNCHER", "1",
        ]

    returncode, stdout, stderr = _run(args)

    if returncode is None:
        return False, f"adb command to {ip} timed out."
    if returncode != 0:
        return False, f"adb launch failed on {ip}: {stderr or stdout}"

    return True, f"Launched {package_name} on {ip}."


def list_installed_packages(ip):
    """Real installed-app data via `pm list packages` — used to power the
    dashboard's app selector. Returns a set of package names, or None if
    the device isn't authorized/reachable (caller should fall back to the
    content catalog's assigned platform in that case)."""
    state = get_device_state(ip)
    if state != "device":
        return None

    returncode, stdout, _ = _run(["-s", _serial(ip), "shell", "pm", "list", "packages"])
    if returncode != 0:
        return None

    packages = set()
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.add(line[len("package:"):])
    return packages


def get_model(ip):
    """Query device model string — used to distinguish Fire TV vs Xiaomi
    Mi TV vs Chromecast w/ Google TV during scan/status. Returns None if
    the device isn't authorized/reachable."""
    state = get_device_state(ip)
    if state != "device":
        return None

    returncode, stdout, _ = _run(
        ["-s", _serial(ip), "shell", "getprop", "ro.product.model"]
    )
    if returncode == 0 and stdout:
        return stdout
    return None
