"""
JSON API routes: device status polling and content launch.
"""

from flask import Blueprint, request, jsonify

import models
import content_catalog
import slot_naming
from config import NETWORKS, ADB_DEVICE_TYPES, PACKAGE_TO_PLATFORM
from device_control import status as status_control
from device_control import launcher
from device_control import scanner
from device_control import adb as adb_control

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


@api_bp.route("/tv/<tv_id>/status")
def tv_status(tv_id):
    """Status for every device belonging to a physical TV group — the
    dashboard's device grid is organized by TV, not network, so this
    mirrors /api/network/<x>/status for that grouping instead."""
    devices = [d for d in models.list_devices() if slot_naming.parse_slot_id(d["slot_id"])[0] == tv_id]
    result = {}
    for device in devices:
        result[device["slot_id"]] = status_control.check_status(
            device["device_type"], device["last_known_ip"]
        )
    return jsonify(result)


@api_bp.route("/devices/<slot_id>/apps")
def device_apps(slot_id):
    """Apps available to launch on this device for the dashboard's app
    selector: real installed apps we can identify, if the device is an
    authorized ADB unit; otherwise fall back to whatever the content
    catalog says is assigned to this slot."""
    device = models.get_device_by_slot(slot_id)
    if not device:
        return jsonify({"error": f"No device with slot_id '{slot_id}'"}), 404

    catalog_entry = content_catalog.get_by_slot(slot_id)

    if device["device_type"] in ADB_DEVICE_TYPES and device["last_known_ip"]:
        packages = adb_control.list_installed_packages(device["last_known_ip"])
        if packages:
            matched = sorted({
                friendly for pkg, friendly in PACKAGE_TO_PLATFORM.items() if pkg in packages
            })
            if matched:
                return jsonify({
                    "source": "installed",
                    "apps": [{"platform": p, "label": p} for p in matched],
                })

    if catalog_entry:
        return jsonify({
            "source": "catalog",
            "apps": [{"platform": catalog_entry["platform"], "label": catalog_entry["platform"]}],
        })

    return jsonify({"source": "none", "apps": []})


@api_bp.route("/launch_auto", methods=["POST"])
def launch_auto():
    """Primary dashboard launch flow: operator picks an app + Live/VOD,
    not a raw content ID. Resolves what to actually launch via the content
    catalog (this slot's own assignment, or a random known title for that
    platform+type elsewhere), then reuses the same launch_content() path
    as manual/Advanced entry — including the OPS-restriction check."""
    data = request.get_json(silent=True) or {}
    slot_id = data.get("slot_id")
    platform = data.get("platform")
    content_type = data.get("content_type")

    if not slot_id or not platform or not content_type:
        return jsonify({
            "success": False,
            "message": "slot_id, platform, and content_type are all required.",
        }), 400

    device = models.get_device_by_slot(slot_id)
    if not device:
        return jsonify({"success": False, "message": f"No device with slot_id '{slot_id}'"}), 404

    match = content_catalog.find_title_for_launch(slot_id, platform, content_type)
    if not match:
        return jsonify({
            "success": False,
            "message": f"No known {content_type} titles for {platform} in the catalog yet — use Advanced entry.",
        }), 404

    success, message = launcher.launch_content(device, match["content_id"], platform)
    if success:
        models.touch_last_seen(slot_id)

    return jsonify({
        "success": success,
        "message": message,
        "launched_title": match["content_title"],
        "source": match["source"],
    })


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
