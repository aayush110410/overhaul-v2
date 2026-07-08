# Cloud Context — Code Change History

> Every code change made in cloud sessions: what was added / modified / deleted / integrated, dated, newest first within each session. Companion to root `HISTORY.md` (project-wide); this file is the fine-grained session ledger.

---

## 2026-07-07 — Session: Living World Phase 2 (live sessions + streaming)

### Phase 2 — complete; suite 231 passed / 2 skipped
- **Modified** `engines/agent_simulation/swarm.py` — injected-graph fixes: `_valid_edges` now derives from `self.edges` in `__init__` (identical 28-edge set on the default graph); added `_node_coords()` (reads `self.nodes`, falls back to NCR set) used by `build_hive_state`/`_build_geojson`; physics sentinel + swarm-agent call sites now pass `nodes`/`edges` through `state`.
- **Fixed 2 more latent NCR-hardcoding bugs found by tests**: `agents/surgical_agent.py _dijkstra_physics_fallback` and `agents/swarm_agent.py _dijkstra_with_hive_weights` both routed on `_DEFAULT_NODES/_DEFAULT_EDGES` regardless of the swarm's graph AND crashed (KeyError) on unreachable destinations. Both now accept `nodes`/`edges` params (NCR default = back-compat) and degrade cleanly when unreachable (one-way dead ends are normal on real OSM graphs).
- **Added** `world/stream.py` — binary frame codec (`pack_frame`/`unpack_frame`, 24 B header + 16 B/agent, spec in `shared/contracts/world_frame.md`) + `WS /ws/world/{id}` + SSE fallback `GET /world/{id}/stream` (frames ≤2 Hz decoded server-side), 20 s keepalive pings.
- **Added** `world/session.py` — `WorldSession`: 10 Hz tick loop (60× sim-time default), 5 Hz binary frame broadcast, 1 Hz metrics, cognitive events every 30 sim-min (live corridor congestion → `swarm._flow_map` → ONE batched hive timestep; sentinel_thought messages per event), 7-engine refresh hourly sim-time (explicit engine list — the nested AgentSimulationEngine must not run), report after 3 events (+1 optional Gemini narrative when LLM on), MAX_SESSIONS=3 eviction, 15-min wall-clock cap, priority broadcast (JSON events evict stale frames on backpressure — frames are droppable, events are not). `create_session()` factory: resolver → roadnet → weather+override → mode-split-sampled agent specs (sentinels = frame indices 0..N-1) → UrbanSwarm on the corridor graph.
- **Added** `app.py` endpoints — `POST /world/start` (no `_VALID_CITIES` gate; 503 on `RoadNetworkUnavailable`), `GET /world/{id}/state`, `POST /world/{id}/stop`; `world_stream_router` included after imagen router.
- **Added** tests: `tests/world/test_frame_codec.py` (5), `tests/world/test_session.py` (6), `tests/engines/agent_simulation/test_injected_graph.py` (4).
- **Verified end-to-end**: uvicorn + WS smoke — prompt "what if it rains during rush hour in noida" → region noida, rain 8 mm/h override, sim clock 08:30, 200 agents streaming at 5 Hz, 87 moving (staggered rush-hour departures), clean stop.
- **Noted for Phase 3 (user request)**: consider React Bits components (`npx shadcn@latest add @react-bits/Aurora-TS-TW`) for UI polish, e.g. the Aurora background on idle/landing states of `/world`.

## 2026-07-06 — Session: Living World (Phase 0 + Phase 1)

### Phase 0
- **Added** `cloud-context/` — `context.md`, `history.md`, `mistakes.md`, `bugs.md` (this folder; standing maintenance protocol).
- **Added** `.claude/skills/superpowers/SKILL.md` — the full superpowers workflow skill (3,148 lines, from user upload) committed so it loads in every future session on this repo.

### Phase 1 — World backend foundation (complete; suite 216 passed / 2 skipped)
- **Added** `world/` package (`__init__.py`):
  - `world/region.py` — `RegionResolver` (prompt → `RegionProfile` + `ScenarioConditions`): gazetteer → capitalized/lowercase place-candidate regex → Nominatim (`llm.geocoding.geocode`) → injected LLM last resort → NCR default. Generates + persists profiles for unknown places under `data/regions/generated/` (Indian places inherit NCR priors). `parse_conditions()` extracts rain/rush-hour/diwali/winter etc.
  - `world/roadnet.py` — `RoadNetwork`: async Overpass fetch (mirror fallback), two-tier graph (movement graph w/ true street geometry + ≤30-node named corridor graph for LLM/engines), disk cache `data/roadnets/{key}.json` (one fetch per region ever), BPR+Dijkstra routing w/ congestion weights, `sample_od`, `to_engine_graph()` (UrbanSwarm/TransportEngine schema), NCR default-graph fallback when Overpass is unreachable, `RoadNetworkUnavailable` otherwise.
  - `world/weather.py` — `WeatherProvider`/`WeatherState`: open-meteo forecast (current/hourly, `timezone=auto`, cloud_cover+visibility) + archive API for past dates; prompt overrides (`apply_override`); `speed_factor()` (1.0 dry → 0.55 floor); degrades to neutral default on API failure.
  - `world/movement.py` — `MovementSim`/`MovingAgent`: per-agent kinematics on real geometry — BPR congestion from live edge occupancy, deterministic signal cycles (`signal_is_red`, crc32 phase offsets), mode factors (car/2W/auto/bus w/ 25s dwell stops/walk 4.7 km/h), weather factor, rush-hour departure staggering, cached route pool (~120 OD Dijkstras at init, never per-tick), `edge_occupancy()`, `corridor_congestion()` (hive feed).
- **Added** `data/regions/` — 7 curated profiles (noida, delhi, gurugram, ghaziabad, faridabad, ncr, new_york) + `_generic_template.json`: center/bbox/timezone, rush hours, driving style, signal timing, 6-band income distribution, mode split, AQI baseline (winter/monsoon multipliers), cultural calendar (Diwali 2026-11-08 spikes), gazetteer, policy_pack ref.
- **Added** `tests/world/` — 38 tests: `test_region_resolver.py` (10), `test_roadnet.py` (13, w/ `fixtures/overpass_sample.json`), `test_weather.py` (5), `test_movement.py` (10).
- **Deleted** `tests/engines/agent_simulation/test_dependencies.py` — stale module-level `import camel` broke ALL collection in fresh environments; camel-ai was deliberately removed 2026-07-01 and Zep is optional per PATH.md.
- **Note**: prefetching real roadnet caches was attempted; the cloud sandbox egress proxy 403-blocks Overpass/Nominatim/open-meteo, so caches will self-build on first run in the user's environment (NCR fallback keeps this sandbox demo-able).
- **Note**: a container rollback mid-session wiped the first Phase-1 commit (`7611c2169`); all files were restored from session context and re-committed. A git bundle backup of the original commit was delivered to the user in-chat.
