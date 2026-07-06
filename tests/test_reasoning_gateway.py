"""Deterministic (offline) tests for the ReasoningGateway + the real hive loop.

These never touch the network — ``reasoning.providers.call_json`` is monkeypatched —
so they are the load-bearing guarantee that the cognition is genuinely LLM-driven
(sentinels reason, brains distill real edge IDs, the swarm inherits them), and that
the free-tier survival kit (batching, cache/trigger-gate, circuit breaker) behaves.
"""
import asyncio

import pytest

import reasoning.providers as prov
from reasoning.adapters import coerce_decision, coerce_truth, valid_edge_ids
from reasoning.gateway import ReasoningGateway, ReasonRequest

VALID = sorted(valid_edge_ids())


# ── coercion (the anti-theater guard) ────────────────────────────────────
def test_coercion_drops_out_of_vocab_and_clamps():
    d = coerce_decision(
        {"route": ["connaught_place->ito", "FAKE->ROUTE"], "avoid": ["ito->noida_sec18"],
         "mood": "angry", "confidence": 5}, frozenset(VALID))
    assert d["route"] == ["connaught_place->ito"]      # FAKE dropped
    assert d["avoid"] == ["ito->noida_sec18"]
    assert d["mood"] == "stable"                         # invalid mood -> default
    assert d["confidence"] == 1.0 and d["fallback"] is False

    t = coerce_truth({"preferred_routes": ["ito->noida_sec18", "junk"],
                      "segment_mood": "frustrated", "confidence": 0.7}, 3, frozenset(VALID))
    assert t.preferred_routes == ["ito->noida_sec18"] and t.segment_mood == "frustrated"


# ── batching + cache/trigger-gate ────────────────────────────────────────
@pytest.mark.asyncio
async def test_batching_and_cache(monkeypatch):
    calls = {"n": 0}

    async def fake(model, *, prompt, system, max_output_tokens):
        calls["n"] += 1
        n = prompt.count("i=")
        return {"decisions": [{"i": i, "route": [VALID[0]], "avoid": [], "mood": "adaptive",
                               "confidence": 0.6, "why": "x"} for i in range(n)]}

    monkeypatch.setattr(prov, "call_json", fake)
    gw = ReasoningGateway(batch_size=8, sentinel_pool=["qwen", "kimi", "gpt_oss"])
    reqs = [ReasonRequest(1000 + i, {"segment": "office_workers", "origin": "connaught_place",
                                     "destination": "noida_sec18", "mood": "stable", "preferred": []})
            for i in range(20)]
    world = {"valid_edges": frozenset(VALID), "congestion": {VALID[0]: 0.9}}
    out = await gw.reason_many(reqs, world=world)
    assert len(out) == 20 and all(o["route"] == [VALID[0]] for o in out)
    assert calls["n"] <= 6                       # 20 coalesced into <=6 batched calls
    before = calls["n"]
    await gw.reason_many(reqs, world=world)      # identical -> all cached
    assert calls["n"] == before
    assert gw.stats()["cache"]["hits"] >= 20


# ── circuit breaker -> physics fallback ──────────────────────────────────
@pytest.mark.asyncio
async def test_breaker_degrades_to_fallback(monkeypatch):
    async def boom(model, *, prompt, system, max_output_tokens):
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr(prov, "call_json", boom)
    gw = ReasoningGateway(batch_size=8, sentinel_pool=["qwen", "kimi", "gpt_oss"])
    reqs = [ReasonRequest(2000 + i, {"segment": "students", "origin": "ito",
                                     "destination": "greater_noida", "mood": "stable", "preferred": []})
            for i in range(10)]
    out = await gw.reason_many(reqs, world={"valid_edges": frozenset(VALID), "congestion": {}})
    assert len(out) == 10 and all(o["fallback"] for o in out)   # never hangs, always completes


# ── the full hive loop is genuinely LLM-driven (offline) ─────────────────
@pytest.mark.asyncio
async def test_hive_loop_real_cognition(monkeypatch):
    async def fake(model, *, prompt, system, max_output_tokens):
        if "Hive distiller" in system:
            segs = [ln.split("segment=")[1].strip() for ln in prompt.split("\n") if "segment=" in ln]
            return {"truths": [{"segment": s, "preferred_routes": VALID, "avoid_zones": [],
                                "segment_mood": "adaptive", "confidence": 0.66,
                                "dissenting_signals": []} for s in segs]}
        n = prompt.count("i=")
        return {"decisions": [{"i": i, "route": [VALID[0]], "avoid": [], "mood": "frustrated",
                               "confidence": 0.7, "why": "congested"} for i in range(n)]}

    monkeypatch.setattr(prov, "call_json", fake)
    from engines.agent_simulation.swarm import UrbanSwarm
    from engines.agent_simulation.config import get_agent_sim_config
    import copy

    cfg = copy.deepcopy(get_agent_sim_config().swarm)
    cfg.commuter_count = 200
    cfg.freight_count = 20
    cfg.timesteps = 3
    sw = UrbanSwarm(config=cfg)
    sw.enable_llm = True
    sw.sentinel_count_per_segment = 2
    await sw.initialize()
    res = await sw.run()

    assert sum(t.sentinel_discoveries for t in res.timesteps) > 0      # sentinels reasoned
    assert sum(t.swarm_inherited_routes for t in res.timesteps) > 0    # truth bit the swarm
    truths = [b.get_current_truth() for b in sw.segment_brains.values()]
    assert all(t and t.preferred_routes for t in truths)              # real edge-id truth, all 7
    state = sw.build_hive_state()
    assert len(state["brains"]) == 7 and len(state["sentinels"]) == 14
    assert state["sentinels"][0]["coords"] and len(state["geojson"]["features"]) > 0
