# DriveBC South VI Alert — Deployment Checklist (Linux + cron)

## 1. Files

Place these files on your Linux machine, for example:

```text
/opt/drivebc_south_vi_production/
  alert/
    alert.py
    requirements.txt
    config/
      south_vi_cameras.yaml   # your verified 9-camera config
```

At first run, the script will create:

- `alert/state/` — per-camera JSON state
- `alert/incident_log.jsonl` — append-only JSONL log

## 2. Python environment

```bash
cd /opt/drivebc_south_vi_production/alert

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## 3. SMTP environment variables

Set these in your shell profile (`~/.bashrc` or similar) or a systemd service environment:

```bash
export SMTP_SERVER="smtp.yourprovider.com"
export SMTP_PORT="587"
export SMTP_USER="your_smtp_username"
export SMTP_PASSWORD="your_smtp_password"
# Optional override (default is anstey.method@gmail.com)
export ALERT_EMAIL="anstey.method@gmail.com"
```

Reload:

```bash
source ~/.bashrc
```

## 4. Manual smoke test

```bash
cd /opt/drivebc_south_vi_production/alert
source venv/bin/activate
python alert.py
```

Check:

- No `[FATAL]` SMTP errors
- Cameras load correctly
- `incident_log.jsonl` created and appended
- If conditions met, email arrives at `ALERT_EMAIL`

## 5. Cron job (every 3 minutes)

```bash
crontab -e
```

Add:

```cron
*/3 * * * * cd /opt/drivebc_south_vi_production/alert && /opt/drivebc_south_vi_production/alert/venv/bin/python alert.py >> monitor.log 2>&1
```

Save and exit.

This will run the alert system every 3 minutes, 24/7.
