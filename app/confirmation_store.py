import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import BASE_DIR


CONFIRM_TTL_SECONDS = 300
CONFIRM_DIR = BASE_DIR / "runtime" / "confirmations"


def create_confirmation(action: str, data: dict[str, Any]) -> str:
    token = f"confirm_{uuid4().hex}"
    now = int(time.time())
    payload = {"token": token, "action": action, "created_at": now, "expires_at": now + CONFIRM_TTL_SECONDS, **data}
    CONFIRM_DIR.mkdir(parents=True, exist_ok=True)
    _path(token).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return token


def token_suffix(token: str) -> str:
    return token.rsplit("_", 1)[-1][-6:]


def consume_confirmation(token: str | None, action: str, expected: dict[str, Any]) -> str | None:
    data = _read(token)
    if not data:
        return "确认 token 无效"
    if data.get("action") != action:
        return "确认 token 与请求不匹配"
    if int(data.get("expires_at", 0)) < int(time.time()):
        _path(token or "").unlink(missing_ok=True)
        return "确认 token 已过期"
    for key, value in expected.items():
        if data.get(key) != value:
            return "确认 token 与请求不匹配"
    _path(token or "").unlink(missing_ok=True)
    return None


def find_pending_confirmation(action: str, user_id: str, conversation_id: str | None) -> dict[str, Any] | None:
    now = int(time.time())
    matches = []
    for path in CONFIRM_DIR.glob("confirm_*.json"):
        data = _read_path(path)
        if data and data.get("action") == action and int(data.get("expires_at", 0)) >= now:
            if data.get("user_id") == user_id and data.get("conversation_id") == conversation_id:
                matches.append(data)
    return max(matches, key=lambda item: int(item.get("created_at", 0)), default=None)


def _path(token: str) -> Path:
    return CONFIRM_DIR / f"{token}.json"


def _read(token: str | None) -> dict[str, Any] | None:
    return _read_path(_path(token)) if token else None


def _read_path(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
