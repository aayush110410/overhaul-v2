import pytest
import os
from typing import Optional

from engines.agent_simulation.swarm import UrbanSwarm
from engines.agent_simulation.config import SwarmConfig
from engines.agent_simulation.llm_providers import auto_provider
from engines.registry import EngineRegistry

# Mock nodes and edges for a minimal simulation
DEFAULT_NODES = {"node_1": {"x": 0, "y": 0}, "node_2": {"x": 1, "y": 1}}
DEFAULT_EDGES = [("node_1", "node_2", {"weight": 1, "capacity": 100, "free_speed": 40})]

@pytest.mark.asyncio
@pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OLLAMA_HOST")),
    reason="No LLM API key or host configured"
)
async def test_full_simulation_with_llm_reasoning():
    """
    Full end-to-end simulation with a real LLM provider.
    Verifies that the Hive loop completes and produces valid metrics.
    """
    # Minimal config to keep costs/time low
    config = SwarmConfig(
        commuter_count=10,
        sentinel_count=3,
        timesteps=2
    )

    # Get the best available provider
    provider = auto_provider()

    swarm = UrbanSwarm(
        nodes=DEFAULT_NODES,
        edges=DEFAULT_EDGES,
        config=config
    )

    # Initialize with the real LLM provider
    await swarm.initialize(llm_provider=provider)

    # Run the simulation
    result = await swarm.run()

    # Verifications
    assert result is not None
    assert result.total_vkt > 0, "Simulation should have produced vehicle kilometers traveled"
    assert result.avg_speed_kmh > 0, "Simulation should have a positive average speed"
    assert hasattr(result, 'hotspots'), "Result should contain hotspots"

    print(f"\nE2E LLM Simulation Result: VKT={result.total_vkt}, AvgSpeed={result.avg_speed_kmh}")
