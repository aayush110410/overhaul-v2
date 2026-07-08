"""Tests for world.session — the live tick loop (LLM off, everything offline)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import pytest_asyncio

from world.region import RegionProfile, ScenarioConditions, parse_conditions
from world.roadnet import RoadNetwork, parse_overpass
from world.session import MAX_SESSIONS, SESSIONS, WorldSession, create_session
from world.stream import unpack_frame
from world.weather import WeatherProvider, WeatherState

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_sample.json"
REGIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions"

DRY = WeatherState("clear", 10.0, 0.0, 8.0, 30.0, 10000.0, "test")


class _StubResolver:
    """Pins the region but keeps real condition parsing (rain/rush-hour)."""

    def __init__(self, profile, conditions=None):
        self._profile = profile
        self._conditions = conditions

    async def resolve(self, prompt):
        return self._profile, self._conditions or parse_conditions(prompt)


class _StubWeather(WeatherProvider):
    def __init__(self, state=DRY):
        super().__init__(fetch_json=None)
        self._state = state

    async def fetch(self, profile, when=None):
        return self._state


def _profile(key="noida") -> RegionProfile:
    return RegionProfile.from_dict(json.loads((REGIONS_DIR / f"{key}.json").read_text()))


async def _roadnet_loader(profile, **kwargs) -> RoadNetwork:
    return RoadNetwork(parse_overpass(json.loads(FIXTURE.read_text())), key=profile.key)


async def _make(**kwargs) -> WorldSession:
    kwargs.setdefault("prompt", "what if it rains during rush hour in noida")
    kwargs.setdefault("agent_count", 30)
    kwargs.setdefault("sentinels", 7)
    kwargs.setdefault("speed", 600)  # 1 tick = 60 sim-seconds → fast tests
    kwargs.setdefault("enable_llm", False)
    kwargs.setdefault("resolver", _StubResolver(_profile()))
    kwargs.setdefault("weather_provider", _StubWeather())
    kwargs.setdefault("roadnet_loader", _roadnet_loader)
    return await create_session(**kwargs)


@pytest_asyncio.fixture(autouse=True)
async def _clean_sessions():
    yield
    for s in list(SESSIONS.values()):
        await s.stop()


@pytest.mark.asyncio
async def test_create_session_registers_and_streams_frames():
    session = await _make()
    assert session.session_id in SESSIONS
    assert session.running

    hello = session.hello_message()
    assert hello["type"] == "hello"
    assert hello["region"]["key"] == "noida"
    assert hello["agents"]["total"] == 30
    assert hello["agents"]["sentinel_indices"] == list(range(7))
    assert hello["weather"]["precip_mm_h"] == 8.0  # rain override from the prompt
    assert hello["roads"]["features"]

    queue = session.subscribe()
    binary = None
    for _ in range(40):
        item = await asyncio.wait_for(queue.get(), timeout=2.0)
        if isinstance(item, (bytes, bytearray)):
            binary = item
            break
    assert binary is not None, "expected a binary frame from the live loop"
    frame = unpack_frame(binary)
    assert frame["agent_count"] == 30
    assert any(a["agent_class"] == 1 for a in frame["agents"][:7])
    await session.stop()
    assert session.session_id not in SESSIONS


@pytest.mark.asyncio
async def test_step_advances_clock_and_emits_metrics():
    session = await _make(speed=600)
    await session.stop()  # kill the live loop; drive ticks manually
    SESSIONS[session.session_id] = session  # stop() deregisters; re-add for the test
    queue = session.subscribe()

    for _ in range(10):
        await session.step()
    assert session.sim_s == pytest.approx(10 * 0.1 * 600)

    kinds = []
    while not queue.empty():
        item = queue.get_nowait()
        kinds.append("bin" if isinstance(item, (bytes, bytearray)) else item.get("type"))
    assert "bin" in kinds
    assert "metrics" in kinds
    SESSIONS.pop(session.session_id, None)


@pytest.mark.asyncio
async def test_cognitive_event_feeds_hive_and_broadcasts_thoughts():
    session = await _make(speed=600)
    await session.stop()
    queue = session.subscribe()

    # 30 ticks × 60 sim-s = 1800 sim-s → exactly one cognitive event.
    for _ in range(30):
        await session.step()
    assert session._cog_events == 1
    assert session.swarm._flow_map, "corridor congestion must reach the hive"

    types = []
    while not queue.empty():
        item = queue.get_nowait()
        if not isinstance(item, (bytes, bytearray)) and item is not None:
            types.append(item["type"])
    assert "phase" in types
    assert "sentinel_thought" in types


@pytest.mark.asyncio
async def test_report_after_three_events():
    session = await _make(speed=600)
    await session.stop()
    queue = session.subscribe()
    for _ in range(95):  # ≥ 3 cognitive events (5700 sim-s)
        await session.step()
    assert session._cog_events >= 3
    report = None
    while not queue.empty():
        item = queue.get_nowait()
        if isinstance(item, dict) and item.get("type") == "report":
            report = item
    assert report is not None
    assert report["brains"]
    assert "avg speed" in report["summary"] or report["summary"]


@pytest.mark.asyncio
async def test_max_sessions_evicts_oldest():
    first = await _make()
    for _ in range(MAX_SESSIONS):
        await _make()
    assert len(SESSIONS) <= MAX_SESSIONS
    assert first.session_id not in SESSIONS
    assert not first.running


@pytest.mark.asyncio
async def test_state_json_shape():
    session = await _make()
    state = session.state_json()
    assert state["region"] == "noida"
    assert {"running", "speed", "sim_clock", "agents_total", "arrived", "avg_speed_kmh"} <= set(state)
    await session.stop()


@pytest.mark.asyncio
async def test_set_speed_pauses_and_clamps():
    session = await _make(speed=600)
    await session.stop()
    assert session.set_speed(0) == 0
    before = session.sim_s
    await session.step()
    assert session.sim_s == before  # paused: sim time frozen
    assert session.set_speed(9999) == 600  # clamped
    await session.step()
    assert session.sim_s > before
