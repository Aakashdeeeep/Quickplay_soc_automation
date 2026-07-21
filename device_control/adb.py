"""
Control for Android-based devices (Fire TV, Android TV / Google TV boxes,
Chromecast with Google TV) via wireless ADB.

Two distinct pairing paths, confirmed against real hardware:
- USB-based `adb tcpip 5555`: fixes ADB on port 5555 over WiFi. This is
  what ADB_PORT (the default below) assumes.
- On-device "Wireless debugging" (Developer Options, no USB/computer
  needed): uses `adb pair <ip>:<pairing_port> <code>` then
  `adb connect <ip>:<port>`, where <port> is a RANDOM port shown on that
  device's screen, not 5555. Confirmed on a real Chromecast — its ADB
  port was neither 5555 nor discoverable by scanning; only visible via
  the pairing screen. That port is stored per-device (devices.adb_port),
  same reasoning as Roku's per-device app ID.

Either way, once paired ADB remembers the device as authorized
indefinitely (until factory reset or the device revokes it), so
`adb devices` reporting "device" (not "unauthorized") is what we key off
of for status.
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


def _serial(ip, port=None):
    return f"{ip}:{port or ADB_PORT}"


def get_device_state(ip, port=None):
    """Return one of: 'device' (authorized, ready), 'unauthorized'
    (pairing prompt/code not yet accepted), 'offline' (adb knows it but
    can't reach it), or 'not_connected' (no adb session established yet)."""
    serial = _serial(ip, port)
    _, stdout, _ = _run(["devices"])
    for line in stdout.splitlines()[1:]:  # skip "List of devices attached" header
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] == serial:
            return parts[1]  # "device", "unauthorized", "offline", etc.
    return "not_connected"


def ensure_connected(ip, port=None):
    """Attempt `adb connect` if not already tracked, then report state.
    Safe to call repeatedly — adb connect is idempotent.

    Only handles the `connect` half — a device paired via the on-device
    Wireless Debugging flow needs `adb pair` done first (interactively,
    since it needs a fresh code off the device's screen); this can't do
    that part for you."""
    state = get_device_state(ip, port)
    if state == "device":
        return state

    returncode, stdout, stderr = _run(["connect", _serial(ip, port)], timeout=5)
    if returncode is None:
        return "offline"  # timed out reaching the device

    return get_device_state(ip, port)


def launch_content(ip, package_name, deep_link_url=None, port=None):
    """Launch an app, optionally deep-linking to a specific content URL.

    Returns (True, message) on success, (False, message) with a specific
    reason (offline / unauthorized / etc.) on failure.
    """
    state = ensure_connected(ip, port)

    if state == "unauthorized":
        return False, (
            f"Device at {ip} is not authorized yet — accept the 'Allow debugging' "
            "prompt (or pair it, if it uses Wireless Debugging) on the device, then try again."
        )
    if state in ("offline", "not_connected"):
        return False, f"Could not reach ADB device at {ip} — device may be off or unreachable."

    serial = _serial(ip, port)

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


def list_installed_packages(ip, port=None):
    """Real installed-app data via `pm list packages` — used to power the
    dashboard's app selector. Returns a set of package names, or None if
    the device isn't authorized/reachable (caller should fall back to the
    content catalog's assigned platform in that case)."""
    state = get_device_state(ip, port)
    if state != "device":
        return None

    returncode, stdout, _ = _run(["-s", _serial(ip, port), "shell", "pm", "list", "packages"])
    if returncode != 0:
        return None

    packages = set()
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.add(line[len("package:"):])
    return packages


def get_model(ip, port=None):
    """Query device model string — used to distinguish Fire TV vs Xiaomi
    Mi TV vs Chromecast w/ Google TV during scan/status. Returns None if
    the device isn't authorized/reachable."""
    state = get_device_state(ip, port)
    if state != "device":
        return None

    returncode, stdout, _ = _run(
        ["-s", _serial(ip, port), "shell", "getprop", "ro.product.model"]
    )
    if returncode == 0 and stdout:
        return stdout
    return None
