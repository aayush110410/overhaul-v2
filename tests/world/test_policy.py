"""Tests for world.policy packs + EconomicEngine grounding."""

from __future__ import annotations

import pytest

from engines.base import Scenario
from engines.economic.engine import EconomicEngine
from world.policy import load_policy_pack


def test_packs_load_and_validate():
    for key in ("noida", "delhi", "new_york"):
        pack = load_policy_pack(key)
        assert pack is not None, key
        assert pack["region"] == key
        assert pack["facts"] and all(
            {"claim", "source", "as_of", "confidence"} <= set(f) for f in pack["facts"]
        )
        assert "land" in pack and "acts" in pack


def test_missing_pack_returns_none():
    assert load_policy_pack("atlantis") is None
    assert load_policy_pack(None) is None


@pytest.mark.asyncio
async def test_economic_engine_consumes_pack():
    engine = EconomicEngine()
    scenario = Scenario(name="test", description="", interventions=[])

    with_pack = await engine.simulate(scenario, {"policy_pack": load_policy_pack("noida")})
    assert with_pack.metadata["policy_pack"]["land_authority"].startswith("New Okhla")
    assert with_pack.metadata["policy_pack"]["facts"] > 0

    without = await engine.simulate(scenario, {"policy_pack_missing": True})
    assert any("No policy pack" in w for w in without.warnings)
    assert without.confidence < with_pack.confidence
