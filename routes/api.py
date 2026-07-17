"""
JSON API routes: device status polling and content launch.
"""

from flask import Blueprint, request, jsonify

import models
from config import NETWORKS
from device_control import status as status_control
from device_control import launcher
from device_control import scanner

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/network/<network_name>/status")
def network_status(network_name):
    """Status for every device on a network — used by the grid view to
    refresh online/offline badges without a full page reload."""
    devices = models.list_devices(network=network_name)
    result = {}
    for device in devices:
        result[device["slot_id"]] = status_control.check_status(
            device["device_type"], device["last_known_ip"]
        )
    return jsonify(result)


@api_bp.route("/devices/<slot_id>/status")
def device_status(slot_id):
    device = models.get_device_by_slot(slot_id)
    if not device:
        return jsonify({"error": f"No device with slot_id '{slot_id}'"}), 404
    result = status_control.check_status(device["device_type"], device["last_known_ip"])
    return jsonify(result)


@api_bp.route("/scan/<network_name>", methods=["POST"])
def scan_network_route(network_name):
    if network_name not in NETWORKS:
        return jsonify({"error": f"Unknown network '{network_name}'"}), 404

    subnet_prefix = NETWORKS[network_name].get("subnet_prefix")
    if not subnet_prefix:
        return jsonify({"error": f"No subnet configured for {network_name} yet."}), 400

    result = scanner.scan_network(network_name, subnet_prefix)
    return jsonify(result)


@api_bp.route("/launch", methods=["POST"])
def launch():
    data = request.get_json(silent=True) or {}
    slot_id = data.get("slot_id")
    content_id = data.get("content_id")
    platform = data.get("platform")

    if not slot_id or not content_id or not platform:
        return jsonify({
            "success": False,
            "message": "slot_id, content_id, and platform are all required.",
        }), 400

    device = models.get_device_by_slot(slot_id)
    if not device:
        return jsonify({"success": False, "message": f"No device with slot_id '{slot_id}'"}), 404

    success, message = launcher.launch_content(device, content_id, platform)
    if success:
        models.touch_last_seen(slot_id)

    return jsonify({"success": success, "message": message})
