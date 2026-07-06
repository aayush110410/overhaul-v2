import pytest
import asyncio
from unittest.mock import patch
from engines.agent_simulation.swarm import UrbanSwarm

@pytest.mark.asyncio
async def test_sentinel_agents_have_valid_nodes():
    """
    Verify that sentinel agents are initialized with nodes that exist in the road graph.
    Invalid nodes (like 'default_node') will cause routing/Dijkstra failures.
    """
    # Use default nodes and edges
    swarm = UrbanSwarm()

    # IMPORTANT: In the current buggy version, initialize() generates agents
    # which are then used by _create_sentinel_agents().
    # To hit the 'default_node' bug, we MUST clear the agents AFTER initialize()
    # but BEFORE _create_sentinel_agents().
    # Since initialize() calls _create_sentinel_agents() at the end,
    # we'll mock the population generators to return empty lists.

    with patch("engines.agent_simulation.swarm.generate_commuter_agents", return_value=[]), \
         patch("engines.agent_simulation.swarm.generate_freight_agents", return_value=[]):
        await swarm.initialize()

    valid_node_ids = set(swarm.nodes.keys())

    for sentinel in swarm.sentinel_agents:
        assert sentinel.origin in valid_node_ids, f"Sentinel {sentinel.agent_id} has invalid origin: {sentinel.origin}"
        assert sentinel.destination in valid_node_ids, f"Sentinel {sentinel.agent_id} has invalid destination: {sentinel.destination}"
