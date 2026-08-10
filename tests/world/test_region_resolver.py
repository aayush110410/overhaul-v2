"""Tests for world.region — prompt → RegionProfile + ScenarioConditions.

Token-efficiency invariant: curated-region prompts must resolve with ZERO
geocoder and ZERO LLM calls.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from world.region import (
    DEFAULT_REGION_KEY,
    RegionProfile,
    RegionResolver,
    ScenarioConditions,
    parse_conditions,
)

REGIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions"


class _Spy:
    """Async callable that records calls and returns a canned payload."""

    def __init__(self, payload=None, fail=False):
        self.calls: list = []
        self.payload = payload
        self.fail = fail

    async def __call__(self, arg):
        self.calls.append(arg)
        if self.fail:
            raise AssertionError(f"must not be called (got {arg!r})")
        return self.payload


def _resolver(**kwargs) -> RegionResolver:
    kwargs.setdefault("geocode_fn", _Spy(fail=True))
    kwargs.setdefault("llm_fn", _Spy(fail=True))
    kwargs.setdefault("regions_dir", REGIONS_DIR)
    return RegionResolver(**kwargs)


# ── Curated profiles load ──


def test_curated_profiles_load():
    resolver = _resolver()
    keys = set(resolver.profiles)
    assert {"noida", "delhi", "gurugram", "ghaziabad", "faridabad", "ncr", "new_york"} <= keys
    noida = resolver.profiles["noida"]
    assert isinstance(noida, RegionProfile)
    assert noida.timezone == "Asia/Kolkata"
    assert abs(sum(noida.income_distribution.values()) - 1.0) < 0.02
    assert abs(sum(noida.mode_split.values()) - 1.0) < 0.02
    assert noida.rush_hours and noida.signals["avg_cycle_s"] > 0


# ── Gazetteer resolution (zero external calls) ──


@pytest.mark.asyncio
async def test_gazetteer_hit_new_york_with_conditions():
    resolver = _resolver()
    profile, cond = await resolver.resolve(
        "What happens if it rains during rush hour in New York?"
    )
    assert profile.key == "new_york"
    assert cond.precip_mm_h == 8.0
    assert cond.time_of_day == "rush_hour_am"


@pytest.mark.asyncio
async def test_gazetteer_alias_gurgaon():
    profile, _ = await _resolver().resolve("shut one lane of MG Road in gurgaon for a month")
    assert profile.key == "gurugram"


@pytest.mark.asyncio
async def test_gazetteer_prefers_longest_match():
    # "greater noida" and plain "noida" both exist; longest term wins deterministically.
    profile, _ = await _resolver().resolve("new metro line to greater noida")
    assert profile.key == "noida"


@pytest.mark.asyncio
async def test_no_location_defaults_to_ncr():
    # LLM is the last resort for unresolved prompts; here it confirms "no place".
    llm = _Spy(payload=None)
    profile, cond = await _resolver(llm_fn=llm).resolve("add 500 electric buses to the fleet")
    assert profile.key == DEFAULT_REGION_KEY
    assert cond == ScenarioConditions()
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_no_location_without_llm_still_defaults():
    profile, _ = await _resolver(llm_fn=None).resolve("add 500 electric buses to the fleet")
    assert profile.key == DEFAULT_REGION_KEY


# ── Condition parsing ──


def test_parse_conditions_variants():
    c = parse_conditions("heavy rain during the evening rush hour on diwali")
    assert c.precip_mm_h == 15.0
    assert c.time_of_day == "rush_hour_pm"
    assert c.date_context == "diwali"

    c = parse_conditions("light drizzle at night in winter smog")
    assert c.precip_mm_h == 2.0
    assert c.time_of_day == "night"
    assert c.date_context == "winter"

    assert parse_conditions("widen the expressway") == ScenarioConditions()


# ── Geocode fallback for unknown places ──


def _tmp_regions(tmp_path: Path) -> Path:
    regions = tmp_path / "regions"
    regions.mkdir()
    for name in ("_generic_template.json", "ncr.json"):
        shutil.copy(REGIONS_DIR / name, regions / name)
    return regions


@pytest.mark.asyncio
async def test_unknown_place_geocoded_and_persisted(tmp_path):
    geocode = _Spy(
        payload=[
            {
                "display_name": "Springfield, Sangamon County, Illinois, USA",
                "lat": 39.7817,
                "lon": -89.6501,
                "type": "city",
                "address": {"country_code": "us"},
            }
        ]
    )
    regions = _tmp_regions(tmp_path)
    resolver = RegionResolver(regions_dir=regions, geocode_fn=geocode, llm_fn=_Spy(fail=True))

    profile, _ = await resolver.resolve("simulate congestion in Springfield next week")
    assert profile.key == "springfield"
    assert profile.center == [-89.6501, 39.7817]
    assert profile.bbox[0] < profile.center[0] < profile.bbox[2]
    assert profile.bbox[1] < profile.center[1] < profile.bbox[3]
    persisted = regions / "generated" / "springfield.json"
    assert persisted.exists()
    assert json.loads(persisted.read_text())["key"] == "springfield"
    assert len(geocode.calls) == 1

    # Second resolve reuses the cached profile — no second geocode call.
    profile2, _ = await resolver.resolve("now flood Springfield with buses")
    assert profile2.key == "springfield"
    assert len(geocode.calls) == 1


@pytest.mark.asyncio
async def test_geocode_rejects_non_place_hits(tmp_path):
    geocode = _Spy(payload=[{"display_name": "x", "lat": 1.0, "lon": 1.0, "type": "restaurant", "address": {}}])
    resolver = RegionResolver(
        regions_dir=_tmp_regions(tmp_path), geocode_fn=geocode, llm_fn=_Spy(payload=None)
    )
    profile, _ = await resolver.resolve("simulate congestion in Xanadu24 tomorrow")
    assert profile.key == DEFAULT_REGION_KEY  # fell through to default


# ── LLM last resort ──


@pytest.mark.asyncio
async def test_llm_last_resort_extracts_place(tmp_path):
    geocode = _Spy(
        payload=[
            {
                "display_name": "Springfield, Illinois, USA",
                "lat": 39.7817,
                "lon": -89.6501,
                "type": "administrative",
                "address": {"country_code": "us"},
            }
        ]
    )
    llm = _Spy(payload="Springfield")
    resolver = RegionResolver(regions_dir=_tmp_regions(tmp_path), geocode_fn=geocode, llm_fn=llm)
    # Lowercase, prepositionless phrasing defeats both gazetteer and regex candidates.
    profile, _ = await resolver.resolve("springfield gridlock: what if every office opens 9am sharp")
    assert profile.key == "springfield"
    assert len(llm.calls) == 1
    assert len(geocode.calls) == 1
