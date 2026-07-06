"""Consistent-hash sharding: agent_id -> model.

Stable across timesteps (so an agent's cache + circuit state stay coherent) and
spreads load evenly across the healthy provider pool. The pool is computed by
the gateway each call so a parked (circuit-open) provider drops out
automatically.
"""
from __future__ import annotations

import hashlib
from typing import Optional, Sequence


def model_for(agent_id: int, pool: Sequence[str]) -> Optional[str]:
    if not pool:
        return None
    digest = hashlib.blake2b(str(agent_id).encode("utf-8"), digest_size=8).digest()
    return pool[int.from_bytes(digest, "big") % len(pool)]
