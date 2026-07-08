"""Live world sessions: the persistent tick loop behind the Living Map.

A ``WorldSession`` owns one region's running world: a ``MovementSim`` advanced
at ~10 Hz (accelerated sim time), binary agent frames broadcast at ~5 Hz to
every subscriber, plus JSON events (metrics, weather, sentinel thoughts,
engine refreshes, report). Cognition is EVENT-gated for token efficiency:
every 30 sim-minutes the live corridor congestion is pushed into the existing
``UrbanSwarm`` and ONE batched hive timestep runs through the reasoning
gateway (physics fallback when LLM is off/throttled). The 7 domain engines
refresh hourly (sim time) on the region's corridor graph.

Zero LLM calls, zero I/O inside the tick itself.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import math
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from world.movement import MovementSim
from world.region import RegionProfile, RegionResolver, ScenarioConditions
from world.roadnet import RoadNetwork
from world.stream import pack_frame
from world.weather import WeatherProvider, WeatherState

logger = logging.getLogger(__name__)

MAX_SESSIONS = 3
SESSIONS: Dict[str, "WorldSession"] = {}

_TICK_REAL_S = 0.1  # 10 Hz loop
_BROADCAST_EVERY_TICKS = 2  # → 5 Hz frames
_METRICS_EVERY_TICKS = 10  # → 1 Hz metrics
_COGNITIVE_INTERVAL_SIM_S = 1800.0  # hive thinks every 30 sim-minutes
_ENGINE_INTERVAL_SIM_S = 3600.0  # engines refresh every sim-hour
_REPORT_AFTER_EVENTS = 3
_MAX_WALL_S = 900.0  # free-tier guard: a session lives ≤15 real minutes
_QUEUE_MAX = 64

_TIME_OF_DAY_CLOCK_S = {
    "rush_hour_am": 8.5 * 3600,
    "morning": 7 * 3600,
    "afternoon": 14 * 3600,
    "rush_hour_pm": 18 * 3600,
    "evening": 19 * 3600,
    "night": 23 * 3600,
}

_resolver: Optional[RegionResolver] = None


def _get_resolver() -> RegionResolver:
    global _resolver
    if _resolver is None:
        _resolver = RegionResolver(llm_fn=_llm_place_extract)
    return _resolver


async def _llm_place_extract(prompt: str) -> Optional[str]:
    """Last-resort place extraction — one tiny gateway call, gateway-cached."""
    from reasoning import get_gateway

    text = await get_gateway().reason_text(
        prompt=(
            "Extract the real-world city or place this question is about. "
            f"Reply with ONLY the place name, or NONE.\nQuestion: {prompt}\nPlace:"
        ),
        system="You extract place names. Reply with only the place name or NONE.",
        prefer="qwen",
    )
    name = (text or "").strip().splitlines()[0].strip(" .\"'")[:60]
    if not name or name.upper().startswith("NONE"):
        return None
    return name


class WorldSession:
    """One live, streaming world. Construct via ``create_session()``."""

    def __init__(
        self,
        session_id: str,
        prompt: str,
        profile: RegionProfile,
        conditions: ScenarioConditions,
        roadnet: RoadNetwork,
        weather: WeatherState,
        swarm: Any,  # UrbanSwarm (typed loosely to keep import cost down)
        scenario: Any,  # engines.base.Scenario
        movement: MovementSim,
        speed: int = 60,
        enable_llm: bool = False,
    ):
        self.session_id = session_id
        self.prompt = prompt
        self.profile = profile
        self.conditions = conditions
        self.roadnet = roadnet
        self.weather = weather
        self.swarm = swarm
        self.scenario = scenario
        self.movement = movement
        self.speed = max(1, int(speed))
        self.enable_llm = enable_llm

        self.running = False
        self.created_at = time.time()
        self.sim_s = 0.0
        self.clock0_s = _TIME_OF_DAY_CLOCK_S.get(
            conditions.time_of_day or "", _now_clock_s()
        )
        self.engine_domains: Dict[str, Any] = {}

        self._task: Optional[asyncio.Task] = None
        self._subscribers: List[asyncio.Queue] = []
        self._seq = 0
        self._tick_i = 0
        self._cog_events = 0
        self._report_sent = False
        self._last_cog_s = 0.0
        self._last_engine_s = 0.0
        self._sentinel_indices = [
            a.idx for a in movement.agents if a.agent_class == 1
        ]

    # ── subscriptions ──

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _broadcast(self, item: Any) -> None:
        # Binary frames are droppable (dead-reckoning covers gaps); JSON events
        # and the end sentinel must land — evict the oldest queued item instead.
        important = not isinstance(item, (bytes, bytearray))
        for q in list(self._subscribers):
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                if not important:
                    continue
                try:
                    q.get_nowait()
                    q.put_nowait(item)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def set_speed(self, speed: int) -> int:
        """Runtime time-dilation control (0 pauses; clamped to ≤600×)."""
        self.speed = max(0, min(int(speed), 600))
        self._broadcast({"type": "phase", "phase": "speed", "speed": self.speed})
        return self.speed

    # ── public messages/state ──

    def hello_message(self) -> Dict[str, Any]:
        return {
            "type": "hello",
            "session_id": self.session_id,
            "prompt": self.prompt,
            "region": {
                "key": self.profile.key,
                "display_name": self.profile.display_name,
                "center": self.profile.center,
                "bbox": self.profile.bbox,
                "timezone": self.profile.timezone,
                "country": self.profile.country,
            },
            "conditions": self.conditions.to_dict(),
            "weather": self.weather.to_dict(),
            "agents": {
                "total": len(self.movement.agents),
                "sentinel_indices": self._sentinel_indices,
            },
            "roads": self.swarm._build_geojson(),
            "roadnet_fallback": self.roadnet.fallback,
            "speed": self.speed,
            "sim_clock_s": (self.clock0_s + self.sim_s) % 86400,
        }

    def state_json(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "running": self.running,
            "speed": self.speed,
            "region": self.profile.key,
            "sim_s": round(self.sim_s, 1),
            "sim_clock": _fmt_clock(self.clock0_s + self.sim_s),
            "weather": self.weather.to_dict(),
            "cognitive_events": self._cog_events,
            "engine_domains": sorted(self.engine_domains),
            **self._metrics_core(),
        }

    # ── lifecycle ──

    async def start(self) -> None:
        self.running = True
        self._task = asyncio.create_task(self._loop(), name=f"world-{self.session_id}")

    async def stop(self) -> None:
        self.running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._broadcast(None)
        SESSIONS.pop(self.session_id, None)

    async def _loop(self) -> None:
        try:
            await self._refresh_engines()
            while self.running:
                t0 = time.monotonic()
                await self.step()
                if time.time() - self.created_at > _MAX_WALL_S:
                    logger.info("world %s hit wall-clock cap; stopping", self.session_id)
                    break
                await asyncio.sleep(max(_TICK_REAL_S - (time.monotonic() - t0), 0.005))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("world %s loop crashed", self.session_id)
            self._broadcast({"type": "error", "message": "world loop crashed"})
        finally:
            self.running = False
            self._broadcast(None)
            SESSIONS.pop(self.session_id, None)

    # ── one tick (pure sim; broadcasts; event-gated cognition) ──

    async def step(self) -> None:
        self._tick_i += 1
        dt = _TICK_REAL_S * self.speed
        self.movement.tick(dt)
        self.sim_s += dt

        if self._tick_i % _BROADCAST_EVERY_TICKS == 0:
            self._seq += 1
            self._broadcast(pack_frame(self._seq, self.sim_s, self.movement.agents))
        if self._tick_i % _METRICS_EVERY_TICKS == 0:
            self._broadcast({"type": "metrics", **self._metrics_core(),
                             "sim_clock": _fmt_clock(self.clock0_s + self.sim_s)})

        if self.sim_s - self._last_cog_s >= _COGNITIVE_INTERVAL_SIM_S:
            self._last_cog_s = self.sim_s
            await self._cognitive_event()
        if self.sim_s - self._last_engine_s >= _ENGINE_INTERVAL_SIM_S:
            self._last_engine_s = self.sim_s
            await self._refresh_engines()

    def _metrics_core(self) -> Dict[str, Any]:
        agents = self.movement.agents
        en_route = [a for a in agents if a.state in ("moving", "congested", "queued")]
        moving = [a for a in en_route if a.speed_kmh > 0]
        slow = [a for a in en_route if a.state in ("congested", "queued")]
        return {
            "agents_total": len(agents),
            "en_route": len(en_route),
            "arrived": sum(1 for a in agents if a.state == "arrived"),
            "avg_speed_kmh": round(
                sum(a.speed_kmh for a in moving) / len(moving), 1
            ) if moving else 0.0,
            "congestion_pct": round(100 * len(slow) / len(en_route), 1) if en_route else 0.0,
        }

    # ── cognition (the ONLY place LLM calls can happen) ──

    async def _cognitive_event(self) -> None:
        self._cog_events += 1
        self._broadcast({"type": "phase", "phase": "cognition", "event": self._cog_events})

        # Feed live movement congestion into the hive's world model.
        congestion = self.movement.corridor_congestion()
        cap = {f"{e['u']}->{e['v']}": e["capacity"] for e in self.roadnet.corridors["edges"]}
        self.swarm._flow_map = {
            eid: ratio * cap.get(eid, 1800.0) for eid, ratio in congestion.items()
        }

        weights = {
            "congestion_memory_weight": self.swarm.config.congestion_memory_weight,
            "peer_influence_weight": self.swarm.config.peer_influence_weight,
        }
        try:
            await self.swarm._run_timestep_hive(
                step=self._cog_events - 1, config_weights=weights
            )
        except Exception:
            logger.warning("world %s hive timestep failed", self.session_id, exc_info=True)

        for i, sentinel in enumerate(self.swarm.sentinel_agents):
            if i >= len(self._sentinel_indices):
                break
            dec = getattr(sentinel, "last_decision", None) or {}
            self._broadcast(
                {
                    "type": "sentinel_thought",
                    "idx": self._sentinel_indices[i],
                    "segment": sentinel.segment_name,
                    "mood": dec.get("mood", "stable"),
                    "why": dec.get("why", ""),
                    "route": dec.get("route") or [],
                    "confidence": float(dec.get("confidence", 0.0) or 0.0),
                    "fallback": bool(dec.get("fallback", True)),
                }
            )

        if self._cog_events >= _REPORT_AFTER_EVENTS and not self._report_sent:
            self._report_sent = True
            await self._send_report()

    async def _refresh_engines(self) -> None:
        self._broadcast({"type": "phase", "phase": "engines"})
        try:
            from engines import get_registry

            nodes, edges = self.roadnet.to_engine_graph()
            data: Dict[str, Any] = {"nodes": nodes, "edges": edges, "agent_count": 200}
            if self.profile.country == "IN":
                try:
                    from agents.ncr_data_loader import get_ncr_summary
                    from data_integration.bridge import ncr_data_to_engine_input

                    data = {**ncr_data_to_engine_input(get_ncr_summary()), **data}
                except Exception:
                    pass
            m = self._metrics_core()
            data["transport_result"] = {
                "avg_speed_kmh": m["avg_speed_kmh"],
                "congestion_pct": m["congestion_pct"],
                "agents_simulated": m["agents_total"],
                "simulation_mode": "living_world",
            }
            # Explicit 7-engine list: the nested AgentSimulationEngine must NOT
            # run — this session's live movement/hive IS the agent simulation.
            raw = await get_registry().run_scenario(
                self.scenario,
                data,
                engines=[
                    "TransportEngine", "EnvironmentEngine", "InfrastructureEngine",
                    "EnergyEngine", "EconomicEngine", "PopulationEngine",
                    "LogisticsEngine",
                ],
            )
            domains: Dict[str, Any] = {}
            for name, r in raw.items():
                dom = r.domain.value if hasattr(r.domain, "value") else str(r.domain)
                domains[dom] = {
                    "metrics": getattr(r, "metrics", {}),
                    "impacts": getattr(r, "impacts", {}),
                    "confidence": getattr(r, "confidence", 0.0),
                    "recommendations": getattr(r, "recommendations", [])[:3],
                }
            # The living movement layer IS transport reality — report it as such.
            domains["transport"] = {
                "metrics": data["transport_result"],
                "impacts": {},
                "confidence": 0.8,
                "recommendations": [],
            }
            self.engine_domains = domains
            self._broadcast({"type": "engines", "domains": domains})
        except Exception:
            logger.warning("world %s engine refresh failed", self.session_id, exc_info=True)

    async def _send_report(self) -> None:
        hive = self.swarm.build_hive_state()
        m = self._metrics_core()
        summary = (
            f"{self.profile.display_name}: {m['agents_total']} agents simulated — "
            f"avg speed {m['avg_speed_kmh']} km/h, {m['congestion_pct']}% congested, "
            f"{m['arrived']} arrived. Weather: {self.weather.condition} "
            f"({self.weather.precip_mm_h} mm/h)."
        )
        narrative = ""
        if self.enable_llm:
            try:
                from reasoning import get_gateway

                narrative = await get_gateway().reason_text(
                    prompt=(
                        f"Scenario: '{self.prompt}' in {self.profile.display_name}. "
                        f"Live simulation: {summary} "
                        "Write a 3-sentence decision-grade brief for a policymaker."
                    ),
                    system="You are a senior urban-policy analyst. Concise, quantitative.",
                    prefer="gemini",
                )
            except Exception:
                narrative = ""
        self._broadcast(
            {
                "type": "report",
                "summary": narrative or summary,
                "metrics": m,
                "brains": hive["brains"],
                "engine_domains": sorted(self.engine_domains),
            }
        )


# ── factory ──


async def create_session(
    prompt: str,
    agent_count: int = 1500,
    sentinels: int = 14,
    speed: int = 60,
    enable_llm: bool = True,
    seed: int = 42,
    resolver: Optional[RegionResolver] = None,
    weather_provider: Optional[WeatherProvider] = None,
    roadnet_loader: Any = None,
) -> WorldSession:
    """Resolve → roads → weather → agents → hive → running session."""
    # Free-tier guard: evict the oldest session beyond the cap.
    while len(SESSIONS) >= MAX_SESSIONS:
        oldest = min(SESSIONS.values(), key=lambda s: s.created_at)
        logger.info("evicting world session %s (MAX_SESSIONS)", oldest.session_id)
        await oldest.stop()

    resolver = resolver or _get_resolver()
    profile, conditions = await resolver.resolve(prompt)

    loader = roadnet_loader or RoadNetwork.load
    roadnet = await loader(profile)

    wp = weather_provider or WeatherProvider()
    weather = wp.apply_override(await wp.fetch(profile), conditions)

    # Agent specs: sentinels first (stable frame indices), swarm sampled from
    # the region's real mode split across the 7 population segments.
    from shared.contracts.simulation_state import SEGMENT_LABELS

    rng = random.Random(seed)
    segments = list(SEGMENT_LABELS)
    modes = list(profile.mode_split)
    weights = [profile.mode_split[m] for m in modes]
    sentinels = max(1, min(int(sentinels), 70, agent_count))
    specs: List[Dict[str, Any]] = [
        {"mode": "car", "agent_class": 1, "segment": segments[i % len(segments)]}
        for i in range(sentinels)
    ] + [
        {
            "mode": rng.choices(modes, weights=weights)[0],
            "agent_class": 0,
            "segment": rng.choice(segments),
        }
        for _ in range(max(0, agent_count - sentinels))
    ]

    # Hive cognition on the small corridor graph (LLM vocabulary stays tiny).
    from data_integration.bridge import build_scenario_from_prompt
    from engines.agent_simulation.config import get_agent_sim_config
    from engines.agent_simulation.swarm import UrbanSwarm

    cnodes, cedges = roadnet.to_engine_graph()
    cfg = copy.deepcopy(get_agent_sim_config().swarm)
    cfg.commuter_count = min(agent_count, 2000)
    cfg.timesteps = _REPORT_AFTER_EVENTS + 1
    swarm = UrbanSwarm(
        nodes=cnodes, edges=cedges, config=cfg,
        live_context={"scenario_description": prompt},
    )
    swarm.enable_llm = enable_llm
    swarm.sentinel_count_per_segment = max(1, sentinels // 7)
    await swarm.initialize()

    scenario = build_scenario_from_prompt(prompt, city=profile.key)
    swarm.apply_interventions(
        [{"name": iv.name, "parameters": iv.parameters} for iv in scenario.interventions]
    )

    start_clock = _clock_datetime(conditions)
    movement = MovementSim(
        roadnet, profile, specs, seed=seed, start_clock=start_clock
    )
    movement.set_weather(weather)

    session = WorldSession(
        session_id=str(uuid.uuid4())[:8],
        prompt=prompt,
        profile=profile,
        conditions=conditions,
        roadnet=roadnet,
        weather=weather,
        swarm=swarm,
        scenario=scenario,
        movement=movement,
        speed=speed,
        enable_llm=enable_llm,
    )
    SESSIONS[session.session_id] = session
    await session.start()
    return session


def _now_clock_s() -> float:
    now = datetime.now()
    return now.hour * 3600 + now.minute * 60 + now.second


def _clock_datetime(conditions: ScenarioConditions) -> datetime:
    base = datetime.now()
    clock_s = _TIME_OF_DAY_CLOCK_S.get(conditions.time_of_day or "")
    if clock_s is None:
        return base
    return base.replace(
        hour=int(clock_s // 3600), minute=int((clock_s % 3600) // 60), second=0
    )


def _fmt_clock(clock_s: float) -> str:
    s = int(clock_s) % 86400
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"
