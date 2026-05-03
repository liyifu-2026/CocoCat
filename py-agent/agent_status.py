import os
import json
import tempfile
import time

_STATUS_FILE = None


def _status_path() -> str:
    global _STATUS_FILE
    if _STATUS_FILE:
        return _STATUS_FILE
    _STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "_status.json")
    return _STATUS_FILE


def set_status_file(path: str):
    global _STATUS_FILE
    _STATUS_FILE = path


def _read_all() -> dict:
    path = _status_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict):
    path = _status_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def report(agent_id: str, status: str, detail: str = ""):
    entries = _read_all()
    entries[agent_id] = {
        "status": status,
        "detail": detail,
        "updated_at": time.time(),
        "updated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _write_all(entries)


def get_status(agent_id: str) -> dict:
    entries = _read_all()
    entry = entries.get(agent_id, {})
    return {
        "agent_id": agent_id,
        "status": entry.get("status", "unknown"),
        "detail": entry.get("detail", ""),
        "updated_at": entry.get("updated_at_iso", ""),
    }


def list_all() -> dict:
    return _read_all()


def detect_stale(timeout: int = 300) -> list[str]:
    now = time.time()
    stale = []
    for agent_id, entry in _read_all().items():
        last = entry.get("updated_at", 0)
        if now - last > timeout:
            stale.append(agent_id)
    return stale
