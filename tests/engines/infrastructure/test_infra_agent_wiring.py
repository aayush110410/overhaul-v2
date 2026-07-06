import pytest
from unittest.mock import AsyncMock, MagicMock
from engines.infrastructure.engine import InfrastructureEngine
from engines.base import Scenario, Intervention

@pytest.mark.asyncio
async def test_infrastructure_engine_uses_agent_sim_congestion():
    engine = InfrastructureEngine()
    scenario = Scenario(name="Test Scenario", interventions=[])

    # Case 1: No agent simulation data (should use static baseline)
    data_no_sim = {"existing_capacity_vph": 180000, "daily_demand": 12000000}
    result_no_sim = await engine._run(scenario, data_no_sim)
    ratio_no_sim = result_no_sim.metrics["congestion_ratio_after"]

    # Case 2: With agent simulation data (should override)
    # According to task: use transport_result.congestion_pct for capacity utilization
    # In the code, this should influence new_congestion_ratio
    data_with_sim = {
        "existing_capacity_vph": 180000,
        "daily_demand": 12000000,
        "transport_result": {"congestion_pct": 85.0}
    }
    result_with_sim = await engine._run(scenario, data_with_sim)
    ratio_with_sim = result_with_sim.metrics["congestion_ratio_after"]

    assert ratio_no_sim != ratio_with_sim, "Engine should use agent simulation data when available"
