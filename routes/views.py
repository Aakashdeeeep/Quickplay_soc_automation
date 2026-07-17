"""
HTML page routes: network tier view and device grid tier view.
"""

from flask import Blueprint, render_template, abort

from config import NETWORKS, CONTENT_PRESETS
import models

views_bp = Blueprint("views", __name__)

DEVICE_ICONS = {
    "roku": "\U0001F4FA",
    "firetv": "\U0001F525",
    "androidtv": "\U0001F4F1",
    "chromecast-gtv": "\U0001F4E1",
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
    return render_template(
        "devices.html",
        network_name=network_name,
        network_label=NETWORKS[network_name]["label"],
        devices=devices,
        presets=CONTENT_PRESETS,
        device_icons=DEVICE_ICONS,
    )
