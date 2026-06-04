from datetime import UTC, datetime
from typing import Any


def audit_event(action: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "user_id": user_id,
        "payload": payload,
        "created_at": datetime.now(UTC).isoformat(),
    }
