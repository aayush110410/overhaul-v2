"""Tests for world.roadnet — OSM road networks with disk cache + NCR fallback."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from world.region import RegionProfile
from world.roadnet import RoadNetwork, RoadNetworkUnavailable, parse_overpass

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_sample.json"
REGIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions"


def _profile(key: str) -> RegionProfile:
    return RegionProfile.from_dict(json.loads((REGIONS_DIR / f"{key}.json").read_text()))


def _fixture_data() -> dict:
    return parse_overpass(json.loads(FIXTURE.read_text()))


# ── Overpass parsing ──


def test_parse_overpass_schema():
    data = _fixture_data()
    assert set(data) >= {"nodes", "edges", "corridors"}
    for node in data["nodes"].values():
        assert {"lat", "lon", "signal", "label"} <= set(node)
    for edge in data["edges"]:
        assert {"u", "v", "dist_km", "free_speed", "capacity", "lanes",
                "highway", "name", "geometry", "id"} <= set(edge)
        assert edge["dist_km"] > 0
        assert edge["capacity"] > 0
        assert len(edge["geometry"]) >= 2


def test_parse_junctions_and_interior_folding():
    data = _fixture_data()
    # Node 7 is interior to MG Road (not shared, not an endpoint) — folded into geometry.
    assert "7" not in data["nodes"]
    edge_23 = next(e for e in data["edges"] if e["u"] == "2" and e["v"] == "3")
    assert len(edge_23["geometry"]) == 3  # 2 → 7 → 3


def test_parse_signals_detected():
    data = _fixture_data()
    assert data["nodes"]["2"]["signal"] is True
    assert data["nodes"]["1"]["signal"] is False


def test_parse_oneway_and_bidirectional():
    data = _fixture_data()
    pairs = {(e["u"], e["v"]) for e in data["edges"]}
    assert ("1", "2") in pairs and ("2", "1") in pairs  # bidirectional primary
    assert ("3", "6") in pairs and ("6", "3") not in pairs  # oneway trunk


def test_parse_speed_and_lanes_tags():
    data = _fixture_data()
    edge_12 = next(e for e in data["edges"] if e["u"] == "1" and e["v"] == "2")
    assert edge_12["free_speed"] == 60  # maxspeed tag wins over class default
    assert edge_12["lanes"] == 3
    edge_42 = next(e for e in data["edges"] if e["u"] == "4" and e["v"] == "2")
    assert edge_42["free_speed"] == 45  # secondary class default


def test_corridor_graph_bounded_and_labeled():
    data = _fixture_data()
    cnodes, cedges = data["corridors"]["nodes"], data["corridors"]["edges"]
    assert 1 <= len(cnodes) <= 40
    assert all("label" in n for n in cnodes.values())
    for e in cedges:
        assert e["u"] in cnodes and e["v"] in cnodes
        assert {"dist_km", "free_speed", "capacity", "lanes"} <= set(e)


# ── Network operations ──


def _network() -> RoadNetwork:
    return RoadNetwork(_fixture_data(), key="fixture")


def test_route_returns_connected_edges():
    net = _network()
    route = net.route("1", "6")
    assert route, "expected a path 1→6"
    assert route[0]["u"] == "1" and route[-1]["v"] == "6"
    for a, b in zip(route, route[1:]):
        assert a["v"] == b["u"]


def test_route_respects_congestion():
    net = _network()
    base = net.route("4", "5")
    jammed = {e["id"]: e["capacity"] * 3.0 for e in base}
    alt_time = net.route_time("4", "5", congestion=jammed)
    assert alt_time > net.route_time("4", "5")


def test_sample_od_distinct_and_seeded():
    net = _network()
    rng = random.Random(42)
    pairs = [net.sample_od(rng) for _ in range(5)]
    assert all(o != d for o, d in pairs)
    rng2 = random.Random(42)
    assert pairs == [net.sample_od(rng2) for _ in range(5)]


def test_to_engine_graph_matches_transport_schema():
    nodes, edges = _network().to_engine_graph()
    for node in nodes.values():
        assert {"lat", "lon", "label"} <= set(node)
    for e in edges:
        assert {"u", "v", "dist_km", "free_speed", "capacity", "lanes"} <= set(e)


# ── load(): cache + fallback ──


@pytest.mark.asyncio
async def test_load_caches_to_disk(tmp_path, monkeypatch):
    calls = []

    async def fake_fetch(bbox):
        calls.append(bbox)
        return json.loads(FIXTURE.read_text())

    monkeypatch.setattr(RoadNetwork, "_fetch_overpass", staticmethod(fake_fetch))
    profile = _profile("noida")

    net1 = await RoadNetwork.load(profile, cache_dir=tmp_path)
    assert (tmp_path / "noida.json").exists()
    assert len(calls) == 1

    net2 = await RoadNetwork.load(profile, cache_dir=tmp_path)
    assert len(calls) == 1  # served from cache, no second fetch
    assert {e["id"] for e in net2.edges} == {e["id"] for e in net1.edges}


@pytest.mark.asyncio
async def test_load_ncr_fallback_when_overpass_down(tmp_path, monkeypatch):
    async def dead_fetch(bbox):
        raise TimeoutError("overpass down")

    monkeypatch.setattr(RoadNetwork, "_fetch_overpass", staticmethod(dead_fetch))
    net = await RoadNetwork.load(_profile("ncr"), cache_dir=tmp_path)
    assert len(net.nodes) >= 10  # the default NCR corridor graph
    assert net.fallback is True


@pytest.mark.asyncio
async def test_load_non_ncr_raises_when_overpass_down(tmp_path, monkeypatch):
    async def dead_fetch(bbox):
        raise TimeoutError("overpass down")

    monkeypatch.setattr(RoadNetwork, "_fetch_overpass", staticmethod(dead_fetch))
    with pytest.raises(RoadNetworkUnavailable):
        await RoadNetwork.load(_profile("new_york"), cache_dir=tmp_path)
