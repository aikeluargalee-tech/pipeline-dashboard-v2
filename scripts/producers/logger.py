"""
logger.py — JSONL logging for detections, alerts, and active pattern state.

detections.jsonl — append-only log of every detection event
alerts.jsonl    — CONFIRMED + FAILED only
active_patterns.json — overwritten each run, live FORMING patterns
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from config import DATA_DIR


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def log_detection(detection) -> None:
    """Append a detection to detections.jsonl."""
    _ensure_data_dir()
    entry = detection.to_dict()
    path = DATA_DIR / "detections.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def log_alert(detection) -> None:
    """Append a CONFIRMED/FAILED detection to alerts.jsonl."""
    _ensure_data_dir()
    entry = detection.to_dict()
    path = DATA_DIR / "alerts.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def write_active_patterns(active: List[dict], archived_ids: List[str] = None) -> None:
    """Overwrite active_patterns.json with current FORMING patterns + archived resolved ones."""
    _ensure_data_dir()
    path = DATA_DIR / "active_patterns.json"
    existing = read_active_patterns()
    # Preserve existing archived list, add new confirmations/failures
    old_archived = set(existing.get("archived", []))
    if archived_ids:
        old_archived.update(archived_ids)
    with open(path, "w") as f:
        json.dump({
            "updated": datetime.now(timezone.utc).isoformat(),
            "active": active,
            "archived": sorted(old_archived),
        }, f, indent=2)


def read_active_patterns() -> dict:
    """Read current active patterns state."""
    path = DATA_DIR / "active_patterns.json"
    if not path.exists():
        return {"updated": None, "active": []}
    with open(path) as f:
        return json.load(f)


def load_detections(limit: int = None) -> List[dict]:
    """Load recent detections from JSONL."""
    path = DATA_DIR / "detections.jsonl"
    if not path.exists():
        return []
    with open(path) as f:
        lines = f.readlines()
    if limit:
        lines = lines[-limit:]
    detections = []
    for line in lines:
        try:
            detections.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return detections


def load_alerts(limit: int = None) -> List[dict]:
    """Load recent alerts from JSONL."""
    path = DATA_DIR / "alerts.jsonl"
    if not path.exists():
        return []
    with open(path) as f:
        lines = f.readlines()
    if limit:
        lines = lines[-limit:]
    alerts = []
    for line in lines:
        try:
            alerts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return alerts
