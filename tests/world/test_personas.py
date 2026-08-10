"""Tests for world.personas — income-strata human behavior sampling."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from shared.contracts.simulation_state import SEGMENT_LABELS
from world.personas import STRATA, STRATA_BEHAVIOR, PersonaSampler
from world.region import RegionProfile

REGIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions"


def _profile(key="noida") -> RegionProfile:
    return RegionProfile.from_dict(json.loads((REGIONS_DIR / f"{key}.json").read_text()))


def test_strata_behavior_is_complete_and_normalized():
    assert list(STRATA_BEHAVIOR) == STRATA
    for stratum, behavior in STRATA_BEHAVIOR.items():
        assert abs(sum(behavior["modes"].values()) - 1.0) < 0.01, stratum
        assert 0 <= behavior["wfh"] <= 1
        assert behavior["weather_sensitivity"] > 0


def test_sample_matches_region_income_distribution():
    profile = _profile()
    personas = PersonaSampler(profile, seed=7).sample(4000)
    counts = Counter(p.stratum for p in personas)
    for stratum, share in profile.income_distribution.items():
        observed = counts[stratum] / len(personas)
        assert abs(observed - share) < 0.03, f"{stratum}: {observed:.3f} vs {share:.3f}"


def test_income_shapes_mode_choice():
    personas = PersonaSampler(_profile(), seed=7).sample(4000)
    car_share = {
        s: sum(1 for p in personas if p.stratum == s and p.mode == "car")
        / max(sum(1 for p in personas if p.stratum == s), 1)
        for s in ("lt_3L", "gt_1Cr")
    }
    assert car_share["gt_1Cr"] > car_share["lt_3L"] * 3


def test_segments_cover_all_seven_and_map_sanely():
    personas = PersonaSampler(_profile(), seed=7).sample(4000)
    segs = {p.segment for p in personas}
    assert segs <= set(SEGMENT_LABELS)
    assert len(segs) == len(SEGMENT_LABELS)
    # top earners skew to the high-income segment
    top = [p for p in personas if p.stratum == "gt_1Cr"]
    assert sum(1 for p in top if p.segment == "high_income") / len(top) > 0.4


def test_deterministic_and_region_sensitive():
    a = PersonaSampler(_profile(), seed=7).sample(300)
    b = PersonaSampler(_profile(), seed=7).sample(300)
    assert [(p.stratum, p.mode, p.segment) for p in a] == [(p.stratum, p.mode, p.segment) for p in b]

    ny = PersonaSampler(_profile("new_york"), seed=7).sample(2000)
    noida = PersonaSampler(_profile("noida"), seed=7).sample(2000)
    ny_2w = sum(1 for p in ny if p.mode == "two_wheeler") / len(ny)
    noida_2w = sum(1 for p in noida if p.mode == "two_wheeler") / len(noida)
    assert noida_2w > ny_2w * 5  # scooters dominate Noida, not Manhattan


def test_sentinel_context_shape():
    persona = PersonaSampler(_profile(), seed=7).sample(1)[0]
    ctx = persona.sentinel_context()
    assert {"stratum", "income_label", "mode", "wfh_capable"} <= set(ctx)
