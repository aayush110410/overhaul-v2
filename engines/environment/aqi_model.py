"""Seasonal AQI intelligence per region — the pollution engine's brain.

Combines a region's annual PM2.5 baseline with everything a local would know:
  - **winter inversion** (Nov-Feb smog, scaled by the profile's multiplier),
  - **monsoon washout** (Jul-Aug),
  - the **stubble-burning window** (Oct 15 - Nov 30, Indo-Gangetic plain only),
  - **Diwali fireworks** (date table 2024-2030, ±2-day decay, spike magnitude
    from the region's cultural calendar),
  - the **diurnal double-hump** (morning + evening traffic/inversion peaks).

`current()` prefers a live feed (OpenAQ / open-meteo, injected) and degrades
to this model — so the pollution engine works identically offline. AQI values
use the CPCB PM2.5 sub-index (linear interpolation between breakpoints).

No network, no LLM, importable anywhere. Historical ground truth for NCR
lives in ``data/aqi/`` and ``data/noida_aqi_2024.xlsx`` (used by tests and
future calibration, not required at runtime).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional

from world.region import RegionProfile

logger = logging.getLogger(__name__)

# Lakshmi-Puja day per year (fireworks night). ±1 day regional variation is
# absorbed by the ±2-day decay window.
DIWALI_DATES: Dict[int, date] = {
    2024: date(2024, 11, 1),
    2025: date(2025, 10, 20),
    2026: date(2026, 11, 8),
    2027: date(2027, 10, 29),
    2028: date(2028, 10, 17),
    2029: date(2029, 11, 5),
    2030: date(2030, 10, 26),
}
_DIWALI_DECAY = {0: 1.0, 1: 0.6, 2: 0.3}  # |days from Diwali| → spike weight

# Stubble-burning geography: Indo-Gangetic plain latitudes (Punjab/Haryana
# smoke reaching NCR). Applied only to Indian regions inside this band.
_STUBBLE_LAT = (26.0, 31.5)
_STUBBLE_START = (10, 15)  # Oct 15
_STUBBLE_END = (11, 30)  # Nov 30
_STUBBLE_FACTOR = 1.25

# CPCB PM2.5 sub-index breakpoints: (pm25_lo, pm25_hi, aqi_lo, aqi_hi)
_CPCB_PM25 = [
    (0, 30, 0, 50),
    (30, 60, 50, 100),
    (60, 90, 100, 200),
    (90, 120, 200, 300),
    (120, 250, 300, 400),
    (250, 500, 400, 500),
]


def pm25_to_aqi(pm25: float) -> int:
    """CPCB PM2.5 sub-index (India's AQI scale), capped at 500."""
    pm25 = max(0.0, float(pm25))
    for lo, hi, aqi_lo, aqi_hi in _CPCB_PM25:
        if pm25 <= hi:
            return round(aqi_lo + (pm25 - lo) / (hi - lo) * (aqi_hi - aqi_lo))
    return 500


def _hour_factor(hour: int) -> float:
    if 7 <= hour < 10:
        return 1.15  # morning rush + shallow boundary layer
    if 12 <= hour < 16:
        return 0.85  # afternoon mixing
    if 18 <= hour < 23:
        return 1.20  # evening rush + inversion onset
    return 1.0


class AQISeries:
    """Region-aware PM2.5/AQI estimates, hourly forecasts and live current."""

    def __init__(
        self,
        profile: RegionProfile,
        fetch_live: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
    ):
        self.profile = profile
        self._fetch_live = fetch_live
        base = profile.aqi_baseline
        w = float(base.get("winter_multiplier", 1.2))
        mo = float(base.get("monsoon_multiplier", 0.9))
        self._month_factor = {
            1: 0.95 * w, 2: 0.75 * w, 3: 1.05, 4: 0.95, 5: 1.0, 6: 0.75,
            7: mo, 8: mo, 9: 0.80, 10: 1.15, 11: 1.0 * w, 12: 1.0 * w,
        }
        self._diwali_spike = next(
            (float(e.get("aqi_spike", 2.0)) for e in profile.cultural_calendar
             if "diwali" in str(e.get("name", "")).lower()),
            2.0 if profile.country == "IN" else 1.0,
        )
        lat = profile.center[1]
        self._stubble_region = (
            profile.country == "IN" and _STUBBLE_LAT[0] <= lat <= _STUBBLE_LAT[1]
        )

    # ── the model ──

    def seasonal_factor(self, dt: datetime) -> float:
        """Multiplier on the annual mean for this exact moment."""
        factor = self._month_factor[dt.month] * _hour_factor(dt.hour)

        if self._stubble_region:
            start = date(dt.year, *_STUBBLE_START)
            end = date(dt.year, *_STUBBLE_END)
            if start <= dt.date() <= end:
                factor *= _STUBBLE_FACTOR

        diwali = DIWALI_DATES.get(dt.year)
        if diwali and self._diwali_spike > 1.0:
            delta = abs((dt.date() - diwali).days)
            weight = _DIWALI_DECAY.get(delta, 0.0)
            factor *= 1.0 + (self._diwali_spike - 1.0) * weight

        return round(factor, 4)

    def estimate_pm25(self, dt: datetime) -> float:
        annual = float(self.profile.aqi_baseline.get("annual_mean_pm25", 25))
        return round(annual * self.seasonal_factor(dt), 1)

    def forecast_hourly(self, start: datetime, hours: int = 24) -> List[Dict[str, Any]]:
        out = []
        for i in range(hours):
            t = start + timedelta(hours=i)
            pm25 = self.estimate_pm25(t)
            out.append({"time": t.isoformat(timespec="hours"),
                        "pm25": pm25, "aqi": pm25_to_aqi(pm25)})
        return out

    # ── live-first current reading ──

    async def current(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now()
        if self._fetch_live is not None:
            try:
                live = await self._fetch_live()
                pm25 = float(live["pm25"])
                return {
                    "pm25": pm25,
                    "aqi": pm25_to_aqi(pm25),
                    "source": live.get("source", "live"),
                    "seasonal_factor": self.seasonal_factor(now),
                }
            except Exception:
                logger.warning("live AQI fetch failed for %s; using seasonal model",
                               self.profile.key, exc_info=True)
        pm25 = self.estimate_pm25(now)
        return {
            "pm25": pm25,
            "aqi": pm25_to_aqi(pm25),
            "source": "seasonal_model",
            "seasonal_factor": self.seasonal_factor(now),
        }


def open_meteo_live_fetcher(profile: RegionProfile) -> Callable[[], Awaitable[Dict[str, Any]]]:
    """Live PM2.5 via the existing keyless open-meteo AQI adapter."""

    async def fetch() -> Dict[str, Any]:
        from data_integration.adapters.api_adapter import OpenMeteoAqiAdapter

        result = await OpenMeteoAqiAdapter().fetch(
            lat=profile.center[1], lon=profile.center[0]
        )
        payload = getattr(result, "data", None) or {}
        pm25 = payload.get("pm25") or payload.get("pm2_5")
        if pm25 is None:
            raise ValueError("no pm25 in open-meteo payload")
        return {"pm25": float(pm25), "source": "open_meteo_aqi"}

    return fetch
