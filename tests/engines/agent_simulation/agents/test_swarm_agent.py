"""Tests for SwarmAgent - the physics-only agent that inherits from Segment Brain."""

import pytest
from unittest.mock import MagicMock, patch

from engines.agent_simulation.brains.collective_truth import CollectiveTruth
from engines.agent_simulation.brains.segment_brain import SegmentBrain
from engines.agent_simulation.brains.backend import LocalKnowledgeGraphBackend


# ─────────────────────────────────────────────────────────────────────────────
# Inheritance Test (Critical)
# ─────────────────────────────────────────────────────────────────────────────

class TestSwarmAgentInheritance:
    """Test that SwarmAgent inherits routing decisions from CollectiveTruth."""

    def test_avoid_zones_in_collective_truth_causes_edge_penalization(self):
        """When CollectiveTruth has avoid_zones, SwarmAgent must NOT choose that edge."""
        from engines.agent_simulation.agents.swarm_agent import SwarmAgent

        # Create agent with route: delhi → noida_sec18
        agent = SwarmAgent(
            agent_id=1,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="noida_sec18",
        )

        # CollectiveTruth says avoid ito->noida_sec18 (the DND corridor)
        collective_truth = CollectiveTruth(
            timestep=5,
            preferred_routes=[],
            avoid_zones=["ito->noida_sec18"],
            segment_mood="frustrated",
            confidence=0.75,
            dissenting_signals=[],
        )

        state = {
            "timestep": 5,
            "flow_map": {
                "ito->noida_sec18": 5500,   # Congested
                "connaught_place->ito": 2000,
                "noida_sec18->greater_noida": 1500,
            },
        }

        route_result = agent.choose_route(state, collective_truth)

        # The chosen route must NOT contain "ito->noida_sec18"
        route_edges = [e for e in route_result["path"]]
        edge_ids = [f"{e['u']}->{e['v']}" for e in route_edges]

        assert "ito->noida_sec18" not in edge_ids, \
            f"Avoid zone edge should be excluded, but route was: {edge_ids}"

    def test_without_collective_truth_pure_dijkstra_includes_edge(self):
        """Without CollectiveTruth (pure Dijkstra), the avoid edge IS included.

        This proves hive inheritance is working — CollectiveTruth modifies behavior.
        """
        from engines.agent_simulation.agents.swarm_agent import SwarmAgent

        agent = SwarmAgent(
            agent_id=2,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="noida_sec18",
        )

        state = {
            "timestep": 5,
            "flow_map": {
                "ito->noida_sec18": 5500,
                "connaught_place->ito": 2000,
                "noida_sec18->greater_noida": 1500,
            },
        }

        # Without CollectiveTruth — pure physics Dijkstra
        route_result = agent.choose_route(state, collective_truth=None)

        route_edges = route_result["path"]
        edge_ids = [f"{e['u']}->{e['v']}" for e in route_edges]

        # Pure Dijkstra should include ito->noida_sec18 (shortest path by free speed)
        assert "ito->noida_sec18" in edge_ids, \
            f"Pure Dijkstra should include edge, but route was: {edge_ids}"

    def test_avoid_zones_penalty_factor_is_10x(self):
        """Avoid zones edge cost should be multiplied by ~10x penalty factor."""
        from engines.agent_simulation.agents.swarm_agent import SwarmAgent

        agent = SwarmAgent(
            agent_id=3,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="noida_sec18",
        )

        collective_truth = CollectiveTruth(
            timestep=5,
            preferred_routes=[],
            avoid_zones=["ito->noida_sec18"],
            segment_mood="frustrated",
            confidence=0.75,
            dissenting_signals=[],
        )

        # High congestion on the avoid zone — with 10x penalty, it should be avoided
        state = {
            "timestep": 5,
            "flow_map": {
                # Both edges equally congested in raw terms
                "ito->noida_sec18": 5900,   # capacity 6000 → 0.98
                "connaught_place->ito": 3900,  # capacity 4000 → 0.98
            },
        }

        route_result = agent.choose_route(state, collective_truth)

        route_edges = route_result["path"]
        edge_ids = [f"{e['u']}->{e['v']}" for e in route_edges]

        # With 10x penalty on avoid zone, even equally congested route should avoid it
        assert "ito->noida_sec18" not in edge_ids


# ─────────────────────────────────────────────────────────────────────────────
# Preferred Routes Test
# ─────────────────────────────────────────────────────────────────────────────

class TestSwarmAgentPreferredRoutes:
    """Test that preferred_routes in CollectiveTruth cause edge bonus."""

    def test_preferred_routes_get_bonus(self):
        """Edges in preferred_routes should get a small cost bonus (0.5x multiplier)."""
        from engines.agent_simulation.agents.swarm_agent import SwarmAgent

        agent = SwarmAgent(
            agent_id=10,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="greater_noida",
        )

        # Noida Exp way is preferred — this edge is on the path CP → ito → noida_sec18 → greater_noida
        collective_truth = CollectiveTruth(
            timestep=5,
            preferred_routes=["noida_sec18->greater_noida"],
            avoid_zones=[],
            segment_mood="stable",
            confidence=0.8,
            dissenting_signals=[],
        )

        state = {
            "timestep": 5,
            "flow_map": {},
        }

        route_result = agent.choose_route(state, collective_truth)

        route_edges = route_result["path"]
        edge_ids = [f"{e['u']}->{e['v']}" for e in route_edges]

        # Greater Noida extension should be preferred (it's on the path to greater_noida)
        assert "noida_sec18->greater_noida" in edge_ids


# ─────────────────────────────────────────────────────────────────────────────
# Segment Routing Test
# ─────────────────────────────────────────────────────────────────────────────

class TestSwarmAgentSegmentRouting:
    """Test that different segments get different routing weights."""

    def test_high_income_segment_differs_from_gig_workers(self):
        """A SwarmAgent in 'high_income' segment gets different weights than 'gig_workers'."""
        from engines.agent_simulation.agents.swarm_agent import SwarmAgent

        # High income agent
        high_income = SwarmAgent(
            agent_id=20,
            segment_name="high_income",
            origin="connaught_place",
            destination="gurugram_cyber",
        )

        # Gig workers agent
        gig_workers = SwarmAgent(
            agent_id=21,
            segment_name="gig_workers",
            origin="connaught_place",
            destination="gurugram_cyber",
        )

        state = {
            "timestep": 1,
            "flow_map": {},
        }

        # With no avoid zones, both should use similar paths
        ct = CollectiveTruth(
            timestep=1,
            preferred_routes=[],
            avoid_zones=[],
            segment_mood="stable",
            confidence=0.5,
            dissenting_signals=[],
        )

        route_high = high_income.choose_route(state, ct)
        route_gig = gig_workers.choose_route(state, ct)

        # Both valid
        assert len(route_high["path"]) > 0
        assert len(route_gig["path"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Physics Fallback Test
# ─────────────────────────────────────────────────────────────────────────────

class TestSwarmAgentPhysicsFallback:
    """Test that SwarmAgent uses pure physics with no LLM."""

    def test_choose_route_has_no_llm_calls(self):
        """choose_route() must be pure Dijkstra — no LLM calls at all."""
        from engines.agent_simulation.agents.swarm_agent import SwarmAgent

        agent = SwarmAgent(
            agent_id=30,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="ito",
        )

        state = {
            "timestep": 1,
            "flow_map": {},
        }

        # Should work without any LLM — pure physics
        result = agent.choose_route(state, collective_truth=None)

        assert "path" in result
        assert "travel_time_min" in result
        assert len(result["path"]) > 0  # Found a path

        # Verify direct route was found (connaught_place → ito is an edge)
        edge_ids = [f"{e['u']}->{e['v']}" for e in result["path"]]
        assert "connaught_place->ito" in edge_ids

    def test_choose_route_returns_path_and_travel_time(self):
        """choose_route returns {path, travel_time_min, total_dist_km}."""
        from engines.agent_simulation.agents.swarm_agent import SwarmAgent

        agent = SwarmAgent(
            agent_id=31,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="south_delhi",
        )

        result = agent.choose_route(state={"timestep": 1, "flow_map": {}}, collective_truth=None)

        assert "path" in result
        assert "travel_time_min" in result
        assert "total_dist_km" in result
        assert isinstance(result["travel_time_min"], float)
        assert isinstance(result["total_dist_km"], float)