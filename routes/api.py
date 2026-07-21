"""
JSON API routes: device status polling and content launch.
"""

from flask import Blueprint, request, jsonify

import models
import content_catalog
import slot_naming
from config import NETWORKS, DEVICE_TYPES, ADB_DEVICE_TYPES, PACKAGE_TO_PLATFORM, PLATFORMS
from device_control import status as status_control
from device_control import launcher
from device_control import scanner
from device_control import adb as adb_control

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _clean(value):
    """Blank-string-to-None normalization for form/JSON input."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clean_int(value):
    cleaned = _clean(value) if isinstance(value, str) else value
    if cleaned is None or cleaned == "":
        return None
    try:
        return int(cleaned)
    except (TypeError, ValueError):
        return None


@api_bp.route("/devices", methods=["GET"])
def list_devices_route():
    """Full registry listing — powers the admin device management table."""
    return jsonify(models.list_devices())


def _create_one_device(data, seen_macs):
    """Shared validation + insert for both the single-device and bulk
    create endpoints. seen_macs tracks MACs already claimed earlier in the
    same batch, so two new rows in one bulk submission can't both grab the
    same MAC before either is committed to the DB.

    Returns (success: bool, message: str, device: dict|None)."""
    slot_id = _clean(data.get("slot_id"))
    device_type = _clean(data.get("device_type"))

    if not slot_id or not device_type:
        return False, "slot_id and device_type are required.", None
    if device_type not in DEVICE_TYPES:
        return False, f"device_type must be one of: {', '.join(DEVICE_TYPES)}", None
    if models.get_device_by_slot(slot_id):
        return False, f"'{slot_id}' already exists — edit it instead.", None

    mac_address = _clean(data.get("mac_address"))
    if mac_address:
        mac_address = mac_address.lower()
        if mac_address in seen_macs:
            return False, f"MAC {mac_address} is used more than once in this batch.", None
        conflict = models.get_device_by_mac(mac_address)
        if conflict:
            return False, f"MAC {mac_address} is already registered to '{conflict['slot_id']}'.", None
        seen_macs.add(mac_address)

    device = models.upsert_device(
        slot_id=slot_id,
        device_type=device_type,
        last_known_ip=_clean(data.get("last_known_ip")),
        network=_clean(data.get("network")),
        friendly_name=_clean(data.get("friendly_name")),
        platform=_clean(data.get("platform")),
        roku_app_id=_clean(data.get("roku_app_id")),
        mac_address=mac_address,
        adb_port=_clean_int(data.get("adb_port")),
        touch_last_seen=False,
    )
    return True, f"Created {slot_id}.", device


@api_bp.route("/devices", methods=["POST"])
def create_device_route():
    """Add a new device to the registry via the admin UI. A device with a
    new TV-group prefix in its slot_id (e.g. "TV2-CH1") just shows up as a
    new TV card on Screen 1 automatically — there's no separate "create a
    TV" step."""
    data = request.get_json(silent=True) or {}
    success, message, device = _create_one_device(data, set())
    if not success:
        status = 409 if "already" in message or "more than once" in message else 400
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "device": device})


@api_bp.route("/devices/bulk", methods=["POST"])
def create_devices_bulk_route():
    """Add many devices in one go — e.g. all of a new TV's channels at
    once — instead of the admin UI's single-device form N times over.
    Partial success is expected and reported per-row: one bad MAC
    shouldn't block the rest of the batch."""
    data = request.get_json(silent=True) or {}
    devices_in = data.get("devices")
    if not isinstance(devices_in, list) or not devices_in:
        return jsonify({"success": False, "message": "devices must be a non-empty list."}), 400

    seen_macs = set()
    results = []
    for row in devices_in:
        success, message, device = _create_one_device(row, seen_macs)
        results.append({
            "slot_id": row.get("slot_id"),
            "success": success,
            "message": message,
        })

    created_count = sum(1 for r in results if r["success"])
    return jsonify({
        "success": created_count > 0,
        "created_count": created_count,
        "total": len(results),
        "results": results,
    })


@api_bp.route("/devices/<slot_id>", methods=["PUT"])
def update_device_route(slot_id):
    """Edit an existing device via the admin UI. Any field present in the
    request body is set exactly (including cleared to blank); anything
    absent keeps its current value."""
    existing = models.get_device_by_slot(slot_id)
    if not existing:
        return jsonify({"success": False, "message": f"No device with slot_id '{slot_id}'"}), 404

    data = request.get_json(silent=True) or {}

    def field(name):
        return _clean(data[name]) if name in data else existing[name]

    def int_field(name):
        return _clean_int(data[name]) if name in data else existing[name]

    device_type = field("device_type") or existing["device_type"]
    if device_type not in DEVICE_TYPES:
        return jsonify({"success": False, "message": f"device_type must be one of: {', '.join(DEVICE_TYPES)}"}), 400

    mac_address = field("mac_address")
    if mac_address:
        mac_address = mac_address.lower()
        conflict = models.get_device_by_mac(mac_address)
        if conflict and conflict["slot_id"] != slot_id:
            return jsonify({
                "success": False,
                "message": f"MAC {mac_address} is already registered to '{conflict['slot_id']}'.",
            }), 409

    device = models.replace_device_fields(
        slot_id=slot_id,
        device_type=device_type,
        last_known_ip=field("last_known_ip"),
        network=field("network"),
        friendly_name=field("friendly_name"),
        platform=field("platform"),
        roku_app_id=field("roku_app_id"),
        mac_address=mac_address,
        adb_port=int_field("adb_port"),
    )
    return jsonify({"success": True, "device": device})


@api_bp.route("/devices/<slot_id>", methods=["DELETE"])
def delete_device_route(slot_id):
    if not models.get_device_by_slot(slot_id):
        return jsonify({"success": False, "message": f"No device with slot_id '{slot_id}'"}), 404
    models.delete_device(slot_id)
    return jsonify({"success": True})


@api_bp.route("/network/<network_name>/status")
def network_status(network_name):
    """Status for every device on a network — used by the grid view to
    refresh online/offline badges without a full page reload."""
    devices = models.list_devices(network=network_name)
    result = {}
    for device in devices:
        result[device["slot_id"]] = status_control.check_status(
            device["device_type"], device["last_known_ip"], device.get("adb_port")
        )
    return jsonify(result)


@api_bp.route("/devices/<slot_id>/status")
def device_status(slot_id):
    device = models.get_device_by_slot(slot_id)
    if not device:
        return jsonify({"error": f"No device with slot_id '{slot_id}'"}), 404
    result = status_control.check_status(device["device_type"], device["last_known_ip"], device.get("adb_port"))
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
            device["device_type"], device["last_known_ip"], device.get("adb_port")
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
        packages = adb_control.list_installed_packages(device["last_known_ip"], device.get("adb_port"))
        if packages:
            matched = sorted({
                key for pkg, key in PACKAGE_TO_PLATFORM.items() if pkg in packages
            })
            if matched:
                return jsonify({
                    "source": "installed",
                    "apps": [{"platform": p, "label": PLATFORMS.get(p, {}).get("label", p)} for p in matched],
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

    success, message = launcher.launch_content(
        device, match["content_id"], platform, nav_sequence=match.get("nav_sequence")
    )
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

    subnet_prefixes = NETWORKS[network_name].get("subnet_prefixes")
    if not subnet_prefixes:
        return jsonify({"error": f"No subnet configured for {network_name} yet."}), 400

    result = scanner.scan_network(network_name, subnet_prefixes)
    return jsonify(result)


@api_bp.route("/launch", methods=["POST"])
def launch():
    data = request.get_json(silent=True) or {}
    slot_id = data.get("slot_id")
    content_id = _clean(data.get("content_id"))  # blank is valid: "just open the app"
    platform = data.get("platform")

    if not slot_id or not platform:
        return jsonify({
            "success": False,
            "message": "slot_id and platform are required.",
        }), 400

    device = models.get_device_by_slot(slot_id)
    if not device:
        return jsonify({"success": False, "message": f"No device with slot_id '{slot_id}'"}), 404

    success, message = launcher.launch_content(device, content_id, platform)
    if success:
        models.touch_last_seen(slot_id)

    return jsonify({"success": success, "message": message})
