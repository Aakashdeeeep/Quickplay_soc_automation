"""
Roku Discovery Script
----------------------
Finds all Roku devices on the local network using SSDP (Simple Service
Discovery Protocol). Roku devices respond automatically to this broadcast,
so no IP scanning or guessing is needed.

Usage:
    python discover_roku.py

Requires: nothing extra, uses only Python's built-in socket library.
"""

import socket
import re

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 3  # seconds to wait for responses
SSDP_ST = "roku:ecp"  # Roku-specific search target

SEARCH_MSG = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
    'MAN: "ssdp:discover"\r\n'
    f"MX: {SSDP_MX}\r\n"
    f"ST: {SSDP_ST}\r\n"
    "\r\n"
).encode("utf-8")


def discover_roku_devices(timeout=4):
    """Broadcast SSDP search and collect Roku device responses."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)

    sock.sendto(SEARCH_MSG, (SSDP_ADDR, SSDP_PORT))

    devices = []
    seen_ips = set()

    try:
        while True:
            data, addr = sock.recvfrom(1024)
            ip = addr[0]
            if ip in seen_ips:
                continue
            seen_ips.add(ip)

            response = data.decode("utf-8", errors="ignore")
            location_match = re.search(r"LOCATION:\s*(.+)", response, re.IGNORECASE)
            location = location_match.group(1).strip() if location_match else "unknown"

            devices.append({"ip": ip, "location": location})
    except socket.timeout:
        pass
    finally:
        sock.close()

    return devices


if __name__ == "__main__":
    print("Scanning for Roku devices on the local network (SSDP)...")
    print(f"Waiting up to {SSDP_MX + 1} seconds for responses...\n")

    found = discover_roku_devices(timeout=SSDP_MX + 1)

    if not found:
        print("No Roku devices found. Possible reasons:")
        print("  - You're not connected to the same network as the Rokus")
        print("  - Firewall is blocking UDP multicast traffic")
        print("  - Rokus are on a different subnet/VLAN that blocks SSDP")
    else:
        print(f"Found {len(found)} Roku device(s):\n")
        for i, dev in enumerate(found, start=1):
            print(f"  {i}. IP: {dev['ip']}")
            print(f"     ECP URL: http://{dev['ip']}:8060")
            print(f"     Details: {dev['location']}\n")