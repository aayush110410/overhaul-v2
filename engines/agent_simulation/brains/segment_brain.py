"""SegmentBrain - Hive component managing collective memory for one population segment."""
from typing import List, Optional, Callable, Dict, Any

from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
from engines.agent_simulation.brains.collective_truth import CollectiveTruth


class SegmentBrain:
    """Manages collective memory and truth distillation for one population segment.

    The SegmentBrain is the core Hive component. It:
    - Stores discoveries from Sentinel agents (contribute_discovery)
    - Distills discoveries into a CollectiveTruth via LLM (distill_collective_truth)
    - Caches the current truth for SwarmAgents to consume (get_current_truth)
    - Records aggregate swarm behavior stats (update_swarm_stats)
    - Provides historical timeline (get_history)

    The LLM is passed as a dependency (llm_provider) to avoid coupling to a
    specific LLM implementation. This also makes testing straightforward via mocks.

    Args:
        segment_name: Identifier for this population segment (e.g. "commuters_north").
        backend: KnowledgeGraphBackend instance for persistence (interface-based).
        llm_provider: Optional callable that takes a list of discovery dicts and
            returns a CollectiveTruth. If not provided, a default synthesis is used.
    """

    def __init__(
        self,
        segment_name: str,
        backend: KnowledgeGraphBackend,
        llm_provider: Optional[Callable[[List[dict]], CollectiveTruth]] = None,
    ) -> None:
        self.segment_name = segment_name
        self._backend = backend
        self._llm: Optional[Callable[[List[dict]], CollectiveTruth]] = llm_provider

        # Internal state
        self._discoveries: Dict[int, List[dict]] = {}  # timestep -> list of discovery dicts
        self._stats: Dict[int, dict] = {}  # timestep -> stats dict
        self._current_truth: Optional[CollectiveTruth] = None
        self._current_truth_timestep: Optional[int] = None
        self._truth_history: Dict[int, CollectiveTruth] = {}  # timestep -> CollectiveTruth

    @property
    def llm_provider(self) -> Optional[Callable[[List[dict]], CollectiveTruth]]:
        """Return the LLM provider."""
        return self._llm

    def set_llm_provider(self, provider: Callable[[List[dict]], CollectiveTruth]) -> None:
        """Set or replace the LLM provider."""
        self._llm = provider

    def record_truth(self, truth: CollectiveTruth) -> None:
        """Store a CollectiveTruth produced by the async, gateway-driven hive
        distillation path.

        Mirrors the cache update ``distill_collective_truth`` performs so that
        ``get_current_truth()`` / ``get_history()`` (and therefore the swarm and
        the ReportAgent) see the gateway-distilled truth. Used when distillation
        runs through the ReasoningGateway instead of the sync ``_llm`` callable.
        """
        self._current_truth = truth
        self._current_truth_timestep = truth.timestep
        self._truth_history[truth.timestep] = truth

    def contribute_discovery(
        self,
        sentinel_id: int,
        timestep: int,
        discovery_data: dict,
    ) -> None:
        """Tag and store a discovery from a Sentinel agent.

        Args:
            sentinel_id: ID of the Sentinel agent that produced this discovery.
            timestep: Simulation timestep when the discovery was made.
            discovery_data: Arbitrary dict containing route status, traffic info, etc.
        """
        entry = {
            "sentinel_id": sentinel_id,
            "timestep": timestep,
            "discovery_data": discovery_data,
        }
        if timestep not in self._discoveries:
            self._discoveries[timestep] = []
        self._discoveries[timestep].append(entry)

    def get_discoveries_for_timestep(self, timestep: int) -> List[dict]:
        """Return all discoveries for a specific timestep (for testing)."""
        return list(self._discoveries.get(timestep, []))

    def _filter_window(self, current_timestep: int, lookback: int) -> List[dict]:
        """Return discoveries within the [current_timestep - lookback, current_timestep] window."""
        min_timestep = current_timestep - lookback
        result = []
        for t in range(min_timestep, current_timestep + 1):
            result.extend(self._discoveries.get(t, []))
        return result

    def distill_collective_truth(
        self,
        timestep: int,
        lookback: int = 1,
    ) -> CollectiveTruth:
        """Synthesize discoveries from the window into a CollectiveTruth via LLM.

        Filters discoveries to the timestep window [timestep - lookback, timestep],
        then calls the LLM provider to synthesize them into a CollectiveTruth.

        If the LLM call fails (returns None or raises), the previous truth is
        returned with stale=True.

        Args:
            timestep: The current simulation timestep.
            lookback: Number of previous timesteps to include (default 1).

        Returns:
            CollectiveTruth with all 6 fields populated.
        """
        discoveries = self._filter_window(timestep, lookback)

        if self._llm is None:
            # No LLM configured — return a default truth
            return CollectiveTruth(
                timestep=timestep,
                preferred_routes=[],
                avoid_zones=[],
                segment_mood="stable",
                confidence=0.0,
                dissenting_signals=["No LLM configured for distillation"],
                stale=True,
            )

        try:
            truth = self._llm(discoveries)
            if truth is None:
                raise ValueError("LLM returned None")
        except Exception:
            # LLM failure — retain previous truth, mark stale
            if self._current_truth is not None:
                return CollectiveTruth(
                    timestep=self._current_truth.timestep,
                    preferred_routes=self._current_truth.preferred_routes,
                    avoid_zones=self._current_truth.avoid_zones,
                    segment_mood=self._current_truth.segment_mood,
                    confidence=self._current_truth.confidence,
                    dissenting_signals=self._current_truth.dissenting_signals + ["LLM distillation failed"],
                    stale=True,
                )
            else:
                return CollectiveTruth(
                    timestep=timestep,
                    preferred_routes=[],
                    avoid_zones=[],
                    segment_mood="stable",
                    confidence=0.0,
                    dissenting_signals=["LLM distillation failed — no prior truth available"],
                    stale=True,
                )

        # Update cached truth
        self._current_truth = truth
        self._current_truth_timestep = timestep
        self._truth_history[timestep] = truth
        return truth

    def update_swarm_stats(self, timestep: int, stats_data: dict) -> None:
        """Record aggregate swarm behavior for a timestep.

        This is written by the swarm after execution — no LLM involved.

        Args:
            timestep: Simulation timestep.
            stats_data: Dict containing flow, avg_speed, congestion_level, etc.
        """
        self._stats[timestep] = stats_data

    def get_stats_for_timestep(self, timestep: int) -> Optional[dict]:
        """Return swarm stats for a specific timestep (for testing)."""
        return self._stats.get(timestep)

    def get_current_truth(self) -> Optional[CollectiveTruth]:
        """Return the cached latest distilled CollectiveTruth.

        Returns None if no distillation has occurred yet.
        """
        return self._current_truth

    def get_history(
        self,
        from_timestep: int,
        to_timestep: int,
    ) -> List[CollectiveTruth]:
        """Return CollectiveTruth objects for timesteps in the given range (inclusive).

        Args:
            from_timestep: Start of the range (inclusive).
            to_timestep: End of the range (inclusive).

        Returns:
            List of CollectiveTruth objects, ordered by timestep ascending.
        """
        result = []
        for t in range(from_timestep, to_timestep + 1):
            if t in self._truth_history:
                result.append(self._truth_history[t])
        return result

    def _build_distillation_prompt(self, timestep: int, lookback: int) -> str:
        """Build a distillation prompt from discoveries in the window.

        Args:
            timestep: The current simulation timestep.
            lookback: Number of previous timesteps to include.

        Returns:
            A well-structured prompt for LLM distillation.
        """
        discoveries = self._filter_window(timestep, lookback)

        if not discoveries:
            return f"""No recent observations for {self.segment_name} at timestep {timestep}.
Synthesize a stable state. Respond with ONLY valid JSON:
{{"preferred_routes": [], "avoid_zones": [], "segment_mood": "stable", "confidence": 0.0, "dissenting_signals": ["No data available"]}}"""

        lines = []
        for d in discoveries:
            data = d.get("discovery_data", {})
            lines.append(
                f"- Sentinel {d.get('sentinel_id', '?')} at timestep {d.get('timestep', '?')}: "
                f"{data.get('observation', data.get('route', 'N/A'))} "
                f"(status: {data.get('status', 'unknown')}, "
                f"speed: {data.get('speed_kmh', data.get('speed', '?'))} km/h, "
                f"congestion: {data.get('congestion_level', '?')})"
            )
        discoveries_text = "\n".join(lines) if lines else "No observations."

        return f"""You are the collective intelligence coordinator for the {self.segment_name} population segment in Delhi NCR.

Recent sentinel observations:
{discoveries_text}

Synthesize the collective truth for {self.segment_name} at timestep {timestep}.
Consider:
- What routes are preferred based on reported speeds and congestion?
- What zones should be avoided based on status reports?
- What is the overall mood (frustrated/adaptive/stable/optimistic)?
- Are there conflicting signals that should be noted as dissenting?

Respond with ONLY valid JSON:
{{"preferred_routes": [...], "avoid_zones": [...], "segment_mood": "frustrated|adaptive|stable|optimistic", "confidence": 0.0-1.0, "dissenting_signals": [...]}}"""