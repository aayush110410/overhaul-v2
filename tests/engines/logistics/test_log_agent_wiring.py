import pytest
from unittest.mock import AsyncMock, MagicMock
from engines.logistics.engine import LogisticsEngine
from engines.base import Scenario, Intervention

@pytest.mark.asyncio
async def test_logistics_engine_uses_agent_sim_vkt():
    engine = LogisticsEngine()
    scenario = Scenario(name="Test Scenario", interventions=[])

    # Case 1: No agent simulation data
    data_no_sim = {"daily_freight_trips": 420000, "e_commerce_parcels": 2800000}
    result_no_sim = await engine._run(scenario, data_no_sim)
    vkt_no_sim = result_no_sim.metrics["projected_freight_vkt"]

    # Case 2: With agent simulation data
    # According to task: use transport_result.total_vkt for freight VKT
    data_with_sim = {
        "daily_freight_trips": 420000,
        "e_commerce_parcels": 2800000,
        "transport_result": {"total_vkt": 15000000}
    }
    result_with_sim = await engine._run(scenario, data_with_sim)
    vkt_with_sim = result_with_sim.metrics["projected_freight_vkt"]

    assert vkt_no_sim != vkt_with_sim, "Engine should use agent simulation total_vkt when available"
