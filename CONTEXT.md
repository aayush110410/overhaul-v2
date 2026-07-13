# OVERHAUL Project Context

> 📋 **MAINTENANCE PROTOCOL (standing rule, set 2026-07-01).** Keep these docs living:
> - **Any code/structure change →** update `CONTEXT.md` (Current State, below) **and** `HISTORY.md` (a dated session entry).
> - **Any discussion/decision (even with no code change) →** add a **dated** note to `CONTEXT.md`.
> - Use absolute dates; newest entries supersede older ones. Doc updates are part of "done".

> ⚠️ **SOURCE OF TRUTH = `PATH.md`** (architecture/target). **Current built state = the section directly below + `README.md` + `HIVE_ENGINE.md`.** Older "✅ COMPLETE" claims further down describe scaffolding that was theater until 2026-07-01; where they conflict, the **Current State** section wins.

---

## ⭐ CURRENT STATE — 2026-07-13 (newest; supersedes older sections)

**Living World (Phases 0–6) is SHIPPED** (2026-07-08, draft PR #1; see `cloud-context/` for the full ledger): `/world` renders any-city, game-realistic 3D agent simulation — real OSM roads, live weather, seasonal AQI (Diwali table), income-strata personas, policy packs, binary WS streaming, tokenless basemap fallback. Suite ~254 tests.

**2026-07-13 loose-end cleanup** (branch `claude/codebase-review-agents-nts5xt`): `/world` now renders the streamed 7-domain engine results (IMPACT ENGINES panel); FlyoverSim honors `VITE_API_BASE`; all stale "Llama 3.3 70B" references corrected to the real analysis model Kimi k2.6 (code + `/ldrago/status` + docs); `/live/route` docstrings now describe the real OSRM-first behavior. Open: merge PR #1, Mapbox-token visual pass, optional glTF vehicles, `graphiti_kuzu` backend.

---

## CURRENT STATE — 2026-07-01 (superseded by above)

**The Sentinel-Swarm-Hive loop is REAL** (the 2026-06-03 audit theater is resolved):
- Sentinels reason via real LLM, Segment Brains LLM-distill `CollectiveTruth` with **real edge IDs**, the swarm **inherits** it (proven `swarm_inherited_routes > 0`), the hive loop is **parallel** (`asyncio.gather`), and the old `suggested_route` crash is fixed.
- **New L2 packages:** `reasoning/` (the ReasoningGateway — batch · shard · cache · rate-limit · circuit-break over the real `llm/chat.py`), `memory/` (swappable KG factory, `GRAPH_BACKEND`), `shared/contracts/` (`SimulationState` schema + Pydantic mirror).
- **New endpoint:** `POST /simulate/hive` → schema-valid `SimulationState` (NL parse → hive run → 7 engines → ReportAgent + Gemini brief). Fixed the `llama_chat_text` import bug (unblocked `/chat`) and a `PopulationEngine` crash.
- **Frontend:** `HiveCommand.jsx` routed at `/hive`, `Math.random()` removed, consumes `/simulate/hive` (real brains/sentinels/congestion + live telemetry).
- **Live progress (2026-07-01):** `GET /simulate/hive/stream` (SSE) emits per-phase events (`start · sentinels · distill · timestep · engines · report → done`); `HiveCommand.jsx` drives the surgical trace + a pulsing live status line off the stream via `EventSource`, with a safe blocking-POST fallback (no double-spend). Added `UrbanSwarm.on_event` callback; `/simulate/hive` refactored to share `_run_hive(req, on_event)`.
- **Surgical Command Center visuals (2026-07-01):** rebuilt `/hive` with **deck.gl** (`deck.gl@9`, `MapboxOverlay`): GPU **swarm particle-flow** (density ∝ real edge `flow`, speed ∝ real congestion — added `flow`/`capacity` to `_build_geojson`), **pulsing surgical probes** (mood-colored, click → reasoning-trace panel), **hive-mesh `ArcLayer`** (each sentinel → its segment-brain centroid), glass-morphism panels, SVG confidence **gauges** per brain, a **HIVE MOOD** nav readout, and a scanline. Brutalist lime brand preserved. deck.gl loads only on `/hive` (lazy route).
- **Browser-verified (2026-07-02):** loaded `/hive` via Playwright — shell/panels/gauges/HIVE-MOOD render exactly to spec, **0 console errors**, deck.gl overlay canvas active, SSE live progress advances (SENSING→REASONING→…). **Fix:** `dark-v11` loaded but Mapbox rendered light on this token, so added a `.mapboxgl-canvas { filter: brightness(0.32) saturate(0.55) contrast(1.12) }` darken (targets only the base map, not the deck overlay) → proper dark "void canvas". Swarm particle render itself not screenshot-confirmed (a live run stayed mid-flight for minutes under free-tier 429 throttling — the known constraint, not a viz bug; particle pipeline is unit-tested).
- **UI redesign v2 (2026-07-02):** user rejected the boxy two-sidebar dashboard ("feels cheap / wrong aesthetic / rethink layout"), chose a **cinematic + editorial** mix. Rebuilt `HiveCommand.jsx`/`.css` (`hc-*` classes): full-bleed dark map hero with vignette depth, thin quiet top bar, a **spotlight command bar** (bottom-center glass pill), a big Bebas display **idle hero** ("Simulate reality before you change it"), and on-result an **editorial briefing** panel (huge verdict headline, big-number metrics, LLM brief in Inter body, recommendations, a 7-mind hive strip). Restrained palette — near-black + lime used *sparingly*; Inter for prose, Bebas for display, Space Mono for labels. Idle state browser-verified (0 console errors, premium look); production build clean. Editorial-briefing state not yet screenshot-verified (needs a completed run).
- **Binding constraint:** OpenRouter **free-tier rate limits** (models flap / 429). The gateway degrades to physics so runs always complete; for reliable full-LLM demos **add ~$5–10 OpenRouter credit** and raise `sentinels` toward 49. Model IDs repinned to currently-live free models.
- **Tests:** 180 pass + 1 skipped. `tests/test_reasoning_gateway.py` is the deterministic offline proof the loop is LLM-driven.

**Project cleanup (2026-07-01):** removed `rendering-engine/` (357 MB), `archive/`, `traffic-god/` legacy CV (+ its endpoints/bridge), `services/` microservices (+ `docker-compose.yml` + orphaned test), `external/` (F1 predictor), root `demo2/`, `llm_client.py`/`privacy_guard.py`/`train_models.py`, 201 `(file).md` artifacts, and dead deps (camel-ai, sumolib, traci, opencv, ultralytics, norfair, stable-baselines3, gym, tensorboard, chromadb, gsap, maplibre-gl). **Kept** `/demo` `/demo2` `/flyover`, `new_traffic_god` (the separate `/traffic-god-llm`). Structure stays flat; see `README.md` for the documented tree.

---

> ⚠️ **SOURCE OF TRUTH = `PATH.md`.** Load `PATH.md` first. It defines the target architecture, the build path, and the locked decisions. When this file's older "✅ COMPLETE" claims conflict with `PATH.md` or the **Reality Check** (see bottom, Session 2026-06-03), **PATH.md and the Reality Check win.** Much of the "✅" below describes intent/scaffolding, not verified end-to-end behavior.

## Overview
OVERHAUL is an AI-Powered Decision Intelligence Platform for Urban Simulation, currently focusing on the Delhi NCR region. It aims to move from a deterministic "physics calculator" to an emergent reasoning world using the MiroFish framework.

## Core Architecture
- **LDRAGO v2**: A 6-agent cognitive pipeline (Parser $\rightarrow$ Planner $\rightarrow$ Researcher $\rightarrow$ Reasoner $\rightarrow$ Critic $\rightarrow$ Synthesizer).
- **Simulation Engines**: 7 domain engines (Transport, Environment, Infrastructure, Energy, Economic, Population, Logistics).
- **Data Layer**: Integrates local NCR CSVs with live APIs (OpenAQ, TomTom, OpenSky).
- **Frontend**: React + Three.js 3D globe visualization.

## MiroFish Integration Goal (The Vision)
The goal is to integrate the "MiroFish" pipeline to create "Thinking Agents":
1. **GraphBuilderService**: Input data $\rightarrow$ Zep Cloud Knowledge Graph.
2. **OasisProfileGenerator**: Zep Entities $\rightarrow$ Rich LLM Agent Personas.
3. **OASIS Simulation Loop**: Agents make LLM-powered decisions instead of following rules.
4. **ZepGraphMemoryUpdater**: Agent actions $\rightarrow$ Natural Language $\rightarrow$ Graph Updates.
5. **SimulationIPC**: Mid-sim agent interviews.
6. **ReportAgent**: Sim trace $\rightarrow$ LLM reasoned policy brief.

## 8-Layer Gap Analysis (Previous State)
- Layer 0: Dependencies (`camel-oasis`, `zep-cloud`) not installed. ✅ **FIXED** (Task 1.1)
- Layer 1: Zep Async Init bug (Zep never connects). ✅ **FIXED** (Task 1.4)
- Layer 2: Memory recall/persist not wired. ✅ **FIXED** (Phase 1 + Phase 2)
- Layer 3: Zep Graph API unused (only Memory API used). ✅ **FIXED** (Phase 1)
- Layer 4: OASIS loop never runs (always falls back to Python). ✅ **FIXED** (Phase 3 + Phase 4)
- Layer 5: Policy/Environment agents are phantoms (no factories). ✅ **FIXED** (Phase 5)
- Layer 6: IPC system not wired to API. ✅ **FIXED** (UrbanSwarm.interview_agent)
- Layer 7: ReportAgent not implemented. ✅ **FIXED** (Phase 5)

## Target Stages
- **Stage A**: Wire Zep + OASIS + PolicyAgent $\rightarrow$ Thinking agents in a static world. ✅ **COMPLETE**
- **Stage B**: Connect live data (OpenAQ, TomTom) $\rightarrow$ Living model of the city.
  - B.1: OpenAQ adapter. ✅ **COMPLETE** — `OpenAQA laqiAdapter` registered in `manager.py`, 9 tests passing.
  - B.2: Wire `get_ncr_context()` into `AgentSimulationEngine._run()`. ✅ **COMPLETE** — live PM2.5 + speed seeded into swarm, flow map calibrated from TomTom.
  - B.3: Environment engine accepts live PM2.5 override. ✅ **COMPLETE** — `EnvironmentEngine._run()` tracks `baseline_pm25` source, adds `pm25_data_source` metadata ("live_openaq" vs "csv_baseline"), 3 tests passing.
  - B.4: Integration test for live-data path. ✅ **COMPLETE** — 4 tests pass (mocked swarm).
  - B.5: OpenSky adapter design. ✅ **COMPLETE** — `OpenSkyNetworkAdapter` implemented with bounding box query, graceful no-key fallback, documented design spec in docstring, `AIR_TRAFFIC` domain added to `DataDomain` enum.

## Stage C: Validate & Harden ✅
- C.1: Sentinel node init bug. ✅ **COMPLETE** — Fixed `_create_sentinel_agents()` to pick valid nodes from `self._nodes.keys()` instead of `"default_node"`. 136 agent_simulation tests passing.
- C.2: Full swarm E2E. ✅ **COMPLETE** — `UrbanSwarm.run()` now completes end-to-end with valid results.
- C.3: LDRAGO v2 parser. ✅ **COMPLETE** — `LDRAGOParser` converts SwarmResult → ParsedSimulationBrief + markdown summary. 3 tests pass.

## Stage D: Downstream Engines ✅
- D.1: EconomicEngine wiring. ✅ — `transport_result` override for time_saved_min based on agent speed/congestion, `agent_sim_used` metadata flag. 2 tests pass.
- D.2: EnergyEngine wiring. ✅ — `transport_result.ev_share` overrides static 3% baseline, `ev_share_source` metric tag. 2 tests pass.
- D.3: Infrastructure + Population + Logistics wiring. ✅ — Infra uses `congestion_pct`, Pop uses `mode_shifts`, Logistics uses `total_vkt` from transport_result. 3 tests pass.

## Stage E: Frontend Integration ✅
- E.1: API endpoint for simulation results. ✅ COMPLETE
- E.2: Live AQI overlay data endpoint. ✅ COMPLETE

## Stage F: LLM Reasoner Tuning ✅
- F.1: LLM provider abstraction (OpenAI / Anthropic / Ollama). ✅ COMPLETE
- F.2: Prompt templates for route reasoning. ✅ COMPLETE
- F.3: End-to-end test with real LLM. ✅ COMPLETE (Added test, skips when keys missing)

## Integration Philosophy
"MiroFish" is not a separate service but a pipeline framework. The goal is to replace random.choice() persona generation with LLM-driven personas, replace rule-based routing with LLM-powered reasoning, and replace static outputs with an emergent behavior report synthesized by a ReportAgent.

## Sentinel-Swarm-Hive Architecture (Finalized Design)
See: `docs/superpowers/specs/2026-04-13-mirofish-integration-design.md`

### Key Concepts
- **SentinelAgents** ($\approx 50$): Full LLM-powered "stress testers" with individual Zep personas.
- **SwarmAgents** ($2000+$): Physics-only agents inheriting collective routing from Segment Brains.
- **SegmentBrain** (7 instances, one per population segment): Zep-backed collective memory with LLM distillation.
- **GlobalKnowledgeGraph**: The regulatory/legal/policy layer that PolicyAgent writes to.
- **Trigger-Based Reasoning**: LLM calls only on "Cognitive Events" (hotspots, policy changes, satisfaction drops).

### Backend Strategy
- **Phase 1**: Zep Cloud (paid) for TDD validation.
- **Phase 2**: Swap to Graphiti + Kuzu (local, zero-cost) via a `KnowledgeGraphBackend` abstract interface.

## LLM Brain Configuration (Updated 2026-05-28)
- **Primary Brain (Analysis)**: `moonshotai/kimi-k2.6:free`
- **Validation Brain**: `openai/gpt-oss-120b:free`
- **Orchestration Brain**: `gemini-3.1-pro-preview`
- **Fast Brain**: `qwen/qwen3-4b:free`

## UI Vision: "The Surgical Command Center"
The UI is transitioning from a standard dashboard to a **Palantir-inspired 3D tactical interface**.
- **Visual Style**: Modern-Industrial Tech. Dark void canvas, high-density data points, neon-cyan and deep-purple accents. No "AI cliches"; focused on precision and systemic flow.
- **Agent Visualization**:
    - **Swarm (2k)**: Fluid, systemic particle flow using a "data-smoke" effect.
    - **Sentinels (50)**: High-fidelity "Surgical Probes" — distinct, pulsing nodes that leave reasoning traces on the map.
    - **Hive Connectivity**: Subtle, geometric connections between Sentinels and their corresponding Segment Brains.
- **Tactical Overlays**: Glass-morphism panels for Hive Mood, Confidence Gauges, and the "Surgical Trace" (Policy $\rightarrow$ Reason $\rightarrow$ Distill $\ la-Execute).


## Current Focus (May 2026)
- **Objective**: Transition the frontend from a static "Results" view to a **Dynamic Hive Command Center**.
- **Key Deliverable**: `HiveCommand.jsx` — a high-fidelity tactical interface visualizing 50 Sentinels (as Probes) and 2000 Swarm Agents (as Particle Flow) on a 3D Mapbox canvas.
- **Core Requirements**:
    - Full functionality (no dead buttons/tabs).
    - Visual alignment with the "Brutalist Luxury" home page.
    - Real-time wiring to simulation results and segment brain states.

### Phase 2 — The Hive ✅
- `CollectiveTruth` dataclass (7 fields, validation, serialization)
- `SegmentBrain` class (contribute, distill, update stats, get truth/history)

### Phase 3 — The Agents ✅
- `SurgicalAgent` (LLM-powered Sentinel with physics fallback)
- `SwarmAgent` (physics-only with CollectiveTruth inheritance)
- `PolicyAgent` (autonomous regulatory monitor)
- `ReportAgent` (quantitative-first brief generator)

### Phase 4 — UrbanSwarm Hive Loop ✅
- `async initialize()` with `_init_backend()`, `_create_segment_brains()`, `_create_sentinel_agents()`
- 5-step Hive Loop per timestep: Policy Broadcast $\rightarrow$ Sentinel Reasoning $\rightarrow$ Hive Distillation $\rightarrow$ Swarm Execution $\rightarrow$ Swarm Feedback
- `await swarm.initialize()` in AgentSimulationEngine

## Key Files

### Agents Package (`engines/agent_simulation/agents/`)
| File | Purpose |
|------|---------|
| `types.py` | AgentProfile, AgentType, TransportMode, agent_choose_route, generate_commuter_agents, etc. |
| `surgical_agent.py` | LLM-powered Sentinel agent with parallel KG+brain queries |
| `swarm_agent.py` | Physics-only Swarm agent with CollectiveTruth inheritance |
| `policy_agent.py` | Autonomous regulatory monitor |
| `report_agent.py` | Simulation brief generator |
| `__init__.py` | Package exports |

### Brains Package (`engines/agent_simulation/brains/`)
| File | Purpose |
|------|---------|
| `backend.py` | KnowledgeGraphBackend ABC + LocalBackend + ZepBackend |
| `collective_truth.py` | CollectiveTruth dataclass |
| `segment_brain.py` | SegmentBrain Hive component |

### Orchestration
| File | Purpose |
|------|---------|
| `swarm.py` | UrbanSwarm: Hive Loop orchestrator |
| `engine.py` | AgentSimulationEngine (SimulationEngine interface) |

## Test Status
- **161 tests passing** across full test suite (was 130 $\rightarrow$ 146 $\rightarrow$ 149 $\rightarrow$ 161)
- All TDD critical tests passing:
  - `test_distillation_conflict` — Sentinels disagree, consensus forms
  - `test_swarm_inheritance` — avoid_zones propagate to routing
  - `test_async_convergence` — 50 agents resolve within 2s
- New: 9 OpenAQ adapter tests passing

---

# Session 2026-06-03 — Honest Audit, PATH.md, Reality Check & Decisions

> This section is the **current truth** and supersedes the optimistic "✅ COMPLETE" claims above where they conflict. Created `PATH.md` (the definitive architecture + build path). Updated global memory.

## 1. Honest Audit — Critical Flaws Found
A 3-agent parallel audit (architecture / implementation / frontend) found the system makes grand "AI-powered emergent reasoning" claims that the code does not yet back. Top findings:

| Severity | Flaw |
|----------|------|
| CRITICAL | `llm_client.py` (root) is a **100% hardcoded mock** — returns `[LLM MOCK RESPONSE]`. (NOTE: real LLM calls DO exist separately in `llm/chat.py` — see §3.) |
| CRITICAL | `HiveCommand.jsx` uses **`Math.random()`** to fake ~50 sentinel positions (lines ~177–190) when sim data is empty — which it always is. |
| CRITICAL | **API contract mismatch**: frontend expects `brains[]`, `simulation_results.nodes[]`, `geojson`; `/chat` returns `response`, `engine_results`, `ncr_data`. No real data→sim→UI flow. |
| CRITICAL | **Zep migration is vapor** — `ZepBackend` exists, no `GraphitiBackend`. Single-vendor, paid, no exit yet. |
| HIGH | **Sentinels are decorative** — on LLM timeout they silently fall back to Dijkstra; routing is still physics. LLM mostly annotates, doesn't decide. |
| HIGH | `FallbackProvider` (`agent_simulation/llm_providers.py`) returns **hardcoded keyword heuristics**, not reasoning. |
| HIGH | "177 tests passing" are **mostly mocks** — zero real E2E hive-loop-with-real-LLM test. |
| MEDIUM | Microservices in docs, **monolith in code** (`app.py`); `agents/` duplicates `agent_simulation/`; `camel-ai` dead; `archive/` + F1-predictor dirs unrelated. |

Full remediation = the 6-phase plan in **PATH.md §9**.

## 2. PATH.md Created (the source of truth)
Resolves the audit into a buildable target. Key contents: locked decisions, the honest cognitive loop, 4-model reasoning layer, swappable memory, MAANG-grade file structure, literal removal list, 6-phase migration, definition-of-done, invariants.

## 3. Corrected Tech-Stack Facts (verified by import scan)
- **AI/agent framework: NONE.** The Sentinel-Swarm-Hive + LDRAGO v2 system is **custom-built Python**. No LangChain / LlamaIndex / CrewAI / AutoGen / DSPy.
- **LLM access is REAL** in `llm/chat.py` — direct `httpx` REST to OpenRouter (Kimi k2.6, GPT-OSS-120B, Qwen-3) + Google AI (Gemini 3.1 Pro), with a real fallback chain + ensemble. **This is the keeper.** `llm_client.py` (the mock) must be deleted.
- **`camel-ai`** appears only in `tests/.../test_dependencies.py` — dead in production. **`camel-oasis`** already removed. **MiroFish** is a *concept*, not an installed package.
- **ML stack:** **PyTorch is the primary ML framework.** Supporting: `ultralytics` (YOLO), `stable-baselines3` (RL), `scikit-learn`, `xgboost`, `sentence-transformers`. Plus `numpy`/`pandas`, `FastAPI`, `zep-cloud`, `supabase`.
- **Domain classification (for applications):** primary = **Generative AI**; secondary = multi-agent systems (RL is marginal, CV not in scope).

## 4. Datasets & Metrics (verified)
**Datasets:** `noida_aqi_2024.xlsx` (13 KB), `noida_tomtom_daily.csv` (18 KB), `historical_metrics.json` (~600 B), `ncr_baselines.json` (1.6 KB) + live OpenAQ/TomTom/OpenSky feeds. Totals: `data/` ≈1.5 MB, `models/` ≈23 MB.

**Key metrics achieved:**
| Model | Metric | Value |
|-------|--------|-------|
| AQI predictor (RandomForest) | R² | 0.77 (MAE 25.94) |
| Traffic speed (GradientBoosting) | R² | 0.74 (MAE 4.15 km/h) |
| Congestion classifier (GB) | Accuracy | 79.7% |

## 5. Locked Decisions (from PATH.md §1)
- **Dual target:** investor-grade demo **AND** production-ready. **Real results only — no mocks in shipped paths.**
- **LLMs are the brain;** physics handles the deterministic world.
- **"Every agent feels human"** delivered via **trigger-based reasoning + Segment-Brain inheritance**, NOT per-tick LLM calls for all 2000 agents.
- **Keep 4 distinct free-tier models, load-balanced by role**, behind one provider interface.
- **Swappable graph backend** (`in_memory | graphiti_kuzu | zep`) via config — Zep optional.
- **MAANG-grade structure**, contract-first API (`shared/contracts`).

## 6. Reasoning Gateway Decision (50-sentinel scaling)
Resolved how ~50 sentinels + swarm reason without overwhelming ~4 LLM endpoints. **Clarified misconception:** Claude-Code-style subagents do NOT each get their own model — they are parallel *requests* to one model. So "50 agents" = "50 requests to a small endpoint pool," and the real limits are **rate limits / latency / quota**, not model "overload." Solution = a **Reasoning Gateway** (PATH.md §5, to be elaborated):
- Concurrency pool (asyncio semaphore) · provider sharding (~12 sentinels/model) · **request batching** (N agents per prompt) · caching · trigger-based (not every tick) · tiered routing (Qwen=high-volume).
- **Optional hybrid for true per-agent brains:** local model pool (**Ollama / vLLM continuous batching**) for high-volume agent ticks; reserve the 4 cloud models for distillation/synthesis/validation. Removes rate limits + per-call cost; best for demo safety + free-tier production. ✅ **Specced into PATH.md §5.1 + §5.2** (gateway mechanisms, `ReasoningGateway` interface, routing policy, local/cloud hybrid, config knobs, DoD).

## 7. Global Memory Updated
- `project_overhaul.md` — locked decisions + PATH.md as source of truth.
- `feedback_parallel_agents_default.md` — parallel sub-agents are the default for all multi-file reads/research (token efficiency).

## 8. Immediate Next Actions (PATH.md §9 order)
1. **Phase 0 cleanup:** delete `llm_client.py`, `train_models.py`, `privacy_guard.py`, `archive/`, F1 dirs, duplicate `ai-flyover-sim/frontend/`; strip dead deps; split `app.py`.
2. **Phase 1:** author `shared/contracts/simulation_state.schema.json` (kills the API mismatch).
3. **Phase 2:** promote `llm/chat.py` into `reasoning/` behind the gateway (router + cache + quota).
4. Then Phases 3–6 (swappable memory → honest cognition → real viz → E2E).
