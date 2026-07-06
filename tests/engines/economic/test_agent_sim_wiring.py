import pytest
from engines.economic.engine import EconomicEngine
from engines.base import Scenario


@pytest.mark.asyncio
async def test_economic_engine_uses_agent_sim_results():
    """
    Verify that EconomicEngine uses transport_result from AgentSimulationEngine
    to calculate economic impact instead of relying solely on static baselines.
    """
    engine = EconomicEngine()

    scenario = Scenario(
        name="AgentSimWiringTest",
        time_horizon_days=365,
        interventions=[],
    )

    # With agent simulation data showing 100K agents, speed 30km/h
    # Should use agents_simulated for commuter count and compute savings
    transport_result = {
        "agents_simulated": 100_000,
        "avg_speed_kmh": 30.0,
        "total_vkt": 5_000_000,
        "congestion_pct": 15.0,
        "mode_shifts_observed": 5000,
    }

    data_sim = {"transport_result": transport_result}
    result_sim = await engine._run(scenario, data_sim)

    # Metadata must indicate agent sim was used
    assert result_sim.metadata.get("agent_sim_used") is True

    # Time value savings should be non-zero (based on 100K agents)
    assert result_sim.metrics["annual_time_value_saved_cr"] > 0


@pytest.mark.asyncio
async def test_economic_engine_falls_back_without_transport_result():
    """Without transport_result, engine should still work with baseline calculations."""
    engine = EconomicEngine()
    scenario = Scenario(name="NoAgentSim", time_horizon_days=365, interventions=[])
    data = {}
    result = await engine._run(scenario, data)

    # Should complete without error
    assert result.metrics["benefit_cost_ratio"] > 0
    # Should NOT mark agent sim used
    assert result.metadata.get("agent_sim_used") is not True
