"""Tests for hive→movement feedback: CollectiveTruth re-routes the swarm."""

from __future__ import annotations

import json
import random
from pathlib import Path

from world.movement import MovementSim
from world.region import RegionProfile
from world.roadnet import RoadNetwork

REGIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions"


def _square_net() -> RoadNetwork:
    """a→d has two paths: fast via b (1.6 km) and slow via c (2.4 km)."""
    nodes = {
        "a": {"lat": 28.500, "lon": 77.300, "signal": False, "label": "A"},
        "b": {"lat": 28.500, "lon": 77.310, "signal": False, "label": "B"},
        "c": {"lat": 28.510, "lon": 77.300, "signal": False, "label": "C"},
        "d": {"lat": 28.510, "lon": 77.310, "signal": False, "label": "D"},
    }

    def edge(u, v, dist):
        return {
            "id": f"{u}->{v}", "u": u, "v": v, "dist_km": dist,
            "free_speed": 40, "capacity": 3600, "lanes": 2,
            "highway": "primary", "name": "",
            "geometry": [
                [nodes[u]["lon"], nodes[u]["lat"]],
                [nodes[v]["lon"], nodes[v]["lat"]],
            ],
        }

    edges = [
        edge("a", "b", 0.8), edge("b", "a", 0.8),
        edge("b", "d", 0.8), edge("d", "b", 0.8),
        edge("a", "c", 1.2), edge("c", "a", 1.2),
        edge("c", "d", 1.2), edge("d", "c", 1.2),
    ]
    corridors = {
        "nodes": {k: {**v, "src": k} for k, v in nodes.items()},
        "edges": [
            {"u": "a", "v": "b", "dist_km": 0.8, "free_speed": 40, "capacity": 3600, "lanes": 2},
            {"u": "b", "v": "d", "dist_km": 0.8, "free_speed": 40, "capacity": 3600, "lanes": 2},
        ],
    }
    return RoadNetwork({"nodes": nodes, "edges": edges, "corridors": corridors}, key="square")


def _profile() -> RegionProfile:
    return RegionProfile.from_dict(json.loads((REGIONS_DIR / "noida.json").read_text()))


def test_avoid_zone_reroutes_swarm_off_member_edges():
    net = _square_net()
    sim = MovementSim(
        net, _profile(),
        [{"mode": "car", "agent_class": 0, "segment": "office_workers"} for _ in range(40)],
        seed=1, stagger_s=0.0, route_pool_size=40,
    )
    # Pin every agent onto the fast a→b→d path so the avoid-zone must bite.
    fast = net.route("a", "d")
    assert [e["id"] for e in fast] == ["a->b", "b->d"]
    for agent in sim.agents:
        agent.route = list(fast)
        agent.origin, agent.dest = "a", "d"
        agent.edge_i = 0
        agent.progress_km = 0.0
    sim._corridor_members = {"a->b": ["a->b"], "b->d": ["b->d"]}
    sim.tick(1.0)

    rerouted = sim.apply_hive_truths(preferred=set(), avoid={"b->d"}, fraction=1.0,
                                     rng=random.Random(3))
    assert rerouted > 0
    for agent in sim.agents:
        remaining = [e["id"] for e in agent.route[agent.edge_i + 1:]]
        assert "b->d" not in remaining  # everyone detours via b→a→c→d
        assert agent.dest == "d"


def test_no_truths_is_a_noop():
    net = _square_net()
    sim = MovementSim(
        net, _profile(),
        [{"mode": "car", "agent_class": 0, "segment": "office_workers"}],
        seed=1, stagger_s=0.0, route_pool_size=4,
    )
    assert sim.apply_hive_truths(set(), set(), fraction=1.0) == 0
