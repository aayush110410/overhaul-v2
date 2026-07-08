"""UrbanSwarm must work on injected (non-NCR) graphs, not just _DEFAULT_NODES.

Regression for the Living World integration: before the fix, `_valid_edges`
was overwritten with the NCR-frozen `reasoning.valid_edge_ids()` and sentinel
coords were resolved via the NCR-only `reasoning.node_coords()`, so on any
injected road graph every sentinel silently vanished from `build_hive_state()`
and the geojson came out empty.
"""

from __future__ import annotations

import pytest

from engines.agent_simulation.config import SwarmConfig
from engines.agent_simulation.swarm import UrbanSwarm

SYNTH_NODES = {
    "alpha": {"lat": 10.0, "lon": 20.0, "label": "Alpha"},
    "beta": {"lat": 10.1, "lon": 20.1, "label": "Beta"},
    "gamma": {"lat": 10.2, "lon": 20.0, "label": "Gamma"},
    "delta": {"lat": 10.3, "lon": 20.2, "label": "Delta"},
}


def _edges() -> list:
    base = [
        {"u": "alpha", "v": "beta", "dist_km": 5.0, "free_speed": 50, "capacity": 3000, "lanes": 2},
        {"u": "beta", "v": "gamma", "dist_km": 4.0, "free_speed": 45, "capacity": 2500, "lanes": 2},
        {"u": "gamma", "v": "delta", "dist_km": 6.0, "free_speed": 55, "capacity": 3500, "lanes": 3},
        {"u": "alpha", "v": "gamma", "dist_km": 7.5, "free_speed": 60, "capacity": 4000, "lanes": 3},
    ]
    return base + [{**e, "u": e["v"], "v": e["u"]} for e in base]


def _cfg() -> SwarmConfig:
    return SwarmConfig(commuter_count=30, freight_count=5, timesteps=2)


@pytest.mark.asyncio
async def test_injected_graph_yields_sentinels_and_geojson():
    swarm = UrbanSwarm(nodes=SYNTH_NODES, edges=_edges(), config=_cfg())
    swarm.sentinel_count_per_segment = 1
    await swarm.initialize()

    state = swarm.build_hive_state()
    assert state["sentinels"], "sentinels must not vanish on injected graphs"
    coords_set = {(n["lon"], n["lat"]) for n in SYNTH_NODES.values()}
    for s in state["sentinels"]:
        assert tuple(s["coords"]) in coords_set

    features = state["geojson"]["features"]
    assert features, "geojson must not be empty on injected graphs"
    for f in features:
        for coord in f["geometry"]["coordinates"]:
            assert tuple(coord) in coords_set


@pytest.mark.asyncio
async def test_valid_edges_derived_from_injected_graph():
    swarm = UrbanSwarm(nodes=SYNTH_NODES, edges=_edges(), config=_cfg())
    await swarm.initialize()
    assert swarm._valid_edges == {f"{e['u']}->{e['v']}" for e in _edges()}


@pytest.mark.asyncio
async def test_physics_timestep_routes_on_injected_graph():
    # Regression: the sentinel physics fallback used to route on the hardcoded
    # NCR graph, KeyError-ing on injected node ids.
    swarm = UrbanSwarm(nodes=SYNTH_NODES, edges=_edges(), config=_cfg())
    swarm.sentinel_count_per_segment = 1
    await swarm.initialize()
    weights = {
        "congestion_memory_weight": swarm.config.congestion_memory_weight,
        "peer_influence_weight": swarm.config.peer_influence_weight,
    }
    ts = await swarm._run_timestep_hive(step=0, config_weights=weights)
    assert ts.sentinel_discoveries == len(swarm.sentinel_agents)
    for s in swarm.sentinel_agents:
        dec = s.last_decision
        assert dec is not None and dec["fallback"] is True
        if dec.get("route"):
            u, v = dec["route"].split("->")
            assert u in SYNTH_NODES and v in SYNTH_NODES


@pytest.mark.asyncio
async def test_default_graph_output_unchanged():
    from reasoning import valid_edge_ids

    swarm = UrbanSwarm(config=_cfg())
    swarm.sentinel_count_per_segment = 1
    await swarm.initialize()

    # Identical LLM edge vocabulary as the frozen NCR set — no behavior change.
    assert swarm._valid_edges == valid_edge_ids()
    state = swarm.build_hive_state()
    assert state["sentinels"]
    assert state["geojson"]["features"]
