"""
Live API Adapters
==================

Adapters for external REST APIs:
  - OpenMeteoAqiAdapter   — Air quality (PM2.5, AQI) via Open-Meteo
  - OSRMRoutingAdapter    — Route distance/duration via OSRM
  - TomTomFlowAdapter     — Real-time traffic flow (key-gated)
  - NominatimAdapter      — Forward / reverse geocoding
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

from data_integration.adapters.base import (
    DataAdapter,
    DataDomain,
    DataResult,
    SourceType,
    RefreshPolicy,
)


# ══════════════════════════════════════════════════════════════════
#  Open-Meteo Air Quality
# ══════════════════════════════════════════════════════════════════

class OpenMeteoAqiAdapter(DataAdapter):
    """
    Fetches hourly PM2.5 / PM10 / AQI from Open-Meteo (no API key).

    Kwargs:
      lat:  latitude  (default 28.62 — Delhi)
      lon:  longitude (default 77.22)
    """

    _URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(self, ttl_seconds: float = 300):
        super().__init__(ttl_seconds=ttl_seconds)

    @property
    def name(self) -> str:
        return "open_meteo_aqi"

    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def domains(self) -> List[DataDomain]:
        return [DataDomain.AQI]

    async def fetch(self, **kwargs) -> DataResult:
        lat = kwargs.get("lat", 28.62)
        lon = kwargs.get("lon", 77.22)

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "pm2_5,pm10,us_aqi",
            "past_days": 2,
            "forecast_days": 1,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        hourly = raw.get("hourly", {})
        pm25_vals = [v for v in (hourly.get("pm2_5") or []) if v is not None]
        aqi_vals = [v for v in (hourly.get("us_aqi") or []) if v is not None]

        latest_pm25 = pm25_vals[-1] if pm25_vals else None
        latest_aqi = aqi_vals[-1] if aqi_vals else None

        return DataResult(
            data={
                "pm25": latest_pm25,
                "aqi": latest_aqi,
                "pm25_series": pm25_vals[-48:],  # last 48 hours
                "aqi_series": aqi_vals[-48:],
                "lat": lat,
                "lon": lon,
                "category": _aqi_category(latest_aqi) if latest_aqi else "Unknown",
            },
            source="Open-Meteo Air Quality API",
            source_type=SourceType.API,
            domain=DataDomain.AQI,
            meta={"hours_returned": len(pm25_vals)},
        )


# ══════════════════════════════════════════════════════════════════
#  OSRM Routing
# ══════════════════════════════════════════════════════════════════

class OSRMRoutingAdapter(DataAdapter):
    """
    Fetches route metrics from the public OSRM instance (no API key).

    Kwargs:
      origin_lat, origin_lon:  start point
      dest_lat, dest_lon:      end point
    """

    _URL = "https://router.project-osrm.org/route/v1/driving"

    def __init__(self, ttl_seconds: float = 120):
        super().__init__(ttl_seconds=ttl_seconds)

    @property
    def name(self) -> str:
        return "osrm_routing"

    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def domains(self) -> List[DataDomain]:
        return [DataDomain.ROUTING]

    async def fetch(self, **kwargs) -> DataResult:
        o_lat = kwargs.get("origin_lat", 28.5825)
        o_lon = kwargs.get("origin_lon", 77.3554)
        d_lat = kwargs.get("dest_lat", 28.6663)
        d_lon = kwargs.get("dest_lon", 77.3649)

        coords = f"{o_lon},{o_lat};{d_lon},{d_lat}"
        url = f"{self._URL}/{coords}"
        params = {"overview": "full", "geometries": "geojson", "steps": "true"}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            raw = resp.json()

        routes = raw.get("routes", [])
        if not routes:
            return DataResult(data={}, source=self.name, error="No route found")

        route = routes[0]
        distance_km = round(route["distance"] / 1000, 2)
        duration_min = round(route["duration"] / 60, 1)
        speed_kmh = round(distance_km / (duration_min / 60), 1) if duration_min > 0 else 0

        return DataResult(
            data={
                "distance_km": distance_km,
                "duration_min": duration_min,
                "speed_kmh": speed_kmh,
                "geometry": route.get("geometry"),
                "origin": {"lat": o_lat, "lon": o_lon},
                "destination": {"lat": d_lat, "lon": d_lon},
            },
            source="OSRM Routing API",
            source_type=SourceType.API,
            domain=DataDomain.ROUTING,
        )


# ══════════════════════════════════════════════════════════════════
#  TomTom Traffic Flow (key-gated)
# ══════════════════════════════════════════════════════════════════

class TomTomFlowAdapter(DataAdapter):
    """
    Fetches real-time traffic flow segment data from TomTom.
    Requires TOMTOM_API_KEY env var; silently returns empty if missing.

    Kwargs:
      lat:  latitude
      lon:  longitude
    """

    _URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

    def __init__(self, ttl_seconds: float = 120):
        super().__init__(ttl_seconds=ttl_seconds)

    @property
    def name(self) -> str:
        return "tomtom_flow"

    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def domains(self) -> List[DataDomain]:
        return [DataDomain.TRAFFIC]

    async def fetch(self, **kwargs) -> DataResult:
        api_key = os.getenv("TOMTOM_API_KEY", "")
        if not api_key:
            return DataResult(
                data={},
                source="TomTom (disabled — no API key)",
                source_type=SourceType.API,
                domain=DataDomain.TRAFFIC,
                meta={"reason": "TOMTOM_API_KEY not set"},
            )

        lat = kwargs.get("lat", 28.62)
        lon = kwargs.get("lon", 77.35)
        params = {"key": api_key, "point": f"{lat},{lon}", "zoom": 12, "unit": "KMPH"}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        fsd = raw.get("flowSegmentData", {})
        return DataResult(
            data={
                "current_speed": fsd.get("currentSpeed"),
                "free_flow_speed": fsd.get("freeFlowSpeed"),
                "current_travel_time": fsd.get("currentTravelTime"),
                "free_flow_travel_time": fsd.get("freeFlowTravelTime"),
                "confidence": fsd.get("confidence"),
                "road_closure": fsd.get("roadClosure"),
            },
            source="TomTom Traffic Flow API",
            source_type=SourceType.API,
            domain=DataDomain.TRAFFIC,
        )


# ══════════════════════════════════════════════════════════════════
#  Nominatim Geocoding
# ══════════════════════════════════════════════════════════════════

class NominatimAdapter(DataAdapter):
    """
    Forward / reverse geocoding via Nominatim (no API key).

    Kwargs:
      query:    search string (forward geocode)
      lat, lon: coordinates  (reverse geocode — used when query is empty)
    """

    _SEARCH_URL = "https://nominatim.openstreetmap.org/search"
    _REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
    _HEADERS = {"User-Agent": "OVERHAUL-Platform/1.0"}

    def __init__(self, ttl_seconds: float = 600):
        super().__init__(ttl_seconds=ttl_seconds)

    @property
    def name(self) -> str:
        return "nominatim_geocoding"

    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def domains(self) -> List[DataDomain]:
        return [DataDomain.GEOCODING]

    async def fetch(self, **kwargs) -> DataResult:
        query = kwargs.get("query", "")
        lat = kwargs.get("lat")
        lon = kwargs.get("lon")

        async with httpx.AsyncClient(timeout=10, headers=self._HEADERS) as client:
            if query:
                params = {"q": query, "format": "json", "limit": 5}
                resp = await client.get(self._SEARCH_URL, params=params)
                resp.raise_for_status()
                results = resp.json()
                if not results:
                    return DataResult(data=[], source=self.name, meta={"query": query})
                return DataResult(
                    data=[
                        {
                            "display_name": r.get("display_name", ""),
                            "lat": float(r.get("lat", 0)),
                            "lon": float(r.get("lon", 0)),
                            "type": r.get("type", ""),
                        }
                        for r in results
                    ],
                    source="Nominatim / OpenStreetMap",
                    source_type=SourceType.API,
                    domain=DataDomain.GEOCODING,
                    meta={"query": query, "count": len(results)},
                )
            elif lat is not None and lon is not None:
                params = {"lat": lat, "lon": lon, "format": "json"}
                resp = await client.get(self._REVERSE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                return DataResult(
                    data={
                        "display_name": data.get("display_name", ""),
                        "lat": float(data.get("lat", lat)),
                        "lon": float(data.get("lon", lon)),
                        "address": data.get("address", {}),
                    },
                    source="Nominatim / OpenStreetMap (reverse)",
                    source_type=SourceType.API,
                    domain=DataDomain.GEOCODING,
                )
            else:
                return DataResult(
                    data=None,
                    source=self.name,
                    error="Provide 'query' for forward geocoding or 'lat'+'lon' for reverse",
                )


# ── Shared helper ─────────────────────────────────────────────────

class OpenAQAqiAdapter(DataAdapter):
    """
    Fetches real-time air quality from the OpenAQ v2 API (free, no API key).

    API: GET https://api.openaq.org/v2/measurements?city=Delhi&limit=10&parameter=pm25

    Returns the most recent PM2.5, PM10, and NO2 readings across Delhi monitoring
    stations (US Embassy, IIT Delhi, CPCB, etc.), along with a weighted city-average
    PM2.5 and AQI category.

    Kwargs:
      city: city name (default "Delhi")
    """

    _URL = "https://api.openaq.org/v2/measurements"

    def __init__(self, ttl_seconds: float = 300):
        super().__init__(ttl_seconds=ttl_seconds)

    @property
    def name(self) -> str:
        return "openaq_aqi"

    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def domains(self) -> List[DataDomain]:
        return [DataDomain.AQI]

    async def fetch(self, **kwargs) -> DataResult:
        city = kwargs.get("city", "Delhi")
        params = {
            "city": city,
            "limit": 10,
            "parameter": "pm25",
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        results = raw.get("results", [])
        stations: List[Dict[str, Any]] = []
        pm25_values: List[float] = []
        aqi_values: List[float] = []

        for r in results:
            meta = r.get("location", "")
            meas = r.get("measurements", [])
            station_pm25: Optional[float] = None
            station_pm10: Optional[float] = None
            station_no2: Optional[float] = None

            for m in meas:
                param = m.get("parameter", "")
                val = m.get("value")
                if val is None:
                    continue
                if param == "pm25":
                    station_pm25 = float(val)
                    pm25_values.append(station_pm25)
                elif param == "pm10":
                    station_pm10 = float(val)
                elif param == "no2":
                    station_no2 = float(val)

            if station_pm25 is not None:
                stations.append({
                    "name": meta,
                    "pm25": station_pm25,
                    "pm10": station_pm10,
                    "no2": station_no2,
                    "lastUpdated": r.get("lastUpdated"),
                })

        # Weighted average PM2.5 (most recent reading per station)
        avg_pm25 = round(sum(pm25_values) / len(pm25_values), 1) if pm25_values else None
        aqi_category = _aqi_category(avg_pm25 * 4 if avg_pm25 else None)  # rough AQI from PM2.5

        return DataResult(
            data={
                "pm25": avg_pm25,
                "pm10": None,
                "no2": None,
                "aqi": None,
                "category": aqi_category,
                "stations": stations,
                "city": city,
                "source": "OpenAQ v2 API",
            },
            source="OpenAQ Air Quality API",
            source_type=SourceType.API,
            domain=DataDomain.AQI,
            meta={"stations_returned": len(stations)},
        )


def _aqi_category(aqi: Optional[float]) -> str:
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def _weather_code_label(code: int) -> str:
    """WMO weather interpretation code → human label."""
    _MAP = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Rime fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Rain showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Severe thunderstorm",
    }
    return _MAP.get(code, f"Code {code}")


# ══════════════════════════════════════════════════════════════════
#  Open-Meteo Weather Forecast
# ══════════════════════════════════════════════════════════════════

class OpenMeteoWeatherAdapter(DataAdapter):
    """
    Fetches current weather + 3-day forecast from Open-Meteo (free, no key).

    Kwargs:
      lat:  latitude  (default 28.62 — Delhi)
      lon:  longitude (default 77.22)
    """

    _URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, ttl_seconds: float = 600):
        super().__init__(ttl_seconds=ttl_seconds)

    @property
    def name(self) -> str:
        return "open_meteo_weather"

    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def domains(self) -> List[DataDomain]:
        return [DataDomain.WEATHER]

    async def fetch(self, **kwargs) -> DataResult:
        lat = kwargs.get("lat", 28.62)
        lon = kwargs.get("lon", 77.22)

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                     "weather_code,wind_speed_10m_max",
            "timezone": "Asia/Kolkata",
            "forecast_days": 3,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self._URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        current = raw.get("current", {})
        daily = raw.get("daily", {})

        forecast_days = []
        dates = daily.get("time", [])
        for i, date in enumerate(dates):
            forecast_days.append({
                "date": date,
                "temp_max": (daily.get("temperature_2m_max") or [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                "temp_min": (daily.get("temperature_2m_min") or [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                "precipitation_mm": (daily.get("precipitation_sum") or [0])[i] if i < len(daily.get("precipitation_sum", [])) else 0,
                "weather_code": (daily.get("weather_code") or [0])[i] if i < len(daily.get("weather_code", [])) else 0,
                "wind_max_kmh": (daily.get("wind_speed_10m_max") or [0])[i] if i < len(daily.get("wind_speed_10m_max", [])) else 0,
                "condition": _weather_code_label((daily.get("weather_code") or [0])[i]) if i < len(daily.get("weather_code", [])) else "Unknown",
            })

        return DataResult(
            data={
                "current": {
                    "temperature_c": current.get("temperature_2m"),
                    "feels_like_c": current.get("apparent_temperature"),
                    "humidity_pct": current.get("relative_humidity_2m"),
                    "precipitation_mm": current.get("precipitation"),
                    "wind_speed_kmh": current.get("wind_speed_10m"),
                    "wind_direction_deg": current.get("wind_direction_10m"),
                    "weather_code": current.get("weather_code"),
                    "condition": _weather_code_label(current.get("weather_code", 0)),
                },
                "forecast": forecast_days,
                "lat": lat,
                "lon": lon,
            },
            source="Open-Meteo Weather Forecast API",
            source_type=SourceType.API,
            domain=DataDomain.WEATHER,
            meta={"forecast_days": len(forecast_days)},
        )


def _weather_code_label(code: int) -> str:
    """WMO weather interpretation code → human label."""
    _MAP = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Rime fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Rain showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Severe thunderstorm",
    }
    return _MAP.get(code, f"Code {code}")


# ══════════════════════════════════════════════════════════════════
#  OpenSky Network (Design Stub — Requires API Key)
# ══════════════════════════════════════════════════════════════════

class OpenSkyNetworkAdapter(DataAdapter):
    """
    Real-time aircraft tracking via OpenSky Network API.

    DESIGN SPECIFICATION (Not implemented — requires API key):

    OpenSky Network provides live air traffic data for Delhi NCR airspace.
    Useful for:
      - Tracking flight congestion at IGI Airport (DEL)
      - Monitoring air cargo traffic
      - Noise pollution modeling from aircraft
      - Emergency medical helicopter tracking

    API Endpoints:
      - GET /states/all          — All aircraft states (requires auth)
      - GET /states/{lamin}/{lomin}/{lamax}/{lomax}  — Bounded region
      - GET /aircraft/24bit      — Specific aircraft by ICAO address

    Authentication:
      - Basic Auth: OPENSKY_USERNAME:OPENSKY_PASSWORD
      - Rate limits: Free tier = 100 req/day, 1 req/10sec

    Implementation Notes:
      - Requires OPENSKY_USERNAME and OPENSKY_PASSWORD env vars
      - Should cache states for 60 seconds (high-frequency updates)
      - Bounding box for Delhi NCR:
        lamin=28.0, lamax=29.2, lomin=76.5, lomax=77.5
      - Returns: callsign, altitude, velocity, heading, vertical_rate

    Example Response (states/all endpoint):
    {
      "states": [
        [
          "780d41",           # ICAO 24-bit address
          "AIC123",           # Callsign
          "DEL",              # Origin (optional)
          "BOM",              # Destination (optional)
          null,               # Call sign (optional)
          35000.0,            # Baro altitude (meters)
          0.0,                # On ground (boolean)
          450.5,              # Velocity (m/s)
          90.0,               # True track (degrees)
          0.0,                # Vertical rate (m/s)
          null,               # Reserved
          null,               # Reserved
          1234567890,         # Last contact (Unix timestamp)
          null,               # Reserved
          null,               # Reserved
          null,               # Reserved
          false,              # SPI (Special Position Identification)
          false               # On ground (redundant)
        ]
      ]
    }

    To Implement:
      1. Add OPENSKY_USERNAME, OPENSKY_PASSWORD to .env
      2. Implement fetch() with bounding box query
      3. Parse aircraft states into DataResult
      4. Cache for 60 seconds (TTL)
      5. Register in manager.py init_adapters()

    Data Return Format (when implemented):
      DataResult(
        data={
          "aircraft_count": int,
          "aircraft": [
            {
              "icao24": str,
              "callsign": str,
              "altitude_m": float,
              "velocity_ms": float,
              "heading_deg": float,
              "vertical_rate_ms": float,
              "on_ground": bool,
            }
          ],
          "bounding_box": {lamin, lamax, lomin, lomax},
          "timestamp": int,
        },
        source="OpenSky Network API",
        source_type=SourceType.API,
        domain=DataDomain.AIR_TRAFFIC,
      )

    Registration (manager.py):
      # OpenSky Network (requires API key)
      if os.getenv("OPENSKY_USERNAME") and os.getenv("OPENSKY_PASSWORD"):
          adapters.append(OpenSkyNetworkAdapter(ttl_seconds=60))
      else:
          log.warning("OpenSky disabled — missing OPENSKY_USERNAME/PASSWORD")
    """

    _URL = "https://opensky-network.org/api/states/all"

    def __init__(self, ttl_seconds: float = 60):
        super().__init__(ttl_seconds=ttl_seconds)

    @property
    def name(self) -> str:
        return "opensky_network"

    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def domains(self) -> List[DataDomain]:
        return [DataDomain.AIR_TRAFFIC]

    async def fetch(self, **kwargs) -> DataResult:
        """Fetch real-time aircraft states over Delhi NCR."""
        # Graceful degradation: return empty if no credentials
        username = os.getenv("OPENSKY_USERNAME", "")
        password = os.getenv("OPENSKY_PASSWORD", "")

        if not username or not password:
            return DataResult(
                data={},
                source="OpenSky Network (disabled — no API key)",
                source_type=SourceType.API,
                domain=DataDomain.AIR_TRAFFIC,
                meta={"reason": "OPENSKY_USERNAME or OPENSKY_PASSWORD not set"},
            )

        # Bounding box for Delhi NCR
        lamin = kwargs.get("lamin", 28.0)    # min latitude
        lamax = kwargs.get("lamax", 29.2)    # max latitude
        lomin = kwargs.get("lomin", 76.5)    # min longitude
        lomax = kwargs.get("lomax", 77.5)    # max longitude

        params = {"lamin": lamin, "lamax": lamax, "lomin": lomin, "lomax": lomax}
        auth = (username, password)

        async with httpx.AsyncClient(timeout=10, auth=auth) as client:
            resp = await client.get(self._URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        states = raw.get("states", [])
        aircraft_list = []

        for state in states:
            aircraft_list.append({
                "icao24": state[0],
                "callsign": state[1].strip() if state[1] else "N/A",
                "altitude_m": state[7] if state[7] is not None else None,
                "velocity_ms": state[9] if state[9] is not None else None,
                "heading_deg": state[10] if state[10] is not None else None,
                "vertical_rate_ms": state[11] if state[11] is not None else None,
                "on_ground": state[8] if state[8] is not None else False,
            })

        return DataResult(
            data={
                "aircraft_count": len(aircraft_list),
                "aircraft": aircraft_list,
                "bounding_box": {
                    "lamin": lamin,
                    "lamax": lamax,
                    "lomin": lomin,
                    "lomax": lomax,
                },
                "timestamp": raw.get("time", 0),
            },
            source="OpenSky Network API",
            source_type=SourceType.API,
            domain=DataDomain.AIR_TRAFFIC,
            meta={"username": username},  # For debugging
        )
