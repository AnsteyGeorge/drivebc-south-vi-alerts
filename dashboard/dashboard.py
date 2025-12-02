from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template
from zoneinfo import ZoneInfo
import yaml

APP_TZ = ZoneInfo("America/Vancouver")
INCIDENT_LOG_PATH = os.environ.get("INCIDENT_LOG_PATH", "alert/incident_log.jsonl")
CAMERA_CONFIG_PATH = os.environ.get("CAMERA_CONFIG_PATH", "alert/config/south_vi_cameras.yaml")

app = Flask(__name__, template_folder="templates", static_folder="static")


@dataclass
class CameraInfo:
    id: str
    name: str
    highway: str
    image_url: Optional[str] = None
    last_risk: Optional[float] = None
    last_incident_type: Optional[str] = None
    last_timestamp: Optional[str] = None


@dataclass
class Incident:
    camera: str
    highway: str
    incident_type: str
    risk: float
    timestamp: str


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def load_cameras() -> Dict[str, CameraInfo]:
    cameras: Dict[str, CameraInfo] = {}
    if not os.path.exists(CAMERA_CONFIG_PATH):
        return cameras

    with open(CAMERA_CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f) or {}

    for cam in data.get("cameras", []):
        cid = str(cam.get("id") or cam.get("drivebc_id") or cam.get("name"))
        image_url = cam.get("image_url") or cam.get("url")
        cameras[cid] = CameraInfo(
            id=cid,
            name=cam.get("name", cid),
            highway=str(cam.get("highway", "?")),
            image_url=image_url,
        )
    return cameras


def load_incident_log() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not os.path.exists(INCIDENT_LOG_PATH):
        return entries
    with open(INCIDENT_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def compute_status() -> Dict[str, Any]:
    now = datetime.now(APP_TZ)
    cameras = load_cameras()
    log_entries = load_incident_log()

    last_check: Optional[datetime] = None
    active_incidents: List[Incident] = []
    per_camera_latest: Dict[str, Dict[str, Any]] = {}

    for entry in log_entries:
        ts_str = entry.get("timestamp")
        ts = _parse_ts(ts_str)
        if ts:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=APP_TZ)
            last_check = max(last_check, ts) if last_check else ts

        cam_name = entry.get("camera")
        highway = str(entry.get("highway", "?"))
        risk = float(entry.get("risk", 0.0))
        incident_type = entry.get("incident_type")
        alerted = bool(entry.get("alerted", False))

        if ts and incident_type and (alerted or risk >= 60.0):
            if now - ts <= timedelta(minutes=30):
                active_incidents.append(
                    Incident(
                        camera=cam_name,
                        highway=highway,
                        incident_type=incident_type,
                        risk=risk,
                        timestamp=ts.astimezone(APP_TZ).isoformat(),
                    )
                )

        if cam_name:
            prev = per_camera_latest.get(cam_name)
            prev_ts = _parse_ts(prev.get("timestamp")) if prev and prev.get("timestamp") else None
            if not prev or (ts and (not prev_ts or ts > prev_ts)):
                per_camera_latest[cam_name] = {
                    "timestamp": ts.astimezone(APP_TZ).isoformat() if ts else None,
                    "risk": risk,
                    "incident_type": incident_type,
                }

    camera_cards: List[Dict[str, Any]] = []
    for cam in cameras.values():
        latest = per_camera_latest.get(cam.name, {})
        cam.last_risk = latest.get("risk")
        cam.last_incident_type = latest.get("incident_type")
        cam.last_timestamp = latest.get("timestamp")
        camera_cards.append(asdict(cam))

    if last_check is None:
        system_status = "unknown"
        status_color = "gray"
        status_message = "No checks recorded yet"
    else:
        age = now - last_check
        if age <= timedelta(minutes=5):
            system_status = "healthy"
            status_color = "green"
            status_message = "Monitoring active"
        elif age <= timedelta(minutes=15):
            system_status = "degraded"
            status_color = "amber"
            status_message = "Monitoring delayed"
        else:
            system_status = "attention"
            status_color = "red"
            status_message = "No recent checks"

    next_check = None
    if last_check:
        next_check = (last_check + timedelta(minutes=3)).astimezone(APP_TZ).isoformat()

    active_incidents.sort(key=lambda i: i.timestamp, reverse=True)
    live_incidents = [asdict(i) for i in active_incidents]

    return {
        "now": now.astimezone(APP_TZ).isoformat(),
        "system_status": system_status,
        "status_color": status_color,
        "status_message": status_message,
        "last_check": last_check.astimezone(APP_TZ).isoformat() if last_check else None,
        "next_check": next_check,
        "camera_count": len(cameras),
        "live_incident_count": len(live_incidents),
        "live_incidents": live_incidents,
        "cameras": camera_cards,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def api_dashboard():
    data = compute_status()
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
