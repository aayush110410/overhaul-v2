# Cloud Context — Code Change History

> Every code change made in cloud sessions: what was added / modified / deleted / integrated, dated, newest first within each session. Companion to root `HISTORY.md` (project-wide); this file is the fine-grained session ledger.

---

## 2026-07-08 — Session: Living World Phase 4 (visible weather + atmosphere)

### Push unblocked + PR opened
- **Push succeeded** after user granted the GitHub App write access — branch `claude/ultraplan-agent-map-ui-md9ucq` live on origin. **Draft PR #1** opened: https://github.com/aayush110410/overhaul-v2/pull/1 (no CI configured on repo; PR watch check-in armed hourly).
- Note: local commits remain unsigned — the container's signing key is a 0-byte stub (platform limitation, logged); identity is correct (`Claude <noreply@anthropic.com>`). Squash-merge via GitHub UI yields a verified merge commit.

### Phase 4 — complete
- **Added** `landing-react/src/world/weatherFx.js` — `applyWeatherToMap` (native `map.setRain`/`setSnow` when available: density/intensity/vignette ∝ precip, direction tilted by wind; fog densification + horizon blend ∝ cloud cover/visibility), `rainBucket`, `hazeOpacity` (annual PM2.5 baseline → 0–0.38 smog tint).
- **Modified** `WorldCommand.jsx/.css` — weather effect wiring on every weather message; **CSS rain fallback overlay** (animated dual-layer streaks, light/heavy) when native precip unsupported (also = tokenless sandbox path); **smog haze overlay** (Noida-brown radial multiply blend, night variant) from `region.aqi_baseline`; day/night state now drives vehicle materials.
- **Modified** `agentLayers.js` — night mode: brighter ambient material + **headlight glow layer** (warm dots offset 2.4 m along bearing for motorized modes).
- **Modified** `world/session.py` — hello `region.aqi_baseline` (UI haze until Phase-5 live AQI streaming).
- Physics/visuals agreement holds by construction: the same WeatherState drives `speed_factor` and the visuals.

## 2026-07-08 — Session: Living World Phase 3 (game-realistic map UI)

### Phase 3 — complete; browser-verified (0 app console errors)
- **Added** `landing-react/src/world/frameCodec.js` — DataView decoder mirroring `world/stream.py` (magic check, 16 B/agent).
- **Added** `landing-react/src/world/useWorldSocket.js` — session hook: `POST /world/start` → WS binary+JSON dispatch, exponential-backoff reconnect (3 tries) → EventSource SSE fallback, mutable `agentsRef` + **dead-reckoning** (`deadReckon(dt)` advances displayed positions by speed×bearing×session-speed between 5 Hz frames → smooth 60 fps), speed control (`POST /world/{id}/speed`), thought ring buffer, stop/cleanup.
- **Added** `landing-react/src/world/agentLayers.js` — procedural low-poly meshes (car/two-wheeler/auto/bus/pedestrian/freight + sentinel beacon; +X-forward boxes, real-meter sizes), realistic per-mode paint palettes w/ brake-red queued tint, one `SimpleMeshLayer` per mode, pickable sentinel beacons (mood-colored) + pulsing halo.
- **Added** `landing-react/src/WorldCommand.jsx` + `.css`, route `/world` in `main.jsx` (`/hive` untouched) — **Mapbox Standard** photoreal style w/ `lightPreset` (dawn/day/dusk/night) driven by the sim clock; cinematic `flyTo` on region resolve; idle hero w/ plain-CSS aurora backdrop (react-bits Aurora concept — repo has no tailwind, so no TS-TW drop-in); glass game-HUD: region+weather+clock chips, speed controls (⏸/1×/4×/10×), live metrics strip, sentinel-minds feed → thought panel, policy-brief panel; graceful no-token fallback.
- **Added** backend runtime speed control: `WorldSession.set_speed` (0=pause, ≤600×) + `POST /world/{id}/speed` + test. Suite: 232 passed / 2 skipped.
- **Fixed env**: repo `node_modules` were macOS-installed — added Linux natives (`@rollup/rollup-linux-x64-gnu`, `@esbuild/linux-x64`, `--no-save`).
- **Verified** (Playwright, headless, no Mapbox token in sandbox): idle hero → prompt → "Noida, Uttar Pradesh · fallback roads", weather chip "rain · 25°C · 8 mm/h", metrics ticking (1500 on the move, 28 km/h, 94.1% congested), clock 08:31→08:34, sentinel thought "#13 high income · stable" + panel, 0 app console errors (only sandbox-blocked gtag/Google-Fonts externals). `npm run build` clean. Screenshots delivered to user. **Visual check of the 3D vehicles on a real token still pending — do on user's machine (Phase 4 verification).** Kept `landing-react/verify_world_ui.mjs` as the repeatable UI check.

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
