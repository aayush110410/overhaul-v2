"""Real road networks for any region: OSM via Overpass, cached to disk forever.

Two-tier output per region:
  - **movement graph** (``nodes``/``edges``): every junction of the major road
    network with true street geometry — what agents drive on.
  - **corridor graph** (``corridors``): ≤ ~30 named, well-spaced junctions with
    aggregated edges — the small vocabulary handed to UrbanSwarm cognition and
    the TransportEngine (LLM prompts must never see thousands of raw OSM ids).

Overpass is hit at most once per region, ever (disk cache under
``data/roadnets/``). When Overpass is unreachable, NCR-family regions fall
back to the hand-curated default corridor graph from the transport engine;
other regions raise ``RoadNetworkUnavailable``.

Edge schema is a strict superset of the swarm/transport schema
``{u, v, dist_km, free_speed, capacity, lanes}``.
"""

from __future__ import annotations

import heapq
import json
import logging
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from engines.transport.engine import _DEFAULT_EDGES, _DEFAULT_NODES, _bpr_time
from world.region import RegionProfile

logger = logging.getLogger(__name__)

_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
_HEADERS = {"User-Agent": "OVERHAUL-LivingWorld/1.0"}
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "roadnets"

_FREE_SPEED = {  # km/h by highway class (before regional driving_style factor)
    "motorway": 80, "trunk": 70, "primary": 55,
    "secondary": 45, "tertiary": 35, "residential": 25,
}
_DEFAULT_LANES = {
    "motorway": 3, "trunk": 3, "primary": 2,
    "secondary": 2, "tertiary": 1, "residential": 1,
}
_CAPACITY_PER_LANE_VPH = 1800

_CORRIDOR_MAX_NODES = 30
_CORRIDOR_MIN_SPACING_KM = 0.8
_CORRIDOR_NEIGHBORS = 3

# Extent of the hand-curated NCR default graph (fallback eligibility).
_DEFAULT_EXTENT = (
    min(n["lon"] for n in _DEFAULT_NODES.values()),
    min(n["lat"] for n in _DEFAULT_NODES.values()),
    max(n["lon"] for n in _DEFAULT_NODES.values()),
    max(n["lat"] for n in _DEFAULT_NODES.values()),
)


class RoadNetworkUnavailable(RuntimeError):
    """No cached network, Overpass failed, and no fallback covers this region."""


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _polyline_km(coords: List[List[float]]) -> float:
    return sum(
        _haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(coords, coords[1:])
    )


def _parse_maxspeed(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    if not m:
        return None
    speed = int(m.group())
    return round(speed * 1.609) if "mph" in raw else speed


def _parse_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    return int(m.group()) if m else None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ── Overpass → graph ──


def parse_overpass(raw: Dict[str, Any], corridor_max: int = _CORRIDOR_MAX_NODES) -> Dict[str, Any]:
    """Parse an Overpass ``out geom`` payload into the two-tier road graph."""
    elements = raw.get("elements", [])
    ways = [
        el for el in elements
        if el.get("type") == "way" and el.get("tags", {}).get("highway")
    ]
    signal_ids = {
        el["id"] for el in elements
        if el.get("type") == "node"
        and el.get("tags", {}).get("highway") == "traffic_signals"
    }

    usage: Counter = Counter()
    for way in ways:
        usage.update(way.get("nodes", []))
    junctions: set = set()
    for way in ways:
        nids = way.get("nodes", [])
        if len(nids) < 2:
            continue
        junctions.add(nids[0])
        junctions.add(nids[-1])
        junctions.update(nid for nid in nids if usage[nid] >= 2)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    eid_counts: Counter = Counter()

    def add_node(nid: int, coord: List[float], way_name: str) -> None:
        key = str(nid)
        node = nodes.setdefault(
            key,
            {"lat": round(coord[1], 6), "lon": round(coord[0], 6),
             "signal": nid in signal_ids, "label": ""},
        )
        if way_name and way_name not in node["label"]:
            node["label"] = f"{node['label']} × {way_name}" if node["label"] else way_name

    def emit(u: str, v: str, coords: List[List[float]], attrs: Dict[str, Any]) -> None:
        dist = _polyline_km(coords)
        if u == v or dist <= 0:
            return
        eid = f"{u}->{v}"
        n = eid_counts[eid]
        eid_counts[eid] += 1
        edges.append(
            {
                "id": f"{eid}#{n}" if n else eid,
                "u": u,
                "v": v,
                "dist_km": round(dist, 4),
                "geometry": [[round(c[0], 5), round(c[1], 5)] for c in coords],
                **attrs,
            }
        )

    for way in ways:
        tags = way.get("tags", {})
        nids = way.get("nodes", [])
        geom = way.get("geometry", [])
        if len(nids) < 2 or len(nids) != len(geom):
            continue
        hw = tags["highway"].replace("_link", "")
        name = tags.get("name", "")
        attrs = {
            "free_speed": _parse_maxspeed(tags.get("maxspeed")) or _FREE_SPEED.get(hw, 40),
            "capacity": (_parse_int(tags.get("lanes")) or _DEFAULT_LANES.get(hw, 2))
            * _CAPACITY_PER_LANE_VPH,
            "lanes": _parse_int(tags.get("lanes")) or _DEFAULT_LANES.get(hw, 2),
            "highway": hw,
            "name": name,
        }
        oneway = tags.get("oneway") in ("yes", "1", "true")
        reverse_oneway = tags.get("oneway") == "-1"

        cur_u = nids[0]
        cur_coords = [[geom[0]["lon"], geom[0]["lat"]]]
        for i in range(1, len(nids)):
            cur_coords.append([geom[i]["lon"], geom[i]["lat"]])
            if nids[i] not in junctions:
                continue
            u, v = str(cur_u), str(nids[i])
            add_node(cur_u, cur_coords[0], name)
            add_node(nids[i], cur_coords[-1], name)
            if reverse_oneway:
                emit(v, u, list(reversed(cur_coords)), attrs)
            else:
                emit(u, v, list(cur_coords), attrs)
                if not oneway:
                    emit(v, u, list(reversed(cur_coords)), attrs)
            cur_u = nids[i]
            cur_coords = [cur_coords[-1]]

    return {
        "nodes": nodes,
        "edges": edges,
        "corridors": _build_corridors(nodes, edges, corridor_max),
    }


def _build_corridors(
    nodes: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    max_nodes: int,
) -> Dict[str, Any]:
    """Reduce the movement graph to a small, named cognition graph."""
    if not nodes:
        return {"nodes": {}, "edges": []}

    degree: Counter = Counter()
    for e in edges:
        degree[e["u"]] += 1
        degree[e["v"]] += 1
    ranked = sorted(nodes, key=lambda n: (-degree[n], n))

    chosen: List[str] = []
    for nid in ranked:
        if len(chosen) >= max_nodes:
            break
        p = nodes[nid]
        if all(
            _haversine_km(p["lon"], p["lat"], nodes[c]["lon"], nodes[c]["lat"])
            >= _CORRIDOR_MIN_SPACING_KM
            for c in chosen
        ):
            chosen.append(nid)
    if not chosen:
        chosen = ranked[:max_nodes]

    # Readable, unique corridor ids: street-name slug + raw node id.
    cid_of = {
        nid: f"{(_slug(nodes[nid]['label'])[:28] or 'j')}_{nid}" for nid in chosen
    }
    cnodes = {
        cid_of[nid]: {
            "lat": nodes[nid]["lat"],
            "lon": nodes[nid]["lon"],
            "label": nodes[nid]["label"] or f"Junction {nid}",
            "src": nid,
        }
        for nid in chosen
    }

    # Network distances between chosen nodes (Dijkstra by km over full graph).
    adj: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in edges:
        adj[e["u"]].append(e)

    def network_dists(src: str) -> Dict[str, Tuple[float, Dict[str, float]]]:
        dist = {src: 0.0}
        agg: Dict[str, Dict[str, float]] = {src: {"spd": 0.0, "cap": math.inf, "lanes": 0.0, "n": 0}}
        pq: List[Tuple[float, str]] = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, math.inf):
                continue
            for e in adj[u]:
                nd = d + e["dist_km"]
                if nd < dist.get(e["v"], math.inf):
                    dist[e["v"]] = nd
                    prev = agg[u]
                    agg[e["v"]] = {
                        "spd": prev["spd"] + e["free_speed"] * e["dist_km"],
                        "cap": min(prev["cap"], e["capacity"]),
                        "lanes": prev["lanes"] + e["lanes"] * e["dist_km"],
                        "n": prev["n"] + 1,
                    }
                    heapq.heappush(pq, (nd, e["v"]))
        return {n: (dist[n], agg[n]) for n in dist}

    cedges: List[Dict[str, Any]] = []
    seen_pairs: set = set()
    chosen_set = set(chosen)
    for nid in chosen:
        reach = network_dists(nid)
        neighbors = sorted(
            ((d, other) for other, (d, _) in reach.items()
             if other in chosen_set and other != nid and d > 0),
        )[:_CORRIDOR_NEIGHBORS]
        for d, other in neighbors:
            pair = (cid_of[nid], cid_of[other])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            _, agg = reach[other]
            spd = agg["spd"] / d if d else 40.0
            lanes = max(1, round(agg["lanes"] / d)) if d else 2
            cap = agg["cap"] if math.isfinite(agg["cap"]) else lanes * _CAPACITY_PER_LANE_VPH
            cedges.append(
                {
                    "u": pair[0], "v": pair[1],
                    "dist_km": round(d, 3),
                    "free_speed": round(spd, 1),
                    "capacity": int(cap),
                    "lanes": lanes,
                }
            )
    return {"nodes": cnodes, "edges": cedges}


# ── RoadNetwork ──


class RoadNetwork:
    """A region's drivable graph with routing, OD sampling and engine export."""

    def __init__(self, data: Dict[str, Any], key: str, fallback: bool = False):
        self.key = key
        self.fallback = fallback
        self.nodes: Dict[str, Dict[str, Any]] = data["nodes"]
        self.edges: List[Dict[str, Any]] = data["edges"]
        self.corridors: Dict[str, Any] = data["corridors"]
        self._adj: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for e in self.edges:
            self._adj[e["u"]].append(e)
        self._node_ids = sorted(self.nodes)

    # ── routing ──

    def _weight(self, edge: Dict[str, Any], congestion: Optional[Dict[str, float]]) -> float:
        flow = (congestion or {}).get(edge["id"], edge["capacity"] * 0.3)
        return _bpr_time(edge["dist_km"], edge["free_speed"], edge["capacity"], flow)

    def _dijkstra(
        self, origin: str, destination: str, congestion: Optional[Dict[str, float]]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        dist: Dict[str, float] = {origin: 0.0}
        prev: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        pq: List[Tuple[float, str]] = [(0.0, origin)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == destination:
                break
            if d > dist.get(u, math.inf):
                continue
            for e in self._adj[u]:
                nd = d + self._weight(e, congestion)
                if nd < dist.get(e["v"], math.inf):
                    dist[e["v"]] = nd
                    prev[e["v"]] = (u, e)
                    heapq.heappush(pq, (nd, e["v"]))
        if destination not in dist:
            return math.inf, []
        path: List[Dict[str, Any]] = []
        node = destination
        while node != origin:
            u, e = prev[node]
            path.append(e)
            node = u
        path.reverse()
        return dist[destination], path

    def route(
        self, origin: str, destination: str, congestion: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """Fastest edge sequence origin→destination under current congestion."""
        return self._dijkstra(origin, destination, congestion)[1]

    def route_time(
        self, origin: str, destination: str, congestion: Optional[Dict[str, float]] = None
    ) -> float:
        """Fastest travel time in minutes (inf if unreachable)."""
        return self._dijkstra(origin, destination, congestion)[0]

    # ── sampling / export ──

    def sample_od(self, rng, min_km: float = 1.0) -> Tuple[str, str]:
        """Random origin/destination pair, preferring trips ≥ ``min_km`` apart."""
        for _ in range(30):
            o, d = rng.choice(self._node_ids), rng.choice(self._node_ids)
            if o == d:
                continue
            a, b = self.nodes[o], self.nodes[d]
            if _haversine_km(a["lon"], a["lat"], b["lon"], b["lat"]) >= min_km:
                return o, d
        while True:
            o, d = rng.choice(self._node_ids), rng.choice(self._node_ids)
            if o != d:
                return o, d

    def to_engine_graph(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Corridor graph in the UrbanSwarm/TransportEngine schema."""
        cnodes = {
            cid: {"lat": n["lat"], "lon": n["lon"], "label": n["label"]}
            for cid, n in self.corridors["nodes"].items()
        }
        cedges = [
            {k: e[k] for k in ("u", "v", "dist_km", "free_speed", "capacity", "lanes")}
            for e in self.corridors["edges"]
        ]
        return cnodes, cedges

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": self.nodes, "edges": self.edges, "corridors": self.corridors}

    # ── loading ──

    @classmethod
    async def load(
        cls,
        profile: RegionProfile,
        cache_dir: Optional[Path] = None,
        max_radius_km: float = 8.0,
        force_refresh: bool = False,
    ) -> "RoadNetwork":
        cache_root = Path(cache_dir) if cache_dir else _CACHE_DIR
        cache = cache_root / f"{profile.key}.json"
        if cache.exists() and not force_refresh:
            return cls(json.loads(cache.read_text()), profile.key)

        bbox = _clip_bbox(profile, max_radius_km)
        try:
            raw = await cls._fetch_overpass(bbox)
            data = parse_overpass(raw)
            if not data["edges"]:
                raise RoadNetworkUnavailable(f"no drivable roads found for {profile.key}")
        except Exception as exc:
            if _overlaps_default_extent(profile.bbox):
                logger.warning(
                    "Overpass unavailable for %s (%s); using default NCR graph",
                    profile.key, exc,
                )
                return cls(cls._fallback_data(), profile.key, fallback=True)
            raise RoadNetworkUnavailable(
                f"road network unavailable for {profile.key}: {exc}"
            ) from exc

        cache_root.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
        logger.info(
            "roadnet %s: %d nodes / %d edges cached to %s",
            profile.key, len(data["nodes"]), len(data["edges"]), cache,
        )
        return cls(data, profile.key)

    @staticmethod
    async def _fetch_overpass(bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
        w, s, e, n = bbox
        query = (
            "[out:json][timeout:25];("
            f'way["highway"~"^(motorway|trunk|primary|secondary|tertiary)(_link)?$"]'
            f"({s},{w},{n},{e});"
            f'node["highway"="traffic_signals"]({s},{w},{n},{e});'
            ");out geom;"
        )
        last_exc: Optional[Exception] = None
        for url in _OVERPASS_ENDPOINTS:
            try:
                async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
                    resp = await client.post(url, data={"data": query})
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:  # try the mirror before giving up
                logger.warning("Overpass endpoint %s failed: %s", url, exc)
                last_exc = exc
        raise RoadNetworkUnavailable(f"all Overpass endpoints failed: {last_exc}")

    @staticmethod
    def _fallback_data() -> Dict[str, Any]:
        """Default NCR corridor graph in roadnet schema (offline safety net)."""
        nodes = {
            nid: {"lat": n["lat"], "lon": n["lon"], "signal": False, "label": n["label"]}
            for nid, n in _DEFAULT_NODES.items()
        }
        eid_counts: Counter = Counter()
        edges = []
        for e in _DEFAULT_EDGES:
            eid = f"{e['u']}->{e['v']}"
            n = eid_counts[eid]
            eid_counts[eid] += 1
            u, v = _DEFAULT_NODES[e["u"]], _DEFAULT_NODES[e["v"]]
            edges.append(
                {
                    "id": f"{eid}#{n}" if n else eid,
                    "u": e["u"], "v": e["v"],
                    "dist_km": e["dist_km"], "free_speed": e["free_speed"],
                    "capacity": e["capacity"], "lanes": e["lanes"],
                    "highway": "primary", "name": "",
                    "geometry": [[u["lon"], u["lat"]], [v["lon"], v["lat"]]],
                }
            )
        corridors = {
            "nodes": {
                nid: {"lat": n["lat"], "lon": n["lon"], "label": n["label"], "src": nid}
                for nid, n in _DEFAULT_NODES.items()
            },
            "edges": [
                {k: e[k] for k in ("u", "v", "dist_km", "free_speed", "capacity", "lanes")}
                for e in _DEFAULT_EDGES
            ],
        }
        return {"nodes": nodes, "edges": edges, "corridors": corridors}


def _clip_bbox(profile: RegionProfile, max_radius_km: float) -> Tuple[float, float, float, float]:
    """Profile bbox clipped to ``max_radius_km`` around its center (Overpass size cap)."""
    lon_c, lat_c = profile.center
    w, s, e, n = profile.bbox
    half_lat = min((n - s) / 2, max_radius_km / 111.0)
    half_lon = min(
        (e - w) / 2,
        max_radius_km / (111.0 * max(math.cos(math.radians(lat_c)), 0.2)),
    )
    return (
        round(lon_c - half_lon, 5), round(lat_c - half_lat, 5),
        round(lon_c + half_lon, 5), round(lat_c + half_lat, 5),
    )


def _overlaps_default_extent(bbox: List[float]) -> bool:
    w, s, e, n = bbox
    dw, ds, de, dn = _DEFAULT_EXTENT
    return not (e < dw or de < w or n < ds or dn < s)
