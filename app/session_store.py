from threading import Lock
from typing import Any


_lock = Lock()
_sessions: dict[str, dict[str, Any]] = {}


def get_session(conversation_id: str) -> dict[str, Any]:
    with _lock:
        return dict(_sessions.get(conversation_id, {}))


def update_session(conversation_id: str, data: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        current = dict(_sessions.get(conversation_id, {}))
        current.update({key: value for key, value in data.items() if value is not None})
        _sessions[conversation_id] = current
        return dict(current)


def clear_session(conversation_id: str) -> None:
    with _lock:
        _sessions.pop(conversation_id, None)
