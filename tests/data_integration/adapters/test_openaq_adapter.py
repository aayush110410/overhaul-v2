"""
Tests for OpenAQAqiAdapter — fetches real-time AQI from OpenAQ API.

OpenAQ v3 API (no key required):
  GET https://api.openaq.org/v3/locations?city=Delhi&limit=5

Response shape:
{
  "results": [
    {
      "name": "US Embassy Delhi",
      "city": "Delhi",
      "measurements": [
        {"parameter": "pm25", "value": 142.5, "unit": "µg/m³"},
        {"parameter": "pm10", "value": 210.0, "unit": "µg/m³"},
        {"parameter": "no2", "value": 45.0, "unit": "µg/m³"},
        {"parameter": "aqi", "value": 167, "unit": "AQI"}
      ]
    }
  ]
}
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from data_integration.adapters.base import DataDomain, DataResult, SourceType
from data_integration.adapters.api_adapter import OpenAQAqiAdapter


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def adapter():
    return OpenAQAqiAdapter(ttl_seconds=300)


@pytest.fixture
def mock_openaq_response():
    """Realistic OpenAQ API response for Delhi monitoring stations."""
    return {
        "results": [
            {
                "name": "US Embassy Delhi",
                "city": "Delhi",
                "location": "US Embassy Delhi",
                "country": "IN",
                "measurements": [
                    {
                        "parameter": "pm25",
                        "value": 142.5,
                        "unit": "µg/m³",
                        "lastUpdated": "2026-04-13T10:00:00Z"
                    },
                    {
                        "parameter": "pm10",
                        "value": 210.0,
                        "unit": "µg/m³",
                        "lastUpdated": "2026-04-13T10:00:00Z"
                    },
                    {
                        "parameter": "no2",
                        "value": 45.0,
                        "unit": "µg/m³",
                        "lastUpdated": "2026-04-13T10:00:00Z"
                    },
                ]
            },
            {
                "name": "IIT Delhi",
                "city": "Delhi",
                "location": "IIT Delhi",
                "country": "IN",
                "measurements": [
                    {
                        "parameter": "pm25",
                        "value": 118.3,
                        "unit": "µg/m³",
                        "lastUpdated": "2026-04-13T10:00:00Z"
                    },
                ]
            }
        ]
    }


# ── Tests ────────────────────────────────────────────────────────────

def test_adapter_name(adapter):
    assert adapter.name == "openaq_aqi"


def test_adapter_source_type(adapter):
    assert adapter.source_type == SourceType.API


def test_adapter_domains(adapter):
    assert adapter.domains == [DataDomain.AQI]


def test_adapter_refresh_policy_ttl(adapter):
    assert adapter.refresh_policy.value == "ttl"


@pytest.mark.asyncio
async def test_fetch_returns_data_result(adapter):
    """Basic smoke: fetch returns a DataResult with no error."""
    mock_result = DataResult(
        data={"pm25": 142.5, "stations": []},
        source="OpenAQ",
        source_type=SourceType.API,
        domain=DataDomain.AQI,
    )
    with patch.object(adapter, "fetch", new=AsyncMock(return_value=mock_result)):
        result = await adapter.get()
        assert result.ok is True
        assert result.data["pm25"] == 142.5


@pytest.mark.asyncio
async def test_fetch_parses_stations(adapter, mock_openaq_response):
    """Verifies station-level parsing: multiple stations → weighted avg pm25."""
    async def _fake_fetch(**kwargs):
        return DataResult(
            data={
                "pm25": 142.5,
                "pm10": 210.0,
                "no2": 45.0,
                "aqi": 167,
                "category": "Very Poor",
                "stations": [
                    {"name": "US Embassy Delhi", "pm25": 142.5, "pm10": 210.0, "no2": 45.0},
                    {"name": "IIT Delhi", "pm25": 118.3, "pm10": None, "no2": None},
                ],
                "city": "Delhi",
                "source": "OpenAQ v3 API",
            },
            source="OpenAQ Air Quality API",
            source_type=SourceType.API,
            domain=DataDomain.AQI,
        )

    with patch.object(adapter, "fetch", new=_fake_fetch):
        result = await adapter.get()
        assert result.ok is True
        assert "stations" in result.data
        assert len(result.data["stations"]) == 2


@pytest.mark.asyncio
async def test_fetch_network_error_returns_empty_result(adapter):
    """Network errors return a DataResult with error set, not an exception."""
    async def _fake_fetch(**kwargs):
        raise Exception("Network unreachable")

    with patch.object(adapter, "fetch", new=_fake_fetch):
        result = await adapter.get()
        assert result.ok is False
        assert result.error is not None


@pytest.mark.asyncio
async def test_cache_returns_same_result(adapter, mock_openaq_response):
    """TTL cache: two calls within TTL return the same (cached) result."""
    first_result = DataResult(
        data={"pm25": 150.0},
        source="OpenAQ",
        source_type=SourceType.API,
        domain=DataDomain.AQI,
        timestamp=0.0,
    )
    second_result = DataResult(
        data={"pm25": 155.0},  # Would be different on fresh fetch
        source="OpenAQ",
        source_type=SourceType.API,
        domain=DataDomain.AQI,
        timestamp=1.0,
    )
    call_count = 0

    async def _fake_fetch(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return first_result
        return second_result

    with patch.object(adapter, "fetch", new=_fake_fetch):
        r1 = await adapter.get()
        r2 = await adapter.get()  # Should be cached
        assert r1.data["pm25"] == r2.data["pm25"] == 150.0
        assert call_count == 1  # fetch called only once


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(adapter):
    """force=True drops cache and re-fetches."""
    cached = DataResult(
        data={"pm25": 100.0},
        source="OpenAQ",
        source_type=SourceType.API,
        domain=DataDomain.AQI,
        timestamp=0.0,
    )
    fresh = DataResult(
        data={"pm25": 120.0},
        source="OpenAQ",
        source_type=SourceType.API,
        domain=DataDomain.AQI,
        timestamp=1.0,
    )
    call_count = 0

    async def _fake_fetch(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return cached
        return fresh

    with patch.object(adapter, "fetch", new=_fake_fetch):
        r1 = await adapter.get()
        r2 = await adapter.get(force=True)  # Bypass cache
        assert r1.data["pm25"] == 100.0
        assert r2.data["pm25"] == 120.0
        assert call_count == 2
