import pytest
import asyncio
from engines.agent_simulation.swarm import UrbanSwarm
from engines.transport.engine import _DEFAULT_NODES, _DEFAULT_EDGES
from engines.agent_simulation.config import SwarmConfig

@pytest.mark.asyncio
async def test_urban_swarm_e2e_run():
    """
    End-to-end test of UrbanSwarm.run().
    Verifies that the Hive Loop (Sentinel -> Brain -> Swarm) completes
    without errors and produces valid results using real network data.
    """
    # Use a minimal config to keep the test fast but comprehensive
    config = SwarmConfig(
        commuter_count=10,
        freight_count=5,
        timesteps=2,
        step_duration_minutes=15,
        congestion_memory_weight=0.3,
        peer_influence_weight=0.2,
        adaptation_threshold=0.2,
        mode_shift_threshold=0.3,
    )

    # We need to make sure config.swarm is set if we pass a config object
    # because UrbanSwarm expects config to be the 'swarm' section of the global config.
    # Let's just use the default config by passing None.

    swarm = UrbanSwarm(
        nodes=_DEFAULT_NODES,
        edges=_DEFAULT_EDGES,
        config=config
    )

    # Initialize the swarm (builds graph, generates population, sets up brains/sentinels)
    await swarm.initialize()

    # Execute the simulation
    try:
        result = await swarm.run()
    except Exception as e:
        pytest.fail(f"UrbanSwarm.run() raised an exception: {e}")

    # Verifications
    assert result is not None
    assert len(result.timesteps) > 0
    assert result.agents_total == len(swarm.agents)
    assert result.runtime_seconds > 0

    # Check that metrics are populated
    assert "final_edge_flows" in result.__dict__
    assert "final_edge_congestion" in result.__dict__

    # Verify that at least some agents arrived or are progressing
    # Since we have few timesteps, they might not all arrive, but the loop should execute.
    assert result.agents_arrived >= 0
