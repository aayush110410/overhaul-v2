"""Tests for world.movement — per-agent kinematics on the road graph."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from world.movement import MovementSim, signal_is_red
from world.region import RegionProfile
from world.roadnet import RoadNetwork, parse_overpass
from world.weather import WeatherState

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_sample.json"
REGIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions"

HEAVY_RAIN = WeatherState("heavy_rain", 95, 14.0, 20, 24, 3000, "test")


def _net() -> RoadNetwork:
    return RoadNetwork(parse_overpass(json.loads(FIXTURE.read_text())), key="fixture")


def _profile() -> RegionProfile:
    return RegionProfile.from_dict(json.loads((REGIONS_DIR / "noida.json").read_text()))


def _cars(n: int) -> list:
    return [{"mode": "car", "agent_class": 0, "segment": "office_workers"} for _ in range(n)]


def _sim(agents, **kwargs) -> MovementSim:
    kwargs.setdefault("stagger_s", 0.0)
    return MovementSim(_net(), _profile(), agents, seed=42, **kwargs)


def _run(sim: MovementSim, seconds: float, dt: float = 1.0):
    t = 0.0
    while t < seconds:
        sim.tick(dt)
        t += dt


# ── signal phase helper ──


def test_signal_is_red_deterministic_duty_cycle():
    reds = sum(signal_is_red("2", s, cycle_s=120, green_split=0.45) for s in range(1200))
    assert 0.45 < reds / 1200 < 0.65  # ~55% red
    assert signal_is_red("2", 10.0, 120, 0.45) == signal_is_red("2", 10.0, 120, 0.45)


# ── kinematics ──


def test_agent_advances_at_expected_speed():
    sim = _sim(_cars(1))
    agent = sim.agents[0]
    start = (agent.lon, agent.lat)
    _run(sim, 30)
    assert (agent.lon, agent.lat) != start
    assert agent.speed_kmh > 0
    # Traveled distance ≈ mean speed × time (within signal/step tolerance).
    assert sim.distance_traveled_km(agent) <= (agent.speed_kmh * 30 / 3600) * 3 + 0.05


def test_walk_mode_ignores_road_speed():
    sim = _sim([{"mode": "walk", "agent_class": 0, "segment": "students"}])
    _run(sim, 10)
    assert 0 < sim.agents[0].speed_kmh <= 5.5


def test_congestion_slows_shared_route():
    solo = _sim(_cars(1), route_pool_size=1)
    crowded = _sim(_cars(250), route_pool_size=1)
    _run(solo, 20)
    _run(crowded, 20)
    en_route = [a for a in crowded.agents if a.state in ("moving", "congested")]
    assert en_route, "expected en-route agents in the crowd"
    assert max(a.speed_kmh for a in en_route) < solo.agents[0].speed_kmh


def test_rain_slows_agents():
    dry = _sim(_cars(1))
    wet = _sim(_cars(1))
    wet.set_weather(HEAVY_RAIN)
    _run(dry, 20)
    _run(wet, 20)
    assert wet.agents[0].speed_kmh < dry.agents[0].speed_kmh


def test_signals_queue_agents_eventually():
    # Node 2 is signalized; with a 120s cycle some agent must hit a red phase.
    sim = _sim(_cars(40), route_pool_size=4)
    saw_queued = False
    for _ in range(600):
        sim.tick(1.0)
        if any(a.state == "queued" and a.speed_kmh == 0 for a in sim.agents):
            saw_queued = True
            break
    assert saw_queued


def test_agents_arrive_and_stay():
    sim = _sim(_cars(5))
    _run(sim, 3600, dt=2.0)
    assert all(a.state == "arrived" for a in sim.agents)
    a = sim.agents[0]
    dest = sim.roadnet.nodes[a.dest]
    assert abs(a.lon - dest["lon"]) < 1e-3 and abs(a.lat - dest["lat"]) < 1e-3


def test_seeded_determinism():
    s1, s2 = _sim(_cars(30)), _sim(_cars(30))
    _run(s1, 120)
    _run(s2, 120)
    for a, b in zip(s1.agents, s2.agents):
        assert (a.lon, a.lat, a.state, a.edge_i) == (b.lon, b.lat, b.state, b.edge_i)


# ── aggregates ──


def test_edge_occupancy_counts_match_agents():
    sim = _sim(_cars(50))
    _run(sim, 30)
    occ = sim.edge_occupancy()
    en_route = [a for a in sim.agents if a.state != "arrived"]
    assert sum(occ.values()) == len(en_route)


def test_corridor_congestion_shape():
    sim = _sim(_cars(100))
    _run(sim, 60)
    cong = sim.corridor_congestion()
    corridor_ids = {f"{e['u']}->{e['v']}" for e in sim.roadnet.corridors["edges"]}
    assert set(cong) == corridor_ids
    assert all(0.0 <= v <= 5.0 for v in cong.values())
