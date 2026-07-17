"""
HTML page routes: network tier view and device grid tier view.
"""

from flask import Blueprint, render_template, abort

from config import NETWORKS, CONTENT_PRESETS, is_ops_restricted_platform
import models
import content_catalog

views_bp = Blueprint("views", __name__)

DEVICE_ICONS = {
    "roku": "\U0001F4FA",
    "firetv": "\U0001F525",
    "androidtv": "\U0001F4F1",
    "chromecast-gtv": "\U0001F4E1",
    "mi-stick": "\U0001F4F6",
    "appletv": "\U0001F34E",
}


@views_bp.route("/")
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
    )
