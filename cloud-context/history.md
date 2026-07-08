# Cloud Context — Code Change History

> Every code change made in cloud sessions: what was added / modified / deleted / integrated, dated, newest first within each session. Companion to root `HISTORY.md` (project-wide); this file is the fine-grained session ledger.

---

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
