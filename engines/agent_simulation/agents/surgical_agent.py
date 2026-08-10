"""SurgicalAgent - High-fidelity LLM-powered Sentinel agent.

The Sentinel in the Sentinel-Swarm-Hive model. Each SurgicalAgent:
  1. Queries GlobalKG and SegmentBrain in parallel via asyncio.gather
  2. Builds a context prompt with physics state + brain truth + KG facts
  3. Calls LLM to make a routing decision
  4. Executes the decision and writes discovery to SegmentBrain

On LLM failure, falls back to physics-only Dijkstra (reuses _bpr_time from transport engine).
"""

from __future__ import annotations

import asyncio
import heapq
import inspect
import logging
from typing import Any, Dict, List, Optional

from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
from engines.agent_simulation.brains.collective_truth import CollectiveTruth
from engines.agent_simulation.brains.segment_brain import SegmentBrain
from engines.transport.engine import _DEFAULT_NODES, _DEFAULT_EDGES, _bpr_time

LOGGER = logging.getLogger(__name__)

# Non-fatal error marker for LLM fallback
_NON_FATAL_ERROR = "NON_FATAL_ERROR"


def _dijkstra_physics_fallback(
    origin: str,
    destination: str,
    flow_map: Dict[str, float],
    avoid_zones: Optional[List[str]] = None,
    preferred_zones: Optional[List[str]] = None,
    nodes: Optional[List[str]] = None,
    edges: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Physics-only Dijkstra shortest path.

    Reuses the BPR travel time model and Dijkstra logic from transport/engine.py.

    Args:
        origin: Starting node ID.
        destination: Target node ID.
        flow_map: Current edge flow map (edge_id -> flow).
        avoid_zones: Edge IDs to penalize with 10x cost multiplier.
        preferred_zones: Edge IDs to bonus with 0.5x cost multiplier.
        nodes/edges: The graph to route on (defaults to the NCR corridor set,
            preserving legacy behavior; injected graphs MUST pass their own).

    Returns:
        Dict with path (list of edges), travel_time_min, total_dist_km.
    """
    nodes = list(nodes) if nodes is not None else list(_DEFAULT_NODES.keys())
    edges = list(edges) if edges is not None else list(_DEFAULT_EDGES)
    if origin not in nodes or destination not in nodes:
        return {"travel_time_min": float("inf"), "path": [], "total_dist_km": 0.0}

    AVOID_PENALTY = 10.0
    PREFERRED_BONUS = 0.5
    avoid_zones = avoid_zones or []
    preferred_zones = preferred_zones or []

    adj: Dict[str, List] = {n: [] for n in nodes}
    for e in edges:
        eid = f"{e['u']}->{e['v']}"
        flow = flow_map.get(eid, e["capacity"] * 0.6)
        tt = _bpr_time(e["dist_km"], e["free_speed"], e["capacity"], flow)

        # Apply avoid zone penalty
        if eid in avoid_zones:
            tt *= AVOID_PENALTY

        # Apply preferred zone bonus (only for edges in both preferred AND avoid = net 1.0x)
        if eid in preferred_zones and eid not in avoid_zones:
            tt *= PREFERRED_BONUS

        adj[e["u"]].append((e["v"], tt, e))

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
        # Unreachable (e.g. one-way dead ends on real road graphs) — degrade.
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


class SurgicalAgent:
    """High-fidelity LLM-powered Sentinel agent.

    Each SurgicalAgent reads physics state + SegmentBrain truth + GlobalKG facts,
    then uses an LLM to make a routing decision. On failure, falls back to
    physics-only Dijkstra.

    Args:
        agent_id: Unique identifier for this agent.
        segment_name: Population segment this agent represents.
        origin: Starting node ID.
        destination: Target node ID.
        backend: GlobalKnowledgeGraph backend for semantic queries.
        llm_provider: Callable that takes a context dict and returns a decision dict.
    """

    def __init__(
        self,
        agent_id: int,
        segment_name: str,
        origin: str,
        destination: str,
        backend: KnowledgeGraphBackend,
        llm_provider,
    ) -> None:
        self.agent_id = agent_id
        self.segment_name = segment_name
        self.origin = origin
        self.destination = destination
        self.backend = backend
        self.llm_provider = llm_provider

    async def think(
        self,
        state: dict,
        segment_brain: SegmentBrain,
        global_kg: KnowledgeGraphBackend,
    ) -> Dict[str, Any]:
        """Make a routing decision using parallel backend queries + LLM.

        Layer 1: Query GlobalKG and SegmentBrain in parallel via asyncio.gather
        Layer 2: Build context prompt from physics + brain state + KG facts
        Layer 3: Call LLM → returns {action, why, result, route}
        Layer 4: Return decision dict (fallback to Dijkstra on LLM failure)

        Args:
            state: Current simulation state (must include 'timestep' and 'flow_map').
            segment_brain: The SegmentBrain for this agent's segment.
            global_kg: The GlobalKnowledgeGraph backend.

        Returns:
            Decision dict with keys: action, why, result, route, fallback (bool).
        """
        timestep = state.get("timestep", 0)
        flow_map = state.get("flow_map", {})

        # Layer 1: Parallel backend queries via asyncio.gather
        # (1a) Semantic query against GlobalKG
        kg_query_task = asyncio.create_task(
            self._query_global_kg(global_kg)
        )
        # (1b) Get current truth from SegmentBrain (sync, but we treat it similarly)
        brain_truth = segment_brain.get_current_truth()
        brain_discoveries = segment_brain.get_discoveries_for_timestep(timestep)

        kg_results = await kg_query_task

        # Layer 2: Build context for LLM
        context = self._build_context(state, brain_truth, brain_discoveries, kg_results)

        # Layer 3: Call LLM
        try:
            decision = await self._call_llm(context)
            decision["fallback"] = False
            return decision
        except Exception as exc:
            # Layer 4: Fallback to physics-only Dijkstra
            LOGGER.error(
                f"{_NON_FATAL_ERROR} SurgicalAgent.{self.agent_id} LLM failed: {exc}. "
                "Falling back to physics-only Dijkstra."
            )
            return await self._physics_fallback(state, brain_truth)

    async def _query_global_kg(self, global_kg: KnowledgeGraphBackend) -> List[str]:
        """Query the GlobalKnowledgeGraph for semantic facts."""
        query = f"traffic routing {self.destination}"
        try:
            if hasattr(global_kg, "semantic_query"):
                result = global_kg.semantic_query(query)
                return result if result else []
            return []
        except Exception:
            return []

    def _build_context(
        self,
        state: dict,
        brain_truth: Optional[CollectiveTruth],
        brain_discoveries: List[dict],
        kg_results: List[str],
    ) -> dict:
        """Build the context dict passed to the LLM provider."""
        return {
            "agent_id": self.agent_id,
            "segment_name": self.segment_name,
            "origin": self.origin,
            "destination": self.destination,
            "timestep": state.get("timestep", 0),
            "physics": {
                "flow_map": state.get("flow_map", {}),
            },
            "segment_brain": {
                "current_truth": brain_truth.to_dict() if brain_truth else None,
                "recent_discoveries": brain_discoveries[-5:],  # Last 5 discoveries
            },
            "global_kg": {
                "semantic_facts": kg_results,
            },
        }

    async def _call_llm(self, context: dict) -> Dict[str, Any]:
        """Call the LLM provider with the context."""
        provider = self.llm_provider
        # Support both sync and async LLM providers
        if inspect.iscoroutinefunction(provider):
            result = await provider(context)
        else:
            result = provider(context)
        return result

    async def _physics_fallback(
        self,
        state: dict,
        brain_truth: Optional[CollectiveTruth],
    ) -> Dict[str, Any]:
        """Use physics-only Dijkstra when LLM is unavailable."""
        flow_map = state.get("flow_map", {})
        avoid_zones = []
        preferred_zones = []

        if brain_truth:
            avoid_zones = brain_truth.avoid_zones
            preferred_zones = brain_truth.preferred_routes

        result = _dijkstra_physics_fallback(
            origin=self.origin,
            destination=self.destination,
            flow_map=flow_map,
            avoid_zones=avoid_zones,
            preferred_zones=preferred_zones,
            nodes=state.get("nodes"),
            edges=state.get("edges"),
        )

        route_edges = [f"{e['u']}->{e['v']}" for e in result["path"]]

        return {
            "action": "take_route",
            "why": "physics-only Dijkstra fallback (LLM unavailable)",
            "result": f"route_selected: {route_edges[0] if route_edges else 'none'}",
            "route": route_edges[0] if route_edges else None,
            "fallback": True,
            "travel_time_min": result["travel_time_min"],
        }

    async def act(self, decision: Dict[str, Any], timestep: int, segment_brain: SegmentBrain) -> None:
        """Execute the decision and write discovery to SegmentBrain.

        Args:
            decision: The decision dict from think().
            timestep: Current simulation timestep.
            segment_brain: The SegmentBrain to write discovery to.
        """
        discovery_data = {
            "action": decision.get("action"),
            "why": decision.get("why"),
            "result": decision.get("result"),
            "route": decision.get("route"),
            "fallback": decision.get("fallback", False),
            "origin": self.origin,
            "destination": self.destination,
        }

        # Write directly to SegmentBrain
        segment_brain.contribute_discovery(
            sentinel_id=self.agent_id,
            timestep=timestep,
            discovery_data=discovery_data,
        )

    async def run_step(
        self,
        state: dict,
        segment_brain: SegmentBrain,
        global_kg: KnowledgeGraphBackend,
        timestep: int,
    ) -> Dict[str, Any]:
        """Run one complete agent step: think() then act().

        Args:
            state: Current simulation state.
            segment_brain: The agent's SegmentBrain.
            global_kg: The GlobalKnowledgeGraph.
            timestep: Current simulation timestep.

        Returns:
            The decision dict from think().
        """
        # Think
        decision = await self.think(state, segment_brain, global_kg)

        # Act (write discovery to brain)
        await self.act(decision, timestep, segment_brain)

        return decision