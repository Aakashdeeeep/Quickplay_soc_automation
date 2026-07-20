"""
Central configuration: networks, subnet prefixes, ports, and content presets.

IP-to-device mapping is NOT here — that lives in the SQLite registry (models.py)
because it changes as devices get moved around. This file only holds things
that are structurally stable: which networks exist, which ports mean what,
and known app/content IDs.
"""

import re

# Networks operators can pick from in the UI.
# subnet_prefix is used by the (future) scan feature — fill in SOC/US1/US2
# once confirmed. US1/US2 are two bands (2.4GHz/5GHz) off the same router,
# so they may end up sharing a prefix or needing VLAN-specific handling.
NETWORKS = {
    "OPS": {"label": "OPS", "subnet_prefix": "192.168.208."},
    "SOC": {"label": "SOC", "subnet_prefix": None},
    "US1": {"label": "US1 (2.4GHz)", "subnet_prefix": None},
    "US2": {"label": "US2 (5GHz)", "subnet_prefix": None},
}

DEVICE_TYPES = ["roku", "firetv", "androidtv", "chromecast-gtv", "mi-stick", "appletv"]

# device_types controlled over wireless ADB — Fire TV, Android TV boxes,
# Chromecast w/ Google TV, and Xiaomi Mi TV Stick all confirmed to behave
# identically over ADB. Shared here so launcher.py and status.py can't
# drift out of sync on which types dispatch to the ADB control path.
ADB_DEVICE_TYPES = ("firetv", "androidtv", "chromecast-gtv", "mi-stick")

# Ports used during discovery/status checks.
ROKU_ECP_PORT = 8060
ADB_PORT = 5555

# Per-platform identifiers needed to launch content.
# Roku channels are launched by numeric/string "app ID", Android apps by
# package name. Add more platforms here as they get proven out.
PLATFORMS = {
    "aha": {
        "label": "aha",
        # Roku channel IDs for aha differ per device (privately-distributed
        # channel) — no safe global default. Set per-device via
        # devices.roku_app_id (seed_devices.py --roku-app-id) instead.
        "roku_app_id": None,
        "android_package": "ahaflix.tv",
        "deep_link_template": "https://www.aha.video/movie/{content_id}",
    },
}

# Platforms that must ONLY ever be launched on a device currently on the
# OPS network. Business rule — hard-enforced in device_control/launcher.py
# before any ECP/ADB command is sent, regardless of platform launch config
# completeness. Matched as whole words/phrases against the content's
# platform string, so "aha Telugu" / "Cignal Play" etc. still match.
OPS_RESTRICTED_PLATFORMS = ["aha", "tm", "local now", "tvnz", "plive", "cignal", "upb", "tizen"]

# Some catalog platform strings are regional variants of a platform we do
# have launch config for (e.g. "aha Telugu" -> the "aha" PLATFORMS entry).
# Anything not listed here falls back to its own lowercased/underscored
# name, which will correctly report "no launch config yet" until added.
PLATFORM_KEY_ALIASES = {
    "aha telugu": "aha",
    "aha tamil": "aha",
}


def is_ops_restricted_platform(platform):
    """True if `platform` (a free-text platform/content label) matches
    one of the OPS-only platforms, as a whole word/phrase match."""
    if not platform:
        return False
    p = platform.strip().lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", p) for kw in OPS_RESTRICTED_PLATFORMS)


def resolve_platform_key(platform):
    """Map a free-text platform/content label to a PLATFORMS config key."""
    if not platform:
        return ""
    normalized = platform.strip().lower()
    if normalized in PLATFORM_KEY_ALIASES:
        return PLATFORM_KEY_ALIASES[normalized]
    if normalized.startswith("aha"):
        return "aha"
    return normalized.replace(" ", "_")

# Android package name -> friendly platform name, for mapping real
# `adb shell pm list packages` output to something an operator recognizes.
# Only "aha" is confirmed right now — anything installed that isn't in
# this map is simply not offered as a selectable app (better than showing
# raw package names), and the UI falls back to the content catalog.
PACKAGE_TO_PLATFORM = {
    "ahaflix.tv": "aha",
}

# Preset content titles shown in the launch dropdown, per platform.
# content_id is the slug used both for Roku ECP contentId and the Android
# deep-link URL.
CONTENT_PRESETS = {
    "aha": [
        {"label": "Constable", "content_id": "constable"},
    ],
}

DEFAULT_MEDIA_TYPE = "movie"

# Timeouts (seconds) for network calls to devices.
ROKU_REQUEST_TIMEOUT = 5
ADB_COMMAND_TIMEOUT = 8
STATUS_CHECK_TIMEOUT = 1.5

DB_PATH = "data/wall.db"
