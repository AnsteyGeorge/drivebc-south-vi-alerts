# DriveBC South VI Alerts : dont run this "traffic" alert system for South Vancouver Island highways with "real-time": incident detection and web dashboard

Dont run**South Vancouver Island** traffic alert system for DriveBC highway cameras, plus a local monitoring dashboard.

## Components

- `alert/` — Commute-aware incident detection + email alerts
- `dashboard/` — Local Flask web UI showing system status, live incidents, and camera risk grid

The system is designed for:

- Early warning on Highway 1 / 14 / 17 commute disruptions
- Low false-positive rate (rolling median smoothing + cooldowns)
- 24/7 unattended operation on a Linux host (cron every 3 minutes)

---

## Quick Start

### 1. Clone and create environments

```bash
git clone git@github.com:YOUR_USERNAME/drivebc-south-vi-alerts.git
cd drivebc-south-vi-alerts
```

#### Alert system env

```bash
cd alert
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Dashboard env

```bash
cd ../dashboard
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the template:

```bash
cp .env.example .env
```

Edit `.env` and fill in your SMTP credentials and (optionally) `ALERT_EMAIL`.

Ensure your shell or service loads these variables before running `alert.py`.

### 3. Run a manual smoke test

From the `alert/` directory:

```bash
source venv/bin/activate
python alert.py
```

You should see:

- Cameras loading successfully
- `incident_log.jsonl` created/updated
- An email to your `ALERT_EMAIL` if conditions are met

Then wire cron as described in `alert/README.md`.

### 4. Run the dashboard

From the `dashboard/` directory:

```bash
source venv/bin/activate
python dashboard.py
```

Open <http://localhost:5000> — you should see:

- System status bar (healthy / degraded / attention)
- Live incidents strip (last 30 minutes)
- Camera grid with latest risk per camera

---

## Repository Layout

```text
drivebc-south-vi-alerts/
├── .github/
│   └── workflows/
│       └── ci.yml          # Basic CI (lint/pytest-ready)
├── .gitignore
├── .env.example            # Template for environment variables
├── README.md               # This file
├── alert/
│   ├── alert.py            # Production-hardened alert engine
│   ├── requirements.txt
│   ├── README.md           # Setup + cron + SMTP
│   └── config/
│       └── south_vi_cameras.yaml  # South VI camera list (replace with your verified config)
└── dashboard/
    ├── dashboard.py        # Flask backend
    ├── requirements.txt
    ├── README.md           # Dashboard usage
    ├── templates/
    │   └── index.html
    └── static/
        ├── style.css
        └── app.js
```

---

## CI (GitHub Actions)

A minimal CI workflow is provided at `.github/workflows/ci.yml`:

- Installs Python 3.11
- Installs dependencies for `alert/` and `dashboard/`
- Runs `pytest` (once you add tests under `tests/`)

You can enable branch protection on `main` so that CI must pass before merges.
