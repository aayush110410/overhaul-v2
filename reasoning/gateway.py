"""The Reasoning Gateway — one front door for every agent LLM call.

No agent ever calls a provider directly (PATH.md invariant #5). The gateway
manages the free-tier survival kit so ~50 sentinels + 7 brains reason without
429-ing:

    50 Sentinels ─┐
    7  Brains   ──┼──▶  GATEWAY  ──▶  [qwen · kimi · gpt_oss]  (OpenRouter)
    report narr ──┘    (cache·shard·batch·              └──▶  [gemini]  (Google)
                        ratelimit·breaker)

Batching is **synchronous**: ``reason_many`` receives all pending requests at
once, groups cache-misses by sharded model, chunks each group to <= ``batch_size``,
and fires the chunks concurrently under a semaphore. No background timers → no
races, fully deterministic, easy to test.
"""
from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from engines.agent_simulation.brains.collective_truth import CollectiveTruth

from reasoning import providers as _prov
from reasoning.batching import (
    build_distill_batch,
    build_sentinel_batch,
    chunks,
    split_distill_batch,
    split_sentinel_batch,
)
from reasoning.cache import TTLCache, make_key
from reasoning.circuit import CircuitBreaker, QuotaCounter, TokenBucket, parse_retry_after
from reasoning.adapters import coerce_decision, coerce_truth, valid_edge_ids
from reasoning.sharding import model_for


@dataclass
class ReasonRequest:
    agent_id: int
    context: Dict[str, Any]
    kind: str = "sentinel"
    trigger_key: Optional[str] = None


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class ReasoningGateway:
    def __init__(
        self,
        *,
        concurrency: int = 4,
        batch_size: int = 8,
        cache_ttl_s: float = 120.0,
        sentinel_pool: Optional[Sequence[str]] = None,
    ) -> None:
        self.concurrency = _env_int("REASONING_CONCURRENCY", concurrency)
        self.batch_size = _env_int("REASONING_BATCH_MAX", batch_size)
        self.sentinel_tokens = _env_int("REASONING_SENTINEL_TOKENS", 700)
        self.distill_tokens = _env_int("REASONING_DISTILL_TOKENS", 800)

        self._sem = asyncio.Semaphore(self.concurrency)
        self._cache = TTLCache(ttl_s=_env_float("REASONING_CACHE_TTL_S", cache_ttl_s))

        # Per-account token buckets (the real RPM boundary). Gemini is lower
        # because the free-tier Google quota is the flakiest.
        self._buckets = {
            "openrouter": TokenBucket(_env_float("REASONING_OPENROUTER_RPM", 18)),
            "google": TokenBucket(_env_float("REASONING_GOOGLE_RPM", 8)),
        }
        self._breakers = {m: CircuitBreaker() for m in _prov.PROVIDERS}
        self._quota = {m: QuotaCounter() for m in _prov.PROVIDERS}

        # Default sentinel shard pool = the 3 OpenRouter models (all verified
        # live). Gemini is reserved for the report narrative (with fallback).
        default_pool = os.getenv("REASONING_SENTINEL_POOL", "qwen,kimi,gpt_oss").split(",")
        self.sentinel_pool = [m.strip() for m in (sentinel_pool or default_pool) if m.strip()]

        self._batches_emitted = 0
        self._requests_in = 0
        self._cache_served = 0

    # ── provider plumbing ────────────────────────────────────────────────
    def _account(self, model: str) -> str:
        return _prov.ACCOUNT_OF.get(model, "openrouter")

    def _healthy_pool(self, candidates: Sequence[str]) -> List[str]:
        return [m for m in candidates if not self._breakers[m].is_open()]

    async def _call_json(self, model: str, *, system: str, prompt: str, max_tokens: int) -> dict:
        await self._buckets[self._account(model)].acquire()
        async with self._sem:
            try:
                resp = await _prov.call_json(
                    model, prompt=prompt, system=system, max_output_tokens=max_tokens
                )
                if isinstance(resp, dict) and resp.get("error"):
                    raise RuntimeError(f"provider returned error: {resp.get('error')}")
                self._breakers[model].record_success()
                self._quota[model].record()
                return resp
            except Exception as exc:  # noqa: BLE001 — breaker handles all failures
                retry = parse_retry_after(exc)
                self._breakers[model].record_failure(retry_after=retry)
                self._quota[model].record(error=True, rate_limited=bool(retry))
                raise

    async def _call_text(self, model: str, *, system: str, prompt: str, max_tokens: int) -> str:
        await self._buckets[self._account(model)].acquire()
        async with self._sem:
            try:
                out = await _prov.call_text(
                    model, prompt=prompt, system=system, max_output_tokens=max_tokens
                )
                self._breakers[model].record_success()
                self._quota[model].record()
                return out
            except Exception as exc:  # noqa: BLE001
                retry = parse_retry_after(exc)
                self._breakers[model].record_failure(retry_after=retry)
                self._quota[model].record(error=True, rate_limited=bool(retry))
                raise

    # ── sentinel reasoning (batched) ─────────────────────────────────────
    def _cache_key(self, req: ReasonRequest, cong_digest: dict) -> str:
        c = req.context
        return make_key(
            {
                "k": req.kind,
                "seg": c.get("segment"),
                "o": c.get("origin"),
                "d": c.get("destination"),
                "mood": c.get("mood"),
                "pref": sorted(c.get("preferred", []) or []),
                "cong": cong_digest,
            }
        )

    @staticmethod
    def _fallback_decision(why: str = "gateway fallback (no LLM)") -> dict:
        return {
            "action": "take_route",
            "route": [],
            "avoid": [],
            "mood": "stable",
            "confidence": 0.0,
            "why": why,
            "fallback": True,
        }

    async def reason_many(
        self, requests: Sequence[ReasonRequest], *, world: Optional[dict] = None
    ) -> List[dict]:
        """Decide for many sentinels at once. Returns decisions in input order."""
        world = world or {}
        valid = world.get("valid_edges") or valid_edge_ids()
        world = {**world, "valid_edges": valid}
        congestion = world.get("congestion", {}) or {}
        cong_digest = {e: round(r * 20) / 20 for e, r in congestion.items()}

        self._requests_in += len(requests)
        results: List[Optional[dict]] = [None] * len(requests)

        # 1. cache / trigger-gate
        misses: List[tuple[int, ReasonRequest, str]] = []
        for idx, req in enumerate(requests):
            key = self._cache_key(req, cong_digest)
            cached = self._cache.get(key)
            if cached is not None:
                results[idx] = cached
                self._cache_served += 1
            else:
                misses.append((idx, req, key))

        # 2. shard misses across the healthy pool
        pool = self._healthy_pool(self.sentinel_pool)
        if not pool:
            for idx, _req, _key in misses:
                results[idx] = self._fallback_decision("all providers parked")
            return [r if r is not None else self._fallback_decision() for r in results]

        groups: Dict[str, List[tuple[int, ReasonRequest, str]]] = defaultdict(list)
        for idx, req, key in misses:
            groups[model_for(req.agent_id, pool)].append((idx, req, key))

        # 3. chunk each group and fire concurrently
        tasks = []
        for model, items in groups.items():
            for chunk in chunks(items, self.batch_size):
                tasks.append(self._run_sentinel_chunk(model, chunk, world, results, valid))
        if tasks:
            await asyncio.gather(*tasks)

        return [r if r is not None else self._fallback_decision() for r in results]

    async def _run_sentinel_chunk(self, model, chunk, world, results, valid) -> None:
        reqs = [c[1] for c in chunk]
        system, prompt = build_sentinel_batch(reqs, world)
        self._batches_emitted += 1
        try:
            resp = await self._call_json(
                model, system=system, prompt=prompt, max_tokens=self.sentinel_tokens
            )
            split = split_sentinel_batch(resp, len(reqs))
        except Exception:  # noqa: BLE001
            split = [None] * len(reqs)
        for (idx, _req, key), raw in zip(chunk, split):
            if raw is None:
                results[idx] = self._fallback_decision("llm unavailable")
            else:
                dec = coerce_decision(raw, valid)
                results[idx] = dec
                if not dec["fallback"]:
                    self._cache.set(key, dec)

    async def reason(
        self, *, agent_id: int, context: dict, kind: str = "sentinel", valid_edges=None
    ) -> dict:
        """Single-agent convenience path (used by make_sentinel_provider)."""
        world = {
            "valid_edges": valid_edges or valid_edge_ids(),
            "congestion": context.get("congestion", {}) or {},
        }
        out = await self.reason_many([ReasonRequest(agent_id, context, kind)], world=world)
        return out[0]

    # ── hive distillation (batched) ──────────────────────────────────────
    async def distill_many(
        self, items: Sequence[tuple[str, str]], *, timestep: int, world: Optional[dict] = None
    ) -> Dict[str, CollectiveTruth]:
        """Distill CollectiveTruth for many segments. items = (segment, text)."""
        world = world or {}
        valid = world.get("valid_edges") or valid_edge_ids()
        world = {**world, "valid_edges": valid}
        segments = [seg for seg, _ in items]
        out: Dict[str, CollectiveTruth] = {}

        pool = self._healthy_pool([m for m in ("kimi", "gpt_oss", "qwen") if m in self.sentinel_pool] or self.sentinel_pool)
        if not pool:
            for seg in segments:
                out[seg] = coerce_truth(None, timestep, valid)
            return out

        for chunk in chunks(list(items), self.batch_size):
            model = pool[0]
            system, prompt = build_distill_batch(chunk, world)
            self._batches_emitted += 1
            try:
                resp = await self._call_json(
                    model, system=system, prompt=prompt, max_tokens=self.distill_tokens
                )
                mapped = split_distill_batch(resp, [s for s, _ in chunk])
            except Exception:  # noqa: BLE001
                mapped = {s: None for s, _ in chunk}
            for seg, _text in chunk:
                out[seg] = coerce_truth(mapped.get(seg), timestep, valid)
        return out

    async def distill(
        self, *, segment_name: str, discoveries_text: str, timestep: int, valid_edges=None
    ) -> CollectiveTruth:
        world = {"valid_edges": valid_edges or valid_edge_ids()}
        res = await self.distill_many([(segment_name, discoveries_text)], timestep=timestep, world=world)
        return res[segment_name]

    # ── one-off narrative / policy text ──────────────────────────────────
    async def reason_text(self, *, prompt: str, system: str = "", prefer: str = "gemini") -> str:
        candidates = [prefer] + [m for m in ("kimi", "gpt_oss", "qwen") if m != prefer]
        pool = self._healthy_pool(candidates) or ["kimi"]
        for model in pool:
            try:
                return await self._call_text(model, system=system, prompt=prompt, max_tokens=1200)
            except Exception:  # noqa: BLE001
                continue
        return ""

    # ── observability ────────────────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "per_provider": {
                m: {
                    "calls": self._quota[m].calls,
                    "errors": self._quota[m].errors,
                    "rate_limited": self._quota[m].rate_limited,
                    "circuit": self._breakers[m].state,
                }
                for m in _prov.PROVIDERS
            },
            "cache": self._cache.stats(),
            "batches": {
                "emitted": self._batches_emitted,
                "requests_in": self._requests_in,
                "cache_served": self._cache_served,
            },
            "config": {
                "concurrency": self.concurrency,
                "batch_size": self.batch_size,
                "sentinel_pool": self.sentinel_pool,
            },
        }


_GATEWAY: Optional[ReasoningGateway] = None


def get_gateway() -> ReasoningGateway:
    """Process-wide singleton (one gateway shares cache + breakers + buckets)."""
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = ReasoningGateway()
    return _GATEWAY


def reset_gateway() -> None:
    """Drop the singleton (tests)."""
    global _GATEWAY
    _GATEWAY = None
