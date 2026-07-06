"""Reasoning cache — hash(normalized situation) -> decision, with TTL.

Identical situations (same segment + origin/dest + bucketed congestion + hive
mood) reuse a prior decision instead of spending quota. This doubles as the
"trigger gate": when an agent's situation is unchanged, its cache key is
unchanged, so it never re-hits the LLM.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional


class TTLCache:
    def __init__(self, ttl_s: float = 120.0) -> None:
        self.ttl_s = ttl_s
        self._store: dict[str, tuple[float, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is not None and (time.monotonic() - entry[0]) < self.ttl_s:
            self.hits += 1
            return entry[1]
        if entry is not None:
            self._store.pop(key, None)
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)

    @property
    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": self.size,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }


def make_key(parts: dict) -> str:
    """Stable hash of a small, canonical situation dict."""
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
