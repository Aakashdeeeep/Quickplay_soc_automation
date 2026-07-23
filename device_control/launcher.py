"""
Single dispatch point for launching content on a device, regardless of
underlying protocol. This is the seam that keeps routes/UI code ignorant
of Roku-vs-ADB-vs-(future)AppleTV details — adding a new device_type means
adding a branch here and a control module, nothing else changes.
"""

import random

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


DEFAULT_SEEK_MAX_PRESSES = 10
DEFAULT_WAIT_TEXT_TIMEOUT = 12


def _parse_nav_sequence(nav_sequence):
    """Parse a nav_sequence string into a list of step dicts for
    device_control.adb.send_key_sequence(). Comma-separated tokens, each
    one of:
      "KEY"              — press once
      "KEY*N"            — press N times
      "KEY*MIN-MAX"      — press a random number of times in that
                            inclusive range each run (e.g. landing on a
                            different item in a row, like a random movie,
                            instead of always the same one)
      "KEY?text1|text2"  — press KEY (up to DEFAULT_SEEK_MAX_PRESSES times)
                            until the focused UI element's text matches
                            one of text1/text2 — verified navigation that
                            self-corrects if the app's layout has shifted,
                            instead of trusting a fixed press-count that
                            can silently land on the wrong row
      "KEY?text1|text2:N"    — same, with an explicit max press count
      "KEY?text1|text2:N:S" — same, but press `key` S times with NO check
                            first ("skip"), then verify for up to N more.
                            Each check costs a couple seconds (uiautomator
                            dump is slow on-device no matter how it's
                            called) — skipping presses already known to be
                            needed (e.g. "Free" is reliably ~5 DOWN presses
                            away) keeps most of the speed of blind
                            pressing while still verifying the landing.
      "WAIT:text"            — block (up to DEFAULT_WAIT_TEXT_TIMEOUT
                            seconds) until `text` appears anywhere on
                            screen before continuing to the next step.
                            For apps whose splash/loading screen keeps the
                            UI non-navigable well after the app's activity
                            already has window focus (confirmed on CH3,
                            Gotham Sports: window focus lands in ~1-2s but
                            the splash animation blocks real navigation
                            for several seconds longer) — put this first
                            so blind presses don't land on whatever was
                            still in the foreground before the app
                            finished loading.
      "WAIT:text:N"          — same, with an explicit timeout of N seconds
    """
    steps = []
    for token in nav_sequence.split(","):
        token = token.strip()
        if not token:
            continue

        if token.startswith("WAIT:"):
            rest = token[len("WAIT:"):]
            parts = rest.split(":")
            text = parts[0]
            timeout = int(parts[1].strip()) if len(parts) > 1 else DEFAULT_WAIT_TEXT_TIMEOUT
            steps.append({"type": "wait_text", "text": text, "timeout": timeout})
        elif "?" in token:
            key, rest = token.split("?", 1)
            key = key.strip()
            parts = rest.split(":")
            targets_part = parts[0]
            max_presses = int(parts[1].strip()) if len(parts) > 1 else DEFAULT_SEEK_MAX_PRESSES
            skip = int(parts[2].strip()) if len(parts) > 2 else 0
            targets = [t.strip() for t in targets_part.split("|") if t.strip()]
            steps.append({"type": "seek", "key": key, "targets": targets, "max": max_presses, "skip": skip})
        elif "*" in token:
            key, count_spec = token.split("*", 1)
            key = key.strip()
            count_spec = count_spec.strip()
            if "-" in count_spec:
                lo, hi = count_spec.split("-", 1)
                count = random.randint(int(lo), int(hi))
            else:
                count = int(count_spec)
            steps.append({"type": "press", "key": key, "count": count})
        else:
            steps.append({"type": "press", "key": token, "count": 1})
    return steps


def launch_content(device, content_id, platform_label, nav_sequence=None):
    """device: a dict from models.py (must have device_type, last_known_ip,
    network).
    content_id: platform-specific slug/ID, either a preset or operator-pasted.
    Blank/None is valid — it means "just open the app/channel", for
    platforms where we don't have a working deep-link format yet.
    platform_label: free-text platform name — either a PLATFORMS config key
    (e.g. "aha") from manual entry, or a raw content_catalog platform string
    (e.g. "aha Telugu") from the assigned-title dropdown.
    nav_sequence: comma-separated navigation tokens (see _parse_nav_sequence
    for the grammar) simulating remote-control button presses to reach
    specific content — for platforms where playback needs a real backend/
    DRM handshake a URL can't trigger (confirmed on Unifi TV). Supports
    verified "seek" tokens that check the actually-focused UI element
    before continuing, so navigation self-corrects instead of trusting a
    fixed press-count that can drift when the app's layout shifts. Takes
    priority over content_id/deep-linking when present, and only applies
    to ADB-controlled devices.

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
            steps = _parse_nav_sequence(nav_sequence)
            return adb.send_key_sequence(ip, package, steps, port=adb_port)

        template = platform.get("deep_link_template")
        # Blank content_id means "just open the app" (e.g. no working
        # deep-link format known yet for this platform) - only build a
        # deep link URL when there's an actual ID to put in it.
        deep_link_url = template.format(content_id=content_id) if template and content_id else None
        return adb.launch_content(ip, package, deep_link_url, port=adb_port)

    if device_type == "appletv":
        return False, "AppleTV control is not implemented yet."

    return False, f"Unsupported device_type '{device_type}'."
