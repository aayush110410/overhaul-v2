import pytest
import asyncio
from engines.energy.engine import EnergyEngine
from engines.base import Scenario

# Baselines from energy/engine.py
_BASELINES = {
    "ev_share": 0.03,
    "daily_fuel_consumption_ml": 12.5,
}


@pytest.mark.asyncio
async def test_energy_engine_uses_agent_sim_data():
    """
    Test that EnergyEngine correctly uses agent simulation ev_share
    instead of static 3% baseline.
    """
    engine = EnergyEngine()

    scenario = Scenario(name="Test Wiring", interventions=[])

    # Agent sim reports 18% EV share (not 3% baseline)
    data = {
        "registered_vehicles": 10_000_000,
        "transport_result": {
            "ev_share": 0.18,
            "total_vkt": 200_000_000,
            "avg_speed_kmh": 25,
            "congestion_pct": 0.3,
        }
    }

    result = await engine._run(scenario, data)

    # Agent sim reports 18% EV share → 1.8M projected EVs
    # (baseline would be 3% or 360K)
    assert result.metrics["projected_ev_count"] == 1_800_000, \
        f"Expected 1,800,000 but got {result.metrics['projected_ev_count']}"

    # Should reflect the agent sim EV share (18%)
    assert result.metrics["ev_share_pct"] == 18.0

    # Metadata should indicate source
    assert result.metrics.get("ev_share_source") == "agent_sim"


@pytest.mark.asyncio
async def test_energy_engine_falls_back_without_transport_result():
    """Without transport_result, use static baseline."""
    engine = EnergyEngine()
    scenario = Scenario(name="NoAgentSim", interventions=[])

    data = {
        "registered_vehicles": 12_000_000,
        # No transport_result
    }

    result = await engine._run(scenario, data)

    # Baseline 3% of 12M = 360K
    assert result.metrics["projected_ev_count"] == 360_000
    assert result.metrics["ev_share_source"] == "baseline"


if __name__ == "__main__":
    asyncio.run(test_energy_engine_uses_agent_sim_data())
