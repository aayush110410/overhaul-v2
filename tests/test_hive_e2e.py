"""End-to-end test of the /simulate/hive endpoint with a REAL LLM.

Skipped when no provider keys are present. Asserts structural correctness +
schema validity. It is deliberately tolerant of free-tier throttling: under
rate limits the hive degrades to physics (sentinel_fallbacks rises) but the run
must still COMPLETE and return a valid, populated SimulationState. The strict
"LLM truly drove routing" guarantee lives in test_reasoning_gateway.py (offline,
deterministic).
"""
import os

import pytest

_HAS_KEYS = bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY"))


@pytest.mark.skipif(not _HAS_KEYS, reason="no LLM keys (OPENROUTER_API_KEY / GEMINI_API_KEY)")
@pytest.mark.asyncio
async def test_hive_endpoint_end_to_end():
    from app import HiveRequest, simulate_hive
    from shared.contracts.simulation_state import SimulationState

    state = await simulate_hive(
        HiveRequest(prompt="congestion pricing in central Delhi during peak hours",
                    agent_count=300, sentinels=14, timesteps=2)
    )

    # Schema-valid contract
    assert isinstance(state, SimulationState)
    SimulationState.model_validate(state.model_dump())

    # Populated, real structure
    assert len(state.brains) == 7
    assert len(state.sentinels) > 0 and state.sentinels[0].coords
    assert len(state.timesteps) == 2
    assert sum(t.sentinel_discoveries for t in state.timesteps) > 0   # cognition ran
    assert "transport" in state.engine_results["domains"]
    assert state.report.summary                                        # a brief was produced
    assert state.stats.get("per_provider")                            # gateway was exercised
