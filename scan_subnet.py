"""
OPS Subnet Scanner
-------------------
Scans a local subnet directly (no router access needed) to find:
  - Roku devices (port 8060 open -> confirmed via /query/device-info)
  - ADB-capable devices, i.e. FireTV / Chromecast with Google TV (port 5555 open)

This works even when SSDP/mDNS broadcast discovery is blocked by the network,
since it just checks each IP directly for open ports.

Usage:
    python scan_subnet.py

Edit SUBNET_PREFIX below if you're scanning a different network.
"""

import socket
import concurrent.futures
import urllib.request

SUBNET_PREFIX = "192.168.208."   # OPS network - change for SOC/US1/US2 later
START = 1
END = 254
TIMEOUT = 0.3        # seconds per port check - keep low for speed
MAX_WORKERS = 100     # parallel scan threads


def check_port(ip, port, timeout=TIMEOUT):
    """Return True if the given TCP port is open on ip."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def confirm_roku(ip):
    """Hit Roku's ECP device-info endpoint to confirm it's really a Roku."""
    try:
        url = f"http://{ip}:8060/query/device-info"
        with urllib.request.urlopen(url, timeout=1) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return "<device-info>" in body
    except Exception:
        return False


def scan_ip(ip):
    """Check a single IP for Roku (8060) and ADB (5555) ports."""
    result = None

    if check_port(ip, 8060):
        if confirm_roku(ip):
            result = {"ip": ip, "type": "roku"}

    if result is None and check_port(ip, 5555):
        result = {"ip": ip, "type": "adb-device (firetv/chromecast-gtv)"}

    return result


def scan_subnet(prefix, start, end):
    ips = [f"{prefix}{i}" for i in range(start, end + 1)]
    found = []

    print(f"Scanning {prefix}{start}-{end} ... this may take ~30-60 seconds\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scan_ip, ip): ip for ip in ips}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                found.append(result)
                print(f"  Found: {result['ip']}  ->  {result['type']}")

    return found


if __name__ == "__main__":
    devices = scan_subnet(SUBNET_PREFIX, START, END)

    print(f"\nScan complete. {len(devices)} device(s) found.\n")
    for d in devices:
        print(f"  {d['ip']:<16} {d['type']}")

    if not devices:
        print("No devices found. Double-check you're connected to the OPS wifi.")