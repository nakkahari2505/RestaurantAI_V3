import json
import threading
import time
from pathlib import Path

_STATE_PATH = Path("runtime") / "business_conversation_state.json"
_STATE_LOCK = threading.Lock()
_STATE_TTL_SECONDS = 6 * 60 * 60


def _load() -> dict:
    with _STATE_LOCK:
        if not _STATE_PATH.exists():
            return {}
        try:
            value = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}


def _save(value: dict) -> None:
    with _STATE_LOCK:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _clean(value: dict) -> dict:
    now = time.time()
    cleaned = {}
    for key, item in value.items():
        if not isinstance(item, dict):
            continue
        updated_at = float(item.get("updated_at", 0.0))
        if now - updated_at <= _STATE_TTL_SECONDS:
            cleaned[key] = item
    return cleaned


def get_conversation_query(conversation_id: str | None) -> dict | None:
    if not conversation_id:
        return None
    state = _clean(_load())
    _save(state)
    item = state.get(conversation_id)
    if not isinstance(item, dict):
        return None
    query = item.get("query")
    return query if isinstance(query, dict) else None


def set_conversation_query(conversation_id: str | None, query: dict) -> None:
    if not conversation_id:
        return
    state = _clean(_load())
    state[conversation_id] = {
        "query": query,
        "updated_at": time.time(),
    }
    _save(state)


def clear_conversation_query(conversation_id: str | None) -> None:
    if not conversation_id:
        return
    state = _clean(_load())
    state.pop(conversation_id, None)
    _save(state)
