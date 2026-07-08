"""Tests for engines.environment.aqi_model — seasonal AQI intelligence.

The model must KNOW the region: winter inversion smog, the Oct-Nov stubble
window, Diwali fireworks spikes (2024-2030 date table), monsoon washout and
the daily double-hump — all without any network access.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from engines.environment.aqi_model import AQISeries, DIWALI_DATES, pm25_to_aqi
from world.region import RegionProfile

REGIONS_DIR = Path(__file__).resolve().parents[3] / "data" / "regions"


def _profile(key: str) -> RegionProfile:
    return RegionProfile.from_dict(json.loads((REGIONS_DIR / f"{key}.json").read_text()))


NOIDA = AQISeries(_profile("noida"))
NYC = AQISeries(_profile("new_york"))


# ── CPCB PM2.5 sub-index ──


def test_pm25_to_aqi_breakpoints():
    assert pm25_to_aqi(0) == 0
    assert pm25_to_aqi(30) == 50
    assert pm25_to_aqi(60) == 100
    assert pm25_to_aqi(90) == 200
    assert pm25_to_aqi(120) == 300
    assert pm25_to_aqi(250) == 400
    assert pm25_to_aqi(500) == 500  # capped
    assert 101 <= pm25_to_aqi(75) <= 200  # inside a band, interpolated


# ── seasonal intelligence ──


def test_winter_smog_beats_monsoon():
    winter = NOIDA.estimate_pm25(datetime(2026, 12, 15, 11))
    monsoon = NOIDA.estimate_pm25(datetime(2026, 7, 15, 11))
    annual = NOIDA.profile.aqi_baseline["annual_mean_pm25"]
    assert winter > annual * 1.4
    assert monsoon < annual * 0.8
    assert winter / monsoon > 2.5


def test_diwali_spike_dominates_its_week():
    diwali = DIWALI_DATES[2026]  # 2026-11-08
    on_day = NOIDA.estimate_pm25(datetime(2026, diwali.month, diwali.day, 21))
    week_before = NOIDA.estimate_pm25(datetime(2026, 10, 25, 21))
    assert on_day > week_before * 1.5
    # spike decays with distance from the day
    day_after = NOIDA.estimate_pm25(datetime(2026, 11, 9, 21))
    three_after = NOIDA.estimate_pm25(datetime(2026, 11, 12, 21))
    assert on_day > day_after > three_after


def test_stubble_window_lifts_october_ncr_only():
    ncr_oct = NOIDA.seasonal_factor(datetime(2026, 10, 20, 11))
    ncr_sep = NOIDA.seasonal_factor(datetime(2026, 9, 20, 11))
    assert ncr_oct > ncr_sep
    nyc_oct = NYC.seasonal_factor(datetime(2026, 10, 20, 11))
    nyc_sep = NYC.seasonal_factor(datetime(2026, 9, 20, 11))
    assert nyc_oct / nyc_sep < ncr_oct / ncr_sep  # no stubble burning in NYC


def test_diurnal_double_hump():
    evening = NOIDA.seasonal_factor(datetime(2026, 3, 10, 20))
    afternoon = NOIDA.seasonal_factor(datetime(2026, 3, 10, 14))
    morning = NOIDA.seasonal_factor(datetime(2026, 3, 10, 8))
    assert evening > afternoon
    assert morning > afternoon


def test_nyc_stays_clean_year_round():
    worst = max(
        NYC.estimate_pm25(datetime(2026, m, 15, 20)) for m in range(1, 13)
    )
    assert worst < 25  # baseline 9.5 with mild seasonality


# ── forecast + live fallback ──


def test_forecast_hourly_shape():
    series = NOIDA.forecast_hourly(datetime(2026, 11, 8, 0), hours=24)
    assert len(series) == 24
    assert all({"time", "pm25", "aqi"} <= set(h) for h in series)
    assert max(h["aqi"] for h in series) > 300  # Diwali evening goes severe


@pytest.mark.asyncio
async def test_current_uses_live_fetch_when_available():
    async def live():
        return {"pm25": 142.0, "source": "openaq_live"}

    series = AQISeries(_profile("noida"), fetch_live=live)
    cur = await series.current()
    assert cur["pm25"] == 142.0
    assert cur["source"] == "openaq_live"
    assert cur["aqi"] == pm25_to_aqi(142.0)


@pytest.mark.asyncio
async def test_current_degrades_to_seasonal_model():
    async def dead():
        raise RuntimeError("blocked")

    series = AQISeries(_profile("noida"), fetch_live=dead)
    cur = await series.current()
    assert cur["source"] == "seasonal_model"
    assert cur["pm25"] > 0 and cur["aqi"] == pm25_to_aqi(cur["pm25"])
