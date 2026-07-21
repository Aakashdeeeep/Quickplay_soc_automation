"""
Network discovery: ping every IP in a subnet range to establish presence
and resolve MAC via ARP, additionally checking Roku/ADB ports to guess a
device type for anything that turns out unregistered. Match against the
device registry by MAC. This is the real "Scan Network" feature — earlier
standalone scripts (scan_subnet.py, discover_roku.py) were the prototype
this is built from.

SSDP/mDNS broadcast discovery is blocked on these networks, so this scans
a subnet range directly rather than relying on broadcast discovery.

MAC matching must not be gated behind the Roku/ADB port checks — confirmed
on a real device (a Chromecast paired via Android's on-device Wireless
Debugging, which puts ADB on a random port instead of the fixed 5555 this
scan checks) that a live, correctly-MAC-registered device can have neither
expected port open and would be silently skipped if MAC resolution only
ran for IPs that passed a port check. Presence (ping) and MAC resolution
now always happen; the port checks are only used to guess a device type
for display when a found MAC doesn't match anything in the registry.

MAC resolution must happen right after the probe that populates the ARP
cache entry, not later — ARP entries expire within a few minutes
(confirmed empirically), so a scan that probed-then-came-back-later for
MACs would find most entries already gone.
"""

import socket
import subprocess
import concurrent.futures

import requests

from config import ROKU_ECP_PORT, ADB_PORT, STATUS_CHECK_TIMEOUT
from device_control import mac_lookup
import models

MAX_WORKERS = 100
SCAN_START = 1
SCAN_END = 254


def _ping(ip, timeout_ms=300):
    """Best-effort presence probe — populates the ARP cache regardless of
    what (if anything) is listening on a port. Return value doesn't matter;
    MAC resolution afterward is the real signal."""
    try:
        subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), ip],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass


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
    """Establish presence + MAC via ping/ARP unconditionally, then guess a
    device type from the Roku/ADB ports for anything unregistered."""
    _ping(ip)
    mac = mac_lookup.get_mac_for_ip(ip)

    device_type_guess = "unknown"
    if _check_port(ip, ROKU_ECP_PORT) and _confirm_roku(ip):
        device_type_guess = "roku"
    elif _check_port(ip, ADB_PORT):
        device_type_guess = "adb-device"

    if not mac and device_type_guess == "unknown":
        return None  # nothing here at all

    return {"ip": ip, "device_type_guess": device_type_guess, "mac_address": mac}


def scan_network(network_name, subnet_prefixes, start=SCAN_START, end=SCAN_END):
    """Scan one or more subnet ranges, match discovered devices against the
    registry by MAC, and update their live location. A "network" here isn't
    reliably a single /24 — OPS turned out to span both 192.168.208.x and
    192.168.209.x — so this always takes a list of prefixes, even for a
    network that currently only has one.

    Returns:
      {
        "matched": [device dict, ...],       # known slot, location refreshed
        "unregistered": [{"ip", "mac_address", "device_type_guess"}, ...],
        "no_mac": [{"ip", "device_type_guess"}, ...],  # live but ARP didn't resolve
        "cleared": [slot_id, ...],           # previously on this network, not found now
      }
    """
    if isinstance(subnet_prefixes, str):
        subnet_prefixes = [subnet_prefixes]
    ips = [f"{prefix}{i}" for prefix in subnet_prefixes for i in range(start, end + 1)]

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
