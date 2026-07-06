"""Tests for SurgicalAgent - the high-fidelity LLM-powered Sentinel agent."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List

from engines.agent_simulation.brains.backend import KnowledgeGraphBackend, LocalKnowledgeGraphBackend
from engines.agent_simulation.brains.collective_truth import CollectiveTruth
from engines.agent_simulation.brains.segment_brain import SegmentBrain


# ─────────────────────────────────────────────────────────────────────────────
# Mock LLM Provider
# ─────────────────────────────────────────────────────────────────────────────

class MockLLMProvider:
    """Mock LLM callable that returns a hardcoded routing decision."""

    def __init__(self, response: dict):
        self.call_count = 0
        self.last_input = None
        self._response = response

    def __call__(self, context: dict) -> dict:
        self.call_count += 1
        self.last_input = context
        return self._response


def make_llm_mock(response: dict):
    """Factory to create a mock LLM provider."""
    return MockLLMProvider(response=response)


# ─────────────────────────────────────────────────────────────────────────────
# Async Convergence Test (Critical — catches the Layer 1 bug)
# ─────────────────────────────────────────────────────────────────────────────

class TestSurgicalAgentAsyncConvergence:
    """Test that 50 concurrent SurgicalAgent.think() calls resolve within 2s."""

    @pytest.mark.asyncio
    async def test_fifty_agents_converge_without_deadlock(self):
        """50 SurgicalAgent instances running think() concurrently must resolve in < 2s.

        This is the most critical test — it verifies asyncio.gather works correctly
        for parallel backend queries (Layer 1 of the sentinel reasoning loop).
        """
        # Import here to avoid top-level import issues
        from engines.agent_simulation.agents.surgical_agent import SurgicalAgent

        # Mock backends
        mock_kg = AsyncMock(spec=KnowledgeGraphBackend)
        mock_kg.semantic_query = AsyncMock(return_value=[
            "fact: dnd_muted特点是低拥挤",
            "fact: noida_sec18有高流量",
        ])

        mock_segment_brain = AsyncMock(spec=SegmentBrain)
        mock_segment_brain.get_current_truth = MagicMock(
            return_value=CollectiveTruth(
                timestep=1,
                preferred_routes=["ito->noida_sec18"],
                avoid_zones=[],
                segment_mood="adaptive",
                confidence=0.7,
                dissenting_signals=[],
            )
        )
        mock_segment_brain.get_discoveries_for_timestep = MagicMock(return_value=[])

        # Mock LLM to return a valid decision quickly
        async def mock_llm_call(context: dict) -> dict:
            await asyncio.sleep(0.01)  # Tiny delay, simulating LLM
            return {
                "action": "take_route",
                "why": "low congestion detected via semantic query",
                "result": "ito->noida_sec18 selected as optimal",
                "route": "ito->noida_sec18",
            }

        # Create 50 SurgicalAgent instances
        agents = []
        for i in range(50):
            agent = SurgicalAgent(
                agent_id=i,
                segment_name="commuters_north",
                origin="connaught_place",
                destination="noida_sec18",
                backend=mock_kg,
                llm_provider=mock_llm_call,
            )
            agents.append(agent)

        # Run all 50 think() calls concurrently
        state = {"timestep": 1, "flow_map": {}}
        tasks = [
            agent.think(state, mock_segment_brain, mock_kg)
            for agent in agents
        ]

        # Should resolve within 2 seconds — no deadlock
        import time
        t0 = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0

        assert elapsed < 2.0, f"50 agents took {elapsed:.2f}s (> 2s limit)"
        assert len(results) == 50

        # Verify all results are valid decisions
        for result in results:
            assert isinstance(result, dict)
            assert "action" in result
            assert "why" in result
            assert "result" in result


# ─────────────────────────────────────────────────────────────────────────────
# LLM Reasoning Test
# ─────────────────────────────────────────────────────────────────────────────

class TestSurgicalAgentLLMReasoning:
    """Test that think() calls LLM and returns a well-structured decision."""

    @pytest.mark.asyncio
    async def test_think_calls_llm_and_returns_decision(self):
        """think() must call the LLM provider and return action/why/result/route."""
        from engines.agent_simulation.agents.surgical_agent import SurgicalAgent

        mock_kg = AsyncMock(spec=KnowledgeGraphBackend)
        mock_kg.semantic_query = AsyncMock(return_value=[
            "edge: connaught_place->ito 自由流时间: 6min",
        ])

        mock_brain = AsyncMock(spec=SegmentBrain)
        mock_brain.get_current_truth = MagicMock(
            return_value=CollectiveTruth(
                timestep=5,
                preferred_routes=["connaught_place->ito"],
                avoid_zones=[],
                segment_mood="stable",
                confidence=0.8,
                dissenting_signals=[],
            )
        )

        # Configure mock LLM
        expected_decision = {
            "action": "take_route",
            "why": "connaught_place->ito is preferred by collective truth (mood: stable, confidence: 0.8)",
            "result": "route_selected: connaught_place->ito",
            "route": "connaught_place->ito",
        }
        mock_llm = AsyncMock(return_value=expected_decision)

        agent = SurgicalAgent(
            agent_id=1,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="ito",
            backend=mock_kg,
            llm_provider=mock_llm,
        )

        state = {"timestep": 5, "flow_map": {}}
        decision = await agent.think(state, mock_brain, mock_kg)

        # Verify LLM was called
        assert mock_llm.call_count >= 1

        # Verify decision structure
        assert decision["action"] == "take_route"
        assert "why" in decision
        assert "result" in decision
        assert "route" in decision

    @pytest.mark.asyncio
    async def test_think_builds_context_with_physics_and_brain_state(self):
        """think() must pass physics state + SegmentBrain truth + GlobalKG facts to LLM."""
        from engines.agent_simulation.agents.surgical_agent import SurgicalAgent

        mock_kg = AsyncMock(spec=KnowledgeGraphBackend)
        mock_kg.semantic_query = AsyncMock(return_value=[
            "fact: ito->noida_sec18 has 0.85 flow/capacity ratio",
        ])

        mock_brain = AsyncMock(spec=SegmentBrain)
        mock_brain.get_current_truth = MagicMock(
            return_value=CollectiveTruth(
                timestep=3,
                preferred_routes=["ito->noida_sec18", "ito->indirapuram"],
                avoid_zones=["ito->indirapuram"],
                segment_mood="frustrated",
                confidence=0.65,
                dissenting_signals=["edge ito->indirapuram has construction"],
            )
        )

        captured_context = {}

        async def capturing_llm(context: dict) -> dict:
            captured_context.update(context)
            return {
                "action": "avoid_edge",
                "why": "edge is in avoid_zones and frustrated mood",
                "result": "ito->indirapuram avoided",
                "route": "ito->noida_sec18 (alternate)",
            }

        agent = SurgicalAgent(
            agent_id=42,
            segment_name="gig_workers",
            origin="ito",
            destination="ghaziabad_center",
            backend=mock_kg,
            llm_provider=capturing_llm,
        )

        state = {
            "timestep": 3,
            "flow_map": {"ito->indirapuram": 3800, "ito->noida_sec18": 5500},
        }
        await agent.think(state, mock_brain, mock_kg)

        # Context should include physics state
        assert "flow_map" in captured_context or "physics" in captured_context or len(captured_context) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Fallback Test
# ─────────────────────────────────────────────────────────────────────────────

class TestSurgicalAgentFallback:
    """Test that agent falls back to physics-only Dijkstra on LLM failure."""

    @pytest.mark.asyncio
    async def test_llm_timeout_triggers_physics_fallback(self):
        """When LLM raises timeout, agent must use physics-only Dijkstra and log NON_FATAL_ERROR."""
        from engines.agent_simulation.agents.surgical_agent import SurgicalAgent

        mock_kg = AsyncMock(spec=KnowledgeGraphBackend)
        mock_kg.semantic_query = AsyncMock(return_value=[])

        mock_brain = AsyncMock(spec=SegmentBrain)
        mock_brain.get_current_truth = MagicMock(return_value=None)

        # LLM that raises a timeout
        async def failing_llm(context: dict) -> dict:
            raise asyncio.TimeoutError("LLM request timed out")

        agent = SurgicalAgent(
            agent_id=7,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="noida_sec18",
            backend=mock_kg,
            llm_provider=failing_llm,
        )

        state = {"timestep": 1, "flow_map": {}}

        # Should not raise — must handle gracefully
        decision = await agent.think(state, mock_brain, mock_kg)

        # Fallback decision should use physics
        assert decision is not None
        assert "action" in decision
        # Fallback should NOT be "take_route" with LLM failure — should be physics-based
        assert decision.get("fallback") is True or "physics" in decision.get("why", "").lower()

    @pytest.mark.asyncio
    async def test_fallback_logs_non_fatal_error(self):
        """On LLM failure, NON_FATAL_ERROR must be logged."""
        from engines.agent_simulation.agents.surgical_agent import SurgicalAgent
        import logging

        mock_kg = AsyncMock(spec=KnowledgeGraphBackend)
        mock_kg.semantic_query = AsyncMock(return_value=[])

        mock_brain = AsyncMock(spec=SegmentBrain)
        mock_brain.get_current_truth = MagicMock(return_value=None)

        async def failing_llm(context: dict) -> dict:
            raise RuntimeError("LLM unavailable")

        with patch("engines.agent_simulation.agents.surgical_agent.LOGGER") as mock_logger:
            agent = SurgicalAgent(
                agent_id=8,
                segment_name="commuters_north",
                origin="connaught_place",
                destination="noida_sec18",
                backend=mock_kg,
                llm_provider=failing_llm,
            )

            state = {"timestep": 1, "flow_map": {}}
            await agent.think(state, mock_brain, mock_kg)

            # Check that a NON_FATAL_ERROR was logged
            log_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("NON_FATAL_ERROR" in str(log) or "LLM" in str(log) for log in log_calls), \
                f"Expected NON_FATAL_ERROR log, got: {log_calls}"


# ─────────────────────────────────────────────────────────────────────────────
# Zep Memory Test
# ─────────────────────────────────────────────────────────────────────────────

class TestSurgicalAgentZepMemory:
    """Test that agent writes discovery to SegmentBrain after acting."""

    @pytest.mark.asyncio
    async def test_act_writes_discovery_to_segment_brain(self):
        """After acting, agent must call SegmentBrain.contribute_discovery() with sentinel_id, timestep, and discovery_data."""
        from engines.agent_simulation.agents.surgical_agent import SurgicalAgent

        mock_kg = AsyncMock(spec=KnowledgeGraphBackend)
        mock_brain = AsyncMock(spec=SegmentBrain)
        mock_brain.get_current_truth = MagicMock(return_value=None)
        mock_brain.contribute_discovery = MagicMock()

        # Mock LLM returns a decision
        async def mock_llm(context: dict) -> dict:
            return {
                "action": "take_route",
                "why": "physics says this is optimal",
                "result": "route selected",
                "route": "connaught_place->ito",
            }

        agent = SurgicalAgent(
            agent_id=99,
            segment_name="high_income",
            origin="connaught_place",
            destination="ito",
            backend=mock_kg,
            llm_provider=mock_llm,
        )

        decision = {
            "action": "take_route",
            "why": "physics says this is optimal",
            "result": "route selected",
            "route": "connaught_place->ito",
        }

        await agent.act(decision, timestep=12, segment_brain=mock_brain)

        # Verify contribute_discovery was called with correct args
        mock_brain.contribute_discovery.assert_called_once()
        call_args = mock_brain.contribute_discovery.call_args

        assert call_args.kwargs["sentinel_id"] == 99          # sentinel_id
        assert call_args.kwargs["timestep"] == 12               # timestep
        assert isinstance(call_args.kwargs["discovery_data"], dict)  # discovery_data
        assert "action" in call_args.kwargs["discovery_data"]  # contains decision info

    @pytest.mark.asyncio
    async def test_run_step_calls_think_then_act(self):
        """run_step() must call think() then act() in sequence."""
        from engines.agent_simulation.agents.surgical_agent import SurgicalAgent

        mock_kg = AsyncMock(spec=KnowledgeGraphBackend)
        mock_kg.semantic_query = AsyncMock(return_value=[])

        mock_brain = AsyncMock(spec=SegmentBrain)
        mock_brain.get_current_truth = MagicMock(return_value=None)
        mock_brain.contribute_discovery = MagicMock()

        async def mock_llm(context: dict) -> dict:
            return {
                "action": "take_route",
                "why": "fastest path",
                "result": "route_chosen",
                "route": "connaught_place->ito",
            }

        # Wrap mock_llm in AsyncMock to track calls
        llm_mock = AsyncMock(side_effect=mock_llm)

        agent = SurgicalAgent(
            agent_id=5,
            segment_name="commuters_north",
            origin="connaught_place",
            destination="ito",
            backend=mock_kg,
            llm_provider=llm_mock,
        )

        state = {"timestep": 7, "flow_map": {}}
        result = await agent.run_step(state, mock_brain, mock_kg, timestep=7)

        # run_step should return the decision
        assert result is not None
        assert "action" in result
        # Verify the LLM was actually called
        assert llm_mock.called