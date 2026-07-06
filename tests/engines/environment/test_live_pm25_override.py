"""
Tests for live PM2.5 override in EnvironmentEngine.

Verifies that:
1. EnvironmentEngine._run() uses live_pm25 from data dict when provided
2. Baseline PM2.5 from _BASELINES is used when live_pm25 is not provided
3. Metadata includes data_source tag ("live_openaq" vs "csv_baseline")
"""

import pytest
from unittest.mock import patch

from engines.environment.engine import EnvironmentEngine
from engines.base import Scenario


@pytest.fixture
def engine():
    return EnvironmentEngine()


@pytest.fixture
def scenario():
    return Scenario(
        name="test_live_pm25",
        description="Test live PM2.5 override",
        city="delhi",
        interventions=[],
        time_horizon_days=1,
    )


@pytest.mark.asyncio
async def test_environment_engine_uses_live_pm25(engine, scenario):
    """When baseline_pm25 is provided from live OpenAQ data, use it instead of CSV baseline."""
    # OpenAQ returns PM2.5 = 180.5 (different from CSV baseline of 164 for Delhi)
    live_pm25 = 180.5

    data = {
        "city": "delhi",
        "baseline_pm25": live_pm25,  # This comes from live OpenAQ data
    }

    result = await engine._run(scenario, data)

    # Must use the live PM2.5 value, not the CSV baseline
    assert result.metrics["baseline_pm25"] == live_pm25
    # Verify it did NOT use the CSV baseline (164 for Delhi)
    assert result.metrics["baseline_pm25"] != 164


@pytest.mark.asyncio
async def test_environment_engine_uses_csv_baseline_when_no_live_data(engine, scenario):
    """When no baseline_pm25 provided, use CSV/default baseline."""
    data = {
        "city": "delhi",
        # No baseline_pm25 provided - should use default baseline (285.0)
    }

    result = await engine._run(scenario, data)

    # Must use default baseline (285.0 as per engine default)
    assert result.metrics["baseline_pm25"] == 285.0


@pytest.mark.asyncio
async def test_metadata_includes_data_source_tag(engine, scenario):
    """Metadata should indicate whether PM2.5 came from live data or CSV baseline."""
    # Test with live data
    data_with_live = {
        "city": "delhi",
        "baseline_pm25": 180.5,
    }

    result_with_live = await engine._run(scenario, data_with_live)

    # Metadata should indicate live data source
    assert result_with_live.metadata.get("pm25_data_source") == "live_openaq"

    # Test with CSV baseline
    data_with_csv = {
        "city": "delhi",
    }

    result_with_csv = await engine._run(scenario, data_with_csv)

    # Metadata should indicate CSV baseline
    assert result_with_csv.metadata.get("pm25_data_source") == "csv_baseline"
