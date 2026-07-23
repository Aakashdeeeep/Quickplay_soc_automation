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
import time
import xml.etree.ElementTree as ET

from config import ADB_PORT, ADB_COMMAND_TIMEOUT

NAV_KEY_DELAY_SECONDS = 0.5
UI_DUMP_PATH = "/sdcard/window_dump.xml"


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


def _wait_for_foreground(serial, package_name, timeout=6, interval=0.5):
    """Poll until `package_name` actually owns window focus. Necessary
    because a fixed sleep before navigating is unreliable — confirmed on a
    real device (CH3) that the app took longer to get window focus at all
    than a flat 1.5s wait, so the first nav presses landed on whatever was
    still in the foreground (the Fire TV launcher) instead of the app.
    Returns True once confirmed, False if it never happened within
    `timeout` (caller proceeds anyway, best-effort). NOTE: window focus
    alone is not sufficient to know the app is actually navigable — see
    _wait_for_ui_text below, which checks for real content."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, stdout, _ = _run(["-s", serial, "shell", "dumpsys", "window", "windows"], timeout=5)
        for line in stdout.splitlines():
            if "mCurrentFocus" in line and package_name in line:
                return True
        time.sleep(interval)
    return False


def _wait_for_ui_text(serial, target_text, timeout=12, interval=1.0):
    """Poll uiautomator dumps until `target_text` appears anywhere on
    screen. Confirmed necessary on a real device (CH3, Gotham Sports/
    com.yesnetwork.yes): the app's activity gets window focus (see
    _wait_for_foreground) within ~1-2s, but its splash animation ("the
    home of...") keeps the real home screen from being navigable for
    several more seconds — window focus alone caused nav presses to be
    silently swallowed or misdirected. This checks for actual rendered
    content instead of guessing how long a splash takes. Returns True
    once seen, False if it never appeared within `timeout` (caller
    proceeds anyway, best-effort)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _run(["-s", serial, "shell", "uiautomator", "dump", UI_DUMP_PATH], timeout=5)
        _, stdout, _ = _run(["-s", serial, "shell", "cat", UI_DUMP_PATH], timeout=5)
        if target_text in stdout:
            return True
        time.sleep(interval)
    return False


def _monkey_launch(serial, package_name):
    """Bring an app to the foreground via `monkey`. Tries the standard
    LAUNCHER category first, then falls back to LEANBACK_LAUNCHER —
    confirmed some Android TV apps (e.g. Univision Now/com.univision.prendetv)
    only declare a LEANBACK_LAUNCHER-category main activity, not LAUNCHER,
    so the plain monkey call fails with no matching activity found."""
    for category in ("android.intent.category.LAUNCHER", "android.intent.category.LEANBACK_LAUNCHER"):
        returncode, stdout, stderr = _run([
            "-s", serial, "shell", "monkey",
            "-p", package_name,
            "-c", category, "1",
        ])
        if returncode == 0:
            return returncode, stdout, stderr
    return returncode, stdout, stderr


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
        returncode, stdout, stderr = _run(args)
    else:
        returncode, stdout, stderr = _monkey_launch(serial, package_name)

    if returncode is None:
        return False, f"adb command to {ip} timed out."
    if returncode != 0:
        return False, f"adb launch failed on {ip}: {stderr or stdout}"

    return True, f"Launched {package_name} on {ip}."


def _press_key(serial, key):
    return _run(["-s", serial, "shell", "input", "keyevent", f"KEYCODE_{key}"])


def _first_text_in_subtree(node):
    """Depth-first search for the first non-empty text/content-desc in a
    node or its descendants. Needed because many TV apps' focused/selected
    node is a plain layout container (empty text of its own) wrapping the
    actual label as a child TextView — confirmed on Unifi TV: the node
    with focused="true" was an empty ViewGroup, with "Free" living on a
    child node several levels down."""
    text = (node.get("text") or "").strip()
    if text:
        return text
    desc = (node.get("content-desc") or "").strip()
    if desc:
        return desc
    for child in node:
        found = _first_text_in_subtree(child)
        if found:
            return found
    return None


def get_focused_element_text(serial):
    """Dump the current UI via `uiautomator dump` and return the label of
    whichever element currently has focus (or, failing that, is marked
    selected), or None if the dump fails or nothing is focused/selected.
    This is how nav_sequence "seek" steps verify they've actually reached
    a target screen/item, instead of trusting a fixed press-count that
    drifts whenever the app's layout changes (confirmed: a promotional row
    above the target row can appear/disappear between sessions, shifting a
    fixed count out from under it)."""
    dump_result = _run(["-s", serial, "shell", "uiautomator", "dump", UI_DUMP_PATH], timeout=10)
    if dump_result[0] != 0:
        return None

    cat_result = _run(["-s", serial, "shell", "cat", UI_DUMP_PATH], timeout=10)
    if cat_result[0] != 0 or not cat_result[1]:
        return None

    xml_text = cat_result[1]
    # uiautomator sometimes prints a "UI hierchary dumped to..." status
    # line before the XML — trim to the actual document.
    start = xml_text.find("<?xml")
    if start > 0:
        xml_text = xml_text[start:]

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    target = None
    for node in root.iter("node"):
        if node.get("focused") == "true":
            target = node
            break
    if target is None:
        for node in root.iter("node"):
            if node.get("selected") == "true":
                target = node
                break
    if target is None:
        return None

    return _first_text_in_subtree(target)


def _seek_focused(serial, key, targets, max_presses, delay, skip=0):
    """Press `key` up to max_presses times, checking the focused element's
    text/content-desc after each press (and once before, in case we're
    already there), stopping as soon as it case-insensitively contains
    any of `targets`. Returns (found: bool, last_seen_text: str|None).

    `skip`: press `key` this many times with NO check first. Each check
    is a `uiautomator dump`, which costs ~2 seconds on-device regardless
    of how it's invoked (confirmed: combining the dump+read into one adb
    call didn't meaningfully change the timing — the dump itself is the
    slow part, not the round-trip). Skipping the presses we already know
    are needed (e.g. "Free" is reliably ~5 DOWN presses away) keeps most
    of the speed of blind pressing while still verifying the landing.
    """
    for _ in range(skip):
        _press_key(serial, key)
        time.sleep(delay)

    last_text = None
    for attempt in range(max_presses + 1):
        current = get_focused_element_text(serial)
        if current is not None:
            last_text = current
            if any(t.lower() in current.lower() for t in targets):
                return True, current
        if attempt == max_presses:
            break
        _press_key(serial, key)
        time.sleep(delay)
    return False, last_text


def send_key_sequence(ip, package_name, steps, port=None, key_delay=NAV_KEY_DELAY_SECONDS):
    """Launch an app plainly, then execute a sequence of remote-control
    navigation steps to reach and play specific content — for platforms
    where playback requires a real backend/DRM handshake that a URL deep
    link can't trigger (confirmed on Unifi TV: its player calls its own
    oauth2/device-register/content-authorize/widevine-license APIs when a
    human selects a channel in the running app; there's no equivalent URL
    shortcut for that).

    steps: list of dicts, each one of:
      {"type": "press", "key": "DPAD_DOWN", "count": 1}
          — press `key` exactly `count` times, no verification.
      {"type": "seek", "key": "DPAD_DOWN", "targets": ["Free"], "max": 10}
          — press `key` up to `max` times, stopping as soon as the
            focused element's text matches one of `targets`. This is what
            makes navigation robust to the app's layout shifting between
            sessions, instead of a fixed count silently landing on the
            wrong row.
    See device_control/launcher.py's _parse_nav_sequence() for the string
    grammar these get built from.

    Returns (True, message) on success, (False, message) on failure.
    Still fragile in the sense that it replays a specific path through the
    app's menu — if a seek step can't find its target at all, it gives up
    after `max` presses and continues anyway (best-effort), so a launch
    can still land on the wrong screen if the app changes more than the
    seek steps account for.

    Always force-stops the app before relaunching it, even if it's already
    running — a recorded sequence assumes a fresh Home/start screen, and if
    the app was left mid-playback from a previous launch, simply bringing
    it to the foreground resumes that same screen instead of resetting it.
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

    _run(["-s", serial, "shell", "am", "force-stop", package_name])
    time.sleep(0.5)  # let the stop actually land before relaunching

    returncode, stdout, stderr = _monkey_launch(serial, package_name)
    if returncode is None:
        return False, f"adb command to {ip} timed out."
    if returncode != 0:
        return False, f"Failed to launch {package_name} on {ip}: {stderr or stdout}"

    _wait_for_foreground(serial, package_name)

    seek_notes = []
    for step in steps:
        if step["type"] == "wait_text":
            if not _wait_for_ui_text(serial, step["text"], timeout=step["timeout"]):
                seek_notes.append(
                    f"never saw {step['text']!r} on screen within {step['timeout']}s "
                    "(app may still have been on its splash screen) — continued anyway"
                )
            continue

        if step["type"] == "seek":
            found, last_seen = _seek_focused(
                serial, step["key"], step["targets"], step["max"], key_delay, skip=step.get("skip", 0)
            )
            if not found:
                seek_notes.append(
                    f"couldn't confirm reaching {step['targets']!r} within {step['max']} presses "
                    f"of {step['key']} (last saw {last_seen!r}) — continued anyway"
                )
            continue

        for _ in range(step["count"]):
            returncode, stdout, stderr = _press_key(serial, step["key"])
            if returncode is None:
                return False, f"adb command to {ip} timed out partway through navigation."
            if returncode != 0:
                return False, f"Navigation key '{step['key']}' failed on {ip}: {stderr or stdout}"
            time.sleep(key_delay)

    message = f"Navigated to content on {ip}."
    if seek_notes:
        message += " Warning: " + "; ".join(seek_notes)
    return True, message


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
