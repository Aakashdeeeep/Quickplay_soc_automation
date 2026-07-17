# Quickplay SOC Automation

Centralized visual automation platform for controlling a 56-device TV wall used for
live/VOD content testing across OTT platforms (Roku, Fire TV, Android TV / Google TV,
AppleTV planned) in a Service Operations Center.

## Stack

- Python 3 + Flask
- SQLite device registry (`data/wall.db`, created at runtime)
- Roku control via ECP (`requests`)
- Android TV / Fire TV / Chromecast w/ Google TV control via wireless ADB (`subprocess`)

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python db.py
python app.py
```

The app serves on `http://localhost:5000`.

## Registering devices

Scan/discovery UI is a later phase. Until then, register devices manually:

```
python seed_devices.py add TV1-01 roku 192.168.1.42 OPS --platform aha
python seed_devices.py list
```

## Project layout

- `device_control/` — protocol-specific launch logic (`roku.py`, `adb.py`), the
  `launcher.py` dispatcher, and `status.py` online/offline probes.
- `routes/` — Flask blueprints: `views.py` (pages), `api.py` (JSON endpoints).
- `templates/` / `static/` — dark-themed UI.
- `models.py` / `db.py` — SQLite device registry.
- `config.py` — networks, ports, and per-platform app IDs/presets.
