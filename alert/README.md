# DriveBC South VI Alert System

Commute-aware incident detection + email alerts for South Vancouver Island using DriveBC cameras.

## Files

- `alert.py` — main script (run every 3 minutes via cron)
- `requirements.txt` — Python dependencies
- `config/south_vi_cameras.yaml` — South VI camera list (Highways 1 / 14 / 17)

At runtime, the script creates:

- `state/` — per-camera JSON state (cooldowns + metric history)
- `incident_log.jsonl` — append-only log of risk evaluations

## Setup

1. Create and activate a virtualenv:

```bash
cd alert
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure SMTP environment variables (see repo-level `.env.example`):

```bash
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export ALERT_EMAIL="recipient@example.com"
```

3. Run a smoke test:

```bash
python alert.py
```

## Cron

Example crontab entry (every 3 minutes):

```cron
*/3 * * * * cd /opt/drivebc-south-vi-alerts/alert && /opt/drivebc-south-vi-alerts/alert/venv/bin/python alert.py >> monitor.log 2>&1
```

For more step-by-step deployment details, see `deployment_checklist.md`.
