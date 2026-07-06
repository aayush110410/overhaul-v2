# PATH.md — OVERHAUL Definitive Architecture & Build Path

> **This is the source of truth.** Load this file first in any session. It tells you what OVERHAUL must become, how it works inside-out, what to delete, and the exact order to build it. `CONTEXT.md` = current snapshot, `HISTORY.md` = chronological log. When they disagree with PATH.md, **PATH.md wins** — update the others to match.

---

## 0. START HERE (cold-session checklist)

If you just loaded this file in a fresh session, do this before touching code:

1. Read this whole file once. It is self-contained.
2. The **locked decisions** in §1 are non-negotiable unless the user changes them.
3. The **target architecture** (§3–§6) is the destination. The **migration plan** (§9) is the order.
4. Always use **parallel sub-agents** for any multi-file read or research (global default — token efficiency).
5. Before deleting anything in §8, confirm it still matches reality (the tree may have moved on).
6. Real results only. No `Math.random()`, no stub responses, no mocked "AI" in shipped paths.

---

## 1. LOCKED DECISIONS (the contract)

| # | Decision | Rule |
|---|----------|------|
| D1 | **Dual target** | Investor-grade jaw-dropping demo **AND** production-ready for real users. Both, not either. |
| D2 | **Real results** | Every number shown traces to a real computation or real data. No fabricated/mock outputs in shipped paths. |
| D3 | **LLMs are the brain** | LLMs do the reasoning, calculation, and decision-making that makes agents feel human. Physics handles the deterministic world we code (movement, capacity, conservation laws). |
| D4 | **Feasible humanity** | "Every agent feels human" is delivered via **trigger-based reasoning + Segment-Brain inheritance** (§4), NOT 2000 LLM calls per tick — that is impossible on free tiers and not real-time. |
| D5 | **4 distinct models, load-balanced** | Keep Kimi k2.6 / GPT-OSS-120B / Gemini 3.1 Pro / Qwen-3. Route by role to spread load across each free tier's context + usage caps. Behind one provider interface. |
| D6 | **Swappable graph backend** | One `KnowledgeGraphBackend` interface. Zep is paid and OPTIONAL. Free alternatives (in-memory, Graphiti+Kuzu) drop in with **zero callsite changes** via config. |
| D7 | **MAANG-grade structure** | Production file naming + layout (§7). Contract-first API. One source of truth for schemas. |

---

## 2. WHAT OVERHAUL IS (one paragraph)

OVERHAUL is an AI decision-intelligence platform for urban policy in Delhi NCR. A user asks a "what if" question (e.g. *"What if we ban diesel trucks on Ring Road 7–10am?"*). The system runs a **Sentinel-Swarm-Hive** agent simulation where LLM-reasoning agents behave like real humans navigating a physics-accurate city, a collective "Hive" distills their emergent behavior into policy wisdom, seven domain engines (transport, environment, energy, economic, infrastructure, population, logistics) quantify the downstream impact, and the system returns a defensible policy brief plus a live tactical visualization of the simulated city.

---

## 3. ARCHITECTURE OVERVIEW (inside-out)

Five layers, top (user) to bottom (world):

```
┌─────────────────────────────────────────────────────────────┐
│  L5  PRESENTATION   React command center (real SimulationState)│
├─────────────────────────────────────────────────────────────┤
│  L4  ORCHESTRATION  LDRAGO v2 pipeline + FastAPI contract      │
│       Parser → Planner → Researcher → Reasoner → Critic → Synth│
├─────────────────────────────────────────────────────────────┤
│  L3  COGNITION      Sentinel-Swarm-Hive loop  (the brain)      │
│       Sentinels (LLM) · Swarm (physics+triggers) · SegmentBrains│
├─────────────────────────────────────────────────────────────┤
│  L2  CAPABILITY     Reasoning(4-model router) · Memory(graph)  │
│       7 Domain Engines · Data adapters (CSV + live APIs)        │
├─────────────────────────────────────────────────────────────┤
│  L1  WORLD          Road graph · baselines · live AQI/traffic  │
│       Deterministic physics we code                            │
└─────────────────────────────────────────────────────────────┘
```

**Dependency rule (enforced):** higher layers depend on lower; lower layers NEVER import higher. L3 cognition depends on L2 capability (reasoning + memory interfaces), never the reverse. This is what makes the graph backend and LLM providers swappable.

---

## 4. THE COGNITIVE LOOP (how "every agent feels human" actually works)

This is the heart of the system and the resolution of D3+D4. Read carefully.

### Agents

- **Sentinels (~50; 7 per population segment).** Full LLM cognition **every cognitive step**. Each owns a persona in the knowledge graph. Per step they: query graph memory → assemble context (world state + collective truth + personal history) → **LLM reasons** (route choice, frustration, what they noticed) → act → write the discovery back to memory + contribute it to their Segment Brain. These are the deep "thinking humans" that explore and stress-test the city.

- **Swarm (2000+).** Physics by default (Dijkstra over hive-weighted edges). They **feel human via two mechanisms**:
  1. **Inheritance** — every step they execute the *distilled LLM wisdom* (`CollectiveTruth`: preferred routes, avoid zones, mood) produced by their Segment Brain. Their behavior is shaped by LLM reasoning even when they don't call one.
  2. **Trigger-based escalation** — when a **cognitive event** fires (frustration > threshold, novel blockage, a real decision fork), the agent escalates to a fast/cheap LLM (Qwen-3) for a genuine human-like reasoning step, then rejoins physics. So agents reason *when it matters*, not wastefully every tick.

  This is the ONLY design that delivers human-feeling behavior for thousands of agents within free-tier usage/context caps and real-time latency.

- **Segment Brains (7).** Collective memory per segment, backed by the swappable graph. They run `distill_collective_truth()`: aggregate all sentinel discoveries + escalated swarm events → **LLM distillation** → emit `CollectiveTruth`. This wisdom flows *down* to the swarm. This is the "hive mind."

### The Hive Loop (per simulated timestep)

```
1. BROADCAST   scenario/policy → all 7 Segment Brains
2. SENSE       agents read world state (live + baseline)
3. REASON      Sentinels think via LLM (parallel, role-routed across 4 models)
4. EXECUTE     Swarm runs physics; escalates to LLM only on cognitive triggers
5. DISTILL     Segment Brains LLM-distill discoveries → CollectiveTruth
6. FEEDBACK    CollectiveTruth re-weights edges → influences next timestep
7. AGGREGATE   flow/emissions/mode-share → 7 domain engines → metrics
```

Feedback (step 6) is what produces emergence: collective decisions change the world the next step sees.

### Why this satisfies the constraints

- **Real reasoning** drives every agent (directly for sentinels, via distilled wisdom + triggers for swarm) → D3 ✓
- **Free-tier survivable**: ~50 sentinel calls + 7 distillation calls + bounded trigger calls per step, not 2000+ → D4/D5 ✓
- **Honest**: no agent's behavior is faked; physics and LLM each do real work → D2 ✓

---

## 5. THE REASONING LAYER (4-model brain, load-balanced)

One `LLMProvider` interface. A **router** assigns work by role to spread load across each free tier:

| Model | Role | Why | Volume |
|-------|------|-----|--------|
| **Kimi k2.6** | Deep analysis / Sentinel reasoning | Strong long-context reasoning | Medium |
| **GPT-OSS-120B** | Validation / Critic (LDRAGO) | Independent second opinion, catches bad outputs | Low |
| **Gemini 3.1 Pro** | Orchestration / Synthesis | Long context, good at planning + final briefs | Low |
| **Qwen-3** | Fast / Swarm trigger escalation | Cheapest + fastest, highest call volume | High |

Mandatory features of this layer (free-tier survival kit):

- **Reasoning cache** — hash(context) → cached decision. Identical situations don't re-spend quota.
- **Real fallback chain** — if a provider 429s/times out, degrade to the next model (NOT a hardcoded heuristic). Circuit-breaker per provider.
- **Quota/usage tracking** — per-provider token + request counters so we respect each cap and route around exhausted ones.
- **Ensemble (optional)** — for high-stakes distillation, query 2 models and reconcile.

> Today `llm/chat.py` already implements the real Qwen/Gemini/Kimi/GPT-OSS calls + a fallback chain + ensemble — **this is the keeper**. `llm_client.py` (root) is a hardcoded mock — **delete it** (§8). The `FallbackProvider` heuristic in `agent_simulation/llm_providers.py` must become a thin adapter over `llm/chat.py`, not a fake reasoner.

### 5.1 The Reasoning Gateway (how 50 sentinels + swarm scale on ~4 endpoints)

**The misconception to kill first:** "50 agents" does **not** mean 50 LLMs. Claude-Code-style subagents are parallel *requests* to **one** shared model, not separate brains. So our reality is **50 agents → many requests → a pool of ~4 endpoints**. The real limits are **rate limits, latency, and quota** — never "the model gets overloaded/confused." The fix is a traffic-management layer, not more models.

**Position:** every agent's reasoning call goes through ONE gateway. No agent ever calls a provider directly (invariant §11.5).

```
50 Sentinels ─┐
Swarm triggers ┼─▶  REASONING GATEWAY  ─▶  [Kimi · GPT-OSS · Gemini · Qwen]  (cloud)
7 Brains ─────┘     (queue·batch·cache·         └─▶  [Ollama / vLLM pool]    (local, optional)
                     shard·route·breaker)
```

**Mechanisms (each maps to a real bottleneck):**

| Mechanism | Concrete behavior | Solves |
|-----------|-------------------|--------|
| **Concurrency pool** | `asyncio.Semaphore(N)` per provider; fire-concurrent, not 50-at-once nor 1-at-a-time | Latency: 150s sequential → ~10–15s |
| **Provider sharding** | Consistent-hash `agent_id → model` so each endpoint sees ~12 reqs, not 50 | Rate limits |
| **Request batching** | Coalesce similar pending requests into ONE prompt ("decide for these K agents") within a small batch window (e.g. 50–150ms / K≤8) | Quota: 50 calls → ~7–10 |
| **Reasoning cache** | `hash(normalized_context) → decision`, short TTL; same segment + same blockage reuses | Quota + latency |
| **Trigger gate** | Only escalate to LLM on cognitive events (frustration/novelty/decision-fork, §4); else inherit CollectiveTruth | Cuts volume 5–10× |
| **Tiered routing** | Map task priority → model tier (below). High-volume → cheapest/fastest | Spreads load by capability |
| **Fallback + breaker** | On 429/timeout, degrade to next model in chain; circuit-breaker parks a dead provider; quota tracker routes around exhausted tiers | Reliability under free-tier caps |

**Routing policy (priority → tier):**

| Task | Tier | Default model |
|------|------|---------------|
| Swarm trigger escalation (high volume) | FAST | Qwen-3 / local |
| Sentinel step reasoning | ANALYSIS | Kimi k2.6 |
| Segment-Brain distillation | ANALYSIS (+ optional ensemble) | Kimi + Gemini |
| LDRAGO Critic / validation | VALIDATION | GPT-OSS-120B |
| LDRAGO synthesis / final brief | ORCHESTRATION | Gemini 3.1 Pro |

**Interface (what agents see — they never touch providers):**

```python
@dataclass
class ReasoningRequest:
    agent_id: str
    task: Literal["route", "distill", "critic", "synth", "escalate"]
    context: dict          # SMALL, focused — persona + local situation + relevant memory only
    priority: Literal["fast", "analysis", "validation", "orchestration"]
    cache_key: str | None = None   # if set, eligible for cache + batch coalescing

@dataclass
class ReasoningResult:
    decision: dict
    model_used: str
    cached: bool
    latency_ms: int

class ReasoningGateway(ABC):
    async def reason(self, req: ReasoningRequest) -> ReasoningResult: ...
    async def reason_many(self, reqs: list[ReasoningRequest]) -> list[ReasoningResult]: ...  # fan-out: pool+batch+shard internally
    def stats(self) -> dict: ...   # per-provider usage, cache hit-rate, breaker state
```

The **subagent lesson that DOES transfer**: keep each `context` *small and single-task* (persona + local situation + top-k memory), never the whole world state. Small prompts = faster, cheaper, within free-tier context caps — and they batch better.

### 5.2 Local/Cloud Hybrid (the only way to literally give agents "their own brain")

To remove rate limits + per-call cost for the high-volume path, add a **local model pool** as a provider behind the same gateway:

- **Ollama** or **vLLM** (continuous batching) serving a small model (Qwen-3 4B / Llama 3.2 3B / Phi) on local GPU.
- vLLM serves many concurrent agent requests on a single instance efficiently — genuinely "many agents, one shared brain, no quota wall."

**Recommended split (best for dual demo/production on free tiers — demo never dies mid-pitch on a 429):**

```
High-volume agent ticks (sentinel steps + swarm escalations)  →  LOCAL pool (Ollama/vLLM)
High-stakes work (distillation · validation · synthesis)      →  4 CLOUD frontier models
```

This is a **config + one new provider adapter**, not an architecture change — the gateway already abstracts it.

**Config (env):**
```
REASONING_CONCURRENCY=8          # semaphore per provider
REASONING_BATCH_WINDOW_MS=100    # coalesce window
REASONING_BATCH_MAX=8            # K agents per batched prompt
REASONING_CACHE_TTL_S=120
LOCAL_LLM_ENABLED=true|false
LOCAL_LLM_BACKEND=ollama|vllm
LOCAL_LLM_MODEL=qwen2.5:3b
ROUTING_PROFILE=hybrid|cloud_only|local_only
```

**Lives at:** `backend/src/overhaul/reasoning/` (§7) — `provider.py` (interface), `gateway.py` (pool·batch·cache·route), `router.py` (priority→tier), `providers/{kimi,gemini,gpt_oss,qwen,local}.py`, `quota.py`, `cache.py`. Migration: wrap the existing real `llm/chat.py` calls as the cloud providers; build the gateway in front; point agents at `gateway.reason()`.

**Gateway DoD:** 50 concurrent sentinel reasons complete < ~15s on free tiers without tripping a rate limit; cache hit-rate reported; flip `ROUTING_PROFILE=local_only` runs the full loop offline with zero cloud calls.

---

## 6. THE MEMORY LAYER (swappable graph — D6)

One abstract interface, three implementations, selected by config. **Nothing outside this folder may import a concrete backend.**

```
memory/
├── backend.py          # KnowledgeGraphBackend (ABC) — the ONLY thing callsites import
├── in_memory.py        # default for dev/demo, zero deps, zero cost
├── graphiti_kuzu.py    # FREE production default (temporal KG, embedded) — target
└── zep.py              # paid, OPTIONAL — behind the same interface
```

Selection (env): `GRAPH_BACKEND=in_memory | graphiti_kuzu | zep`

Interface (stable contract — all backends implement exactly this):

```python
class KnowledgeGraphBackend(ABC):
    async def add_episode(self, agent_id: str, content: dict) -> None: ...
    async def search(self, agent_id: str, query: str, k: int = 5) -> list[dict]: ...
    async def get_persona(self, agent_id: str) -> dict: ...
    async def upsert_collective(self, segment: str, truth: dict) -> None: ...
    async def health(self) -> bool: ...
```

**Migration rule:** to drop Zep entirely, set `GRAPH_BACKEND=graphiti_kuzu` (or `in_memory`). No other file changes. To add a new backend, implement the ABC + register it in the factory. That is the whole job.

Current state to preserve: the ABC already exists at `engines/agent_simulation/brains/backend.py` with `LocalKnowledgeGraphBackend` + `ZepBackend`. Migration = move it to `memory/`, rename `Local→InMemory`, add `graphiti_kuzu.py`, route selection through a single factory (today it's inline in `swarm.py:_init_backend`).

---

## 7. TARGET FILE STRUCTURE (MAANG-grade)

Monorepo: `backend/` (Python, src-layout) + `frontend/` (React) + `shared/` (the API contract that kills the schema mismatch) + infra/data/scripts.

```
overhaul/
├── PATH.md  CONTEXT.md  HISTORY.md  README.md
├── Makefile                         # make dev | test | lint | run | clean
├── docker-compose.yml               # local infra (graph db when needed)
├── .env.example                     # every required key, documented
│
├── shared/
│   └── contracts/
│       ├── simulation_state.schema.json   # THE source of truth for the API
│       └── README.md                      # how TS types are generated from it
│
├── backend/
│   ├── pyproject.toml               # deps + ruff + mypy + pytest config (single file)
│   ├── src/overhaul/
│   │   ├── api/                     # thin transport layer ONLY
│   │   │   ├── main.py              # FastAPI app factory
│   │   │   ├── routers/             # /simulate, /chat, /health, /integrations
│   │   │   ├── schemas/             # Pydantic models == shared/contracts
│   │   │   └── deps.py              # DI wiring (providers, backend, engines)
│   │   ├── core/                    # config, settings, logging, types, errors
│   │   ├── simulation/              # L3 cognition — the Hive
│   │   │   ├── engine.py            # UrbanSwarm orchestrator (the Hive Loop)
│   │   │   ├── agents/              # sentinel.py, swarm.py, base.py
│   │   │   ├── hive/                # segment_brain.py, collective_truth.py, distill.py
│   │   │   └── triggers.py          # cognitive-event escalation rules
│   │   ├── reasoning/               # L2 — the 4-model brain
│   │   │   ├── provider.py          # LLMProvider interface
│   │   │   ├── router.py            # role routing + load balancing
│   │   │   ├── providers/           # kimi.py gemini.py gpt_oss.py qwen.py
│   │   │   ├── cache.py             # reasoning cache
│   │   │   ├── quota.py             # per-provider usage tracking + breaker
│   │   │   └── prompts/             # versioned prompt templates
│   │   ├── memory/                  # L2 — swappable graph (see §6)
│   │   ├── engines/                 # L2 — 7 domain engines + registry
│   │   │   ├── transport/ environment/ energy/ economic/
│   │   │   ├── infrastructure/ population/ logistics/
│   │   │   └── registry.py
│   │   ├── data/                    # L1 — adapters + baselines
│   │   │   ├── adapters/            # csv_*, openaq, tomtom, opensky, osrm
│   │   │   └── baselines/           # loaders (no silent hardcoded fallbacks)
│   │   ├── orchestration/           # L4 — LDRAGO v2 pipeline stages
│   │   │   └── ldrago/              # parser planner researcher reasoner critic synth
│   │   └── reporting/               # policy-brief synthesis
│   └── tests/
│       ├── unit/  integration/  e2e/   # e2e = REAL llm + REAL hive loop
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── routes/                  # router config
│       ├── features/                # command-center/, scenario-builder/, report/
│       ├── components/              # shared presentational
│       ├── lib/api/                 # typed client generated from shared/contracts
│       ├── types/                   # mirror of SimulationState (generated)
│       └── visualization/           # WebGL swarm (r3f) + Mapbox layers
│
├── data/                            # NCR datasets (large = gitignored + script)
├── infra/                           # deploy manifests, CI
└── scripts/                         # one-off ops, data prep
```

**Naming conventions:** Python `snake_case` modules, `PascalCase` classes; one responsibility per module; no file > ~400 LOC (split `app.py`). Frontend `feature-folder` pattern (colocate component+styles+hooks+tests). No duplicate parallel apps.

---

## 8. REMOVE — literally delete these (the cleanup)

Confirm each still exists before deleting; the tree may have changed.

### Delete immediately (dead / stub / unrelated)
| Path | Reason |
|------|--------|
| `llm_client.py` | 100% hardcoded mock (`[LLM MOCK RESPONSE]`). Real LLM lives in `llm/chat.py`. Pure liability. |
| `train_models.py` | Training script never used by any service. |
| `privacy_guard.py` | Incomplete ethics stub, only referenced by archived code. |
| `archive/` (whole dir) | Old code + unused agents + superseded models. |
| `external/2025_f1_predictions/` | F1 racing predictor — unrelated to OVERHAUL. |
| `landing-react/external/2025_f1_predictions/` | Duplicate of the above. |
| `ai-flyover-sim/frontend/` | Full duplicate of the landing-react flyover. Consolidate into one frontend. |

### Delete from dependencies
- **Python (`requirements.txt`/`pyproject`):** `camel-ai` (zero imports), `chromadb` (commented/disabled), `sumolib` + `traci` (SUMO — only old traffic-god), move `flake8/mypy/black/jupyterlab/tensorboard` to a dev group.
- **Frontend (`package.json`):** `chart.js`, `react-chartjs-2`, `gsap`, `maplibre-gl` (zero imports). **Keep** `@react-three/fiber` + `@react-three/drei` — the target swarm visualization (§L5) needs them; they're unused *today* but are the real perf path for 2000-agent rendering.

### Consolidate then delete (post-migration, not before)
| Path | Action |
|------|--------|
| `agents/` (root, 19 files) | Old framework duplicating `agent_simulation/`. Merge into `simulation/`, then delete. |
| `traffic-god/` (40+ files) | Superseded by `new_traffic_god/`. Migrate any live endpoint, then delete. |
| `services/` (8 micro-stubs) | The 6 "microservices" are never instantiated; `app.py` is the real monolith. Fold real logic into `backend/src/overhaul/`, delete the empty service shells. Do NOT build true microservices yet (YAGNI for current scale). |

### Rebuild (don't keep as-is, don't blind-delete)
- `HiveCommand.jsx` — orphaned + uses `Math.random()` sentinel positions (lines ~177–190) + expects fields the API never returns. **Gut the mock, rewire to the real `SimulationState` contract.** Salvage the visual shell only.

---

## 9. MIGRATION PLAN (build order — each step ships something real)

> Sequence matters: fix the contract and the brain before the visuals, or you'll polish a disconnected UI again.

### Phase 0 — Cleanup & skeleton (low risk, do first)
- Delete the §8 "immediately" list. Strip dead deps.
- Create the §7 directory skeleton. Move code in, don't rewrite logic yet.
- Split `app.py` into `api/main.py` + `routers/`.
- **DoD:** app still boots; tests still pass; tree matches §7.

### Phase 1 — The contract (kills the #1 bug)
- Author `shared/contracts/simulation_state.schema.json`: `brains[]`, `sentinels[]{coords,mood,confidence}`, `swarm` (geojson flow), `timesteps[]`, `engine_results`, `report`.
- Backend Pydantic `schemas/` mirror it exactly; generate frontend TS `types/` from it.
- **DoD:** one schema, both sides import it, no field drift.

### Phase 2 — Real brain wiring
- Promote `llm/chat.py` into `reasoning/` behind `LLMProvider`. Build `router.py` (role map §5), `cache.py`, `quota.py`.
- Replace the heuristic `FallbackProvider` with a real adapter; keep a real fallback *chain*.
- **DoD:** an integration test makes a real LLM call through the router and gets a real decision.

### Phase 3 — Swappable memory
- Move the KG ABC to `memory/`; rename `Local→InMemory`; add a single backend **factory** + `GRAPH_BACKEND` env switch.
- Stub `graphiti_kuzu.py` implementing the ABC (free default target).
- **DoD:** flip `GRAPH_BACKEND` between `in_memory`/`zep` with zero callsite edits; health check passes for each.

### Phase 4 — Honest cognition
- Implement `triggers.py` (frustration/novelty/decision-fork escalation) for the swarm.
- Wire Sentinel `think()` → real LLM; Segment Brain `distill()` → real LLM; CollectiveTruth → edge re-weighting feedback.
- **DoD:** `/simulate/hive` runs the full §4 loop and returns a populated `SimulationState`.

### Phase 5 — Real visualization
- Rebuild the command center against `SimulationState`. Sentinel probes from real coords, swarm via r3f/WebGL instancing (perf path), brain panels from real distillation.
- Unify API base config (kill hardcoded `localhost:8001`; one `VITE_API_BASE`).
- **DoD:** click "run" → real data → live city renders at interactive FPS. Zero `Math.random()`.

### Phase 6 — E2E + demo hardening
- One real `tests/e2e/` test: query → hive loop (real LLM, real graph) → engines → report → schema-valid response.
- Error states (provider down, quota hit) degrade gracefully and visibly — never silent-fake.
- **DoD:** the investor demo path runs end-to-end on free tiers, repeatably.

---

## 10. DEFINITION OF DONE (the bar for "real" + "demo-ready")

A feature is done only when ALL hold:
- [ ] Output is real (traceable to computation/data) — **no mock in the shipped path**
- [ ] Backend response validates against `shared/contracts`
- [ ] Frontend consumes it with no field remapping hacks
- [ ] Works on **free-tier** LLM + a **free** graph backend (`in_memory` or `graphiti_kuzu`)
- [ ] Failure modes are visible, not silently faked
- [ ] Covered by at least one non-mock test
- [ ] Runs at interactive latency for the demo scenario

---

## 11. INVARIANTS (never violate)

1. No layer imports a layer above it (§3). 2. No concrete LLM provider or graph backend is imported outside `reasoning/providers` / `memory/` (§5,§6). 3. The API schema has exactly one source: `shared/contracts` (§7). 4. No `Math.random()` standing in for data; no hardcoded "mock response"; no silent fallback to fabricated numbers (§D2). 5. Every LLM call goes through the router (cache + quota + fallback) — no raw provider calls scattered in agents (§5). 6. Swapping the graph backend is a config change, never a code change (§D6).

---

## 12. KNOWN-GOOD vs KNOWN-BAD (today's reality, for orientation)

**Keep (genuinely real & working):** `llm/chat.py` (real 4-model calls + fallback + ensemble), `data_integration/adapters/*` (real CSV + OpenAQ/TomTom/OpenSky/OSRM), the 7 `engines/*`, the KG ABC at `agent_simulation/brains/backend.py`, `new_traffic_god/`, `Demo2.jsx` (routed, real-ish), `Flyover3DViewer.jsx` (real Three.js).

**Bad (fix/remove):** `llm_client.py` (mock — delete), `FallbackProvider` heuristics (fake reasoning — replace), `HiveCommand.jsx` `Math.random()` (rebuild), API contract mismatch `/chat` vs frontend (Phase 1), hardcoded `localhost:8001` in flyover components, `app.py` monolith (split), silent hardcoded baseline fallback in `engine.py:_load_baselines` (mark synthetic or fail loudly).

---

*End of PATH.md. Update CONTEXT.md/HISTORY.md to point here. When in doubt, this file wins.*
