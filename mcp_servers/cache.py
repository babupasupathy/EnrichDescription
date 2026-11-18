"""Tiny in-memory TTL cache (PRD: 24-hour cache per marketplace and category).

Per container instance only. Good enough for a demo; swap for Firestore or Redis if needed.
"""

import time
from typing import Any

TTL_SECONDS = 24 * 60 * 60
_store: dict[str, tuple[float, Any]] = {}


def get(key: str) -> Any | None:
    hit = _store.get(key)
    if hit and time.time() - hit[0] < TTL_SECONDS:
        return hit[1]
    _store.pop(key, None)
    return None


def put(key: str, value: Any) -> None:
    _store[key] = (time.time(), value)


def clear() -> None:
    _store.clear()
