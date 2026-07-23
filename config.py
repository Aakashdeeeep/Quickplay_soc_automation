"""
Central configuration: networks, subnet prefixes, ports, and content presets.

IP-to-device mapping is NOT here — that lives in the SQLite registry (models.py)
because it changes as devices get moved around. This file only holds things
that are structurally stable: which networks exist, which ports mean what,
and known app/content IDs.
"""

import re

# Networks operators can pick from in the UI.
# subnet_prefixes drives the scan feature — a list, not a single prefix,
# because a "network" here isn't reliably one clean /24: OPS turned out to
# span both 192.168.208.x and 192.168.209.x (confirmed by a device that
# only showed up once .209 was added — likely one DHCP pool spanning a
# /23, or two scopes on the same broadcast domain, not confirmed which).
# Fill in SOC/Soc_usa/soc_tp_usan once confirmed. Soc_usa/soc_tp_usan are
# two bands (2.4GHz/5GHz) off the same router, so they may end up sharing
# prefixes.
NETWORKS = {
    "OPS": {"label": "OPS", "subnet_prefixes": ["192.168.208.", "192.168.209."]},
    "SOC": {"label": "SOC", "subnet_prefixes": None},
    "Soc_usa": {"label": "Soc_usa (2.4GHz)", "subnet_prefixes": ["192.168.50."]},
    "soc_tp_usan": {"label": "soc_tp_usan (5GHz)", "subnet_prefixes": None},
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
        # Confirmed on a real device (TV1-CH1): /movie/{id} opens the
        # content's detail page but does not start playback; /player/{id}
        # (found via `adb shell dumpsys package ahaflix.tv`'s registered
        # intent-filter path patterns, not documented anywhere) actually
        # plays it. This is Android/ADB-only — Roku's launch path uses ECP's
        # own contentId+mediaType params, not a URL template, so it's
        # unaffected by this.
        "deep_link_template": "https://www.aha.video/player/{content_id}",
    },
    "tm": {
        # "Unifi TV" (Telekom Malaysia) — same underlying white-label
        # platform as aha (com.quickplay.ott.*), confirmed on a real
        # device (TV1-CH4, a Xiaomi Mi TV Stick). "tm" as the key matches
        # the OPS_RESTRICTED_PLATFORMS keyword and the original content
        # catalog draft's platform label for this slot.
        "label": "Unifi TV (TM)",
        "roku_app_id": None,  # ADB-only so far; no Roku instance confirmed yet
        "android_package": "com.tm.unifitv.tv",
        # Same /player/{id} pattern confirmed to work for aha — not yet
        # tested with a real Unifi TV content ID.
        "deep_link_template": "https://tm-web-ui-cdn.api.tmcms.quickplay.com/player/{content_id}",
    },
    # The following 5 confirmed on real Soc_usa devices (CH5/CH8/CH10/CH13/
    # CH16) via `adb shell pm list packages` and Roku `/query/apps`. No
    # deep-link templates known yet — launching just opens the app.
    "univision": {
        # Company-internal UI label differs from the Roku channel name
        # ("Univision App: Stream TV Shows") — distinct from "univision_now"
        # below, which is a different app entirely, not a typo/duplicate.
        "label": "Univision TVE",
        "roku_app_id": "573804",
        "android_package": "com.univision.android",
        "deep_link_template": None,
    },
    "univision_now": {
        "label": "Univision DTC",
        "roku_app_id": "122460",
        "android_package": "com.univision.prendetv",
        "deep_link_template": None,
    },
    "canela": {
        "label": "Canela",
        "roku_app_id": "584171",
        "android_package": "com.canela.ott.tv",
        "deep_link_template": None,
    },
    "the_weather_channel": {
        "label": "The Weather Channel",
        "roku_app_id": "273862",
        "android_package": "com.weathergroup.twc",
        "deep_link_template": None,
    },
    "gotham_sports": {
        "label": "Gotham Sports",
        "roku_app_id": "765408",
        # Confirmed on CH3 — Gotham Sports Network is distributed under
        # the com.yesnetwork.yes package (YES Network/GSN rebrand), not a
        # separately-named app.
        "android_package": "com.yesnetwork.yes",
        "deep_link_template": None,
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

# Android package name -> PLATFORMS key, for mapping real
# `adb shell pm list packages` output to something an operator recognizes.
# Anything installed that isn't in this map is simply not offered as a
# selectable app (better than showing raw package names), and the UI
# falls back to the content catalog.
PACKAGE_TO_PLATFORM = {
    "ahaflix.tv": "aha",
    "com.tm.unifitv.tv": "tm",
    "com.univision.android": "univision",
    "com.univision.prendetv": "univision_now",
    "com.canela.ott.tv": "canela",
    "com.weathergroup.twc": "the_weather_channel",
    "com.yesnetwork.yes": "gotham_sports",
}

# Preset content titles shown in the launch dropdown, per platform.
# content_id is the slug used both for Roku ECP contentId and the Android
# deep-link URL.
CONTENT_PRESETS = {
    "aha": [
        {"label": "Constable", "content_id": "constable"},
    ],
    # No known working deep-link content IDs yet for Unifi TV — leave the
    # content-ID field blank in Advanced entry to just open the app.
    "tm": [],
}

DEFAULT_MEDIA_TYPE = "movie"

# Timeouts (seconds) for network calls to devices.
ROKU_REQUEST_TIMEOUT = 5
ADB_COMMAND_TIMEOUT = 8
STATUS_CHECK_TIMEOUT = 1.5

DB_PATH = "data/wall.db"
