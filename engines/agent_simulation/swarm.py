"""
Urban Swarm Orchestrator
==========================

Runs the multi-agent timestep simulation loop:
  1. Policy Broadcast: PolicyAgent updates GlobalKG and SegmentBrains
  2. Sentinel Reasoning: SurgicalAgents identify discoveries and contribute to SegmentBrains
  3. Hive Distillation: SegmentBrains distill collective truth for their population
  4. Swarm Execution: SwarmAgents choose routes based on CollectiveTruth and current state
  5. Swarm Feedback: Aggregate stats are written back to SegmentBrains
  6. Physics Update: BPR travel times recomputed with new flows

Wraps the OASIS simulation lifecycle when available,
falls back to pure Python loop otherwise.

Output: Aggregated metrics in the same format as TransportEngine,
ready for consumption by downstream engines.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)

from engines.transport.engine import (
    _DEFAULT_NODES,
    _DEFAULT_EDGES,
    _EMISSION_FACTORS,
    _bpr_time,
)
from engines.agent_simulation.agents.types import (
    AgentProfile, AgentType, TransportMode, agent_choose_route,
    agent_update_after_trip, share_congestion_within_segment,
    compute_agent_emissions, generate_commuter_agents, generate_freight_agents,
)
from engines.agent_simulation.agents import SurgicalAgent, SwarmAgent
from engines.agent_simulation.agents.surgical_agent import _dijkstra_physics_fallback
from engines.agent_simulation.brains.backend import KnowledgeGraphBackend, LocalKnowledgeGraphBackend
from engines.agent_simulation.brains.collective_truth import CollectiveTruth
from engines.agent_simulation.brains.segment_brain import SegmentBrain
from engines.agent_simulation.graph_bridge import (
    build_ncr_knowledge_graph,
    LocalKnowledgeGraph,
    ZepKnowledgeGraph,
)
from engines.agent_simulation.agents.policy_agent import PolicyAgent
from engines.agent_simulation.config import SwarmConfig, get_agent_sim_config
from engines.population.engine import _SEGMENTS

# NOTE: the L2 ``reasoning`` package is imported LAZILY inside the methods that
# use it. A top-level import would create a cycle (reasoning -> collective_truth
# -> engines.agent_simulation.__init__ -> engine -> swarm -> reasoning).


@dataclass
class TimestepResult:
    """Metrics from a single simulation timestep."""
    step: int
    edge_flows: Dict[str, float] = field(default_factory=dict)
    edge_travel_times: Dict[str, float] = field(default_factory=dict)
    edge_congestion: Dict[str, float] = field(default_factory=dict)
    total_vkt: float = 0.0
    total_co2_kg: float = 0.0
    total_pm25_g: float = 0.0
    agents_arrived: int = 0
    agents_rerouted: int = 0
    mode_shifts: int = 0
    avg_speed_kmh: float = 0.0
    avg_travel_time_min: float = 0.0


@dataclass
class HiveTimestepResult(TimestepResult):
    """Metrics from a single Hive-loop simulation timestep."""
    sentinel_discoveries: int = 0
    distillations: int = 0
    swarm_inherited_routes: int = 0
    sentinel_fallbacks: int = 0


@dataclass
class SwarmResult:
    """Complete simulation output from the swarm."""
    timesteps: List[TimestepResult] = field(default_factory=list)
    final_edge_flows: Dict[str, float] = field(default_factory=dict)
    final_edge_congestion: Dict[str, float] = field(default_factory=dict)
    total_vkt: float = 0.0
    total_co2_kg: float = 0.0
    total_pm25_g: float = 0.0
    avg_speed_kmh: float = 0.0
    congestion_pct: float = 0.0
    agents_total: int = 0
    agents_arrived: int = 0
    total_mode_shifts: int = 0
    hotspots: List[Dict[str, Any]] = field(default_factory=list)
    segment_breakdown: Dict[str, Any] = field(default_factory=dict)
    ev_share: float = 0.0
    runtime_seconds: float = 0.0
    graph_info: Dict[str, Any] = field(default_factory=dict)


class UrbanSwarm:
    """Multi-agent urban simulation swarm orchestrator.

    Manages agent population, knowledge graph, simulation loop,
    and result aggregation.
    """

    def __init__(
        self,
        nodes: Optional[Dict[str, Any]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        config: Optional[SwarmConfig] = None,
        live_context: Optional[Dict[str, Any]] = None,
    ):
        self.nodes = nodes or dict(_DEFAULT_NODES)
        # Only use one direction for edges (dedup bidirectional)
        raw_edges = edges or list(_DEFAULT_EDGES)
        self.edges = self._dedup_edges(raw_edges)
        self.config = config or get_agent_sim_config().swarm
        self.live_context: Dict[str, Any] = live_context or {}

        self.agents: List[AgentProfile] = []
        self.graph = None
        self._flow_map: Dict[str, float] = {}  # Current edge flows

        # Hive Orchestration Variables
        self.backend: Optional[KnowledgeGraphBackend] = None
        self._backend_initialized = False
        self.segment_brains: Dict[str, SegmentBrain] = {}
        self.sentinel_agents: List[SurgicalAgent] = []
        self.global_kg: Optional[KnowledgeGraphBackend] = None

        # Cognition toggle: when False (default) the loop runs pure physics
        # (legacy /simulate/agent-based). When True, sentinels + brains reason
        # through the ReasoningGateway (the real Sentinel-Swarm-Hive).
        self.enable_llm = False
        self._gateway = None
        self._valid_edges = None
        self._sentinel_provider = None
        self.policy_agent: Optional[PolicyAgent] = None
        # Sentinels per segment (7 segments). 7 => 49 sentinels (production);
        # lower it for free-tier demos to cut LLM call volume.
        self.sentinel_count_per_segment = 7
        # Optional async progress callback: on_event(dict) -> awaitable. Used by
        # the /simulate/hive/stream SSE endpoint; None = silent (default).
        self.on_event = None

    @staticmethod
    def _dedup_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep bidirectional edges — needed for full routing."""
        return edges

    async def _init_backend(self, zep_api_key: Optional[str] = None) -> None:
        """Initialize the knowledge graph backend (Zep or Local)."""
        if zep_api_key:
            from engines.agent_simulation.brains.backend import ZepBackend
            self.backend = ZepBackend(api_key=zep_api_key)
        else:
            self.backend = LocalKnowledgeGraphBackend()
        await self.backend.initialize()
        self._backend_initialized = True

    def _create_segment_brains(self):
        """Create SegmentBrains for each population segment."""
        for segment in _SEGMENTS:
            # Using a simple default LLM provider that synthesizes discoveries into CollectiveTruth
            self.segment_brains[segment] = SegmentBrain(
                segment_name=segment,
                backend=self.backend,
                llm_provider=None # Default internal synthesis logic
            )

    def _create_sentinel_agents(self):
        """Create SurgicalAgents distributed across segments."""
        sentinel_count_per_segment = max(1, int(self.sentinel_count_per_segment))
        agent_id_offset = 1000000 # Offset to avoid collision with swarm agents

        # Group swarm agents by segment to pick origins/destinations
        segment_data = {}
        for agent in self.agents:
            if agent.segment not in segment_data:
                segment_data[agent.segment] = []
            segment_data[agent.segment].append(agent)

        for segment in _SEGMENTS:
            segment_agents = segment_data.get(segment, [])
            for i in range(sentinel_count_per_segment):
                # Pick a random agent from the segment for O/D reference, or use defaults
                ref_agent = random.choice(segment_agents) if segment_agents else None

                sentinel = SurgicalAgent(
                    agent_id=agent_id_offset + (list(_SEGMENTS).index(segment) * sentinel_count_per_segment) + i,
                    segment_name=segment,
                    origin=ref_agent.origin if ref_agent else random.choice(list(self.nodes.keys())),
                    destination=ref_agent.destination if ref_agent else random.choice(list(self.nodes.keys())),
                    backend=self.backend,
                    # Real gateway-backed provider when cognition is on; None keeps
                    # the legacy physics path byte-compatible.
                    llm_provider=self._sentinel_provider,
                )
                sentinel.last_decision = None  # populated each step for the contract trace
                self.sentinel_agents.append(sentinel)

    async def initialize(self, zep_api_key: Optional[str] = None, live_context: Optional[Dict[str, Any]] = None):
        """Set up knowledge graph and generate agent population.

        Args:
            zep_api_key: Optional Zep Cloud API key for memory persistence.
            live_context: Optional live data dict from get_ncr_context().
                Expected keys: live_aqi (pm25), tomtom (current_speed).
        """
        self.live_context = live_context or {}

        # Build knowledge graph
        self.graph = build_ncr_knowledge_graph(
            nodes=self.nodes,
            edges=self.edges,
            zep_api_key=zep_api_key,
        )

        # Generate agent populations
        commuters = generate_commuter_agents(
            count=self.config.commuter_count,
            nodes=self.nodes,
        )
        freight = generate_freight_agents(
            count=self.config.freight_count,
            nodes=self.nodes,
        )
        self.agents = commuters + freight

        # Initialize flow map — seed from live context if available
        self._init_flow_map_from_context()

        # Sentinel-Swarm-Hive Initialization
        await self._init_backend(zep_api_key=zep_api_key)

        # Wire the reasoning gateway BEFORE creating sentinels so they receive a
        # real provider. Without enable_llm the loop stays pure physics.
        if self.enable_llm:
            from reasoning import get_gateway, make_sentinel_provider, valid_edge_ids

            self._gateway = get_gateway()
            self._valid_edges = valid_edge_ids()
            self._sentinel_provider = make_sentinel_provider(self._gateway, self._valid_edges)

        self._create_segment_brains()
        self._create_sentinel_agents()

        # Step 1 of the Hive Loop — Policy Broadcast (once, gated off by default
        # to conserve free-tier quota). Writes regulatory facts to the GlobalKG
        # that sentinels read during reasoning.
        if self.enable_llm and os.getenv("OVERHAUL_HIVE_POLICY") == "1":
            await self._run_policy_broadcast()

    def _init_flow_map_from_context(self) -> None:
        """Seed the flow map from live context data.

        Uses TomTom current_speed to calibrate flow_ratio per edge.
        Falls back to hardcoded 0.6 baseline if no live data available.
        """
        tomtom = self.live_context.get("tomtom", {})
        live_speed = tomtom.get("current_speed")
        free_flow_speed = tomtom.get("free_flow_speed", 50.0)

        if live_speed and free_flow_speed and free_flow_speed > 0:
            # TomTom provides real-time speed — infer congestion from speed ratio
            # v_over_c ratio: (free_flow_speed / current_speed) - 1, clamped to a safe range
            speed_ratio = live_speed / free_flow_speed
            flow_ratio = min(max(speed_ratio, 0.3), 0.95)
        else:
            flow_ratio = 0.6  # default baseline

        for edge in self.edges:
            eid = f"{edge['u']}->{edge['v']}"
            self._flow_map[eid] = edge["capacity"] * flow_ratio

    def apply_interventions(self, interventions: List[Dict[str, Any]]):
        """Apply scenario interventions to the simulation state.

        Modifies edge properties, agent behavior, and flow assumptions
        based on the user's what-if scenario.
        """
        for intv in interventions:
            name = intv.get("name", "")
            params = intv.get("parameters", {})

            if name == "congestion_pricing":
                # Reduce demand across all edges
                reduction = params.get("demand_reduction_pct", 12) / 100.0
                for eid in self._flow_map:
                    self._flow_map[eid] *= (1.0 - reduction)

            elif name == "metro_expansion":
                # Shift some car agents to metro
                shift_pct = params.get("mode_shift_pct", 8) / 100.0
                for agent in self.agents:
                    if (
                        agent.agent_type == AgentType.COMMUTER
                        and agent.mode == TransportMode.CAR
                        and agent.flexibility > 0.3
                    ):
                        import random
                        if random.random() < shift_pct * agent.flexibility:
                            agent.mode = TransportMode.METRO

            elif name == "signal_optimization":
                # Increase free speed on all edges
                speed_gain = params.get("speed_gain_pct", 10) / 100.0
                for edge in self.edges:
                    edge["free_speed"] *= (1.0 + speed_gain)

            elif name == "bus_rapid_transit":
                # Reduce car capacity, shift some agents to bus
                car_cap_reduction = params.get("car_capacity_reduction_pct", 15) / 100.0
                for edge in self.edges:
                    edge["capacity"] *= (1.0 - car_cap_reduction)

            elif name == "ev_fleet_expansion":
                # Increase EV readiness of agents
                ev_increase = params.get("ev_share_increase", 0.10)
                for agent in self.agents:
                    agent.ev_readiness = min(1.0, agent.ev_readiness + ev_increase)

            elif name == "road_capacity_expansion":
                # Increase capacity on all edges
                cap_increase = params.get("capacity_increase_pct", 20) / 100.0
                for edge in self.edges:
                    edge["capacity"] *= (1.0 + cap_increase)

    async def run(self) -> SwarmResult:
        """Execute the multi-agent simulation loop.

        Implements the Sentinel-Swarm-Hive orchestration loop per timestep.
        """
        t0 = time.perf_counter()
        result = SwarmResult(agents_total=len(self.agents))
        config_weights = {
            "congestion_memory_weight": self.config.congestion_memory_weight,
            "peer_influence_weight": self.config.peer_influence_weight,
        }

        total_mode_shifts = 0

        await self._emit({
            "phase": "start",
            "timesteps": self.config.timesteps,
            "sentinels": len(self.sentinel_agents),
            "segments": len(self.segment_brains),
            "agents": len(self.agents),
        })

        for step in range(self.config.timesteps):
            # New Hive Loop implementation
            step_result = await self._run_timestep_hive(
                step=step,
                config_weights=config_weights,
            )
            result.timesteps.append(step_result)
            total_mode_shifts += step_result.mode_shifts

            await self._emit({
                "phase": "timestep",
                "step": step,
                "total_steps": self.config.timesteps,
                "avg_speed_kmh": step_result.avg_speed_kmh,
                "discoveries": step_result.sentinel_discoveries,
                "distillations": step_result.distillations,
                "inherited": step_result.swarm_inherited_routes,
                "fallbacks": step_result.sentinel_fallbacks,
            })

            # Update knowledge graph with current congestion
            if self.graph:
                for eid, congestion in step_result.edge_congestion.items():
                    road_entity_id = eid.replace("->", "__")
                    self.graph.update_entity_property(
                        f"road_{road_entity_id}", "current_congestion", congestion
                    )

        # Aggregate final results
        last_step = result.timesteps[-1] if result.timesteps else TimestepResult(step=0)
        result.final_edge_flows = last_step.edge_flows
        result.final_edge_congestion = last_step.edge_congestion
        result.total_vkt = sum(s.total_vkt for s in result.timesteps)
        result.total_co2_kg = sum(s.total_co2_kg for s in result.timesteps)
        result.total_pm25_g = sum(s.total_pm25_g for s in result.timesteps)
        # Average speed across all timesteps that had arrivals
        speeds_all = [s.avg_speed_kmh for s in result.timesteps if s.avg_speed_kmh > 0]
        result.avg_speed_kmh = round(sum(speeds_all) / max(len(speeds_all), 1), 1) if speeds_all else 0.0
        result.agents_arrived = sum(s.agents_arrived for s in result.timesteps)
        result.total_mode_shifts = total_mode_shifts

        # Congestion percentage
        congested_edges = sum(
            1 for c in last_step.edge_congestion.values() if c > 0.8
        )
        total_edges = max(len(last_step.edge_congestion), 1)
        result.congestion_pct = round(congested_edges / total_edges * 100, 1)

        # Hotspot detection (top 5 most congested edges)
        sorted_congestion = sorted(
            last_step.edge_congestion.items(), key=lambda x: -x[1]
        )
        result.hotspots = [
            {"edge": eid, "congestion_ratio": round(c, 3)}
            for eid, c in sorted_congestion[:5]
        ]

        # Segment breakdown
        result.segment_breakdown = self._compute_segment_breakdown()

        # EV share
        ev_agents = sum(
            1 for a in self.agents
            if a.ev_readiness > 0.5 and a.mode == TransportMode.CAR
        )
        car_agents = sum(1 for a in self.agents if a.mode == TransportMode.CAR)
        result.ev_share = round(ev_agents / max(car_agents, 1), 3)

        # Graph info
        if self.graph:
            result.graph_info = self.graph.to_dict()

        result.runtime_seconds = time.perf_counter() - t0
        return result

    @staticmethod
    def _discovery_text(brain: SegmentBrain, step: int) -> str:
        """Compact, LLM-ready summary of a segment's recent sentinel discoveries."""
        discoveries = brain._filter_window(step, 1)
        if not discoveries:
            return "no sentinel observations in this window"
        lines = []
        for d in discoveries[:12]:
            data = d.get("discovery_data", {})
            lines.append(
                f"sentinel {d.get('sentinel_id')}: route={data.get('route')} "
                f"avoid={data.get('avoid')} mood={data.get('mood')} "
                f"note={data.get('observation')}"
            )
        return "\n".join(lines)

    def _congestion_snapshot(self) -> Dict[str, float]:
        """Per-edge congestion ratio from the current flow map (shared per step)."""
        snapshot: Dict[str, float] = {}
        for edge in self.edges:
            eid = f"{edge['u']}->{edge['v']}"
            flow = self._flow_map.get(eid, edge["capacity"] * 0.6)
            snapshot[eid] = flow / max(edge["capacity"], 1)
        return snapshot

    async def _emit(self, event: Dict[str, Any]) -> None:
        """Fire the optional progress callback (never fatal)."""
        if self.on_event is not None:
            try:
                await self.on_event(event)
            except Exception:  # noqa: BLE001 — progress is best-effort
                pass

    async def _run_timestep_hive(
        self,
        step: int,
        config_weights: Dict[str, float],
    ) -> HiveTimestepResult:
        """Run a single simulation timestep using the Hive Loop.

        With ``enable_llm`` set, Step 2 (Sentinel reasoning) and Step 3 (Hive
        distillation) are REAL, parallel, gateway-managed LLM calls — 50
        sentinels coalesce into ~7 batched provider calls, 7 distillations into
        ~1, all rate-limited + cached + circuit-broken. Without it, the loop runs
        pure physics (legacy /simulate/agent-based behaviour), minus the
        AttributeError the old ``suggested_route`` line used to throw.
        """
        from reasoning import valid_edge_ids
        from reasoning.adapters import coerce_truth
        from reasoning.gateway import ReasonRequest

        ts = HiveTimestepResult(step=step)
        step_time_min = step * self.config.step_duration_minutes
        valid_edges = self._valid_edges or valid_edge_ids()
        world = {"valid_edges": valid_edges, "congestion": self._congestion_snapshot()}

        # ── Step 2: Sentinel Reasoning ──────────────────────────────────
        if self.enable_llm and self._gateway is not None:
            # Build one request per sentinel, fan out through the gateway (it
            # batches/shards/caches internally), write each discovery ONCE.
            requests = []
            for s in self.sentinel_agents:
                brain = self.segment_brains.get(s.segment_name)
                truth = brain.get_current_truth() if brain else None
                requests.append(
                    ReasonRequest(
                        agent_id=s.agent_id,
                        context={
                            "agent_id": s.agent_id,
                            "segment": s.segment_name,
                            "origin": s.origin,
                            "destination": s.destination,
                            "mood": truth.segment_mood if truth else "stable",
                            "preferred": list(truth.preferred_routes) if truth else [],
                        },
                        kind="sentinel",
                    )
                )
            decisions = await self._gateway.reason_many(requests, world=world)
            for s, dec in zip(self.sentinel_agents, decisions):
                s.last_decision = dec
                ts.sentinel_discoveries += 1
                if dec.get("fallback"):
                    ts.sentinel_fallbacks += 1
                brain = self.segment_brains.get(s.segment_name)
                if brain:
                    brain.contribute_discovery(
                        sentinel_id=s.agent_id,
                        timestep=step,
                        discovery_data={
                            "route": dec.get("route"),
                            "avoid": dec.get("avoid"),
                            "observation": dec.get("why"),
                            "mood": dec.get("mood"),
                            "confidence": dec.get("confidence"),
                            "status": "fallback" if dec.get("fallback") else "llm",
                        },
                    )
        else:
            # Physics path — call the Dijkstra fallback directly (no LLM attempt,
            # so no NON_FATAL noise) and write the discovery once via act().
            for sentinel in self.sentinel_agents:
                brain = self.segment_brains.get(sentinel.segment_name)
                truth = brain.get_current_truth() if brain else None
                discovery = await sentinel._physics_fallback(
                    {"flow_map": self._flow_map, "timestep": step}, truth
                )
                sentinel.last_decision = discovery
                if brain is not None:
                    await sentinel.act(discovery, step, brain)
                ts.sentinel_discoveries += 1
                ts.sentinel_fallbacks += 1

        await self._emit({
            "phase": "sentinels", "step": step,
            "discoveries": ts.sentinel_discoveries, "fallbacks": ts.sentinel_fallbacks,
        })

        # ── Step 3: Hive Distillation ───────────────────────────────────
        segment_truths: Dict[str, CollectiveTruth] = {}
        if self.enable_llm and self._gateway is not None:
            order = list(self.segment_brains.items())
            items = [(seg, self._discovery_text(brain, step)) for seg, brain in order]
            truths = await self._gateway.distill_many(items, timestep=step, world=world)
            for seg, brain in order:
                truth = truths.get(seg) or coerce_truth(None, step, valid_edges)
                brain.record_truth(truth)
                segment_truths[seg] = truth
                ts.distillations += 1
        else:
            for segment, brain in self.segment_brains.items():
                truth = brain.distill_collective_truth(step)
                segment_truths[segment] = truth
                ts.distillations += 1

        await self._emit({"phase": "distill", "step": step, "distillations": ts.distillations})

        # ── Step 4: Swarm Execution ─────────────────────────────────────
        step_flows: Dict[str, float] = {eid: 0.0 for eid in self._flow_map}
        travel_times = []
        speeds = []

        for agent in self.agents:
            if agent.arrived:
                continue
            if agent.departure_offset_min > step_time_min:
                continue
            if agent.mode in (TransportMode.METRO, TransportMode.WFH, TransportMode.CYCLE):
                agent.arrived = True
                ts.agents_arrived += 1
                continue

            # SwarmAgent routing using collective truth
            collective_truth = segment_truths.get(agent.segment)

            # Use SwarmAgent.choose_route logic
            route_data = SwarmAgent(
                agent_id=agent.agent_id,
                segment_name=agent.segment,
                origin=agent.origin,
                destination=agent.destination,
            ).choose_route(
                state={"flow_map": self._flow_map},
                collective_truth=collective_truth,
            )

            route = route_data.get("path")
            travel_time = route_data.get("travel_time_min", 0)

            if not route:
                continue

            # Did this agent inherit a hive-preferred edge? Real edge-ID overlap
            # (the distilled truth now carries actual u->v IDs that bite routing).
            if collective_truth and collective_truth.preferred_routes:
                preferred = set(collective_truth.preferred_routes)
                if any(f"{e['u']}->{e['v']}" in preferred for e in route):
                    ts.swarm_inherited_routes += 1

            for edge in route:
                eid = f"{edge['u']}->{edge['v']}"
                step_flows[eid] = step_flows.get(eid, 0) + 1

            emissions = compute_agent_emissions(agent, route)
            ts.total_co2_kg += emissions["co2_kg"]
            ts.total_pm25_g += emissions["pm25_g"]

            trip_km = sum(e["dist_km"] for e in route)
            ts.total_vkt += trip_km
            travel_times.append(travel_time)
            if travel_time > 0:
                speeds.append(trip_km / (travel_time / 60))

            old_mode = agent.mode
            agent.travel_time_current = travel_time
            agent.current_route = route
            agent.arrived = True
            ts.agents_arrived += 1

            edge_congestion = {}
            for edge in route:
                eid = f"{edge['u']}->{edge['v']}"
                flow = self._flow_map.get(eid, 0) + step_flows.get(eid, 0)
                edge_congestion[eid] = flow / max(edge["capacity"], 1)

            agent_update_after_trip(
                agent=agent,
                route=route,
                travel_time=travel_time,
                edge_congestion=edge_congestion,
                adaptation_threshold=self.config.adaptation_threshold,
                mode_shift_threshold=self.config.mode_shift_threshold,
            )
            if agent.mode != old_mode:
                ts.mode_shifts += 1

        # Step 5 (Swarm Feedback Write)
        # Aggregate stats per segment and update segment brain
        for segment, brain in self.segment_brains.items():
            segment_stats = {
                "avg_travel_time": sum(travel_times) / max(len(travel_times), 1) if travel_times else 0,
                "arrival_count": sum(1 for a in self.agents if a.segment == segment and a.arrived),
            }
            brain.update_swarm_stats(step, segment_stats)

        # Physics Update: BPR recompute
        scale_factor = 7_000_000 / max(len(self.agents), 1)
        total_edges = max(len(self.edges), 1)
        for eid, flow in step_flows.items():
            real_flow = flow * scale_factor / total_edges
            old_flow = self._flow_map.get(eid, 0)
            self._flow_map[eid] = old_flow * 0.8 + real_flow * 0.2

        for edge in self.edges:
            eid = f"{edge['u']}->{edge['v']}"
            flow = self._flow_map.get(eid, edge["capacity"] * 0.6)
            tt = _bpr_time(edge["dist_km"], edge["free_speed"], edge["capacity"], flow)
            congestion = flow / max(edge["capacity"], 1)

            ts.edge_flows[eid] = round(flow)
            ts.edge_travel_times[eid] = round(tt, 2)
            ts.edge_congestion[eid] = round(congestion, 3)

        ts.avg_travel_time_min = round(sum(travel_times) / max(len(travel_times), 1), 2)
        ts.avg_speed_kmh = round(sum(speeds) / max(len(speeds), 1), 1) if speeds else 0.0

        return ts

    async def _run_timestep(
        self,
        step: int,
        config_weights: Dict[str, float],
    ) -> TimestepResult:
        """Run a single simulation timestep (pure-swarm fallback)."""
        ts = TimestepResult(step=step)
        step_time_min = step * self.config.step_duration_minutes

        # Reset edge flows for this timestep
        step_flows: Dict[str, float] = {eid: 0.0 for eid in self._flow_map}
        travel_times = []
        speeds = []

        for agent in self.agents:
            if agent.arrived:
                continue

            if agent.departure_offset_min > step_time_min:
                continue

            if agent.mode in (TransportMode.METRO, TransportMode.WFH, TransportMode.CYCLE):
                agent.arrived = True
                ts.agents_arrived += 1
                continue

            route, travel_time = agent_choose_route(
                agent=agent,
                nodes=self.nodes,
                edges=self.edges,
                flow_map=self._flow_map,
                config_weights=config_weights,
            )

            if not route:
                continue

            for edge in route:
                eid = f"{edge['u']}->{edge['v']}"
                step_flows[eid] = step_flows.get(eid, 0) + 1

            emissions = compute_agent_emissions(agent, route)
            ts.total_co2_kg += emissions["co2_kg"]
            ts.total_pm25_g += emissions["pm25_g"]

            trip_km = sum(e["dist_km"] for e in route)
            ts.total_vkt += trip_km

            travel_times.append(travel_time)
            if travel_time > 0:
                speeds.append(trip_km / (travel_time / 60))

            old_mode = agent.mode
            agent.travel_time_current = travel_time
            agent.current_route = route
            agent.arrived = True
            ts.agents_arrived += 1

            edge_congestion = {}
            for edge in route:
                eid = f"{edge['u']}->{edge['v']}"
                flow = self._flow_map.get(eid, 0) + step_flows.get(eid, 0)
                edge_congestion[eid] = flow / max(edge["capacity"], 1)

            agent_update_after_trip(
                agent=agent,
                route=route,
                travel_time=travel_time,
                edge_congestion=edge_congestion,
                adaptation_threshold=self.config.adaptation_threshold,
                mode_shift_threshold=self.config.mode_shift_threshold,
            )

            if agent.mode != old_mode:
                ts.mode_shifts += 1

        scale_factor = 7_000_000 / max(len(self.agents), 1)
        total_edges = max(len(self.edges), 1)
        for eid, flow in step_flows.items():
            real_flow = flow * scale_factor / total_edges
            old_flow = self._flow_map.get(eid, 0)
            self._flow_map[eid] = old_flow * 0.8 + real_flow * 0.2

        for edge in self.edges:
            eid = f"{edge['u']}->{edge['v']}"
            flow = self._flow_map.get(eid, edge["capacity"] * 0.6)
            tt = _bpr_time(edge["dist_km"], edge["free_speed"], edge["capacity"], flow)
            congestion = flow / max(edge["capacity"], 1)

            ts.edge_flows[eid] = round(flow)
            ts.edge_travel_times[eid] = round(tt, 2)
            ts.edge_congestion[eid] = round(congestion, 3)

        ts.avg_travel_time_min = round(sum(travel_times) / max(len(travel_times), 1), 2)
        ts.avg_speed_kmh = round(sum(speeds) / max(len(speeds), 1), 1) if speeds else 0.0

        return ts

    def _compute_segment_breakdown(self) -> Dict[str, Any]:
        """Compute per-segment metrics for population analysis."""
        segments: Dict[str, Dict] = {}

        for agent in self.agents:
            if agent.agent_type != AgentType.COMMUTER:
                continue
            seg = agent.segment
            if seg not in segments:
                segments[seg] = {
                    "count": 0,
                    "mode_shifts": 0,
                    "car_count": 0,
                    "metro_count": 0,
                    "bus_count": 0,
                    "avg_satisfaction": 0.0,
                    "avg_travel_time": 0.0,
                }

            segments[seg]["count"] += 1
            segments[seg]["avg_satisfaction"] += agent.memory.satisfaction_score
            segments[seg]["avg_travel_time"] += agent.memory.avg_travel_time
            segments[seg]["mode_shifts"] += len(agent.memory.mode_shift_events)

            if agent.mode == TransportMode.CAR:
                segments[seg]["car_count"] += 1
            elif agent.mode == TransportMode.METRO:
                segments[seg]["metro_count"] += 1
            elif agent.mode == TransportMode.BUS:
                segments[seg]["bus_count"] += 1

        for seg, data in segments.items():
            n = max(data["count"], 1)
            data["avg_satisfaction"] = round(data["avg_satisfaction"] / n, 3)
            data["avg_travel_time"] = round(data["avg_travel_time"] / n, 2)
            data["car_mode_share"] = round(data["car_count"] / n, 3)
            data["metro_mode_share"] = round(data["metro_count"] / n, 3)

        return segments

    # ── Step 1: Policy Broadcast (optional, gateway-backed) ─────────────
    def _make_policy_provider(self):
        """Async provider: {"query": str} -> {laws, budgets, announcements}."""
        gateway = self._gateway

        async def provider(payload: dict) -> Dict[str, Any]:
            query = payload.get("query", "")
            text = await gateway.reason_text(
                prompt=(
                    "List up to 3 real, current Delhi-NCR transport or pollution "
                    f"regulations/budget items relevant to: {query}. Respond as JSON "
                    '{"announcements": ["..."], "laws": [], "budgets": []}'
                ),
                system="You are a concise, factual policy research assistant.",
                prefer="gemini",
            )
            data: Dict[str, Any] = {}
            try:
                start, end = text.find("{"), text.rfind("}")
                if start >= 0 and end > start:
                    data = json.loads(text[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                data = {}
            announcements = data.get("announcements") or ([text[:200]] if text else [])
            return {
                "laws": data.get("laws", []),
                "budgets": data.get("budgets", []),
                "announcements": announcements,
            }

        return provider

    async def _run_policy_broadcast(self) -> None:
        """Best-effort regulatory broadcast into the GlobalKG (never fatal)."""
        try:
            if self.policy_agent is None:
                self.policy_agent = PolicyAgent(
                    backend=self.backend, llm_provider=self._make_policy_provider()
                )
            scenario_desc = self.live_context.get(
                "scenario_description", "Delhi NCR urban mobility and air-quality policy"
            )
            await self.policy_agent.run_policy_broadcast(
                research_query=f"regulations relevant to: {scenario_desc}",
                timestep=0,
            )
        except Exception as exc:  # noqa: BLE001 — policy is non-critical
            LOGGER.warning("Policy broadcast skipped: %s", exc)

    # ── Contract assembly (SimulationState pieces) ──────────────────────
    def build_hive_state(self) -> Dict[str, Any]:
        """Assemble brains[], sentinels[], and geojson for the SimulationState
        contract from real distilled truth + real sentinel decisions."""
        from reasoning import node_coords
        from shared.contracts.simulation_state import SEGMENT_LABELS

        brains: List[Dict[str, Any]] = []
        for seg, brain in self.segment_brains.items():
            t = brain.get_current_truth()
            brains.append(
                {
                    "segment": seg,
                    "label": SEGMENT_LABELS.get(seg, seg.replace("_", " ").title()),
                    "segment_mood": t.segment_mood if t else "stable",
                    "confidence": t.confidence if t else 0.0,
                    "preferred_routes": list(t.preferred_routes) if t else [],
                    "avoid_zones": list(t.avoid_zones) if t else [],
                    "dissenting_signals": list(t.dissenting_signals) if t else [],
                    "stale": t.stale if t else False,
                }
            )

        sentinels: List[Dict[str, Any]] = []
        for s in self.sentinel_agents:
            coords = node_coords(s.origin) or node_coords(s.destination)
            if not coords:
                continue
            dec = getattr(s, "last_decision", None) or {}
            brain = self.segment_brains.get(s.segment_name)
            t = brain.get_current_truth() if brain else None
            raw_route = dec.get("route")
            route_list = raw_route if isinstance(raw_route, list) else ([raw_route] if raw_route else [])
            sentinels.append(
                {
                    "id": s.agent_id,
                    "segment": s.segment_name,
                    "coords": coords,
                    "mood": dec.get("mood") or (t.segment_mood if t else "stable"),
                    "confidence": float(dec.get("confidence", t.confidence if t else 0.0)),
                    "trace": {
                        "why": dec.get("why", ""),
                        "route": route_list,
                        "fallback": bool(dec.get("fallback", False)),
                    },
                }
            )

        return {"brains": brains, "sentinels": sentinels, "geojson": self._build_geojson()}

    def _build_geojson(self) -> Dict[str, Any]:
        """FeatureCollection of congestion-colored road edges from final flows."""
        from reasoning import node_coords

        features: List[Dict[str, Any]] = []
        seen = set()
        for edge in self.edges:
            key = tuple(sorted((edge["u"], edge["v"])))
            if key in seen:
                continue
            seen.add(key)
            eid = f"{edge['u']}->{edge['v']}"
            flow = self._flow_map.get(eid, edge["capacity"] * 0.6)
            congestion = round(flow / max(edge["capacity"], 1), 3)
            a, b = node_coords(edge["u"]), node_coords(edge["v"])
            if not a or not b:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [a, b]},
                    "properties": {
                        "edge": eid,
                        "congestion": congestion,
                        # Real vehicle flow on this edge — drives swarm particle
                        # density in the command center (honest, not a random count).
                        "flow": round(flow),
                        "capacity": round(edge["capacity"]),
                        "level": "high" if congestion > 0.8 else "medium" if congestion > 0.5 else "low",
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    async def interview_agent(self, agent_id: int, question: str) -> Dict[str, Any]:
        """Interview a specific agent about its decisions.

        Uses the IPC system for mid-simulation queries.
        Returns agent's state, memory, and reasoning.
        """
        agent = next((a for a in self.agents if a.agent_id == agent_id), None)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}

        return {
            "agent_id": agent_id,
            "type": agent.agent_type.value,
            "segment": agent.segment,
            "mode": agent.mode.value,
            "origin": agent.origin,
            "destination": agent.destination,
            "arrived": agent.arrived,
            "travel_time": agent.travel_time_current,
            "satisfaction": agent.memory.satisfaction_score,
            "known_congested_edges": len(agent.memory.congestion_memory),
            "mode_shift_events": agent.memory.mode_shift_events,
            "total_trips": agent.memory.total_trips,
            "question": question,
            "reasoning": self._generate_agent_reasoning(agent, question),
        }

    @staticmethod
    def _generate_agent_reasoning(agent: AgentProfile, question: str) -> str:
        """Generate rule-based reasoning for agent interview response."""
        lines = []
        lines.append(f"I am a {agent.segment} commuter from {agent.origin} to {agent.destination}.")
        lines.append(f"I currently use {agent.mode.value} for my commute.")

        if agent.memory.satisfaction_score < 0.5:
            lines.append("I am dissatisfied with my current commute.")
        elif agent.memory.satisfaction_score > 0.8:
            lines.append("My commute experience has been good recently.")

        if agent.memory.mode_shift_events:
            last_shift = agent.memory.mode_shift_events[-1]
            lines.append(
                f"I recently switched from {last_shift['from_mode']} due to "
                f"{last_shift['trigger']} (congestion: {last_shift['avg_congestion']:.0%})."
            )

        if agent.memory.congestion_memory:
            worst_edges = sorted(
                agent.memory.congestion_memory.items(), key=lambda x: -x[1]
            )[:3]
            congested = [f"{eid} ({c:.0%})" for eid, c in worst_edges]
            lines.append(f"I know these routes are congested: {', '.join(congested)}.")

        return " ".join(lines)
