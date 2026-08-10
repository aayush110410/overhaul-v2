"""Full-stack Living World E2E — real components, zero network, < 30 s.

Exercises the REAL RegionResolver (gazetteer), REAL RoadNetwork.load (Overpass
forced down → NCR fallback), REAL WeatherProvider (HTTP down → default +
prompt override), personas, MovementSim, WorldSession tick loop, binary
frames, cognition (physics), engines refresh incl. AQI + policy pack, report.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from world.roadnet import RoadNetwork
from world.session import SESSIONS, create_session
from world.stream import unpack_frame
from world.weather import WeatherProvider


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    yield
    for s in list(SESSIONS.values()):
        await s.stop()


@pytest.mark.asyncio
async def test_full_world_lifecycle_offline(monkeypatch, tmp_path):
    async def overpass_down(bbox):
        raise TimeoutError("no egress")

    async def weather_down(url, params):
        raise RuntimeError("no egress")

    monkeypatch.setattr(RoadNetwork, "_fetch_overpass", staticmethod(overpass_down))

    async def loader(profile, **kw):
        return await RoadNetwork.load(profile, cache_dir=tmp_path)

    session = await create_session(
        prompt="what if it rains during the diwali evening rush in Noida?",
        agent_count=120,
        sentinels=7,
        speed=600,
        enable_llm=False,
        weather_provider=WeatherProvider(fetch_json=weather_down),
        roadnet_loader=loader,
    )
    try:
        # Region + conditions understood from lay English, fully offline.
        assert session.profile.key == "noida"
        assert session.conditions.precip_mm_h == 8.0
        assert session.conditions.date_context == "diwali"
        assert session.weather.condition == "rain"
        assert session.roadnet.fallback is True

        hello = session.hello_message()
        assert hello["agents"]["total"] == 120
        assert hello["roads"]["features"]
        assert hello["region"]["aqi_baseline"]["annual_mean_pm25"] == 95

        # Live loop produces frames, metrics, AQI, cognition and the report.
        queue = session.subscribe()
        seen = {"frames": 0, "types": set()}
        report = None
        async with asyncio.timeout(25):
            while seen["frames"] < 10 or report is None:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, (bytes, bytearray)):
                    frame = unpack_frame(item)
                    assert frame["agent_count"] == 120
                    seen["frames"] += 1
                else:
                    seen["types"].add(item["type"])
                    if item["type"] == "report":
                        report = item

        assert seen["frames"] >= 10
        assert {"metrics", "phase", "aqi", "sentinel_thought"} <= seen["types"]
        assert report is not None and report["brains"]
        # Diwali context pushed the AQI model into severe territory.
        aqi_now = await session.aqi_series.current(now=session._sim_datetime())
        assert aqi_now["aqi"] > 200

        state = session.state_json()
        assert state["running"] and state["cognitive_events"] >= 1
    finally:
        await session.stop()
    assert session.session_id not in SESSIONS


@pytest.mark.asyncio
async def test_subscriber_churn_does_not_break_session(monkeypatch, tmp_path):
    async def overpass_down(bbox):
        raise TimeoutError("no egress")

    async def weather_down(url, params):
        raise RuntimeError("no egress")

    monkeypatch.setattr(RoadNetwork, "_fetch_overpass", staticmethod(overpass_down))

    async def loader(profile, **kw):
        return await RoadNetwork.load(profile, cache_dir=tmp_path)

    session = await create_session(
        prompt="noida baseline", agent_count=40, sentinels=7, speed=600,
        enable_llm=False,
        weather_provider=WeatherProvider(fetch_json=weather_down),
        roadnet_loader=loader,
    )
    try:
        # Rapidly attach/detach subscribers, including one that never drains.
        lazy = session.subscribe()  # fills up → exercises backpressure path
        for _ in range(5):
            q = session.subscribe()
            await asyncio.sleep(0.15)
            session.unsubscribe(q)
        active = session.subscribe()
        got_frame = False
        async with asyncio.timeout(10):
            while not got_frame:
                item = await active.get()
                got_frame = isinstance(item, (bytes, bytearray))
        assert got_frame
        assert lazy.qsize() > 0  # the lazy queue absorbed what it could
        assert session.running
    finally:
        await session.stop()
