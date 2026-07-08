"""SwarmAgent - Physics-only agent that inherits from Segment Brain.

The Swarm in the Sentinel-Swarm-Hive model. SwarmAgents:
  - Have NO LLM calls — pure physics only
  - Read CollectiveTruth from SegmentBrain
  - Apply avoid_zones penalty (10x) and preferred_routes bonus (0.5x)
  - Use Dijkstra with BPR travel times from the transport engine

Inheritance from CollectiveTruth proves the hive loop is working —
swarm behavior is modified by sentinel discoveries.
"""

from __future__ import annotations

import heapq
from typing import Any, Dict, List, Optional

from engines.agent_simulation.brains.collective_truth import CollectiveTruth
from engines.transport.engine import _DEFAULT_NODES, _DEFAULT_EDGES, _bpr_time


# Default cost multiplier for avoid zones (10x penalty)
AVOID_PENALTY = 10.0

# Default cost multiplier for preferred routes (0.5x bonus)
PREFERRED_BONUS = 0.5

# Segment-specific routing weight modifiers
_SEGMENT_WEIGHTS = {
    "high_income": {"time_weight": 1.0, "cost_weight": 0.3},
    "gig_workers": {"time_weight": 1.2, "cost_weight": 0.8},
    "commuters_north": {"time_weight": 1.0, "cost_weight": 0.5},
    "default": {"time_weight": 1.0, "cost_weight": 0.5},
}


def _dijkstra_with_hive_weights(
    origin: str,
    destination: str,
    flow_map: Dict[str, float],
    avoid_zones: Optional[List[str]] = None,
    preferred_zones: Optional[List[str]] = None,
    segment_name: str = "default",
    nodes: Optional[List[str]] = None,
    edges: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Dijkstra shortest path with hive collective weights applied.

    Applies:
      - 10x penalty to edges in avoid_zones
      - 0.5x bonus to edges in preferred_zones (that are not also in avoid_zones)
      - Segment-specific routing weights

    Args:
        origin: Starting node ID.
        destination: Target node ID.
        flow_map: Current edge flow map (edge_id -> flow).
        avoid_zones: List of edge IDs to penalize.
        preferred_zones: List of edge IDs to bonus.
        segment_name: Agent's population segment for weight adjustment.

    Returns:
        Dict with path (list of edges), travel_time_min, total_dist_km.
    """
    # Route on the injected graph when provided; NCR default keeps legacy behavior.
    nodes = list(nodes) if nodes is not None else list(_DEFAULT_NODES.keys())
    edges = list(edges) if edges is not None else list(_DEFAULT_EDGES)
    if origin not in nodes or destination not in nodes:
        return {"travel_time_min": float("inf"), "path": [], "total_dist_km": 0.0}

    avoid_zones = avoid_zones or []
    preferred_zones = preferred_zones or []
    seg_weights = _SEGMENT_WEIGHTS.get(segment_name, _SEGMENT_WEIGHTS["default"])

    # Build adjacency with BPR travel times + hive weights
    adj: Dict[str, List] = {n: [] for n in nodes}
    for e in edges:
        eid = f"{e['u']}->{e['v']}"
        base_flow = flow_map.get(eid, e["capacity"] * 0.6)
        tt = _bpr_time(e["dist_km"], e["free_speed"], e["capacity"], base_flow)

        # Apply avoid zone penalty (10x)
        if eid in avoid_zones:
            tt *= AVOID_PENALTY

        # Apply preferred zone bonus (0.5x) — only if not also in avoid_zones
        if eid in preferred_zones and eid not in avoid_zones:
            tt *= PREFERRED_BONUS

        # Apply segment-specific time weight
        tt *= seg_weights["time_weight"]

        adj[e["u"]].append((e["v"], tt, e))

    # Dijkstra
    dist = {n: float("inf") for n in nodes}
    prev: Dict[str, Any] = {n: None for n in nodes}
    dist[origin] = 0.0
    pq = [(0.0, origin)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == destination:
            break
        for v, w, edge in adj.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = (u, edge)
                heapq.heappush(pq, (nd, v))

    if dist.get(destination, float("inf")) == float("inf"):
        # Unreachable (one-way dead ends on real road graphs) — degrade cleanly.
        return {"travel_time_min": float("inf"), "path": [], "total_dist_km": 0.0}

    # Reconstruct path
    path = []
    node = destination
    while prev[node]:
        u, edge = prev[node]
        path.append(edge)
        node = u
    path.reverse()

    return {
        "travel_time_min": round(dist[destination], 2),
        "path": path,
        "total_dist_km": sum(ep["dist_km"] for ep in path),
    }


class SwarmAgent:
    """Physics-only agent that inherits routing from CollectiveTruth.

    SwarmAgents have NO LLM calls — they use pure Dijkstra with BPR travel
    times, modified by CollectiveTruth weights from the hive loop.

    Args:
        agent_id: Unique identifier for this agent.
        segment_name: Population segment (high_income, gig_workers, etc.).
        origin: Starting node ID.
        destination: Target node ID.
    """

    def __init__(
        self,
        agent_id: int,
        segment_name: str,
        origin: str,
        destination: str,
    ) -> None:
        self.agent_id = agent_id
        self.segment_name = segment_name
        self.origin = origin
        self.destination = destination

    def choose_route(
        self,
        state: dict,
        collective_truth: Optional[CollectiveTruth] = None,
    ) -> Dict[str, Any]:
        """Choose route using physics Dijkstra with hive collective weights.

        Pure Dijkstra — no LLM calls. Weights come from:
          - avoid_zones in CollectiveTruth (10x penalty)
          - preferred_routes in CollectiveTruth (0.5x bonus)
          - Segment-specific routing weights

        Args:
            state: Simulation state dict (must include 'flow_map').
            collective_truth: Optional CollectiveTruth from SegmentBrain distillation.
                If None, uses pure physics Dijkstra.

        Returns:
            Dict with keys: path (list of edge dicts), travel_time_min, total_dist_km.
        """
        flow_map = state.get("flow_map", {})

        avoid_zones = []
        preferred_zones = []

        if collective_truth is not None:
            avoid_zones = collective_truth.avoid_zones
            preferred_zones = collective_truth.preferred_routes

        result = _dijkstra_with_hive_weights(
            origin=self.origin,
            destination=self.destination,
            flow_map=flow_map,
            avoid_zones=avoid_zones,
            preferred_zones=preferred_zones,
            segment_name=self.segment_name,
            nodes=state.get("nodes"),
            edges=state.get("edges"),
        )

        return result