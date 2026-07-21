# Quickplay SOC Automation

Centralized visual automation platform for controlling a 56-device TV wall used for
live/VOD content testing across OTT platforms (Roku, Fire TV, Android TV / Google TV,
AppleTV planned) in a Service Operations Center.

## Stack

- Python 3 + Flask
- SQLite device registry (`data/wall.db`, created at runtime)
- Roku control via ECP (`requests`)
- Android TV / Fire TV / Chromecast w/ Google TV control via wireless ADB (`subprocess`)

## Setup (first time only)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python db.py
```

## Running it

```
venv\Scripts\activate
python app.py
```

Open `http://localhost:5000` — that's Screen 1 (pick a TV). "Manage Devices" and
"Admin / Scan" are in the top nav.

To scan a network for live devices from the command line instead of the UI:

```
curl -X POST http://localhost:5000/api/scan/OPS
```

## Registering devices

Use the "Manage Devices" page in the UI (add one device, or "+ Add TV" to add a
whole TV's channels at once) — no code needed for day-to-day registry changes.

The CLI scripts still work for bulk/scripted imports:

```
python seed_devices.py add TV1-CH1 roku 192.168.1.42 OPS --platform aha
python import_device_registry.py registry_data/tv1_mac_registry.csv
python import_content_catalog.py content_catalog.csv
```

## Project layout

- `device_control/` — protocol-specific launch logic (`roku.py`, `adb.py`), the
  `launcher.py` dispatcher, `scanner.py` (network discovery), `mac_lookup.py`
  (ARP-based MAC resolution), and `status.py` online/offline probes.
- `routes/` — Flask blueprints: `views.py` (pages), `api.py` (JSON endpoints).
- `templates/` / `static/` — dark-themed dashboard UI.
- `models.py` / `db.py` — SQLite device registry (MAC is the permanent identity;
  IP/network are transient, refreshed by scanning).
- `content_catalog.py` — what platform/title/type is assigned to each slot.
- `config.py` — networks, ports, per-platform app IDs/presets, OPS-restriction rules.
- `slot_naming.py` — parses a slot_id (e.g. `TV1-CH11`) into its TV group + channel.
