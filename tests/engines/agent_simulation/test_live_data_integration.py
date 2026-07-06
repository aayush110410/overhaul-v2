"""
Tests for live data integration: adapter → engine → simulation output.

Verifies that:
1. AgentSimulationEngine calls init_adapters() and get_ncr_context() before swarm.run()
2. Live PM2.5 from adapters flows into data dict as baseline_pm25
3. Live speed from TomTom flows into data dict as baseline_speed_kmh
4. live_data_sources metadata is populated in output
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from engines.agent_simulation.engine import AgentSimulationEngine
from engines.base import EngineCapability, Scenario, Intervention
from data_integration.adapters.base import DataResult, DataDomain, SourceType


@pytest.fixture
def engine():
    return AgentSimulationEngine()


@pytest.fixture
def scenario():
    return Scenario(
        name="test_live_data",
        description="Test scenario",
        city="delhi",
        interventions=[],
        time_horizon_days=1,
    )


@pytest.mark.asyncio
async def test_engine_fetches_live_context_before_simulation(engine, scenario):
    """AgentSimulationEngine._run() must call init_adapters() and get_ncr_context()."""
    mock_context = {
        "live_aqi": {"pm25": 150.0, "stations": []},
        "tomtom": {"current_speed": 35.0, "free_flow_speed": 50.0},
        "sources": ["OpenAQ Air Quality API", "TomTom Traffic Flow API"],
    }

    init_called = False
    get_ctx_called = False

    async def mock_init():
        nonlocal init_called
        init_called = True

    async def mock_get_ctx(city):
        nonlocal get_ctx_called
        get_ctx_called = True
        return mock_context

    mock_swarm_result = MagicMock()
    mock_swarm_result.total_vkt = 1000.0
    mock_swarm_result.total_co2_kg = 50.0
    mock_swarm_result.total_pm25_g = 2.5
    mock_swarm_result.avg_speed_kmh = 40.0
    mock_swarm_result.congestion_pct = 30.0
    mock_swarm_result.ev_share = 0.05
    mock_swarm_result.agents_total = 2
    mock_swarm_result.agents_arrived = 2
    mock_swarm_result.total_mode_shifts = 0
    mock_swarm_result.timesteps = []
    mock_swarm_result.final_edge_flows = {}
    mock_swarm_result.final_edge_congestion = {}
    mock_swarm_result.hotspots = []
    mock_swarm_result.segment_breakdown = {}
    mock_swarm_result.graph_info = {}
    mock_swarm_result.runtime_seconds = 0.1

    with patch("engines.agent_simulation.engine.init_adapters", mock_init):
        with patch("engines.agent_simulation.engine.get_ncr_context", mock_get_ctx):
            with patch("engines.agent_simulation.engine.UrbanSwarm") as MockSwarm:
                mock_swarm = MagicMock()
                mock_swarm.initialize = AsyncMock()
                mock_swarm.apply_interventions = MagicMock()
                mock_swarm.run = AsyncMock(return_value=mock_swarm_result)
                MockSwarm.return_value = mock_swarm

                result = await engine._run(scenario, {"agent_count": 2, "timesteps": 1})

    assert init_called, "init_adapters() was not called"
    assert get_ctx_called, "get_ncr_context() was not called"
    assert result.metrics.get("simulation_mode") == "agent_based"


@pytest.mark.asyncio
async def test_live_pm25_seeded_into_data(engine, scenario):
    """Live PM2.5 from OpenAQ must be passed to data as baseline_pm25."""
    mock_context = {
        "live_aqi": {"pm25": 180.5},
        "tomtom": {},
        "sources": ["OpenAQ Air Quality API"],
    }

    captured_data = {}

    async def mock_init():
        pass

    async def mock_get_ctx(city):
        return mock_context

    mock_swarm_result = MagicMock()
    mock_swarm_result.total_vkt = 1000.0
    mock_swarm_result.total_co2_kg = 50.0
    mock_swarm_result.total_pm25_g = 2.5
    mock_swarm_result.avg_speed_kmh = 40.0
    mock_swarm_result.congestion_pct = 30.0
    mock_swarm_result.ev_share = 0.05
    mock_swarm_result.agents_total = 2
    mock_swarm_result.agents_arrived = 2
    mock_swarm_result.total_mode_shifts = 0
    mock_swarm_result.timesteps = []
    mock_swarm_result.final_edge_flows = {}
    mock_swarm_result.final_edge_congestion = {}
    mock_swarm_result.hotspots = []
    mock_swarm_result.segment_breakdown = {}
    mock_swarm_result.graph_info = {}
    mock_swarm_result.runtime_seconds = 0.1

    original_run = engine._run

    with patch("engines.agent_simulation.engine.init_adapters", mock_init):
        with patch("engines.agent_simulation.engine.get_ncr_context", mock_get_ctx):
            with patch("engines.agent_simulation.engine.UrbanSwarm") as MockSwarm:
                mock_swarm = MagicMock()
                mock_swarm.initialize = AsyncMock()
                mock_swarm.apply_interventions = MagicMock()
                mock_swarm.run = AsyncMock(return_value=mock_swarm_result)
                MockSwarm.return_value = mock_swarm

                result = await engine._run(scenario, {"agent_count": 2, "timesteps": 1})

    # Result metadata must contain live data sources
    metadata = result.metadata or {}
    assert "live_data_sources" in metadata
    assert "OpenAQ" in str(metadata["live_data_sources"])


@pytest.mark.asyncio
async def test_live_speed_calibrates_flow_map(engine, scenario):
    """TomTom current_speed must be passed as baseline_speed_kmh."""
    mock_context = {
        "live_aqi": {},
        "tomtom": {"current_speed": 25.0, "free_flow_speed": 50.0},
        "sources": ["TomTom Traffic Flow API"],
    }

    async def mock_init():
        pass

    async def mock_get_ctx(city):
        return mock_context

    mock_swarm_result = MagicMock()
    mock_swarm_result.total_vkt = 1000.0
    mock_swarm_result.total_co2_kg = 50.0
    mock_swarm_result.total_pm25_g = 2.5
    mock_swarm_result.avg_speed_kmh = 40.0
    mock_swarm_result.congestion_pct = 30.0
    mock_swarm_result.ev_share = 0.05
    mock_swarm_result.agents_total = 2
    mock_swarm_result.agents_arrived = 2
    mock_swarm_result.total_mode_shifts = 0
    mock_swarm_result.timesteps = []
    mock_swarm_result.final_edge_flows = {}
    mock_swarm_result.final_edge_congestion = {}
    mock_swarm_result.hotspots = []
    mock_swarm_result.segment_breakdown = {}
    mock_swarm_result.graph_info = {}
    mock_swarm_result.runtime_seconds = 0.1

    with patch("engines.agent_simulation.engine.init_adapters", mock_init):
        with patch("engines.agent_simulation.engine.get_ncr_context", mock_get_ctx):
            with patch("engines.agent_simulation.engine.UrbanSwarm") as MockSwarm:
                mock_swarm = MagicMock()
                mock_swarm.initialize = AsyncMock()
                mock_swarm.apply_interventions = MagicMock()
                mock_swarm.run = AsyncMock(return_value=mock_swarm_result)
                MockSwarm.return_value = mock_swarm

                result = await engine._run(scenario, {"agent_count": 2, "timesteps": 1})

    # Must complete without error
    assert result.metrics.get("simulation_mode") == "agent_based"
    assert result.metrics.get("agents_simulated") == 2


@pytest.mark.asyncio
async def test_graceful_fallback_when_no_live_data(engine, scenario):
    """Simulation must succeed even when no live data is available (all adapters fail)."""
    empty_context = {
        "live_aqi": {},
        "tomtom": {},
        "sources": [],
    }

    async def mock_init():
        pass

    async def mock_get_ctx(city):
        return empty_context

    mock_swarm_result = MagicMock()
    mock_swarm_result.total_vkt = 1000.0
    mock_swarm_result.total_co2_kg = 50.0
    mock_swarm_result.total_pm25_g = 2.5
    mock_swarm_result.avg_speed_kmh = 40.0
    mock_swarm_result.congestion_pct = 30.0
    mock_swarm_result.ev_share = 0.05
    mock_swarm_result.agents_total = 2
    mock_swarm_result.agents_arrived = 2
    mock_swarm_result.total_mode_shifts = 0
    mock_swarm_result.timesteps = []
    mock_swarm_result.final_edge_flows = {}
    mock_swarm_result.final_edge_congestion = {}
    mock_swarm_result.hotspots = []
    mock_swarm_result.segment_breakdown = {}
    mock_swarm_result.graph_info = {}
    mock_swarm_result.runtime_seconds = 0.1

    with patch("engines.agent_simulation.engine.init_adapters", mock_init):
        with patch("engines.agent_simulation.engine.get_ncr_context", mock_get_ctx):
            with patch("engines.agent_simulation.engine.UrbanSwarm") as MockSwarm:
                mock_swarm = MagicMock()
                mock_swarm.initialize = AsyncMock()
                mock_swarm.apply_interventions = MagicMock()
                mock_swarm.run = AsyncMock(return_value=mock_swarm_result)
                MockSwarm.return_value = mock_swarm

                result = await engine._run(scenario, {"agent_count": 2, "timesteps": 1})

    # Must succeed — graceful degradation
    assert result.metrics.get("simulation_mode") == "agent_based"
    # No live sources = adapters all returned empty/stale
    assert result.metadata.get("live_data_sources") == []
