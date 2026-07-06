"""Tests for CollectiveTruth dataclass."""
import pytest
from typing import List

from engines.agent_simulation.brains.collective_truth import CollectiveTruth


class TestCollectiveTruthInstantiation:
    """Test that CollectiveTruth can be instantiated with all required fields."""

    def test_instantiation_with_all_fields(self):
        """Test that CollectiveTruth can be instantiated with all required fields."""
        ct = CollectiveTruth(
            timestep=5,
            preferred_routes=["Route_A", "Route_B"],
            avoid_zones=["Zone_3", "Zone_7"],
            segment_mood="adaptive",
            confidence=0.85,
            dissenting_signals=["Route_B has construction"],
        )
        assert ct.timestep == 5
        assert ct.preferred_routes == ["Route_A", "Route_B"]
        assert ct.avoid_zones == ["Zone_3", "Zone_7"]
        assert ct.segment_mood == "adaptive"
        assert ct.confidence == 0.85
        assert ct.dissenting_signals == ["Route_B has construction"]

    def test_stale_attribute_default_false(self):
        """Test that stale attribute defaults to False."""
        ct = CollectiveTruth(
            timestep=1,
            preferred_routes=["Route_A"],
            avoid_zones=[],
            segment_mood="stable",
            confidence=1.0,
            dissenting_signals=[],
        )
        assert ct.stale is False

    def test_stale_attribute_can_be_set(self):
        """Test that stale attribute can be explicitly set."""
        ct = CollectiveTruth(
            timestep=1,
            preferred_routes=["Route_A"],
            avoid_zones=[],
            segment_mood="stable",
            confidence=1.0,
            dissenting_signals=[],
            stale=True,
        )
        assert ct.stale is True


class TestCollectiveTruthSerialization:
    """Test serialization round-trip via to_dict and from_dict."""

    def test_to_dict_includes_all_fields(self):
        """Test that to_dict includes all fields including stale."""
        ct = CollectiveTruth(
            timestep=3,
            preferred_routes=["Route_X"],
            avoid_zones=["Zone_1"],
            segment_mood="frustrated",
            confidence=0.6,
            dissenting_signals=["Traffic jam reported"],
            stale=True,
        )
        d = ct.to_dict()
        assert d["timestep"] == 3
        assert d["preferred_routes"] == ["Route_X"]
        assert d["avoid_zones"] == ["Zone_1"]
        assert d["segment_mood"] == "frustrated"
        assert d["confidence"] == 0.6
        assert d["dissenting_signals"] == ["Traffic jam reported"]
        assert d["stale"] is True

    def test_from_dict_recreates_object(self):
        """Test that from_dict recreates the same object."""
        original = CollectiveTruth(
            timestep=7,
            preferred_routes=["Route_A", "Route_C"],
            avoid_zones=["Zone_5"],
            segment_mood="optimistic",
            confidence=0.92,
            dissenting_signals=["Minor delay on Route_C"],
            stale=False,
        )
        d = original.to_dict()
        recreated = CollectiveTruth.from_dict(d)
        assert recreated.timestep == original.timestep
        assert recreated.preferred_routes == original.preferred_routes
        assert recreated.avoid_zones == original.avoid_zones
        assert recreated.segment_mood == original.segment_mood
        assert recreated.confidence == original.confidence
        assert recreated.dissenting_signals == original.dissenting_signals
        assert recreated.stale == original.stale

    def test_roundtrip_preserves_data(self):
        """Test that serialization round-trip preserves all data."""
        original = CollectiveTruth(
            timestep=10,
            preferred_routes=["R1", "R2", "R3"],
            avoid_zones=["Z1", "Z2"],
            segment_mood="adaptive",
            confidence=0.75,
            dissenting_signals=["Signal1", "Signal2", "Signal3"],
            stale=True,
        )
        json_str = str(original.to_dict())
        restored = CollectiveTruth.from_dict(eval(json_str))
        assert restored.timestep == 10
        assert restored.preferred_routes == ["R1", "R2", "R3"]
        assert restored.avoid_zones == ["Z1", "Z2"]
        assert restored.segment_mood == "adaptive"
        assert restored.confidence == 0.75
        assert restored.dissenting_signals == ["Signal1", "Signal2", "Signal3"]
        assert restored.stale is True


class TestCollectiveTruthValidation:
    """Test validation of confidence range and mood values."""

    @pytest.mark.parametrize("invalid_confidence", [-0.1, -1.0, 1.1, 1.5, 2.0])
    def test_confidence_must_be_between_0_and_1_low(self, invalid_confidence):
        """Test that confidence < 0 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            CollectiveTruth(
                timestep=1,
                preferred_routes=[],
                avoid_zones=[],
                segment_mood="stable",
                confidence=invalid_confidence,
                dissenting_signals=[],
            )

    @pytest.mark.parametrize("invalid_confidence", [1.01, 1.5, 2.0])
    def test_confidence_must_be_between_0_and_1_high(self, invalid_confidence):
        """Test that confidence > 1 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            CollectiveTruth(
                timestep=1,
                preferred_routes=[],
                avoid_zones=[],
                segment_mood="stable",
                confidence=invalid_confidence,
                dissenting_signals=[],
            )

    @pytest.mark.parametrize("valid_confidence", [0.0, 0.5, 1.0, 0.123, 0.999])
    def test_valid_confidence_values(self, valid_confidence):
        """Test that valid confidence values (0 to 1 inclusive) are accepted."""
        ct = CollectiveTruth(
            timestep=1,
            preferred_routes=[],
            avoid_zones=[],
            segment_mood="stable",
            confidence=valid_confidence,
            dissenting_signals=[],
        )
        assert ct.confidence == valid_confidence

    @pytest.mark.parametrize("invalid_mood", ["happy", "sad", "angry", "confused", "UNKNOWN", ""])
    def test_segment_mood_must_be_valid(self, invalid_mood):
        """Test that invalid mood values raise ValueError."""
        with pytest.raises(ValueError, match="segment_mood must be one of:"):
            CollectiveTruth(
                timestep=1,
                preferred_routes=[],
                avoid_zones=[],
                segment_mood=invalid_mood,
                confidence=0.5,
                dissenting_signals=[],
            )

    @pytest.mark.parametrize("valid_mood", ["frustrated", "adaptive", "stable", "optimistic"])
    def test_valid_mood_values(self, valid_mood):
        """Test that valid mood values are accepted."""
        ct = CollectiveTruth(
            timestep=1,
            preferred_routes=[],
            avoid_zones=[],
            segment_mood=valid_mood,
            confidence=0.5,
            dissenting_signals=[],
        )
        assert ct.segment_mood == valid_mood