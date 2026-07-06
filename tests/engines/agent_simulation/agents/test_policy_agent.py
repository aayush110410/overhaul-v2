import pytest
from unittest.mock import MagicMock
from engines.agent_simulation.agents.policy_agent import PolicyAgent

def test_policy_agent_sync_no_llm():
    mock_backend = MagicMock()
    agent = PolicyAgent(backend=mock_backend, llm_provider=None)

    result = agent.sync_from_web("test query")
    assert result["error"] == "No LLM configured"
    assert result["laws"] == []

def test_policy_agent_sync_with_llm():
    mock_backend = MagicMock()
    mock_llm = MagicMock(return_value={
        "laws": [{"id": "L1", "text": "Law 1"}],
        "budgets": [{"id": "B1", "amount": 100}],
        "announcements": ["Announcement 1"]
    })
    agent = PolicyAgent(backend=mock_backend, llm_provider=mock_llm)

    result = agent.sync_from_web("test query")
    assert len(result["laws"]) == 1
    assert result["laws"][0]["id"] == "L1"
    mock_llm.assert_called_once_with({"query": "test query"})

def test_policy_agent_broadcast():
    mock_backend = MagicMock()
    agent = PolicyAgent(backend=mock_backend)
    data = {"laws": [1], "budgets": [2], "announcements": [3]}

    agent.broadcast_to_global_kg(data)
    mock_backend.sync_from_policy_agent.assert_called_once_with(data)

@pytest.mark.asyncio
async def test_run_policy_broadcast():
    mock_backend = MagicMock()
    mock_llm = MagicMock(return_value={
        "laws": [{"id": "L1"}],
        "budgets": [],
        "announcements": []
    })
    agent = PolicyAgent(backend=mock_backend, llm_provider=mock_llm)

    # First run
    result = await agent.run_policy_broadcast("query", timestep=1)
    assert result["status"] == "success"
    assert result["laws_count"] == 1

    # Second run same timestep - should skip
    result_skip = await agent.run_policy_broadcast("query", timestep=1)
    assert result_skip["status"] == "skipped"

    # Next timestep - should run
    result_next = await agent.run_policy_broadcast("query", timestep=2)
    assert result_next["status"] == "success"
