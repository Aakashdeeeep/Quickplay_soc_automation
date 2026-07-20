"""
Parses a slot_id into its physical TV group and channel number, per the
confirmed real convention: "{tv_id}-CH{channel}" (e.g. "TV1-CH11" ->
("TV1", 11)). Used to group devices by physical TV for the dashboard and
to sort a TV's devices in real channel order (channel 10 comes after
channel 2, not before it alphabetically like a plain string sort would).

Companion device naming isn't confirmed yet — anything that doesn't match
this pattern falls back to (slot_id, None) rather than guessing.
"""

import re

_SLOT_PATTERN = re.compile(r"^(.+)-CH(\d+)$")


def parse_slot_id(slot_id):
    """Returns (tv_id, channel:int), or (slot_id, None) if it doesn't
    match the expected convention."""
    match = _SLOT_PATTERN.match(slot_id or "")
    if not match:
        return slot_id, None
    return match.group(1), int(match.group(2))


def channel_sort_key(slot_id):
    """Sort key for ordering a TV's devices in real channel order."""
    _, channel = parse_slot_id(slot_id)
    return (channel is None, channel if channel is not None else 0, slot_id)


_TV_NUMBER_PATTERN = re.compile(r"^TV(\d+)$")


def tv_group_sort_key(tv_id):
    """Sort key for ordering TV groups on the selector screen: TV1, TV2,
    TV3... numerically first, then anything else (e.g. companion devices,
    once their naming is confirmed) alphabetically after."""
    match = _TV_NUMBER_PATTERN.match(tv_id or "")
    if match:
        return (0, int(match.group(1)), tv_id)
    return (1, 0, tv_id)
