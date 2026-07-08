"""Per-agent movement on real road geometry — the beating heart of the map.

Every agent (all sentinels + the whole swarm) is a ``MovingAgent`` advancing
along cached Dijkstra routes each tick. Speed on an edge is::

    free_speed × regional driving factor × BPR congestion factor(live occupancy)
    × mode factor × weather factor

with hard stops at red signals (deterministic per-node phase offsets) and bus
halts. ``tick()`` is pure computation — no I/O, no LLM, O(agents) — so a 10 Hz
loop over 2000 agents stays cheap.

Route strategy (token/CPU efficiency): ~``route_pool_size`` OD pairs are
Dijkstra'd ONCE at init and agents are distributed across them with staggered
departures — never a per-agent per-tick shortest path.
"""

from __future__ import annotations

import bisect
import math
import random
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from world.region import RegionProfile
from world.roadnet import RoadNetwork, _haversine_km
from world.weather import WeatherProvider, WeatherState

_BPR_ALPHA = 0.15
_BPR_BETA = 4.0
_NEAR_CAPACITY_VEH_PER_KM_LANE = 40.0  # occupancy → flow/capacity proxy

_MODE_FACTOR = {"car": 1.0, "two_wheeler": 1.05, "auto": 0.80, "bus": 0.70, "freight": 0.85}
_WALK_SPEED_KMH = 4.7
_BUS_STOP_EVERY_KM = 0.5
_BUS_STOP_S = 25.0
_MIN_MOVING_SPEED_KMH = 3.0
_CONGESTED_RATIO = 0.5  # state="congested" below this fraction of free speed


def signal_is_red(node_id: str, sim_s: float, cycle_s: float, green_split: float) -> bool:
    """Deterministic fixed-cycle signal phase (per-node offset from a stable hash)."""
    if cycle_s <= 0:
        return False
    offset = zlib.crc32(node_id.encode()) % int(cycle_s)
    return (sim_s + offset) % cycle_s > green_split * cycle_s


@dataclass
class MovingAgent:
    idx: int
    agent_class: int  # 0 swarm, 1 sentinel
    mode: str
    segment: str
    origin: str
    dest: str
    route: List[Dict[str, Any]]
    depart_s: float = 0.0
    edge_i: int = 0
    progress_km: float = 0.0
    lon: float = 0.0
    lat: float = 0.0
    bearing: float = 0.0
    speed_kmh: float = 0.0
    state: str = "queued"  # queued | moving | congested | arrived
    _bus_next_stop_km: float = field(default=_BUS_STOP_EVERY_KM, repr=False)
    _halt_until_s: float = field(default=-1.0, repr=False)


class MovementSim:
    """Advances every agent along real streets under live congestion/weather."""

    def __init__(
        self,
        roadnet: RoadNetwork,
        profile: RegionProfile,
        agents: List[Dict[str, Any]],
        seed: int = 42,
        start_clock: Optional[datetime] = None,
        route_pool_size: int = 120,
        stagger_s: Optional[float] = None,
    ):
        self.roadnet = roadnet
        self.profile = profile
        self.sim_s = 0.0
        self._weather_factor = 1.0
        self._drive_factor = float(profile.driving_style.get("speed_factor", 1.0))
        self._cycle_s = float(profile.signals.get("avg_cycle_s", 100))
        self._green_split = float(profile.signals.get("green_split", 0.5))
        rng = random.Random(seed)

        # Cumulative-km index of each edge's geometry (position interpolation).
        self._edge_cum: Dict[str, List[float]] = {}
        for e in roadnet.edges:
            cum = [0.0]
            for a, b in zip(e["geometry"], e["geometry"][1:]):
                cum.append(cum[-1] + _haversine_km(a[0], a[1], b[0], b[1]))
            self._edge_cum[e["id"]] = cum

        # Route pool: Dijkstra once per OD pair, agents share with jitter.
        pool: List[List[Dict[str, Any]]] = []
        attempts = 0
        while len(pool) < route_pool_size and attempts < route_pool_size * 4:
            attempts += 1
            o, d = roadnet.sample_od(rng)
            route = roadnet.route(o, d)
            if route:
                pool.append(route)
        if not pool:
            raise ValueError(f"road network {roadnet.key!r} yielded no routable OD pairs")

        max_stagger = stagger_s if stagger_s is not None else self._default_stagger(start_clock)
        self.agents: List[MovingAgent] = []
        for i, spec in enumerate(agents):
            route = pool[i % len(pool)]
            agent = MovingAgent(
                idx=i,
                agent_class=int(spec.get("agent_class", 0)),
                mode=spec.get("mode", "car"),
                segment=spec.get("segment", ""),
                origin=route[0]["u"],
                dest=route[-1]["v"],
                route=route,
                depart_s=rng.uniform(0.0, max_stagger) if max_stagger > 0 else 0.0,
            )
            agent.lon, agent.lat = route[0]["geometry"][0]
            self.agents.append(agent)

        # Static full-edge → corridor-edge assignment for congestion aggregation.
        self._occupancy: Dict[str, int] = {}
        self._corridor_members: Dict[str, List[str]] = self._assign_corridor_members()

    def _default_stagger(self, start_clock: Optional[datetime]) -> float:
        hour = (start_clock or datetime.now()).hour
        in_rush = any(lo <= hour < hi for lo, hi in self.profile.rush_hours)
        return 900.0 if in_rush else 2700.0

    def _assign_corridor_members(self) -> Dict[str, List[str]]:
        cnodes = self.roadnet.corridors["nodes"]
        members: Dict[str, List[str]] = {
            f"{e['u']}->{e['v']}": [] for e in self.roadnet.corridors["edges"]
        }
        if not members:
            return members
        centers = {
            cid: (n["lon"], n["lat"]) for cid, n in cnodes.items()
        }
        nearest_cnode: Dict[str, str] = {}
        for e in self.roadnet.edges:
            mid = e["geometry"][len(e["geometry"]) // 2]
            nearest_cnode[e["id"]] = min(
                centers,
                key=lambda cid: _haversine_km(mid[0], mid[1], centers[cid][0], centers[cid][1]),
            )
        for ce in self.roadnet.corridors["edges"]:
            key = f"{ce['u']}->{ce['v']}"
            wanted = {ce["u"], ce["v"]}
            members[key] = [
                eid for eid, cid in nearest_cnode.items() if cid in wanted
            ]
        return members

    # ── public controls ──

    def set_weather(self, state: WeatherState) -> None:
        self._weather_factor = WeatherProvider.speed_factor(state)

    def edge_occupancy(self) -> Dict[str, int]:
        """Live count of en-route agents per edge id."""
        return dict(self._occupancy)

    def corridor_congestion(self) -> Dict[str, float]:
        """flow/capacity-style ratio per corridor edge ("u->v") for the hive."""
        ratios: Dict[str, float] = {}
        edge_by_id = {e["id"]: e for e in self.roadnet.edges}
        for key, member_ids in self._corridor_members.items():
            if not member_ids:
                ratios[key] = 0.0
                continue
            total = 0.0
            for eid in member_ids:
                e = edge_by_id[eid]
                veh = self._occupancy.get(eid, 0)
                total += veh / max(e["dist_km"] * e["lanes"] * _NEAR_CAPACITY_VEH_PER_KM_LANE, 1e-6)
            ratios[key] = round(min(total / len(member_ids), 5.0), 4)
        return ratios

    def distance_traveled_km(self, agent: MovingAgent) -> float:
        done = sum(e["dist_km"] for e in agent.route[: agent.edge_i])
        return done + agent.progress_km

    # ── the tick ──

    def tick(self, dt_s: float) -> None:
        """Advance the world by ``dt_s`` sim-seconds. Pure math, no I/O."""
        self.sim_s += dt_s
        occupancy: Dict[str, int] = {}
        for agent in self.agents:
            if agent.state == "arrived":
                continue
            if self.sim_s < agent.depart_s:
                agent.speed_kmh = 0.0
                agent.state = "queued"
                continue
            self._advance(agent, dt_s)
            if agent.state != "arrived":
                occupancy[agent.route[agent.edge_i]["id"]] = (
                    occupancy.get(agent.route[agent.edge_i]["id"], 0) + 1
                )
        self._occupancy = occupancy

    def _advance(self, agent: MovingAgent, dt_s: float) -> None:
        if agent._halt_until_s > self.sim_s:
            agent.speed_kmh = 0.0
            agent.state = "queued"
            return

        edge = agent.route[agent.edge_i]
        speed = self._effective_speed(agent, edge)
        agent.progress_km += speed * dt_s / 3600.0

        # Bus dwell stops every ~500 m.
        if agent.mode == "bus" and agent.progress_km >= agent._bus_next_stop_km:
            agent._bus_next_stop_km += _BUS_STOP_EVERY_KM
            agent._halt_until_s = self.sim_s + _BUS_STOP_S

        while agent.progress_km >= edge["dist_km"]:
            end_node = edge["v"]
            node = self.roadnet.nodes.get(end_node, {})
            if node.get("signal") and signal_is_red(
                end_node, self.sim_s, self._cycle_s, self._green_split
            ):
                agent.progress_km = edge["dist_km"]
                agent.speed_kmh = 0.0
                agent.state = "queued"
                self._place(agent, edge, edge["dist_km"])
                return
            agent.progress_km -= edge["dist_km"]
            agent.edge_i += 1
            if agent.edge_i >= len(agent.route):
                agent.state = "arrived"
                agent.speed_kmh = 0.0
                last = agent.route[-1]["geometry"][-1]
                agent.lon, agent.lat = last
                agent.edge_i = len(agent.route) - 1
                agent.progress_km = agent.route[-1]["dist_km"]
                return
            edge = agent.route[agent.edge_i]

        agent.speed_kmh = round(speed, 2)
        free = edge["free_speed"] * self._drive_factor
        agent.state = (
            "congested"
            if agent.mode != "walk" and speed < _CONGESTED_RATIO * free
            else "moving"
        )
        self._place(agent, edge, agent.progress_km)

    def _effective_speed(self, agent: MovingAgent, edge: Dict[str, Any]) -> float:
        if agent.mode == "walk":
            return _WALK_SPEED_KMH * self._weather_factor
        veh = self._occupancy.get(edge["id"], 0)
        ratio = veh / max(
            edge["dist_km"] * edge["lanes"] * _NEAR_CAPACITY_VEH_PER_KM_LANE, 1e-6
        )
        congestion_factor = 1.0 / (1.0 + _BPR_ALPHA * ratio**_BPR_BETA)
        speed = (
            edge["free_speed"]
            * self._drive_factor
            * congestion_factor
            * _MODE_FACTOR.get(agent.mode, 1.0)
            * self._weather_factor
        )
        return max(speed, _MIN_MOVING_SPEED_KMH)

    def _place(self, agent: MovingAgent, edge: Dict[str, Any], progress_km: float) -> None:
        """Interpolate lon/lat/bearing along the edge's true street geometry."""
        cum = self._edge_cum[edge["id"]]
        geom = edge["geometry"]
        total = cum[-1] or edge["dist_km"]
        target = min(progress_km * (total / edge["dist_km"]) if edge["dist_km"] else 0.0, total)
        i = max(1, bisect.bisect_left(cum, target))
        i = min(i, len(geom) - 1)
        seg_len = cum[i] - cum[i - 1] or 1e-9
        t = (target - cum[i - 1]) / seg_len
        (lon1, lat1), (lon2, lat2) = geom[i - 1], geom[i]
        agent.lon = lon1 + (lon2 - lon1) * t
        agent.lat = lat1 + (lat2 - lat1) * t
        dlon = (lon2 - lon1) * math.cos(math.radians(lat1))
        agent.bearing = round(math.degrees(math.atan2(dlon, lat2 - lat1)) % 360.0, 1)
