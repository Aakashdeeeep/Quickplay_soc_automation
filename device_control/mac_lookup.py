"""
MAC address resolution and matching, in support of the MAC-as-permanent-
identity architecture: a device's slot_id <-> mac_address mapping is
stable; its IP/network are transient and refreshed by scanning.

Not wired into a live "Scan Network" endpoint yet (that feature is still a
later phase) — this module is the standalone building block for it: given
an IP that answered during a port-scan, resolve its MAC via the local ARP
table and match it against the registry.
"""

import re
import subprocess

import models

_MAC_PATTERN = re.compile(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")


def get_mac_for_ip(ip, timeout=3):
    """Resolve an IP to a MAC address via the local ARP table (`arp -a`,
    available on both Windows and Linux/macOS in this form).

    Relies on the OS ARP cache already having an entry for this IP — a
    prior TCP connect or ping to the device populates it, so callers
    should probe the device (e.g. the existing port-scan check) before
    calling this. Returns a lowercase colon-separated MAC, or None if no
    ARP entry is found (e.g. the device hasn't been contacted recently, or
    ARP visibility is blocked on this network the way SSDP/mDNS is).
    """
    try:
        result = subprocess.run(
            ["arp", "-a", ip], capture_output=True, text=True, timeout=timeout
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    match = _MAC_PATTERN.search(result.stdout)
    if not match:
        return None
    return match.group(0).lower().replace("-", ":")


def match_discovered_device(ip, device_type):
    """Given a live IP found during a scan, resolve its MAC and match it
    against the registry.

    Returns one of:
      {"status": "matched", "device": <dict>, "mac_address": mac, "ip": ip}
          - known slot; caller should call models.update_live_location().
      {"status": "unregistered", "mac_address": mac, "ip": ip, "device_type": ...}
          - a real device answered but no slot claims this MAC yet; the UI
            should let an operator assign it to a slot_id.
      {"status": "no_mac", "ip": ip}
          - couldn't resolve a MAC for this IP at all (ARP entry missing
            or blocked); can't identify this device by hardware identity.
    """
    mac = get_mac_for_ip(ip)
    if not mac:
        return {"status": "no_mac", "ip": ip}

    device = models.get_device_by_mac(mac)
    if device:
        return {"status": "matched", "device": device, "mac_address": mac, "ip": ip}

    return {"status": "unregistered", "mac_address": mac, "ip": ip, "device_type": device_type}
