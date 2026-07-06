import pytest
from unittest.mock import AsyncMock, MagicMock
from engines.population.engine import PopulationEngine
from engines.base import Scenario, Intervention

@pytest.mark.asyncio
async def test_population_engine_uses_agent_sim_mode_shifts():
    engine = PopulationEngine()
    scenario = Scenario(name="Test Scenario", interventions=[])

    # Case 1: No agent simulation data
    data_no_sim = {"total_population": 20000000, "commuter_population": 7000000}
    result_no_sim = await engine._run(scenario, data_no_sim)
    vkt_no_sim = result_no_sim.metrics["vkt_after_daily"]

    # Case 2: With agent simulation data
    # According to task: use transport_result.mode_shifts for mode shift rates
    data_with_sim = {
        "total_population": 20000000,
        "commuter_population": 7000000,
        "transport_result": {"mode_shifts_observed": {"car": -0.1, "metro": 0.1}}
    }
    result_with_sim = await engine._run(scenario, data_with_sim)
    vkt_with_sim = result_with_sim.metrics["vkt_after_daily"]

    assert vkt_no_sim != vkt_with_sim, "Engine should use agent simulation mode shifts when available"
