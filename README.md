# OVERHAUL

**AI Decision-Intelligence Platform for Urban Policy — Delhi NCR**

OVERHAUL answers "what if" policy questions about a city. You ask something like
*"What if we ban diesel trucks on Ring Road 7–10am?"* and the system runs a
**Sentinel-Swarm-Hive** agent simulation — LLM-reasoning agents behaving like real
commuters on a physics-accurate road graph, a collective "Hive" that distills their
emergent behavior into routing wisdom, and seven domain engines that quantify the
downstream impact — then returns a defensible policy brief plus a live tactical
visualization.

> **Source of truth for architecture & roadmap:** [`PATH.md`](PATH.md).
> **Run guide for the hive engine:** [`HIVE_ENGINE.md`](HIVE_ENGINE.md).

---

## Architecture (5 layers, top = user)

```
┌───────────────────────────────────────────────────────────────────────┐
│ L5  PRESENTATION   landing-react/  →  /hive command center (real data)  │
├───────────────────────────────────────────────────────────────────────┤
│ L4  ORCHESTRATION  agents/ldrago + app.py (FastAPI)                      │
│      Parser → Planner → Researcher → Reasoner → Critic → Synthesizer     │
├───────────────────────────────────────────────────────────────────────┤
│ L3  COGNITION      engines/agent_simulation/  — the Sentinel-Swarm-Hive  │
│      Sentinels (LLM) · Swarm (physics+inherit) · 7 Segment Brains (LLM)  │
├───────────────────────────────────────────────────────────────────────┤
│ L2  CAPABILITY     reasoning/ (4-model gateway) · memory/ (graph) ·      │
│      engines/ (7 domain engines) · data_integration/ (adapters)          │
├───────────────────────────────────────────────────────────────────────┤
│ L1  WORLD          road graph · NCR baselines · live AQI / traffic feeds │
└───────────────────────────────────────────────────────────────────────┘
```

**The `/simulate/hive` request flow:**
`prompt → build_scenario_from_prompt → UrbanSwarm (LLM cognition ON) → 7 engines
(registry) → ReportAgent + Gemini narrative → schema-valid SimulationState`.
Each hive timestep: sentinels reason (batched LLM) → brains distill `CollectiveTruth`
with real edge IDs → swarm inherits it (Dijkstra over hive-weighted edges) → physics
recompute → metrics. Everything routes through the **Reasoning Gateway** so ~50
sentinels survive free-tier rate limits.

---

## File structure

```
OVERHAUL/
├── app.py                      # FastAPI app — ALL HTTP routes (the monolith)
├── validation_store.py         # validation DB layer (SQLite / Supabase)
├── requirements.txt  .env.example
├── PATH.md  CONTEXT.md  HISTORY.md  HIVE_ENGINE.md  ARCHITECTURE.md  README.md
│
│   ── L2 CAPABILITY ───────────────────────────────────────────────────
├── reasoning/                  # the 4-model brain behind ONE gateway
│   ├── gateway.py              #   ReasoningGateway: batch·shard·cache·ratelimit·breaker
│   ├── providers.py            #   async wrappers over llm/chat.py (only LLM transport here)
│   ├── batching.py             #   coalesce K≤8 agents → 1 prompt + response splitter
│   ├── cache.py  circuit.py    #   TTL cache · token-bucket + circuit breaker + quota
│   ├── sharding.py  adapters.py#   agent→model hash · edge-ID vocab + strict coercion
│   └── __init__.py
├── memory/                     # swappable knowledge-graph backend
│   └── factory.py              #   get_kg_backend(GRAPH_BACKEND=in_memory|zep)
├── shared/contracts/           # the ONE API contract (kills field drift)
│   ├── simulation_state.py     #   Pydantic SimulationState (FastAPI response_model)
│   └── simulation_state.schema.json
│
├── engines/                    # domain simulation engines
│   ├── base.py registry.py     #   SimulationEngine ABC · two-phase registry + cache
│   ├── geospatial.py scenarios.py
│   ├── transport/ environment/ energy/ economic/
│   ├── infrastructure/ population/ logistics/
│   └── agent_simulation/       # ── L3 COGNITION: the Sentinel-Swarm-Hive ──
│       ├── swarm.py            #   UrbanSwarm — the Hive Loop orchestrator
│       ├── engine.py config.py #   AgentSimulationEngine (SimulationEngine iface)
│       ├── ldrago_parser.py graph_bridge.py llm_providers.py
│       ├── agents/             #   surgical_agent (sentinel) · swarm_agent · policy · report · types
│       └── brains/             #   backend (KG ABC + Local + Zep) · segment_brain · collective_truth
│
│   ── L4 ORCHESTRATION + L1/L2 SUPPORT ────────────────────────────────
├── agents/                     # LDRAGO cognitive pipeline + NCR data loaders
│   ├── ldrago_orchestrator.py ncr_data_loader.py gemini_agents.py
│   ├── master_brain.py unified_brain.py   (optional, flag-gated)
│   └── cognitive/              #   parser·planner·researcher·reasoner·critic·synthesizer
├── llm/                        # real 4-model LLM transport (OpenRouter + Google)
│   └── chat.py config.py routing.py usage_tracker.py geocoding.py
├── data_integration/           # L1 data adapters + NL→scenario bridge
│   ├── bridge.py schema.py
│   └── adapters/               #   csv · openaq · tomtom · opensky · osrm · openmeteo · nominatim · manager
├── knowledge/                  # RAG knowledge index (embeddings)
├── imagen_overlay/             # Imagen 3 map-overlay generation (/imagen routes)
├── new_traffic_god/            # custom local LLM (/traffic-god-llm) [large, gitignored]
│
│   ── DATA / ASSETS / TOOLING ─────────────────────────────────────────
├── data/   models/             # NCR datasets + trained baseline models (.pkl)
├── docs/                       # design specs
├── scripts/                    # ops / dev scripts
├── tests/                      # unit · integration · e2e (pytest)
├── storage/                    # runtime artifacts [gitignored]
│
│   ── FRONTEND ────────────────────────────────────────────────────────
├── landing-react/              # PRIMARY frontend (React 19 + Vite 7)
│   └── src/
│       ├── main.jsx            #   router: / /hive /demo /demo2 /flyover /features …
│       ├── HiveCommand.jsx     #   the /hive Sentinel-Swarm-Hive command center
│       ├── App.jsx Demo.jsx Demo2.jsx FlyoverSim.jsx Flyover3DViewer.jsx …
│       └── api/config.js       #   VITE_API_BASE resolver + apiFetchJson
└── ai-flyover-sim/             # /flyover 3D demo backend (:8001) + its components
```

> **Layering invariant:** higher layers import lower, never the reverse. Only
> `reasoning/providers.py` imports the concrete LLM transport; only `memory/` and
> `engines/agent_simulation/brains/` touch graph backends. The API has exactly one
> schema source: `shared/contracts/`.

---

## LLM stack (the 4-model brain)

One `ReasoningGateway` load-balances by role across two API accounts:

| Model | Account | Role | Volume |
|-------|---------|------|--------|
| Qwen-3 / Llama-3.2 | OpenRouter | fast / swarm escalation | high |
| Kimi / Gemma | OpenRouter | sentinel + distillation | medium |
| GPT-OSS-120B | OpenRouter | validation | low |
| Gemini 3.1 Pro | Google | orchestration / final brief | low |

Model IDs are env-overridable (`QWEN_MODEL`/`KIMI_MODEL`/`GPT_OSS_MODEL`/`GEMINI_MODEL`).
**Free-tier endpoints are heavily rate-limited and flap** — the gateway batches, paces,
caches, and circuit-breaks, degrading to physics so a run always completes. For a
reliable, fully-LLM demo, add a few dollars of OpenRouter credit. See `HIVE_ENGINE.md`.

## Seven simulation engines (`engines/`, two-phase)

| Phase | Engine | Models |
|-------|--------|--------|
| 1 | TransportEngine | BPR congestion, speed, travel time |
| 1 | InfrastructureEngine | capacity, ROI, timeline |
| 1 | EnvironmentEngine | PM2.5, AQI, emissions |
| 2 | EnergyEngine | EV grid load, renewables |
| 2 | EconomicEngine | BCR, NPV, jobs |
| 2 | PopulationEngine | 7 demographic segments, mode shift |
| 2 | LogisticsEngine | freight, last-mile |

## Data adapters (`data_integration/adapters/`)

Keyless: Open-Meteo AQI/Weather, OSRM routing, Nominatim geocoding, OpenAQ, local CSV/JSON.
Key-gated: TomTom flow (`TOMTOM_API_KEY`), OpenSky (`OPENSKY_*`). All share TTL caching +
stale-on-error fallback. `get_ncr_context()` aggregates the live + baseline picture.

---

## Quickstart

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set OPENROUTER_API_KEY + GEMINI_API_KEY
uvicorn app:app --reload --port 8000

# Frontend
cd landing-react && npm install && npm run dev   # → http://localhost:5173/hive
```

Try it: `POST /simulate/hive  {"prompt": "congestion pricing in central Delhi"}`
→ a schema-valid `SimulationState` (brains, sentinels, geojson, timesteps, engine
results, policy brief, gateway stats).

### The Living World (`/world`)

Open `http://localhost:5173/world` and type a place in plain English —
*"what if it rains during rush hour in New York?"* The camera flies to the
region, its real OSM street network loads (cached once, forever), and every
agent — sentinels **and** the whole swarm — drives it individually in real
time: income-strata personas pick modes, signals cycle, weather slows traffic
(and renders: GPU rain/snow, smog haze, day/night), the hive's LLM decisions
visibly re-route vehicles, and the 7 engines + a seasonal AQI model (winter
smog, Diwali fireworks) refresh live. Streaming protocol:
[`shared/contracts/world_frame.md`](shared/contracts/world_frame.md).
Works without a Mapbox token (community CARTO basemap) and fully offline
(NCR fallback graph + seasonal weather/AQI models).

### Key environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | **yes** | the sentinel + brain LLM |
| `GEMINI_API_KEY` | recommended | orchestration + policy narrative |
| `VITE_MAPBOX_TOKEN` | for the map | already set in `landing-react/.env` |
| `TOMTOM_API_KEY` | optional | live traffic calibration |
| `GRAPH_BACKEND` | optional | `in_memory` (default) / `zep` (needs `ZEP_API_KEY`) |
| `VALIDATION_ADMIN_TOKEN` | for moderation | validation endpoint auth |

Full list in [`.env.example`](.env.example).

## Tests

```bash
python3 -m pytest tests/test_reasoning_gateway.py -q   # offline proof the loop is LLM-driven
python3 -m pytest tests/ --ignore=tests/test_hive_e2e.py -q   # full regression
python3 -m pytest tests/test_hive_e2e.py -q            # live e2e (needs keys)
```

## Key HTTP endpoints (`app.py`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/world/start` | **start a Living World session** (any city, plain English) |
| WS | `/ws/world/{id}` | binary agent frames @5 Hz + JSON events |
| GET | `/world/{id}/stream` | SSE fallback (≤2 Hz decoded frames) |
| GET/POST | `/world/{id}/state` · `/speed` · `/stop` | session control: snapshot / pause–600× / end |
| POST | `/simulate/hive` | **the Sentinel-Swarm-Hive run** → `SimulationState` |
| GET | `/simulate/hive/stream` | same run as **SSE** — live per-phase progress, then `done` |
| POST | `/simulate/agent-based` | swarm sim, pure physics (no LLM) |
| POST | `/simulate` | engine-registry scenario run |
| POST | `/chat` · `/chat/v2` | LDRAGO conversational analysis |
| GET | `/health` · `/health/llm` | liveness + LLM key/model check |
| GET | `/usage/stats` · `/integrations/status` | telemetry |
| POST | `/traffic-god-llm` | custom local LLM (offline) |

## Deployment

Monolith on Render (`app.py` via uvicorn) — see [`render.yaml`](render.yaml).

## License

See [LICENSE](LICENSE).
