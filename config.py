"""
Central configuration: networks, subnet prefixes, ports, and content presets.

IP-to-device mapping is NOT here — that lives in the SQLite registry (models.py)
because it changes as devices get moved around. This file only holds things
that are structurally stable: which networks exist, which ports mean what,
and known app/content IDs.
"""

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

DEVICE_TYPES = ["roku", "firetv", "androidtv", "chromecast-gtv", "appletv"]

# Ports used during discovery/status checks.
ROKU_ECP_PORT = 8060
ADB_PORT = 5555

# Per-platform identifiers needed to launch content.
# Roku channels are launched by numeric/string "app ID", Android apps by
# package name. Add more platforms here as they get proven out.
PLATFORMS = {
    "aha": {
        "label": "aha",
        "roku_app_id": "",  # TODO: fill in aha's Roku channel ID once known
        "android_package": "ahaflix.tv",
        "deep_link_template": "https://www.aha.video/movie/{content_id}",
    },
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
