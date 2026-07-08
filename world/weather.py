"""Real weather for any region: open-meteo live/forecast/archive.

The existing ``OpenMeteoWeatherAdapter`` is forecast-only, hardcodes
``Asia/Kolkata`` and lacks cloud-cover/visibility, so this module makes its own
open-meteo calls (same free, keyless API): the forecast endpoint for "now" and
near-future, the archive endpoint for historical dates. Failures degrade to a
neutral default state — weather must never kill a world session.

``WeatherState`` drives BOTH the simulation (``speed_factor`` slows agents in
rain/fog/snow) and the map visuals (rain particles, cloud darkening).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx

from world.region import RegionProfile, ScenarioConditions

logger = logging.getLogger(__name__)

FetchJson = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_FIELDS = "temperature_2m,precipitation,weather_code,cloud_cover,visibility,wind_speed_10m"
_ARCHIVE_FIELDS = "temperature_2m,precipitation,weather_code,cloud_cover,wind_speed_10m"

_FORECAST_HORIZON_DAYS = 16
_HEAVY_PRECIP_MM_H = 12.0


@dataclass(frozen=True)
class WeatherState:
    condition: str  # clear | clouds | fog | rain | heavy_rain | snow | storm
    cloud_cover_pct: float
    precip_mm_h: float
    wind_kmh: float
    temp_c: float
    visibility_m: float
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _condition_from_wmo(code: int, precip: float, temp_c: float) -> str:
    if code in (95, 96, 99):
        return "storm"
    if code in (71, 73, 75, 77, 85, 86) or (precip > 0 and temp_c <= 0):
        return "snow"
    if code in (65, 82) or precip >= _HEAVY_PRECIP_MM_H:
        return "heavy_rain"
    if code in (51, 53, 55, 56, 57, 61, 63, 66, 67, 80, 81) or precip > 0:
        return "rain"
    if code in (45, 48):
        return "fog"
    if code in (2, 3):
        return "clouds"
    return "clear"


def _default_state(profile: RegionProfile) -> WeatherState:
    # Neutral fallback; roughly right for most of the year without pretending precision.
    return WeatherState(
        condition="clear",
        cloud_cover_pct=20.0,
        precip_mm_h=0.0,
        wind_kmh=8.0,
        temp_c=25.0,
        visibility_m=10000.0,
        source="default",
    )


async def _httpx_fetch_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


class WeatherProvider:
    """Fetches real weather; applies prompt overrides; scores driving impact."""

    def __init__(self, fetch_json: Optional[FetchJson] = None):
        self._fetch = fetch_json or _httpx_fetch_json

    async def fetch(
        self, profile: RegionProfile, when: Optional[datetime] = None
    ) -> WeatherState:
        lon, lat = profile.center
        try:
            if when is None:
                data = await self._fetch(
                    _FORECAST_URL,
                    {"latitude": lat, "longitude": lon, "current": _FIELDS, "timezone": "auto"},
                )
                return self._from_current(data["current"], "open-meteo:forecast")
            now = datetime.now()
            if when.date() < now.date():
                day = when.strftime("%Y-%m-%d")
                data = await self._fetch(
                    _ARCHIVE_URL,
                    {
                        "latitude": lat, "longitude": lon,
                        "start_date": day, "end_date": day,
                        "hourly": _ARCHIVE_FIELDS, "timezone": "auto",
                    },
                )
                return self._from_hourly(data["hourly"], when, "open-meteo:archive")
            if when <= now + timedelta(days=_FORECAST_HORIZON_DAYS):
                data = await self._fetch(
                    _FORECAST_URL,
                    {
                        "latitude": lat, "longitude": lon,
                        "hourly": _FIELDS, "timezone": "auto",
                        "start_date": when.strftime("%Y-%m-%d"),
                        "end_date": when.strftime("%Y-%m-%d"),
                    },
                )
                return self._from_hourly(data["hourly"], when, "open-meteo:forecast")
        except Exception:
            logger.warning("weather fetch failed for %s; using default", profile.key, exc_info=True)
            return _default_state(profile)
        # Beyond the forecast horizon: no honest source, use the neutral default.
        return _default_state(profile)

    @staticmethod
    def _from_current(cur: Dict[str, Any], source: str) -> WeatherState:
        precip = float(cur.get("precipitation") or 0.0)
        temp = float(cur.get("temperature_2m") or 20.0)
        return WeatherState(
            condition=_condition_from_wmo(int(cur.get("weather_code") or 0), precip, temp),
            cloud_cover_pct=float(cur.get("cloud_cover") or 0.0),
            precip_mm_h=precip,
            wind_kmh=float(cur.get("wind_speed_10m") or 0.0),
            temp_c=temp,
            visibility_m=float(cur.get("visibility") or 10000.0),
            source=source,
        )

    @staticmethod
    def _from_hourly(hourly: Dict[str, Any], when: datetime, source: str) -> WeatherState:
        times = hourly.get("time", [])
        target = when.strftime("%Y-%m-%dT%H:00")
        try:
            i = times.index(target)
        except ValueError:
            i = max(0, min(len(times) - 1, when.hour))
        precip = float(hourly["precipitation"][i] or 0.0)
        temp = float(hourly["temperature_2m"][i] or 20.0)
        vis_list = hourly.get("visibility")
        return WeatherState(
            condition=_condition_from_wmo(int(hourly["weather_code"][i] or 0), precip, temp),
            cloud_cover_pct=float(hourly["cloud_cover"][i] or 0.0),
            precip_mm_h=precip,
            wind_kmh=float(hourly["wind_speed_10m"][i] or 0.0),
            temp_c=temp,
            visibility_m=float(vis_list[i]) if vis_list else (4000.0 if precip >= _HEAVY_PRECIP_MM_H else 10000.0),
            source=source,
        )

    # ── prompt overrides ──

    def apply_override(self, state: WeatherState, conditions: ScenarioConditions) -> WeatherState:
        """Force prompt-demanded weather ("what if it rains…") onto the real state."""
        if conditions.precip_mm_h is None:
            return state
        precip = conditions.precip_mm_h
        if precip > 0 and state.temp_c <= 0:
            condition = "snow"
        elif precip >= _HEAVY_PRECIP_MM_H:
            condition = "heavy_rain"
        elif precip > 0:
            condition = "rain"
        else:
            condition = state.condition
        return WeatherState(
            condition=condition,
            cloud_cover_pct=max(state.cloud_cover_pct, 80.0) if precip > 0 else state.cloud_cover_pct,
            precip_mm_h=precip,
            wind_kmh=state.wind_kmh,
            temp_c=state.temp_c,
            visibility_m=min(
                state.visibility_m,
                3000.0 if precip >= _HEAVY_PRECIP_MM_H else 6000.0,
            )
            if precip > 0
            else state.visibility_m,
            source=f"{state.source}+override",
        )

    # ── simulation impact ──

    @staticmethod
    def speed_factor(state: WeatherState) -> float:
        """Traffic speed multiplier: 1.0 dry → 0.55 floor in the worst weather."""
        factor = 1.0
        if state.condition == "snow":
            factor = 0.62
        elif state.precip_mm_h >= _HEAVY_PRECIP_MM_H:
            factor = 0.72
        elif state.precip_mm_h >= 4.0:
            factor = 0.85
        elif state.precip_mm_h > 0.0:
            factor = 0.92
        if state.visibility_m < 1000.0:
            factor *= 0.80
        return max(round(factor, 3), 0.55)
