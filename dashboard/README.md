# South VI Commute Dashboard

Local Flask web dashboard for the DriveBC South VI alert system.

## Setup

```bash
cd dashboard
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The dashboard expects:

- `INCIDENT_LOG_PATH` — path to `incident_log.jsonl` from the alert system
- `CAMERA_CONFIG_PATH` — path to `south_vi_cameras.yaml`

Defaults (when run from repo root):

- `INCIDENT_LOG_PATH=alert/incident_log.jsonl`
- `CAMERA_CONFIG_PATH=alert/config/south_vi_cameras.yaml`

You can override via environment variables if needed.

## Run

```bash
source venv/bin/activate
python dashboard.py
```

Then open <http://localhost:5000>.

## Features

- System status bar (healthy / degraded / attention)
- Live incident strip (last 30 minutes, high-risk only)
- Camera grid with last risk + timestamp per camera
- Dark, mobile-friendly "traffic ops center" aesthetic
