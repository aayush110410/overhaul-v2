"""ReportAgent - Quantitative-first simulation brief generator.

The ReportAgent generates a structured policy brief from simulation results
using agent traces and SegmentBrain history.

Flow:
  1. Aggregate metrics from SwarmResult
  2. Collect Sentinel reasoning traces from SegmentBrain
  3. Get CollectiveTruth history from each SegmentBrain
  4. Use LLM to synthesize a narrative explanation of "why"
  5. Output structured brief with verdict.json + markdown summary

Output structure:
  {
    "verdict": {
      "verdict": "approve|reject|conditional",
      "confidence": 0.0-1.0,
      "key_metrics": {...},
      "hotspots": [...],
    },
    "summary": "markdown string",
    "sentinel_traces": [...],
    "segment_insights": {...},
    "recommendations": [...],
  }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engines.agent_simulation.brains.segment_brain import SegmentBrain

LOGGER = logging.getLogger(__name__)


@dataclass
class ReportConfig:
    """Configuration for ReportAgent."""
    include_sentinel_traces: bool = True
    include_segment_history: bool = True
    max_trace_entries: int = 20
    llm_model: str = "qwen/qwen3-4b"


@dataclass
class SimulationReport:
    """Complete simulation report from ReportAgent."""
    verdict: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    sentinel_traces: List[Dict[str, Any]] = field(default_factory=list)
    segment_insights: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    raw_metrics: Dict[str, Any] = field(default_factory=dict)


class ReportAgent:
    """Generates structured simulation briefs from agent traces.

    Args:
        segment_brains: Dict mapping segment name → SegmentBrain instance.
        llm_provider: Optional callable that takes report context and returns
            a summary string.
        config: Report configuration.
    """

    def __init__(
        self,
        segment_brains: Dict[str, SegmentBrain],
        llm_provider: Optional[callable] = None,
        config: Optional[ReportConfig] = None,
    ) -> None:
        self.segment_brains = segment_brains
        self._llm = llm_provider
        self.config = config or ReportConfig()

    def generate_verdict(
        self,
        swarm_result: Any,
    ) -> Dict[str, Any]:
        """Generate a verdict from swarm simulation results.

        Args:
            swarm_result: SwarmResult from UrbanSwarm.run().

        Returns:
            Dict with verdict, confidence, key_metrics, and hotspots.
        """
        # Extract key metrics
        hotspots = getattr(swarm_result, 'hotspots', []) or []
        avg_speed = getattr(swarm_result, 'avg_speed_kmh', 0)
        congestion_pct = getattr(swarm_result, 'congestion_pct', 0)
        ev_share = getattr(swarm_result, 'ev_share', 0)

        # Simple heuristic verdict
        if congestion_pct > 40:
            verdict = "reject"
            confidence = 0.8
        elif congestion_pct > 25:
            verdict = "conditional"
            confidence = 0.6
        else:
            verdict = "approve"
            confidence = 0.7

        return {
            "verdict": verdict,
            "confidence": confidence,
            "key_metrics": {
                "avg_speed_kmh": avg_speed,
                "congestion_pct": congestion_pct,
                "ev_share": ev_share,
                "total_vkt": getattr(swarm_result, 'total_vkt', 0),
            },
            "hotspots": hotspots[:5],
        }

    def collect_segment_insights(self) -> Dict[str, Any]:
        """Collect CollectiveTruth history from all SegmentBrains.

        Returns:
            Dict mapping segment name → list of CollectiveTruth dicts.
        """
        insights = {}
        for seg_name, brain in self.segment_brains.items():
            history = brain.get_history(0, 999)  # All timesteps
            insights[seg_name] = [
                {
                    "timestep": ct.timestep,
                    "mood": ct.segment_mood,
                    "confidence": ct.confidence,
                    "preferred_routes": ct.preferred_routes[:3],
                    "avoid_zones": ct.avoid_zones[:3],
                    "dissenting_signals": ct.dissenting_signals[:2],
                    "stale": ct.stale,
                }
                for ct in history[-self.config.max_trace_entries:]
            ]
        return insights

    def generate_summary(
        self,
        verdict: Dict[str, Any],
        segment_insights: Dict[str, Any],
    ) -> str:
        """Generate markdown summary from verdict and segment insights.

        Args:
            verdict: Verdict dict from generate_verdict().
            segment_insights: Dict from collect_segment_insights().

        Returns:
            Markdown string summary.
        """
        if self._llm is not None:
            try:
                context = {"verdict": verdict, "segment_insights": segment_insights}
                return self._llm(context)
            except Exception:
                pass

        # Fallback: rule-based summary
        mood_summary = []
        for seg, truths in segment_insights.items():
            if truths:
                latest = truths[-1]
                mood_summary.append(f"{seg}: {latest['mood']} (conf={latest['confidence']:.2f})")

        summary = [
            f"# Simulation Report",
            f"",
            f"## Verdict: {verdict['verdict'].upper()}",
            f"Confidence: {verdict['confidence']:.0%}",
            f"",
            f"## Key Metrics",
            f"- Congestion: {verdict['key_metrics']['congestion_pct']:.1f}%",
            f"- Avg Speed: {verdict['key_metrics']['avg_speed_kmh']:.1f} km/h",
            f"- EV Share: {verdict['key_metrics']['ev_share']:.1%}",
            f"",
            f"## Segment Moods",
        ] + [f"- {s}" for s in mood_summary]

        return "\n".join(summary)

    def generate_report(
        self,
        swarm_result: Any,
    ) -> SimulationReport:
        """Generate complete simulation report.

        Args:
            swarm_result: SwarmResult from UrbanSwarm.run().

        Returns:
            SimulationReport with verdict, summary, traces, and recommendations.
        """
        # Generate verdict
        verdict = self.generate_verdict(swarm_result)

        # Collect segment insights
        segment_insights = self.collect_segment_insights()

        # Generate summary
        summary = self.generate_summary(verdict, segment_insights)

        # Build recommendations
        recommendations = []
        if verdict['key_metrics']['congestion_pct'] > 30:
            recommendations.append("Consider congestion pricing to reduce peak demand")
        if verdict['key_metrics']['ev_share'] < 0.15:
            recommendations.append("Increase EV incentives to boost adoption")
        if verdict['key_metrics']['avg_speed_kmh'] < 25:
            recommendations.append("Optimize signal timing on congested corridors")

        return SimulationReport(
            verdict=verdict,
            summary=summary,
            sentinel_traces=[],  # TODO: collect from sentinel agent history
            segment_insights=segment_insights,
            recommendations=recommendations,
            raw_metrics={
                "congestion_pct": verdict['key_metrics']['congestion_pct'],
                "avg_speed_kmh": verdict['key_metrics']['avg_speed_kmh'],
                "ev_share": verdict['key_metrics']['ev_share'],
                "total_vkt": verdict['key_metrics']['total_vkt'],
            },
        )
