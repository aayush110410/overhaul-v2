"""Tests for world.weather — live/historical weather with overrides."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from world.region import RegionProfile, ScenarioConditions
from world.weather import WeatherProvider, WeatherState

REGIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions"
NOIDA = RegionProfile.from_dict(json.loads((REGIONS_DIR / "noida.json").read_text()))


class _FakeHttp:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


CURRENT_RAIN = {
    "current": {
        "temperature_2m": 28.4,
        "precipitation": 6.2,
        "weather_code": 63,
        "cloud_cover": 92,
        "visibility": 5200.0,
        "wind_speed_10m": 14.0,
    }
}

HOURLY_ARCHIVE = {
    "hourly": {
        "time": ["2024-11-01T07:00", "2024-11-01T08:00", "2024-11-01T09:00"],
        "temperature_2m": [18.0, 19.5, 21.0],
        "precipitation": [0.0, 0.4, 0.0],
        "weather_code": [45, 51, 2],
        "cloud_cover": [40, 60, 30],
        "wind_speed_10m": [4.0, 6.0, 8.0],
    }
}


@pytest.mark.asyncio
async def test_fetch_current_maps_fields():
    http = _FakeHttp(CURRENT_RAIN)
    state = await WeatherProvider(fetch_json=http).fetch(NOIDA)
    assert state.condition == "rain"
    assert state.temp_c == 28.4
    assert state.precip_mm_h == 6.2
    assert state.cloud_cover_pct == 92
    assert state.visibility_m == 5200.0
    assert state.source == "open-meteo:forecast"
    url, params = http.calls[0]
    assert "api.open-meteo.com" in url
    assert params["latitude"] == NOIDA.center[1]
    assert params["timezone"] == "auto"


@pytest.mark.asyncio
async def test_fetch_past_uses_archive_and_picks_hour():
    http = _FakeHttp(HOURLY_ARCHIVE)
    when = datetime(2024, 11, 1, 8, 20)
    state = await WeatherProvider(fetch_json=http).fetch(NOIDA, when=when)
    url, params = http.calls[0]
    assert "archive-api.open-meteo.com" in url
    assert params["start_date"] == "2024-11-01"
    assert state.temp_c == 19.5  # 08:00 row
    assert state.condition == "rain"  # WMO 51 drizzle
    assert state.source == "open-meteo:archive"


@pytest.mark.asyncio
async def test_fetch_failure_degrades_to_default():
    http = _FakeHttp(RuntimeError("blocked"))
    state = await WeatherProvider(fetch_json=http).fetch(NOIDA)
    assert state.source == "default"
    assert state.precip_mm_h == 0.0
    assert 0 <= state.cloud_cover_pct <= 100


def test_apply_override_forces_rain():
    provider = WeatherProvider(fetch_json=_FakeHttp({}))
    dry = WeatherState("clear", 10.0, 0.0, 8.0, 30.0, 10000.0, "default")
    wet = provider.apply_override(dry, ScenarioConditions(precip_mm_h=15.0))
    assert wet.precip_mm_h == 15.0
    assert wet.condition == "heavy_rain"
    assert wet.cloud_cover_pct >= 80
    assert wet.visibility_m < dry.visibility_m
    assert wet.source.endswith("+override")

    cold = WeatherState("clear", 10.0, 0.0, 8.0, -2.0, 10000.0, "default")
    snowy = provider.apply_override(cold, ScenarioConditions(precip_mm_h=5.0))
    assert snowy.condition == "snow"

    untouched = provider.apply_override(dry, ScenarioConditions())
    assert untouched == dry


def test_speed_factor_monotonic_in_weather_severity():
    dry = WeatherState("clear", 10, 0.0, 8, 30, 10000, "default")
    light = WeatherState("rain", 80, 2.0, 10, 26, 8000, "default")
    heavy = WeatherState("heavy_rain", 95, 14.0, 20, 24, 3000, "default")
    fog = WeatherState("fog", 60, 0.0, 4, 12, 600, "default")
    snow = WeatherState("snow", 90, 4.0, 12, -1, 2000, "default")

    f = WeatherProvider.speed_factor
    assert f(dry) == 1.0
    assert f(heavy) < f(light) < f(dry)
    assert f(fog) < f(dry)
    assert f(snow) <= f(heavy)
    assert all(f(s) >= 0.55 for s in (dry, light, heavy, fog, snow))
