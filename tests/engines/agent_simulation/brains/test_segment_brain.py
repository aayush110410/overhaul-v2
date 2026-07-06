"""Tests for SegmentBrain - the Hive component managing collective memory for one segment."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import List, Optional, Callable

from engines.agent_simulation.brains.backend import KnowledgeGraphBackend, LocalKnowledgeGraphBackend
from engines.agent_simulation.brains.collective_truth import CollectiveTruth
from engines.agent_simulation.brains.segment_brain import SegmentBrain


class MockLLMProvider:
    """Mock LLM callable that returns hardcoded CollectiveTruth objects."""

    def __init__(self, response: Optional[CollectiveTruth] = None):
        self.call_count = 0
        self.last_input = None
        self._response = response

    def __call__(self, discoveries: List[dict]) -> CollectiveTruth:
        self.call_count += 1
        self.last_input = discoveries
        if self._response is None:
            raise RuntimeError("MockLLMProvider not configured with a response")
        return self._response


def make_fake_llm(response: CollectiveTruth) -> Callable[[List[dict]], CollectiveTruth]:
    """Factory to create a mock LLM provider returning a specific response."""
    provider = MockLLMProvider(response=response)
    return provider


class TestSegmentBrainContributeDiscovery:
    """Tests for contribute_discovery method."""

    def test_contribute_discovery_stores_data_with_sentinel_and_timestep(self):
        """Verify discovery data is stored with sentinel_id and timestep."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
        )

        brain.contribute_discovery(
            sentinel_id=101,
            timestep=3,
            discovery_data={"route": "Route_A", "status": "fast", "delay_minutes": 0},
        )

        # Verify it was stored
        stored = brain.get_discoveries_for_timestep(3)
        assert len(stored) == 1
        assert stored[0]["sentinel_id"] == 101
        assert stored[0]["timestep"] == 3
        assert stored[0]["discovery_data"]["route"] == "Route_A"

    def test_contribute_discovery_multiple_sentinels_same_timestep(self):
        """Multiple sentinels at same timestep are all stored."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(segment_name="commuters_north", backend=backend)

        brain.contribute_discovery(1, 5, {"route": "R1", "status": "fast"})
        brain.contribute_discovery(2, 5, {"route": "R1", "status": "fast"})
        brain.contribute_discovery(3, 5, {"route": "R1", "status": "blocked"})

        stored = brain.get_discoveries_for_timestep(5)
        assert len(stored) == 3

    def test_contribute_discovery_across_timesteps(self):
        """Discoveries are correctly separated by timestep."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(segment_name="commuters_north", backend=backend)

        brain.contribute_discovery(1, 1, {"route": "R1"})
        brain.contribute_discovery(2, 2, {"route": "R2"})
        brain.contribute_discovery(3, 3, {"route": "R3"})

        assert len(brain.get_discoveries_for_timestep(1)) == 1
        assert len(brain.get_discoveries_for_timestep(2)) == 1
        assert len(brain.get_discoveries_for_timestep(3)) == 1


class TestSegmentBrainDistillCollectiveTruth:
    """Tests for distill_collective_truth method."""

    def test_distill_collects_windowed_discoveries(self):
        """distill_collective_truth uses only current + lookback window."""
        backend = LocalKnowledgeGraphBackend()
        mock_llm = make_fake_llm(CollectiveTruth(
            timestep=5,
            preferred_routes=["Route_A"],
            avoid_zones=[],
            segment_mood="stable",
            confidence=0.9,
            dissenting_signals=[],
        ))
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=mock_llm,
        )

        # Add discoveries at T3 and T5
        brain.contribute_discovery(1, 3, {"route": "Route_A", "status": "fast"})
        brain.contribute_discovery(2, 5, {"route": "Route_A", "status": "blocked"})

        # With lookback=1, only T4 and T5 should be included (not T3)
        result = brain.distill_collective_truth(timestep=5, lookback=1)

        assert result.timestep == 5
        # Only the T5 discovery should have been passed to LLM
        assert mock_llm.call_count == 1
        assert len(mock_llm.last_input) == 1
        assert mock_llm.last_input[0]["timestep"] == 5

    def test_distill_with_conflict_produces_dissenting_signals(self):
        """2 'fast' + 1 'blocked' -> Route A in preferred_routes, dissenting_signals non-empty."""
        backend = LocalKnowledgeGraphBackend()

        def conflict_llm(discoveries: List[dict]) -> CollectiveTruth:
            # Discoveries are wrapped with sentinel_id, timestep, discovery_data
            route_a_fast = sum(
                1 for d in discoveries
                if d.get("discovery_data", {}).get("status") == "fast"
                and d.get("discovery_data", {}).get("route") == "Route_A"
            )
            route_a_blocked = sum(
                1 for d in discoveries
                if d.get("discovery_data", {}).get("status") == "blocked"
                and d.get("discovery_data", {}).get("route") == "Route_A"
            )
            dissenting = []
            if route_a_blocked > 0:
                dissenting.append("Route_A has conflicting reports")
            return CollectiveTruth(
                timestep=5,
                preferred_routes=["Route_A"],  # Still preferred
                avoid_zones=[],
                segment_mood="adaptive",
                confidence=0.5,  # Lower due to disagreement
                dissenting_signals=dissenting,
            )

        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=conflict_llm,
        )

        # Feed 3 discoveries: 2 "fast", 1 "blocked"
        brain.contribute_discovery(1, 5, {"route": "Route_A", "status": "fast"})
        brain.contribute_discovery(2, 5, {"route": "Route_A", "status": "fast"})
        brain.contribute_discovery(3, 5, {"route": "Route_A", "status": "blocked"})

        result = brain.distill_collective_truth(timestep=5, lookback=0)

        assert "Route_A" in result.preferred_routes
        assert len(result.dissenting_signals) > 0
        assert result.confidence < 0.7

    def test_distill_updates_current_truth(self):
        """distill_collective_truth updates the cached current_truth."""
        backend = LocalKnowledgeGraphBackend()
        mock_llm = make_fake_llm(CollectiveTruth(
            timestep=7,
            preferred_routes=["Route_X"],
            avoid_zones=["Zone_1"],
            segment_mood="optimistic",
            confidence=0.88,
            dissenting_signals=[],
        ))
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=mock_llm,
        )

        brain.contribute_discovery(1, 7, {"route": "Route_X"})
        result = brain.distill_collective_truth(timestep=7, lookback=0)

        current = brain.get_current_truth()
        assert current is not None
        assert current.timestep == 7
        assert current.preferred_routes == ["Route_X"]

    def test_distill_on_llm_failure_retains_previous_truth_stale(self):
        """If LLM returns None, previous truth is retained with stale=True."""
        backend = LocalKnowledgeGraphBackend()

        def failing_llm(discoveries: List[dict]) -> None:
            raise RuntimeError("LLM unavailable")

        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=failing_llm,
        )

        # First distill succeeds
        good_llm = make_fake_llm(CollectiveTruth(
            timestep=5,
            preferred_routes=["Route_A"],
            avoid_zones=[],
            segment_mood="stable",
            confidence=0.9,
            dissenting_signals=[],
        ))
        brain._llm = good_llm
        brain.contribute_discovery(1, 5, {"route": "Route_A"})
        brain.distill_collective_truth(timestep=5, lookback=0)

        # Now fail
        brain._llm = failing_llm
        brain.contribute_discovery(2, 6, {"route": "Route_B"})
        result = brain.distill_collective_truth(timestep=6, lookback=0)

        # Should retain previous truth
        assert result.preferred_routes == ["Route_A"]
        assert result.stale is True
        assert result.timestep == 5  # Previous timestep

    def test_distill_empty_discoveries_returns_default(self):
        """With no discoveries in window, returns a default CollectiveTruth."""
        backend = LocalKnowledgeGraphBackend()
        mock_llm = make_fake_llm(CollectiveTruth(
            timestep=10,
            preferred_routes=[],
            avoid_zones=[],
            segment_mood="stable",
            confidence=0.0,
            dissenting_signals=["No data available"],
        ))
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=mock_llm,
        )

        result = brain.distill_collective_truth(timestep=10, lookback=0)
        assert result.timestep == 10


class TestSegmentBrainUpdateSwarmStats:
    """Tests for update_swarm_stats method."""

    def test_update_swarm_stats_stores_tagged_by_timestep(self):
        """Swarm stats are stored and tagged by timestep."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(segment_name="commuters_north", backend=backend)

        brain.update_swarm_stats(3, {
            "total_agents": 1500,
            "avg_speed": 45.2,
            "congestion_level": 0.65,
        })

        stats = brain.get_stats_for_timestep(3)
        assert stats is not None
        assert stats["total_agents"] == 1500
        assert stats["avg_speed"] == 45.2
        assert stats["congestion_level"] == 0.65

    def test_update_swarm_stats_multiple_timesteps(self):
        """Stats from multiple timesteps are stored separately."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(segment_name="commuters_north", backend=backend)

        brain.update_swarm_stats(1, {"flow": 100})
        brain.update_swarm_stats(2, {"flow": 150})
        brain.update_swarm_stats(3, {"flow": 80})

        assert brain.get_stats_for_timestep(1)["flow"] == 100
        assert brain.get_stats_for_timestep(2)["flow"] == 150
        assert brain.get_stats_for_timestep(3)["flow"] == 80


class TestSegmentBrainGetCurrentTruth:
    """Tests for get_current_truth method."""

    def test_get_current_truth_returns_cached_truth(self):
        """get_current_truth returns the latest distilled CollectiveTruth (cached)."""
        backend = LocalKnowledgeGraphBackend()
        mock_llm = make_fake_llm(CollectiveTruth(
            timestep=5,
            preferred_routes=["Route_C"],
            avoid_zones=["Zone_2"],
            segment_mood="frustrated",
            confidence=0.72,
            dissenting_signals=["Congestion reported"],
        ))
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=mock_llm,
        )

        assert brain.get_current_truth() is None  # Not yet set

        brain.contribute_discovery(1, 5, {"route": "Route_C"})
        brain.distill_collective_truth(timestep=5, lookback=0)

        current = brain.get_current_truth()
        assert current is not None
        assert current.preferred_routes == ["Route_C"]
        assert current.segment_mood == "frustrated"

    def test_get_current_truth_returns_none_before_distillation(self):
        """Before any distillation, get_current_truth returns None."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(segment_name="commuters_north", backend=backend)

        assert brain.get_current_truth() is None


class TestSegmentBrainGetHistory:
    """Tests for get_history method."""

    def test_get_history_returns_collective_truths_in_range(self):
        """get_history returns CollectiveTruth objects between two timesteps."""
        backend = LocalKnowledgeGraphBackend()

        truths = [
            CollectiveTruth(timestep=1, preferred_routes=["R1"], avoid_zones=[], segment_mood="stable", confidence=0.9, dissenting_signals=[]),
            CollectiveTruth(timestep=2, preferred_routes=["R1", "R2"], avoid_zones=[], segment_mood="stable", confidence=0.85, dissenting_signals=[]),
            CollectiveTruth(timestep=3, preferred_routes=["R2"], avoid_zones=["Z1"], segment_mood="adaptive", confidence=0.78, dissenting_signals=["Congestion"]),
            CollectiveTruth(timestep=4, preferred_routes=["R2", "R3"], avoid_zones=[], segment_mood="optimistic", confidence=0.92, dissenting_signals=[]),
            CollectiveTruth(timestep=5, preferred_routes=["R3"], avoid_zones=[], segment_mood="stable", confidence=0.88, dissenting_signals=[]),
        ]

        brain = SegmentBrain(segment_name="commuters_north", backend=backend)

        # Inject truths directly into history
        for t in truths:
            brain._truth_history[t.timestep] = t

        history = brain.get_history(from_timestep=2, to_timestep=4)
        assert len(history) == 3
        assert [t.timestep for t in history] == [2, 3, 4]

    def test_get_history_empty_range(self):
        """get_history returns empty list when no truths in range."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(segment_name="commuters_north", backend=backend)

        history = brain.get_history(from_timestep=10, to_timestep=20)
        assert history == []


class TestSegmentBrainTimestepWindowing:
    """Tests for timestep-windowed behavior."""

    def test_only_windowed_discoveries_used_in_distillation(self):
        """Only current and lookback discoveries are used; older ones ignored."""
        backend = LocalKnowledgeGraphBackend()

        captured_inputs = []

        def mock_llm(discoveries: List[dict]) -> CollectiveTruth:
            captured_inputs.append(discoveries)
            return CollectiveTruth(
                timestep=5,
                preferred_routes=["Route_A"],
                avoid_zones=[],
                segment_mood="stable",
                confidence=0.9,
                dissenting_signals=[],
            )

        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=mock_llm,
        )

        # Add discoveries at T1, T2, T3, T4, T5
        for t in [1, 2, 3, 4, 5]:
            brain.contribute_discovery(t, t, {"timestep": t, "route": f"Route_{t}"})

        # With lookback=2 at T5, should include T3, T4, T5
        brain.distill_collective_truth(timestep=5, lookback=2)

        assert len(captured_inputs) == 1
        input_discoveries = captured_inputs[0]
        input_timesteps = {d["timestep"] for d in input_discoveries}
        # Should have T3, T4, T5 (3 discoveries)
        assert input_timesteps == {3, 4, 5}
        # T1 and T2 should NOT be present
        assert 1 not in input_timesteps
        assert 2 not in input_timesteps

    def test_lookback_0_includes_only_current_timestep(self):
        """lookback=0 means only the current timestep's discoveries are used."""
        backend = LocalKnowledgeGraphBackend()

        captured_inputs = []

        def mock_llm(discoveries: List[dict]) -> CollectiveTruth:
            captured_inputs.append(discoveries)
            return CollectiveTruth(
                timestep=5,
                preferred_routes=["Route_A"],
                avoid_zones=[],
                segment_mood="stable",
                confidence=0.9,
                dissenting_signals=[],
            )

        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
            llm_provider=mock_llm,
        )

        brain.contribute_discovery(1, 4, {"route": "Route_A"})
        brain.contribute_discovery(2, 4, {"route": "Route_B"})
        brain.contribute_discovery(3, 5, {"route": "Route_C"})

        brain.distill_collective_truth(timestep=5, lookback=0)

        assert len(captured_inputs) == 1
        input_timesteps = {d["timestep"] for d in captured_inputs[0]}
        # Only T5
        assert input_timesteps == {5}


class TestSegmentBrainDistillationPrompt:
    """Tests for _build_distillation_prompt method."""

    def test_prompt_includes_segment_name(self):
        """Distillation prompt includes the segment name."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(
            segment_name="office_workers",
            backend=backend,
        )

        prompt = brain._build_distillation_prompt(timestep=5, lookback=1)
        assert "office_workers" in prompt

    def test_prompt_includes_timestep_context(self):
        """Prompt includes the current timestep number."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
        )

        prompt = brain._build_distillation_prompt(timestep=5, lookback=2)
        assert "timestep 5" in prompt

    def test_prompt_includes_recent_discoveries(self):
        """Prompt includes discoveries from the lookback window."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
        )

        brain.contribute_discovery(1, 3, {"route": "Route_A", "status": "fast", "speed_kmh": 45})
        brain.contribute_discovery(2, 4, {"route": "Route_B", "status": "blocked", "speed_kmh": 10})
        brain.contribute_discovery(3, 5, {"route": "Route_A", "status": "congested", "speed_kmh": 20})

        prompt = brain._build_distillation_prompt(timestep=5, lookback=2)

        # Should include discoveries from T3, T4, T5
        assert "Route_A" in prompt
        assert "Route_B" in prompt
        assert "Sentinel 1" in prompt or "Sentinel 2" in prompt

    def test_prompt_empty_when_no_discoveries(self):
        """Prompt indicates no observations when window is empty."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
        )

        prompt = brain._build_distillation_prompt(timestep=5, lookback=1)
        assert "No recent observations" in prompt or "No observations" in prompt

    def test_prompt_requests_json_response_format(self):
        """Prompt instructs LLM to return JSON with required fields."""
        backend = LocalKnowledgeGraphBackend()
        brain = SegmentBrain(
            segment_name="commuters_north",
            backend=backend,
        )

        prompt = brain._build_distillation_prompt(timestep=5, lookback=0)
        assert "preferred_routes" in prompt
        assert "avoid_zones" in prompt
        assert "segment_mood" in prompt
        assert "confidence" in prompt
        assert "dissenting_signals" in prompt