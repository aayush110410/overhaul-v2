from dataclasses import dataclass, field
from typing import List, Any, Dict

@dataclass
class ParsedSimulationBrief:
    avg_speed_kmh: float
    congestion_pct: float
    pm25_kg: float
    co2_tonnes: float
    emergent_hotspots: List[Dict[str, Any]] = field(default_factory=list)
    mode_shift_count: int = 0
    segment_insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)

class LDRAGOParser:
    def parse(self, swarm_result) -> ParsedSimulationBrief:
        """Parse SwarmResult into structured brief."""
        hotspots = getattr(swarm_result, 'hotspots', []) or []
        return ParsedSimulationBrief(
            avg_speed_kmh=getattr(swarm_result, 'avg_speed_kmh', 0),
            congestion_pct=getattr(swarm_result, 'congestion_pct', 0),
            pm25_kg=getattr(swarm_result, 'total_pm25_g', 0) / 1000,
            co2_tonnes=getattr(swarm_result, 'total_co2_kg', 0) / 1000,
            emergent_hotspots=list(hotspots),
            mode_shift_count=getattr(swarm_result, 'total_mode_shifts', 0),
            data_sources=getattr(swarm_result, 'metadata', {}).get('live_data_sources', []) if hasattr(swarm_result, 'metadata') else [],
        )

    def generate_markdown(self, brief: ParsedSimulationBrief) -> str:
        """Generate markdown summary from parsed brief."""
        lines = [
            "# Simulation Brief — LDRAGO v2",
            "",
            f"**Average Speed:** {brief.avg_speed_kmh} km/h",
            f"**Congestion:** {brief.congestion_pct}%",
            f"**CO₂:** {brief.co2_tonnes}t",
            f"**PM2.5:** {brief.pm25_kg * 1000:.0f}g",
            f"**Mode Shifts:** {brief.mode_shift_count}",
            f"**Hotspots:** {len(brief.emergent_hotspots)}",
            "",
        ]
        if brief.recommendations:
            lines.append("## Recommendations")
            for rec in brief.recommendations:
                lines.append(f"- {rec}")
        return "\n".join(lines)