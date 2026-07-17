"""
Manual device registry seeding — stand-in for the scan/assign UI, which
comes in a later phase. Lets you register devices by hand so the launch
flow can be tested end-to-end today.

Usage:
    python seed_devices.py add TV1-01 roku 192.168.208.42 OPS --platform aha --roku-app-id 577103
    python seed_devices.py add TV1-02 firetv 192.168.208.43 OPS --platform aha
    python seed_devices.py list
    python seed_devices.py remove TV1-01

--roku-app-id is per-device: privately-distributed Roku channels (like aha)
can be assigned a different app ID on each Roku unit — check
`/query/apps` on that specific device rather than reusing an ID from
another one.
"""

import argparse

from db import init_db
import models
from config import DEVICE_TYPES, NETWORKS


def cmd_add(args):
    if args.device_type not in DEVICE_TYPES:
        raise SystemExit(f"device_type must be one of: {', '.join(DEVICE_TYPES)}")
    if args.network not in NETWORKS:
        raise SystemExit(f"network must be one of: {', '.join(NETWORKS)}")

    device = models.upsert_device(
        slot_id=args.slot_id,
        device_type=args.device_type,
        last_known_ip=args.ip,
        network=args.network,
        friendly_name=args.friendly_name,
        platform=args.platform,
        roku_app_id=args.roku_app_id,
    )
    print(f"Saved: {device}")


def cmd_list(args):
    devices = models.list_devices(network=args.network)
    if not devices:
        print("No devices registered.")
        return
    for d in devices:
        print(f"  {d['slot_id']:<12} {d['device_type']:<16} {d['last_known_ip'] or '-':<16} "
              f"{d['network']:<6} platform={d['platform'] or '-':<6} roku_app_id={d['roku_app_id'] or '-'}")


def cmd_remove(args):
    models.delete_device(args.slot_id)
    print(f"Removed {args.slot_id}")


def main():
    parser = argparse.ArgumentParser(description="Manually manage the device registry.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add or update a device")
    p_add.add_argument("slot_id", help="Permanent label, e.g. TV1-01")
    p_add.add_argument("device_type", choices=DEVICE_TYPES)
    p_add.add_argument("ip")
    p_add.add_argument("network", choices=list(NETWORKS))
    p_add.add_argument("--platform", default=None, help="Default OTT platform, e.g. aha")
    p_add.add_argument("--friendly-name", default=None)
    p_add.add_argument("--roku-app-id", default=None,
                        help="This device's Roku channel ID for --platform (check /query/apps on the device)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List registered devices")
    p_list.add_argument("--network", default=None, choices=list(NETWORKS))
    p_list.set_defaults(func=cmd_list)

    p_remove = sub.add_parser("remove", help="Remove a device by slot_id")
    p_remove.add_argument("slot_id")
    p_remove.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    init_db()
    args.func(args)


if __name__ == "__main__":
    main()
