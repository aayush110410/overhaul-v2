# Cloud Context — Session Log

> **MAINTENANCE PROTOCOL (standing rule, set 2026-07-06).** This folder is the living memory of Claude Code cloud sessions on this repo:
> - **Every user prompt / discussion / decision** → dated entry in THIS file (`context.md`).
> - **Every code change** (add / modify / delete / integrate) → dated entry in `history.md`.
> - **Every mistake made or pointed out** → entry in `mistakes.md` (so it is never repeated).
> - **Every bug found** → entry in `bugs.md` (detected → root cause → fix → status), so it never resurfaces in new sessions.
> - Use absolute dates; newest entries at the top of each dated section. Updating these files is part of "done".
> - This complements root `CONTEXT.md`/`HISTORY.md` (project-wide docs); cloud-context tracks the *session-level* narrative.

---

## 2026-07-13 — Session: continue from memory-transfer file → loose-end cleanup

### User request
Uploaded the OVERHAUL memory-transfer MD (a snapshot ~2 months stale, ends at "Stage F in progress") and asked to see what's built and **continue**, using parallel sub-agents for a token-efficient full-codebase read.

### What was established
- The repo is far past the MD: Stage F done, hive made real (2026-07-01), Living World Phases 0–6 ALL SHIPPED (2026-07-08, draft PR #1, `main` untouched, both claude/* branches at the same Phase-6 commit).
- Two parallel Explore agents mapped backend + frontend; remaining gaps identified and fixed this session (see `history.md` 2026-07-13): `/world` engines panel unwired, FlyoverSim hardcoded `localhost:8001`, Llama→Kimi model-name drift, stale `/live/route` stub docstrings.

### Still open (user decisions / user-machine work)
1. **Merge PR #1** (draft, mergeable) — user's call.
2. Visual tuning pass of 3D vehicles on the user's real Mapbox token (needs user machine).
3. Optional glTF vehicle upgrade; OpenRouter credit (~$5–10) for 49-sentinel full-LLM runs.
4. PATH.md targets not yet built: `graphiti_kuzu` memory backend (§6), local LLM pool (§5.2), MAANG restructure (§7).

---

## 2026-07-06 — Living World: game-realistic 3D agent map + independent engines

### User request (summarized)
1. **Full-screen game-like 3D map UI**: 50 central (sentinel) agents + 1000+ hive (swarm) agents, each visibly moving individually in real time as the simulation runs.
2. **Location intelligence**: plain-English prompt naming any place ("…in New York") → map flies there → simulation runs on that region's real road network. Engine must understand lay-English prompts. Token-efficient.
3. **Independent, accurate engines**:
   - **Traffic**: replicate real regional traffic (Noida behaves like Noida, Gurgaon like Gurgaon, NYC like NYC — signals, road layout, flow).
   - **Pollution**: Noida/Delhi-NCR AQI focus — live + historical, day/month/year fluctuation, winter smog intelligence, Diwali fireworks spikes.
   - **Human behavior**: swarm agents act like real humans of the region — India income strata (<3L, 3–5L, 5–10L, 10–20L, 30L–1Cr, 1Cr+), cultural/caste diversity, individual lifestyles, economic edge cases.
   - **Economics & Policy**: regional laws, land ownership (govt/private), construction, budget rules incl. 2026 budgets, amendments.
   - **Weather**: real historical + real-time weather of the location, replicated in-sim AND visually on the map (cloud darkening, rain streaks). Heavy, graphically intense.
4. **Housekeeping**: this `cloud-context/` folder (context/history/mistakes/bugs), superpowers skill stored globally (committed at `.claude/skills/superpowers/SKILL.md`), production-grade quality, minimal token waste.

### Decisions (user-confirmed via questions)
1. **Phasing**: work split into phases, each sized to complete within one session limit (commit + push per phase).
2. **Visuals**: FULL GAME-REALISTIC — photorealistic Mapbox Standard style (3D buildings, dawn/day/dusk/night lightPreset), realistic vehicle models. `/hive` (dark tactical view) stays untouched; new view lives at `/world`.
3. **LLM budget**: free-tier defaults (~14 active sentinel thinkers, cache/batch heavy, physics fallback always completes; slider up to 49 once OpenRouter credit added).

### Honest-limits agreement
"Knows every law/policy" is delivered as curated per-region policy packs (`data/policy_packs/`) + on-demand Gemini Google-Search grounding (cached) — engines explicitly discount confidence when a pack is absent. Not literal omniscience.

### Approved plan (7 phases)
- **Phase 0**: this folder + superpowers skill. ✅ (this session)
- **Phase 1**: `world/` backend foundation — RegionResolver (+ 8 curated region JSONs), RoadNetwork (Overpass OSM, two-tier movement/corridor graph, disk cache, NCR fallback), WeatherProvider (open-meteo live/archive), MovementSim (pure-tick kinematics: BPR congestion, signal cycles, weather/mode factors, cached OD routes). TDD.
- **Phase 2**: live WorldSession (10 Hz tick loop, cognitive events → UrbanSwarm sentinel LLM rounds, engine refresh) + WebSocket binary agent-frame streaming (`/ws/world/{id}`, spec in `shared/contracts/world_frame.md`) + `/world/start|state|stop` endpoints + swarm.py injected-graph fixes.
- **Phase 3**: game-realistic Living Map UI at `/world` (Mapbox Standard, deck.gl SimpleMeshLayer vehicles w/ dead-reckoning between 5 Hz frames, fly-to camera, HUD w/ sim clock + speed controls, sentinel thought panels).
- **Phase 4**: weather & atmosphere visuals (native map.setRain/setSnow, cloud/fog darkening, AQI haze, day/night lightPreset tied to sim clock).
- **Phase 5**: engine depth (AQI seasonal model w/ Diwali 2024–2030 spike table + winter inversion + stubble window; income-strata PersonaSampler mapped to 7 segments; policy packs + EconomicEngine wiring; TomTom traffic calibration; hive→movement route feedback).
- **Phase 6**: production hardening (adaptive frame rate, reconnect chaos tests, token-free carto fallback, optional glTF vehicles, E2E, docs).

### Key architecture facts (for future sessions)
- Full plan snapshot lives in git history of this file's session; canonical integration facts: `UrbanSwarm.__init__(nodes=, edges=)` accepts injected graphs (swarm.py:117-127, edge schema `{u,v,dist_km,free_speed,capacity,lanes}`); swarm.py:253/:897/:936 need injected-graph fixes (NCR-frozen `valid_edge_ids`/`node_coords`); LLM cognition must use a ~30-node corridor graph, never raw OSM; `_VALID_CITIES` gate (app.py:2312) stays for legacy endpoints, `/world/*` bypasses it; mapbox-gl 3.17 has native setRain/setSnow (verified in dist); WS frame = 24 B header + 16 B/agent (spec Phase 2).

### Session progress log
- 2026-07-08: **Phase 6 complete — ALL PLANNED PHASES (0–6) SHIPPED.** Hardening: backpressure-adaptive frame rate, full offline E2E + subscriber-churn tests, tokenless MapLibre/CARTO basemap fallback (vehicles + weather work without any Mapbox token), README/PATH docs. Suite 254 passed / 2 skipped; UI verify green. PR #1 tracks the branch. Open follow-ups: visual tuning pass of 3D vehicles on the user's Mapbox token; optional glTF vehicle upgrade; OpenRouter credit for 49-sentinel full-LLM runs.
- 2026-07-08: **Phase 5 complete** — engine depth: seasonal AQI model (Diwali 2024–2030 table, stubble window, winter inversion, CPCB index, live-first), income-strata personas (multiplicative mode blend) feeding movement + sentinel prompts, policy packs (noida/delhi/new_york) grounding the EconomicEngine with honest-limits warnings, hive→movement re-routing (CollectiveTruth avoid-zones visibly redirect traffic), TomTom calibration hook. Suite 252 passed / 2 skipped. Remaining: Phase 6 hardening.
- 2026-07-08: **Phase 3 complete** — game-realistic Living Map at `/world`: Mapbox Standard + sim-clock lightPreset, procedural 3D vehicle meshes w/ dead-reckoned 60 fps motion, fly-to camera, glass HUD (clock/weather/speed controls/metrics), sentinel minds feed + panels, aurora idle hero. Runtime speed endpoint added (pause–600×). Browser-verified headless (0 app errors); 3D visual pass on a real Mapbox token pending (user machine). Suite 232 passed / 2 skipped.
- 2026-07-07: **Phase 2 complete** — live `WorldSession` tick loop + WS binary streaming (`/ws/world/{id}` + SSE fallback) + `POST /world/start` / state / stop endpoints (any-city, no `_VALID_CITIES` gate) + swarm injected-graph fixes (incl. 2 latent physics-Dijkstra bugs). Suite 231 passed / 2 skipped. End-to-end WS smoke verified (Noida rain rush-hour: 200 agents streaming + moving). User suggested React Bits (`@react-bits/Aurora-TS-TW` via shadcn) — noted for Phase 3 UI. Push still blocked on GitHub App write access; auto-retry armed.
- 2026-07-06: Explored repo (3 parallel agents: docs/graph, backend, frontend). Plan designed, user-approved. Phase 0 done (this folder + `.claude/skills/superpowers/SKILL.md`).
- 2026-07-06: **Phase 1 complete** — `world/` backend foundation (region resolver + 7 curated region profiles, OSM road networks w/ corridor graphs, weather provider, per-agent MovementSim). 38 new tests; full suite green (216 passed / 2 skipped). Survived a container rollback (see bugs.md) — all files restored from session context and re-committed. **Blocker**: git push denied (403) — the Claude GitHub App needs WRITE access to `aayush110410/overhaul-v2`; auto-retry armed. Next session: **Phase 2** (WorldSession tick loop + WebSocket binary streaming + `/world/*` endpoints + swarm.py injected-graph fixes).
