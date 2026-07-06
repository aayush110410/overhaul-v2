"""SimulationState — the single source of truth for the /simulate/hive contract.

Pydantic v2 mirror of ``simulation_state.schema.json``. Used as the FastAPI
``response_model`` so every hive response is schema-validated, and imported by
the frontend's expectations (brains[], sentinels[], geojson, timesteps[],
engine_results, report). This is what kills the historical /chat-vs-frontend
field drift (PATH.md Phase 1).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Stable segment vocabulary shared with the frontend label map.
SEGMENT_LABELS: Dict[str, str] = {
    "office_workers": "Office Workers",
    "gig_workers": "Gig Workers",
    "students": "Students",
    "service_sector": "Service Sector",
    "industrial_workers": "Industrial",
    "senior_citizens": "Seniors",
    "high_income": "High Income",
}


class BrainState(BaseModel):
    segment: str
    label: str
    segment_mood: str = "stable"
    confidence: float = 0.0
    preferred_routes: List[str] = Field(default_factory=list)
    avoid_zones: List[str] = Field(default_factory=list)
    dissenting_signals: List[str] = Field(default_factory=list)
    stale: bool = False


class SentinelTrace(BaseModel):
    why: str = ""
    route: List[str] = Field(default_factory=list)
    fallback: bool = False


class SentinelState(BaseModel):
    id: int
    segment: str
    coords: List[float]  # [lon, lat]
    mood: str = "stable"
    confidence: float = 0.0
    trace: SentinelTrace = Field(default_factory=SentinelTrace)


class TimestepState(BaseModel):
    step: int
    avg_speed_kmh: float = 0.0
    congestion_pct: float = 0.0
    agents_arrived: int = 0
    mode_shifts: int = 0
    sentinel_discoveries: int = 0
    distillations: int = 0
    swarm_inherited_routes: int = 0
    sentinel_fallbacks: int = 0


class ReportState(BaseModel):
    verdict: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    recommendations: List[str] = Field(default_factory=list)
    segment_insights: Dict[str, Any] = Field(default_factory=dict)


class SimulationState(BaseModel):
    query: str
    city: str = "delhi"
    scenario: str = ""
    brains: List[BrainState] = Field(default_factory=list)
    sentinels: List[SentinelState] = Field(default_factory=list)
    geojson: Dict[str, Any] = Field(default_factory=dict)
    timesteps: List[TimestepState] = Field(default_factory=list)
    engine_results: Dict[str, Any] = Field(default_factory=dict)
    report: ReportState = Field(default_factory=ReportState)
    stats: Dict[str, Any] = Field(default_factory=dict)
    manifest: Dict[str, Any] = Field(default_factory=dict)
