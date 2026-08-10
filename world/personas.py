"""Income-strata personas: the human-behavior layer of the Living World.

Six India income bands (annual household income; outside India the same keys
mean relative local tiers — see the region template) each carry a behavioral
signature: transport-mode propensities, departure discipline, weather
sensitivity, and work-from-home ability. A sampled persona's final mode blends
its stratum's propensities with the REGION's real mode split, so a Noida
lt_3L persona rides a two-wheeler or bus while a Manhattan one takes transit.

Personas feed three consumers:
  - MovementSim agent specs (mode / segment / departure jitter),
  - sentinel LLM prompts (``sentinel_context()`` → richer, human reasoning),
  - the PopulationEngine's 7 segments (via ``SEGMENT_MAP``).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List

from shared.contracts.simulation_state import SEGMENT_LABELS
from world.region import RegionProfile

STRATA: List[str] = ["lt_3L", "3_5L", "5_10L", "10_20L", "20L_1Cr", "gt_1Cr"]

STRATA_LABELS: Dict[str, str] = {
    "lt_3L": "under ₹3 lakh/yr (low income)",
    "3_5L": "₹3-5 lakh/yr (lower middle)",
    "5_10L": "₹5-10 lakh/yr (middle)",
    "10_20L": "₹10-20 lakh/yr (upper middle)",
    "20L_1Cr": "₹20 lakh-1 crore/yr (affluent)",
    "gt_1Cr": "above ₹1 crore/yr (wealthy)",
}

# Behavioral signatures per stratum. modes must sum to 1; weather_sensitivity
# scales how strongly rain/heat suppress or delay trips (2-wheeler & walking
# households feel weather hardest); wfh = probability the persona CAN work
# remotely (used by sentinel prompts + the population engine, not movement).
STRATA_BEHAVIOR: Dict[str, Dict[str, Any]] = {
    "lt_3L": {
        "modes": {"walk": 0.28, "two_wheeler": 0.22, "bus": 0.38, "auto": 0.10, "car": 0.02},
        "depart_window_min": 20, "weather_sensitivity": 1.35, "wfh": 0.02,
    },
    "3_5L": {
        "modes": {"walk": 0.12, "two_wheeler": 0.44, "bus": 0.30, "auto": 0.09, "car": 0.05},
        "depart_window_min": 25, "weather_sensitivity": 1.25, "wfh": 0.05,
    },
    "5_10L": {
        "modes": {"walk": 0.07, "two_wheeler": 0.40, "bus": 0.21, "auto": 0.12, "car": 0.20},
        "depart_window_min": 30, "weather_sensitivity": 1.1, "wfh": 0.12,
    },
    "10_20L": {
        "modes": {"walk": 0.06, "two_wheeler": 0.24, "bus": 0.12, "auto": 0.14, "car": 0.44},
        "depart_window_min": 35, "weather_sensitivity": 0.95, "wfh": 0.2,
    },
    "20L_1Cr": {
        "modes": {"walk": 0.08, "two_wheeler": 0.07, "bus": 0.05, "auto": 0.12, "car": 0.68},
        "depart_window_min": 45, "weather_sensitivity": 0.85, "wfh": 0.3,
    },
    "gt_1Cr": {
        "modes": {"walk": 0.08, "two_wheeler": 0.01, "bus": 0.01, "auto": 0.05, "car": 0.85},
        "depart_window_min": 60, "weather_sensitivity": 0.8, "wfh": 0.35,
    },
}

# Stratum → population-segment propensities (keys from SEGMENT_LABELS).
SEGMENT_MAP: Dict[str, Dict[str, float]] = {
    "lt_3L": {"service_sector": 0.35, "industrial_workers": 0.30, "gig_workers": 0.20, "students": 0.10, "senior_citizens": 0.05},
    "3_5L": {"gig_workers": 0.30, "service_sector": 0.30, "industrial_workers": 0.15, "students": 0.15, "office_workers": 0.10},
    "5_10L": {"office_workers": 0.40, "students": 0.20, "service_sector": 0.15, "gig_workers": 0.15, "senior_citizens": 0.10},
    "10_20L": {"office_workers": 0.60, "students": 0.10, "senior_citizens": 0.10, "high_income": 0.10, "service_sector": 0.10},
    "20L_1Cr": {"high_income": 0.45, "office_workers": 0.40, "senior_citizens": 0.15},
    "gt_1Cr": {"high_income": 0.75, "office_workers": 0.15, "senior_citizens": 0.10},
}

# Mode choice = stratum propensity × regional availability, renormalized.
# Multiplicative, not averaged: a mode that barely exists in the region
# (two-wheelers in Manhattan) stays rare for EVERY stratum, while regional
# staples win only among strata inclined to use them.


@dataclass(frozen=True)
class Persona:
    stratum: str
    segment: str
    mode: str
    depart_window_min: int
    weather_sensitivity: float
    wfh_capable: bool

    def sentinel_context(self) -> Dict[str, Any]:
        """Extra keys merged into a sentinel's LLM reasoning context."""
        return {
            "stratum": self.stratum,
            "income_label": STRATA_LABELS[self.stratum],
            "mode": self.mode,
            "wfh_capable": self.wfh_capable,
            "weather_sensitivity": self.weather_sensitivity,
        }


class PersonaSampler:
    """Deterministic persona sampling from a region's real distributions."""

    def __init__(self, profile: RegionProfile, seed: int = 42):
        self.profile = profile
        self._rng = random.Random(seed)
        self._strata = list(profile.income_distribution)
        self._strata_weights = [profile.income_distribution[s] for s in self._strata]
        # Pre-blend per-stratum mode tables with the region's mode split.
        region_modes = profile.mode_split
        self._mode_tables: Dict[str, Any] = {}
        for stratum in self._strata:
            base = STRATA_BEHAVIOR[stratum]["modes"]
            modes = sorted(set(base) | set(region_modes))
            weights = [base.get(m, 0.0) * region_modes.get(m, 0.0) for m in modes]
            if sum(weights) <= 0:  # disjoint tables — trust the region
                weights = [region_modes.get(m, 0.0) for m in modes]
            self._mode_tables[stratum] = (modes, weights)

    def sample_one(self) -> Persona:
        rng = self._rng
        stratum = rng.choices(self._strata, weights=self._strata_weights)[0]
        behavior = STRATA_BEHAVIOR[stratum]
        seg_table = SEGMENT_MAP[stratum]
        segment = rng.choices(list(seg_table), weights=list(seg_table.values()))[0]
        modes, weights = self._mode_tables[stratum]
        return Persona(
            stratum=stratum,
            segment=segment,
            mode=rng.choices(modes, weights=weights)[0],
            depart_window_min=behavior["depart_window_min"],
            weather_sensitivity=behavior["weather_sensitivity"],
            wfh_capable=rng.random() < behavior["wfh"],
        )

    def sample(self, n: int) -> List[Persona]:
        return [self.sample_one() for _ in range(n)]


# Ensure every segment is reachable (students-only strata would starve some).
assert set(SEGMENT_LABELS) == {s for table in SEGMENT_MAP.values() for s in table}, \
    "SEGMENT_MAP must cover all 7 segments"
