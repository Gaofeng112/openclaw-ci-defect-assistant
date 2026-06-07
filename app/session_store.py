import json
from pathlib import Path
from typing import Any

from app.config import BASE_DIR


SESSION_DIR = BASE_DIR / "runtime" / "sessions"


def _path(action: str, conversation_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in conversation_id)
    return SESSION_DIR / action / f"{safe_id}.json"


def load_fields(action: str, conversation_id: str | None) -> dict[str, Any]:
    if not conversation_id:
        return {}
    path = _path(action, conversation_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("fields", {})
    except (OSError, json.JSONDecodeError):
        return {}


def save_fields(action: str, conversation_id: str | None, fields: dict[str, Any]) -> None:
    if not conversation_id:
        return
    path = _path(action, conversation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fields": fields}, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_fields(action: str, conversation_id: str | None) -> None:
    if not conversation_id:
        return
    path = _path(action, conversation_id)
    if path.exists():
        path.unlink()
