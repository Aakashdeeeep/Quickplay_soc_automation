"""
Bulk-import the MAC-to-slot device registry from a CSV.

Expected columns: slot_id, mac_address, device_type.

This is registry identity data only — slot_id and mac_address are the
permanent pairing. last_known_ip and network are deliberately left NULL by
this importer regardless of what's currently reachable, since those are
transient fields meant to be populated by an actual scan, not carried over
from out-of-band knowledge. Run the scan (once it exists) or seed_devices.py
to set live location afterward.

Usage:
    python import_device_registry.py registry_data/tv1_mac_registry.csv
"""

import argparse
import csv

from db import init_db
import models


def main():
    parser = argparse.ArgumentParser(description="Bulk-import the MAC-to-slot device registry from CSV.")
    parser.add_argument("csv_path")
    args = parser.parse_args()

    init_db()

    count = 0
    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = (row.get("slot_id") or "").strip()
            mac_address = (row.get("mac_address") or "").strip().lower()
            device_type = (row.get("device_type") or "").strip()
            if not slot_id or not mac_address or not device_type:
                continue

            models.upsert_device(
                slot_id=slot_id,
                device_type=device_type,
                last_known_ip=None,
                network=None,
                mac_address=mac_address,
                touch_last_seen=False,
            )
            count += 1

    print(f"Imported {count} device registry rows (last_known_ip/network left NULL).")


if __name__ == "__main__":
    main()
