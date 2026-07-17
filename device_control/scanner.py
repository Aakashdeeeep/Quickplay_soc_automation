"""
Network discovery: port-scan a subnet for Roku/ADB devices, resolve each
live IP's MAC via ARP immediately after probing it, and match against the
device registry. This is the real "Scan Network" feature — earlier
standalone scripts (scan_subnet.py, discover_roku.py) were the prototype
this is built from.

SSDP/mDNS broadcast discovery is blocked on these networks, so this scans
a subnet range directly (concurrent TCP port checks) rather than relying
on broadcast discovery.

MAC resolution must happen right after the port probe that populates the
ARP cache entry, not later — ARP entries expire within a few minutes
(confirmed empirically), so a scan that probed-then-came-back-later for
MACs would find most entries already gone.
"""

import socket
import concurrent.futures

import requests

from config import ROKU_ECP_PORT, ADB_PORT, STATUS_CHECK_TIMEOUT
from device_control import mac_lookup
import models

MAX_WORKERS = 100
SCAN_START = 1
SCAN_END = 254


def _check_port(ip, port, timeout=STATUS_CHECK_TIMEOUT):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _confirm_roku(ip):
    try:
        resp = requests.get(f"http://{ip}:{ROKU_ECP_PORT}/query/device-info", timeout=2)
        return resp.status_code == 200 and "<device-info>" in resp.text
    except requests.exceptions.RequestException:
        return False


def _probe_ip(ip):
    """Check one IP for Roku/ADB, resolving its MAC immediately if found."""
    if _check_port(ip, ROKU_ECP_PORT) and _confirm_roku(ip):
        mac = mac_lookup.get_mac_for_ip(ip)
        return {"ip": ip, "device_type_guess": "roku", "mac_address": mac}

    if _check_port(ip, ADB_PORT):
        mac = mac_lookup.get_mac_for_ip(ip)
        return {"ip": ip, "device_type_guess": "adb-device", "mac_address": mac}

    return None


def scan_network(network_name, subnet_prefix, start=SCAN_START, end=SCAN_END):
    """Scan a subnet range, match discovered devices against the registry
    by MAC, and update their live location.

    Returns:
      {
        "matched": [device dict, ...],       # known slot, location refreshed
        "unregistered": [{"ip", "mac_address", "device_type_guess"}, ...],
        "no_mac": [{"ip", "device_type_guess"}, ...],  # live but ARP didn't resolve
        "cleared": [slot_id, ...],           # previously on this network, not found now
      }
    """
    ips = [f"{subnet_prefix}{i}" for i in range(start, end + 1)]

    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(_probe_ip, ip) for ip in ips]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                found.append(result)

    matched = []
    unregistered = []
    no_mac = []
    matched_macs = set()

    for item in found:
        mac = item["mac_address"]
        if not mac:
            no_mac.append(item)
            continue
        device = models.get_device_by_mac(mac)
        if device:
            updated = models.update_live_location(mac, item["ip"], network_name)
            matched.append(updated)
            matched_macs.add(mac)
        else:
            unregistered.append(item)

    # Devices previously marked on this network but not seen in this scan
    # are no longer confirmed here — clear the stale claim rather than
    # leave it looking live.
    cleared = []
    for device in models.list_devices(network=network_name):
        if device["mac_address"] and device["mac_address"] not in matched_macs:
            models.clear_live_location(device["mac_address"])
            cleared.append(device["slot_id"])

    return {
        "matched": matched,
        "unregistered": unregistered,
        "no_mac": no_mac,
        "cleared": cleared,
    }
