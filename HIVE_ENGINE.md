# OVERHAUL — Sentinel-Swarm-Hive Engine (run guide)

This documents the real cognitive engine wired up in this session: a natural-language
policy question → an LLM-reasoning agent simulation → a 7-engine impact analysis →
a schema-valid policy brief, rendered live in the `/hive` command center.

## What is real now (was theater before)

| Component | Before | Now |
|-----------|--------|-----|
| 50 sentinels | `llm_provider=None` → all ran Dijkstra | **Real LLM reasoning** through the gateway (batched), physics only on throttle |
| 7 segment brains | returned a canned constant string | **Real LLM distillation** into `CollectiveTruth` with **real edge IDs** |
| Hive loop | sequential `for`; crashed on `suggested_route` | **parallel** `asyncio.gather`, crash fixed, swarm **inherits** the distilled truth |
| Reasoning | heuristic keyword stub, no bridge to `llm/chat.py` | **`reasoning/` gateway**: batch · shard · cache · rate-limit · circuit-break over the real 4-model brain |
| API | no `/simulate/hive`, no schema | **`POST /simulate/hive`** → validated **`SimulationState`** contract (`shared/contracts/`) |
| Frontend | `Math.random()` sentinels, `/chat`, fake pipeline | **`/hive`** renders real sentinels/brains/congestion + live telemetry; zero `Math.random()` |

New packages: `reasoning/` (the gateway), `memory/` (swappable KG factory), `shared/contracts/`
(the `SimulationState` schema + Pydantic mirror).

## API keys (.env at repo root — already gitignored)

| Key | Required | Purpose |
|-----|----------|---------|
| `OPENROUTER_API_KEY` | **yes** | Sentinel reasoning + brain distillation (the brain) |
| `GEMINI_API_KEY` | recommended | Policy-brief narrative + opportunistic distillation |
| `VITE_MAPBOX_TOKEN` | for the map | already set in `landing-react/.env` |
| `TOMTOM_API_KEY` | optional | live traffic-speed calibration (falls back to CSV) |
| `GRAPH_BACKEND` | optional | `in_memory` (default) · `zep` (needs `ZEP_API_KEY`) |

> **Free-tier reality (important).** OpenRouter's *free* model endpoints are heavily
> rate-limited and flap in/out of availability ("temporarily rate-limited upstream",
> 429). The gateway is built to survive this — it batches, paces, circuit-breaks, and
> **degrades gracefully to physics so a run always completes** — but at 49 sentinels the
> free tier often can't deliver real LLM reasoning every run. **For a reliable, fully-LLM
> demo, add ~$5–10 of OpenRouter credit** (their own 429 message says: *"add your own key
> to accumulate your rate limits"*). With credit, raise `sentinels` toward 49 and all
> models (Kimi/Qwen/etc.) become available. The configured free model IDs are pinned to
> ones that were live on 2026-06-30; override via `QWEN_MODEL`/`KIMI_MODEL`/`GPT_OSS_MODEL`/`GEMINI_MODEL`.

## Run it

```bash
# Backend (repo root). OVERHAUL_HIVE_LLM is informational; the /hive endpoint always uses the gateway.
uvicorn app:app --reload --port 8000
#   GET  /health/llm        → confirms keys + that model IDs resolve
#   POST /simulate/hive     → {"prompt": "ban diesel trucks on Ring Road 7-10am"}

# Frontend
cd landing-react && npm install && npm run dev
#   open http://localhost:5173/hive   (set VITE_API_BASE if backend isn't on :8000)
```

`POST /simulate/hive` body (all optional except `prompt`):
```json
{ "prompt": "congestion pricing in central Delhi", "city": "delhi",
  "agent_count": 2000, "sentinels": 14, "timesteps": 4 }
```
`sentinels` defaults to 14 (2/segment) — free-tier survivable. Raise toward 49 with credit.

## Response: `SimulationState` (schema in `shared/contracts/simulation_state.schema.json`)
`brains[]` (7, per segment: mood/confidence/preferred_routes/avoid_zones) · `sentinels[]`
(coords/mood/confidence/trace) · `geojson` (congestion-colored edges) · `timesteps[]`
(per-step discoveries/distillations/inherited/fallbacks) · `engine_results.domains{}` ·
`report{verdict,summary,recommendations}` · `stats` (gateway: per-provider calls, cache,
circuit state) · `manifest`.

## Verify

```bash
# Deterministic proof the cognition is genuinely LLM-driven (offline, no network):
python3 -m pytest tests/test_reasoning_gateway.py -q
# Full regression:
python3 -m pytest tests/ --ignore=tests/test_hive_e2e.py -q
# Live end-to-end (needs keys; tolerant of throttling):
python3 -m pytest tests/test_hive_e2e.py -q
```

In a live run, watch `stats.per_provider` (which models answered vs. circuit-open) and
`timesteps[].sentinel_fallbacks` (low = LLM drove routing; high = free tier throttled →
add credit). `swarm_inherited_routes > 0` proves the distilled truth actually re-weighted
the 2000-agent swarm.
