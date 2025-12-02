import os
import smtplib
import ssl
import time
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from email.message import EmailMessage

import cv2
import numpy as np
import requests
import yaml

# ========================
# CONFIGURATION
# ========================

STATE_DIR = "state"
LOG_FILE = "incident_log.jsonl"
os.makedirs(STATE_DIR, exist_ok=True)

PRIORITY_WEIGHTS = {"1": 1.0, "14": 0.8, "17": 0.7}
COMMUTE_WINDOWS = [(7, 9), (16, 18)]  # 7–9 AM, 4–6 PM
RISK_ALERT_THRESHOLD = 60.0
COOLDOWN_MINUTES = 30
ROLLING_WINDOW_SIZE = 5
TIMEZONE = ZoneInfo("America/Vancouver")


# ========================
# STARTUP VALIDATION
# ========================

def validate_smtp_env() -> None:
    required = ["SMTP_SERVER", "SMTP_USER", "SMTP_PASSWORD", "SMTP_PORT"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        print("[FATAL] Missing required SMTP environment variables:")
        for var in missing:
            print(f"  → {var}")
        print("\nSet them in your environment (or a .env file) and restart.")
        raise SystemExit(1)


# ========================
# STATE & LOGGING
# ========================

def get_camera_id(camera: dict) -> str:
    base = (
        str(camera.get("id"))
        or str(camera.get("drivebc_id"))
        or str(camera.get("name", "unknown"))
    )
    return base.replace(" ", "_").replace("/", "-")


def load_camera_state(camera: dict) -> dict:
    cam_id = get_camera_id(camera)
    path = os.path.join(STATE_DIR, f"{cam_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_camera_state(camera: dict, state: dict) -> None:
    cam_id = get_camera_id(camera)
    path = os.path.join(STATE_DIR, f"{cam_id}.json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def log_incident(entry: dict) -> None:
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ========================
# CORE FUNCTIONS
# ========================

def load_cameras(path: str = "config/south_vi_cameras.yaml") -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Camera config not found: {path}")
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    if not data or "cameras" not in data:
        raise ValueError("Invalid YAML format: missing top-level 'cameras' key")
    return data["cameras"]


def fetch_image(url: str, retries: int = 3) -> tuple[np.ndarray, bytes]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            if len(resp.content) < 5000:
                raise ValueError("Response too small")
            arr = np.frombuffer(resp.content, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None or frame.size == 0:
                raise ValueError("Decoded frame is empty")
            return frame, resp.content
        except Exception as e:
            last_error = e
            print(f"[warn] Fetch attempt {attempt + 1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(3)
    raise ValueError(f"Failed to retrieve valid image from {url}: {last_error}")


def compute_metrics(frame1: np.ndarray, frame2: np.ndarray) -> dict:
    width = 640
    h1, w1 = frame1.shape[:2]
    h2, w2 = frame2.shape[:2]

    frame1_res = cv2.resize(frame1, (width, int(h1 * width / w1)))
    frame2_res = cv2.resize(frame2, (width, int(h2 * width / w2)))

    gray1 = cv2.cvtColor(frame1_res, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2_res, cv2.COLOR_BGR2GRAY)

    brightness2 = float(np.mean(gray2))

    blurred = cv2.GaussianBlur(gray2, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edge_density2 = float(np.mean(edges) / 255.0)

    diff = cv2.absdiff(gray1, gray2)
    motion_score = float(np.mean(diff))

    _, thresh = cv2.threshold(gray2, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    occupancy_score = float(np.mean(thresh) / 255.0)

    return {
        "brightness": brightness2,
        "edge_density": edge_density2,
        "motion_score": motion_score,
        "occupancy_score": occupancy_score,
    }


def compute_median(values: list[float]) -> float:
    if not values:
        return 0.0
    arr = np.array(values, dtype=float)
    return float(np.median(arr))


def get_smoothed_metrics(
    metrics_raw: dict,
    state: dict,
) -> tuple[dict, dict]:
    history: list[dict] = state.get("metric_history", [])

    history.append(
        {
            "timestamp": datetime.now(TIMEZONE).isoformat(),
            "brightness": metrics_raw["brightness"],
            "edge_density": metrics_raw["edge_density"],
            "motion_score": metrics_raw["motion_score"],
            "occupancy_score": metrics_raw["occupancy_score"],
        }
    )

    if len(history) > ROLLING_WINDOW_SIZE:
        history = history[-ROLLING_WINDOW_SIZE:]

    smoothed = {
        "brightness": compute_median([h["brightness"] for h in history]),
        "edge_density": compute_median([h["edge_density"] for h in history]),
        "motion_score": compute_median([h["motion_score"] for h in history]),
        "occupancy_score": compute_median([h["occupancy_score"] for h in history]),
    }

    state["metric_history"] = history
    return smoothed, state


def in_commute_window(dt: datetime) -> bool:
    hour = dt.hour
    return any(start <= hour < end for start, end in COMMUTE_WINDOWS)


def compute_commute_risk(metrics: dict, camera: dict, now: datetime) -> tuple[float, str | None]:
    m = metrics["motion_score"]
    b = metrics["brightness"]
    e = metrics["edge_density"]
    occ = metrics["occupancy_score"]

    night_hours = (now.hour < 6) or (now.hour >= 20)

    base_risk = 0.0
    incident_type: str | None = None

    if m < 2.0 and occ > 0.45:
        base_risk = 90.0
        incident_type = "blocked_or_closed_lane"
    elif m < 5.0 and occ > 0.35:
        base_risk = 70.0
        incident_type = "major_slowdown"
    elif m < 5.0 and b < 60.0 and e < 0.03:
        base_risk = 60.0
        incident_type = "severe_visibility_disruption"

    if night_hours and incident_type == "severe_visibility_disruption" and base_risk == 60.0:
        return 0.0, None

    if incident_type is None:
        return 0.0, None

    priority = PRIORITY_WEIGHTS.get(str(camera.get("highway", "")), 0.6)
    commute_factor = 1.3 if in_commute_window(now) else 1.0

    risk = base_risk * priority * commute_factor
    risk = max(0.0, min(100.0, risk))

    return risk, incident_type


def send_email(
    camera: dict,
    incident_type: str,
    risk: float,
    image_bytes: bytes,
    metrics_smoothed: dict,
    now: datetime,
) -> bool:
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    alert_email = os.getenv("ALERT_EMAIL", "anstey.method@gmail.com")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = alert_email
    msg["Subject"] = (
        f"DriveBC ALERT | {camera['name']} | "
        f"{incident_type.replace('_', ' ').title()} | {risk:.1f}"
    )

    body = (
        "DRIVEBC TRAFFIC ALERT\n\n"
        f"Location: {camera['name']} (Highway {camera.get('highway', 'N/A')})\n"
        f"Detected: {incident_type.replace('_', ' ').title()}\n"
        f"Risk Score: {risk:.1f}/100\n"
        f"Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n"
        "Smoothed Metrics:\n"
        f"• Motion Score: {metrics_smoothed['motion_score']:.2f}\n"
        f"• Brightness: {metrics_smoothed['brightness']:.1f}\n"
        f"• Edge Density: {metrics_smoothed['edge_density']:.4f}\n"
        f"• Occupancy Score: {metrics_smoothed['occupancy_score']:.3f}\n\n"
        "Image attached.\n\n"
        "---\n"
        "Automated DriveBC Monitor\n"
    )

    msg.set_content(body)
    msg.add_attachment(
        image_bytes,
        maintype="image",
        subtype="jpeg",
        filename=f"DriveBC_{get_camera_id(camera)}_{now.strftime('%Y%m%d_%H%M%S')}.jpg",
    )

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"[ALERT] Email sent → {camera['name']} | {incident_type} | {risk:.1f}")
        return True
    except Exception as e:
        print(f"[error] Email failed: {e}")
        return False


def process_camera(camera: dict, now: datetime) -> None:
    print(f"[info] Checking → {camera['name']} (Hwy {camera.get('highway', '?')})")
    try:
        url = camera.get("image_url") or camera.get("url")
        if not url:
            print(f"[warn] Camera {camera.get('name')} missing image_url/url; skipping.")
            return

        frame1, _ = fetch_image(url)
        time.sleep(2.5)
        frame2, image_bytes = fetch_image(url)

        metrics_raw = compute_metrics(frame1, frame2)

        state = load_camera_state(camera)
        metrics_smoothed, state = get_smoothed_metrics(metrics_raw, state)

        risk, incident_type = compute_commute_risk(metrics_smoothed, camera, now)

        alerted = False

        if risk >= RISK_ALERT_THRESHOLD and incident_type:
            last_type = state.get("last_incident_type")
            last_time = state.get("last_alert_time", 0.0)
            cooldown_sec = COOLDOWN_MINUTES * 60

            if (incident_type != last_type) or (time.time() - last_time > cooldown_sec):
                if send_email(camera, incident_type, risk, image_bytes, metrics_smoothed, now):
                    state.update(
                        {
                            "last_alert_time": time.time(),
                            "last_incident_type": incident_type,
                            "last_risk": risk,
                        }
                    )
                    alerted = True

        save_camera_state(camera, state)

        log_entry = {
            "timestamp": now.isoformat(),
            "camera": camera["name"],
            "highway": camera.get("highway"),
            "risk": round(risk, 2),
            "incident_type": incident_type,
            "metrics_raw": metrics_raw,
            "metrics_smoothed": metrics_smoothed,
            "alerted": alerted,
        }
        log_incident(log_entry)

        status = f"Risk {risk:.1f} | {incident_type or 'normal'}"
        if alerted:
            status += " → ALERTED"
        print(f"[result] {camera['name']}: {status}")

    except Exception as e:
        print(f"[error] Failed on {camera['name']}: {e}")
    finally:
        time.sleep(1)


def main() -> None:
    now = datetime.now(TIMEZONE)
    print(f"[start] DriveBC Alert System — {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    validate_smtp_env()

    try:
        cameras = load_cameras()
        print(f"[info] Loaded {len(cameras)} cameras")
    except Exception as e:
        print(f"[fatal] Config error: {e}")
        raise SystemExit(1)

    for camera in cameras:
        process_camera(camera, now)


if __name__ == "__main__":
    main()
