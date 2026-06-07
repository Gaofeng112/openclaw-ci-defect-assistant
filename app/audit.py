import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import CiCommand, CiResult


AUDIT_DIR = Path(__file__).resolve().parent.parent / "runtime" / "audit"
SENSITIVE_KEYS = ("token", "secret", "password", "authorization")


def write_audit(command: CiCommand, result: CiResult) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "time": datetime.now(timezone.utc).isoformat(),
        "request_id": command.request_id,
        "conversation_id": command.conversation_id,
        "user_id": command.user_id,
        "action": command.action,
        "job": command.job,
        "params": _redact(command.params),
        "confirmed": command.confirmed,
        "success": result.success,
        "code": result.code,
        "needs_confirmation": result.needs_confirmation,
        "external_url": result.build_url or result.bug_url,
    }
    path = AUDIT_DIR / f"{datetime.now().date().isoformat()}.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "***" if _is_sensitive(key) else _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(word in lowered for word in SENSITIVE_KEYS)
