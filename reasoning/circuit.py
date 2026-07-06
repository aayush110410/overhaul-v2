"""Free-tier survival primitives: token-bucket rate limiter, circuit breaker,
quota counters.

These are the load-bearing mechanisms that let ~50 LLM sentinels run on free
tiers without tripping a 429 storm:

  * ``TokenBucket``    paces calls per *account* (the real RPM boundary).
  * ``CircuitBreaker`` parks a provider that keeps failing / returns 429, so
    traffic re-shards onto healthy providers instead of hammering a dead one.
  * ``QuotaCounter``   tracks calls/errors/429s per provider for ``stats()``.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict


class TokenBucket:
    """Async token bucket. ``acquire()`` returns once a token is available,
    sleeping (cooperatively, lock released) when the bucket is empty."""

    def __init__(self, rate_per_min: float) -> None:
        self.capacity = float(rate_per_min)
        self.tokens = float(rate_per_min)
        self.refill_per_sec = float(rate_per_min) / 60.0
        self._ts = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity, self.tokens + (now - self._ts) * self.refill_per_sec
                )
                self._ts = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / max(self.refill_per_sec, 1e-6)
            await asyncio.sleep(min(wait, 5.0))


class CircuitBreaker:
    """Per-provider breaker. Opens after ``fail_threshold`` consecutive failures
    or any explicit 429, parks the provider for a cooldown, then half-opens."""

    def __init__(self, fail_threshold: int = 5, cooldown_s: float = 30.0) -> None:
        self.fail_threshold = fail_threshold
        self.cooldown_s = cooldown_s
        self.failures = 0
        self.open_until = 0.0

    def is_open(self) -> bool:
        return self.open_until > time.monotonic()

    @property
    def state(self) -> str:
        if self.is_open():
            return "open"
        if self.open_until and not self.is_open():
            return "half_open"
        return "closed"

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    def record_failure(self, retry_after: float | None = None) -> None:
        self.failures += 1
        if self.failures >= self.fail_threshold or retry_after:
            self.open_until = time.monotonic() + max(self.cooldown_s, retry_after or 0.0)


@dataclass
class QuotaCounter:
    """Per-provider running totals (display + light gating)."""

    calls: int = 0
    errors: int = 0
    rate_limited: int = 0

    def record(self, *, error: bool = False, rate_limited: bool = False) -> None:
        self.calls += 1
        if error:
            self.errors += 1
        if rate_limited:
            self.rate_limited += 1


def parse_retry_after(exc: Exception) -> float | None:
    """Best-effort extraction of a 429 cooldown from an upstream error string."""
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg or "quota" in msg or "exhaust" in msg:
        return 30.0
    return None
