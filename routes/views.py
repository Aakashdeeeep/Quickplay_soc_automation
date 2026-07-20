"""
HTML page routes.

Primary flow (Screens 1-3 of the dashboard): TV selector -> per-TV device
grid -> Action Control overlay (the overlay is markup embedded in the
device grid template, not a separate route).

The network-tier views (networks.html/devices.html) are kept as a
secondary "admin" path — scanning is inherently a per-network operation
(subnet_prefix is a network concept, not a TV concept), so that's where
the Scan Network button still lives.
"""

from flask import Blueprint, render_template, abort

from config import NETWORKS, CONTENT_PRESETS, is_ops_restricted_platform
import models
import content_catalog
import slot_naming

views_bp = Blueprint("views", __name__)

DEVICE_ICONS = {
    "roku": "\U0001F4FA",
    "firetv": "\U0001F525",
    "androidtv": "\U0001F4F1",
    "chromecast-gtv": "\U0001F4E1",
    "mi-stick": "\U0001F4F6",
    "appletv": "\U0001F34E",
}


def _tv_groups():
    """Group all registered devices by physical TV (parsed from slot_id),
    sorted TV1/TV2/TV3.../then anything else alphabetically."""
    groups = {}
    for device in models.list_devices():
        tv_id, _ = slot_naming.parse_slot_id(device["slot_id"])
        groups.setdefault(tv_id, []).append(device)
    return [(tv_id, groups[tv_id]) for tv_id in sorted(groups, key=slot_naming.tv_group_sort_key)]


@views_bp.route("/")
def tv_selector():
    """Screen 1: landing page, one tappable card per physical TV/companion
    device group, derived from whatever's actually in the registry."""
    groups = [{"tv_id": tv_id, "device_count": len(devices)} for tv_id, devices in _tv_groups()]
    return render_template("tv_selector.html", groups=groups)


@views_bp.route("/tv/<tv_id>")
def tv_device_grid(tv_id):
    """Screen 2 + Screen 3: this TV's devices as a grid (real channel
    order), with the Action Control overlay markup for the launch flow."""
    devices = [d for d in models.list_devices()
               if slot_naming.parse_slot_id(d["slot_id"])[0] == tv_id]
    if not devices:
        abort(404)
    for d in devices:
        _, d["channel"] = slot_naming.parse_slot_id(d["slot_id"])
    devices.sort(key=lambda d: slot_naming.channel_sort_key(d["slot_id"]))
    catalog_by_slot = content_catalog.get_by_slots([d["slot_id"] for d in devices])
    return render_template(
        "tv_device_grid.html",
        tv_id=tv_id,
        devices=devices,
        catalog_by_slot=catalog_by_slot,
        device_icons=DEVICE_ICONS,
        is_ops_restricted_platform=is_ops_restricted_platform,
        presets=CONTENT_PRESETS,
    )


@views_bp.route("/networks")
def networks():
    counts = {net: len(models.list_devices(network=net)) for net in NETWORKS}
    return render_template("networks.html", networks=NETWORKS, counts=counts)


@views_bp.route("/network/<network_name>")
def device_grid(network_name):
    if network_name not in NETWORKS:
        abort(404)
    devices = models.list_devices(network=network_name)
    catalog_by_slot = content_catalog.get_by_slots([d["slot_id"] for d in devices])
    return render_template(
        "devices.html",
        network_name=network_name,
        network_label=NETWORKS[network_name]["label"],
        devices=devices,
        catalog_by_slot=catalog_by_slot,
        presets=CONTENT_PRESETS,
        device_icons=DEVICE_ICONS,
        is_ops_restricted_platform=is_ops_restricted_platform,
        scan_available=bool(NETWORKS[network_name].get("subnet_prefix")),
    )
