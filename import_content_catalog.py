"""
Import content catalog rows from a CSV into the content_catalog table.

Expected columns: tv_id, channel, device_type, platform, content_title,
content_type. Optional columns: content_id (machine slug/ID for
deep-linking, if known), notes.

slot_id is derived as f"{tv_id}-CH{channel}", matching the confirmed device
registry convention (e.g. tv_id "TV1" + channel "1" -> "TV1-CH1"). tv_id
must match the registry's slot_id prefix so a catalog entry joins to the
right device. The companion-device prefix convention isn't confirmed yet —
don't guess it when that batch arrives.

Imported rows default to verified=0 (unverified) unless --verified is
passed, since a freshly transcribed catalog should be checked before it's
trusted to drive real launches.

Usage:
    python import_content_catalog.py content_catalog.csv
    python import_content_catalog.py content_catalog.csv --verified
"""

import argparse
import csv

from db import init_db
import content_catalog as catalog


def main():
    parser = argparse.ArgumentParser(description="Import the content assignment catalog from CSV.")
    parser.add_argument("csv_path")
    parser.add_argument("--verified", action="store_true", default=False,
                         help="Mark all imported rows as verified (default: unverified)")
    args = parser.parse_args()

    init_db()

    count = 0
    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tv_id = (row.get("tv_id") or "").strip()
            channel = (row.get("channel") or "").strip()
            if not tv_id or not channel:
                continue
            slot_id = f"{tv_id}-CH{int(channel)}"
            catalog.upsert_entry(
                slot_id=slot_id,
                tv_id=tv_id,
                channel=channel,
                device_type=(row.get("device_type") or "").strip() or None,
                platform=(row.get("platform") or "").strip(),
                content_title=(row.get("content_title") or "").strip(),
                content_type=(row.get("content_type") or "").strip(),
                content_id=(row.get("content_id") or "").strip() or None,
                verified=args.verified,
                notes=(row.get("notes") or "").strip() or None,
            )
            count += 1

    print(f"Imported {count} catalog entries (verified={args.verified}).")


if __name__ == "__main__":
    main()
