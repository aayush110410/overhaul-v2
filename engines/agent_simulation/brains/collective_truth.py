"""CollectiveTruth dataclass for hive-wide consensus signal."""
from dataclasses import dataclass, asdict
from typing import List


VALID_MOODS = frozenset({"frustrated", "adaptive", "stable", "optimistic"})


@dataclass
class CollectiveTruth:
    """Represents the distilled collective state of a segment at a given timestep.

    Synthesized from sentinel discoveries via LLM distillation. This is the
    primary output of the Hive loop that SwarmAgents consume for routing.

    Attributes:
        timestep: Simulation timestep this truth represents.
        preferred_routes: Ranked list of edge IDs the segment should prefer.
        avoid_zones: Edge IDs to penalize (congestion, closure, etc.).
        segment_mood: Aggregate sentiment — frustrated/adaptive/stable/optimistic.
        confidence: Signal strength (0.0-1.0). Low confidence = conflicting signals.
        dissenting_signals: List of contradictory findings for transparency.
        stale: True if this truth was retained from a previous timestep due to
            LLM distillation failure (confidence should be discounted).
    """

    timestep: int
    preferred_routes: List[str]
    avoid_zones: List[str]
    segment_mood: str
    confidence: float
    dissenting_signals: List[str]
    stale: bool = False

    def __post_init__(self) -> None:
        """Validate confidence range and mood values."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if self.segment_mood not in VALID_MOODS:
            raise ValueError(
                f"segment_mood must be one of: {', '.join(sorted(VALID_MOODS))}, "
                f"got '{self.segment_mood}'"
            )

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary (JSON-compatible)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CollectiveTruth":
        """Reconstruct from a plain dictionary."""
        # Accept both old-style field names and new
        return cls(
            timestep=int(data["timestep"]),
            preferred_routes=list(data["preferred_routes"]),
            avoid_zones=list(data["avoid_zones"]),
            segment_mood=str(data["segment_mood"]),
            confidence=float(data["confidence"]),
            dissenting_signals=list(data["dissenting_signals"]),
            stale=bool(data.get("stale", False)),
        )