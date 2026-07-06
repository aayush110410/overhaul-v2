# OVERHAUL Project History

This file tracks all changes, decisions, and milestones across sessions.

## Session: [2026-04-11]
### Events & Decisions
- **Project Onboarding**: User provided full architecture of OVERHAUL and a detailed diagnosis of the "MiroFish" integration gaps.
- **Technical Research**:
    - Investigated `camel-ai/oasis` (OASIS) as the underlying simulation engine.
    - Investigated `Zep Cloud` for GraphRAG and agent memory persistence.
    - Analyzed `MiroFish` as a pipeline framework (GraphBuilder $\rightarrow$ ProfileGenerator $\rightarrow$ Simulation $\rightarrow$ MemoryUpdater $\rightarrow$ ReportAgent).
- **Internal Audit**: Verified that current `agent_simulation` code contains only stubs; no actual connection to Zep or OASIS exists.
- **Framework Alignment**: User requested a "production grade" implementation using the Superpowers framework.
- **Superpowers Activation**: Activated `brainstorming` $\rightarrow$ `writing-plans` $\rightarrow$ `TDD` workflow.
- **Persistence Setup**: Created `CONTEXT.md` and `HISTORY.md` to maintain session state.
- **User Preferences**: Confirmed CLI-only output (no visual companion) and requested strict adherence to all Superpowers implementation skills.

## Session: [2026-04-13]
### Events & Decisions
- **Design Finalization**: Locked the "Sentinel-Swarm-Hive" architecture.
- **Surgical Agents**: Defined as high-fidelity stress testers with full LLM reasoning.
- **Swarm Agents**: Defined as systemic load using Hive-Inheritance from a Segment Brain.
- **The Hive**: Implemented synchronous LLM distillation (Option A) for collective truth.
- **PolicyAgent**: Redefined as a Living Regulatory Monitor using automated feeds.
- **Backend Strategy**: Defined a ZepCloud $\rightarrow$ Graphiti swap path via a `KnowledgeGraphBackend` abstract interface.
- **Spec Finalized**: Wrote and committed the Stage A design spec to `docs/superpowers/specs/2026-04-13-mirofish-integration-design.md`.
- **Brainstorming Complete**: Moved to `writing-plans` phase.
- **Plan Written**: Created implementation plan at `~/.claude/plans/silly-wobbling-codd.md`.
- **Files Committed**: `CONTEXT.md`, `HISTORY.md`, and spec all committed to git.
- **Plan Mode**: Entered plan mode to create implementation tasks.

### Phase 1 Execution
- **Task 1.1 Complete**: Added `zep-cloud==3.13.0` and `camel-ai>=0.2.0` to `requirements.txt`. Note: `camel-oasis` package does not exist - the package is `camel-ai` (imported as `camel`). Installed and verified both packages. Created test file `tests/engines/agent_simulation/test_dependencies.py` which passes.
- **Files Modified**: `requirements.txt`
- **Files Created**: `tests/engines/agent_simulation/test_dependencies.py`

### Task 1.2 Complete: KnowledgeGraphBackend ABC
- **Created directory**: `engines/agent_simulation/brains/`
- **Created `backend.py`**: Defines `KnowledgeGraphBackend` ABC with all required methods (`add_memory`, `get_memory`, `add_fact`, `search_facts`, `sync_from_policy_agent`, `semantic_query`, `async initialize`)
- **Created `LocalKnowledgeGraphBackend`**: In-memory implementation of the ABC
- **Created `ZepBackend`**: Zep Cloud implementation (ONLY class that imports `zep_cloud`)
- **Created `__init__.py`**: Package init with exports
- **Created test file `test_backend_interface.py`**: Tests ABC existence, method presence, inheritance by both concrete classes, and that all methods raise `NotImplementedError` via a test double
- **All 20 tests pass**
- **Files Created**:
  - `engines/agent_simulation/brains/__init__.py`
  - `engines/agent_simulation/brains/backend.py`
  - `tests/engines/agent_simulation/brains/test_backend_interface.py`

### Task 1.3 Complete: LocalKnowledgeGraphBackend Full Implementation
- **Added context manager support**: `__enter__` and `__exit__` methods to `LocalKnowledgeGraphBackend`
- **Added comprehensive tests** in `test_local_backend.py`:
  - `add_memory()` and `get_memory()` — data persistence within session
  - `add_fact()` and `search_facts()` — fact triple storage and querying
  - `semantic_query()` — substring matching on fact content
  - `sync_from_policy_agent()` — stores law and budget facts
  - `initialize()` — no-op that completes immediately
  - Context manager protocol (`__enter__` and `__exit__`)
- **Files Created**: `tests/engines/agent_simulation/brains/test_local_backend.py`

### Task 1.4 Complete: ZepBackend Tests + Async Init Fix
- **Added comprehensive tests** in `test_zep_backend.py`:
  - `ZepBackend.__init__()` accepts `api_key` and `collection_name`
  - `initialize()` is async and sets `_initialized = True`
  - Graceful fallback: when Zep unavailable, `_client = None` and all methods fall back to local
  - Async init bug fix verified: `await backend.initialize()` properly awaits
- **Implementation in `backend.py`**:
  - `async initialize()` connects to Zep Cloud, sets `_initialized = True`; on failure sets `_client = None` (graceful fallback)
  - All methods (`add_memory`, `get_memory`, `add_fact`, `search_facts`, `semantic_query`, `sync_from_policy_agent`) use local fallback when `_client is None`
- **Files Created**: `tests/engines/agent_simulation/brains/test_zep_backend.py`

### Phase 2 Execution

#### Task 2.1 Complete: CollectiveTruth Dataclass
- **Created `collective_truth.py`**: `@dataclass` with 7 fields (`timestep`, `preferred_routes`, `avoid_zones`, `segment_mood`, `confidence`, `dissenting_signals`, `stale: bool = False`)
- **Added `__post_init__` validation** for confidence range (0.0-1.0) and valid mood values (frustrated/adaptive/stable/optimistic)
- **Added `to_dict()` and `from_dict()`** methods for JSON serialization round-trip
- **Created test file `test_collective_truth.py`**: 29 tests covering instantiation, serialization, validation
- **Files Created**:
  - `engines/agent_simulation/brains/collective_truth.py`
  - `tests/engines/agent_simulation/brains/test_collective_truth.py`

#### Task 2.2 Complete: SegmentBrain Class
- **Created `segment_brain.py`**: Core Hive component managing collective memory per segment
- **Constructor**: `__init__(segment_name, backend: KnowledgeGraphBackend, llm_provider: Optional[Callable])`
- **Methods implemented**:
  - `contribute_discovery(sentinel_id, timestep, discovery_data)` — stores wrapped discovery entries
  - `distill_collective_truth(timestep, lookback=1)` — windowed LLM synthesis; on failure retains previous truth with `stale=True`
  - `update_swarm_stats(timestep, stats_data)` — stores swarm aggregate stats
  - `get_current_truth()` — returns cached latest CollectiveTruth
  - `get_history(from_timestep, to_timestep)` — returns list of CollectiveTruth in range
- **Created test file `test_segment_brain.py`**: 16 tests covering all methods, conflict resolution, LLM failure handling, timestep windowing
- **Key test**: `test_distill_with_conflict_produces_dissenting_signals` verifies that 2 "fast" + 1 "blocked" discoveries produce Route A in `preferred_routes` AND a non-empty `dissenting_signals` AND `confidence < 0.7`
- **Updated `__init__.py`**: Added exports for `CollectiveTruth` and `SegmentBrain`
- **Files Created**:
  - `engines/agent_simulation/brains/segment_brain.py`
  - `tests/engines/agent_simulation/brains/test_segment_brain.py`
- **Files Modified**: `engines/agent_simulation/brains/__init__.py`

### All Phase 2 Tasks Complete
- **Total tests**: 105 tests passing (29 for CollectiveTruth + 16 for SegmentBrain + 60 pre-existing)
- **Files Created**:
  - `engines/agent_simulation/brains/collective_truth.py`
  - `engines/agent_simulation/brains/segment_brain.py`
  - `tests/engines/agent_simulation/brains/test_collective_truth.py`
  - `tests/engines/agent_simulation/brains/test_segment_brain.py`
- **Files Modified**: `engines/agent_simulation/brains/__init__.py`
- **Issues Encountered**:
  - MockLLMProvider using `MagicMock` didn't preserve `last_input` between calls — fixed by using plain callable closures that capture inputs in a list
  - Discovery data structure wraps input in `{"sentinel_id", "timestep", "discovery_data"}` — tests corrected to access fields via `discovery_data` key

## Session: [2026-04-13 - Afternoon]
### Events & Decisions
- **Resume Work**: Session resumed after time away. Found project in partially completed state with `surgical_agent.py` and `swarm_agent.py` at wrong location.
- **Module Restructure**: Moved `agents.py` → `agents/types.py` and created proper `agents/` subpackage with `__init__.py` re-exporting all types and agents.
- **Design Spec**: Locked at `docs/superpowers/specs/2026-04-13-mirofish-integration-design.md`

### Phase 3 Execution — The Agents

#### Task 3.1/3.2: Module Structure Fix
- **Problem**: `surgical_agent.py` and `swarm_agent.py` were at `engines/agent_simulation/` root instead of `engines/agent_simulation/agents/`
- **Fix**: Moved files to `engines/agent_simulation/agents/` subpackage
- **Renamed**: `engines/agent_simulation/agents.py` → `engines/agent_simulation/agents/types.py`
- **Created**: `engines/agent_simulation/agents/__init__.py` re-exporting all types and agents

#### SurgicalAgent Fixes
- **Problem**: `act()` stored discovery in instance vars; `run_step()` did the actual write to SegmentBrain. Tests expected `contribute_discovery` called directly from `act()`.
- **Fix**: Updated `act()` signature to `act(decision, timestep, segment_brain)` and moved discovery write directly into `act()`
- **Problem**: `asyncio.iscoroutinefunction` deprecated in Python 3.16
- **Fix**: Replaced with `inspect.iscoroutinefunction` in `_call_llm()`
- **Problem**: Tests used `call_args[0][n]` for keyword args but AsyncMock stores them as `call_args.kwargs`
- **Fix**: Updated test assertions to use `call_args.kwargs["name"]` pattern

#### SwarmAgent Fixes
- **Problem**: `test_preferred_routes_get_bonus` failed — destination `noida_sec18` doesn't contain edge `noida_sec18->greater_noida`
- **Fix**: Changed test destination to `greater_noida` so the preferred edge is on the actual path
- **Problem**: `swarm_agent.py` import path was wrong in tests
- **Fix**: Updated all `from engines.agent_simulation.swarm_agent import` to `from engines.agent_simulation.agents.swarm_agent import`

#### Phase 3 Test Results
- **130 tests passing** across all agent_simulation modules
- **Files Created**:
  - `engines/agent_simulation/agents/__init__.py`
  - `engines/agent_simulation/agents/types.py` (renamed from `agents.py`)
  - `engines/agent_simulation/agents/surgical_agent.py`
  - `engines/agent_simulation/agents/swarm_agent.py`
  - `tests/engines/agent_simulation/agents/test_surgical_agent.py`
  - `tests/engines/agent_simulation/agents/test_swarm_agent.py`
- **Files Modified**: `engines/agent_simulation/swarm.py` (updated imports to use `agents.types`)

### Phase 4 Execution — UrbanSwarm Hive Loop

#### Task 4.1: Updated UrbanSwarm
- **Rewrote `swarm.py`** (668 lines) with full Hive Loop orchestration:
  - **`async initialize()`**: Calls `_init_backend()` → `_create_segment_brains()` → `_create_sentinel_agents()`
  - **`_init_backend()`**: Initializes `ZepBackend` or `LocalKnowledgeGraphBackend` based on API key availability
  - **`_create_segment_brains()`**: Creates 7 `SegmentBrain` instances (one per population segment: office_workers, gig_workers, students, service_sector, industrial_workers, senior_citizens, high_income)
  - **`_create_sentinel_agents()`**: Creates ~50 `SurgicalAgent` instances distributed across segments (~7 per segment)
  - **5-Step Hive Loop** per timestep:
    1. Policy Broadcast (PolicyAgent → GlobalKG + SegmentBrains)
    2. Sentinel Reasoning (SurgicalAgent.run_step → discovery → SegmentBrain.contribute_discovery)
    3. Hive Distillation (SegmentBrain.distill_collective_truth → CollectiveTruth)
    4. Swarm Execution (SwarmAgent.choose_route with CollectiveTruth weights)
    5. Swarm Feedback Write (aggregate stats → SegmentBrain.update_swarm_stats)
- **Updated imports**: Now imports `SurgicalAgent`, `SwarmAgent`, `SegmentBrain`, `CollectiveTruth` from `agents/` package
- **Files Modified**: `engines/agent_simulation/swarm.py`

#### Task 4.2: AgentSimulationEngine Async Init
- **Updated `engine.py`**: Changed `swarm.initialize(zep_api_key=...)` to `await swarm.initialize(zep_api_key=...)` in `_run()` method
- **Files Modified**: `engines/agent_simulation/engine.py`

### Phase 5 Execution — PolicyAgent + ReportAgent

#### Task 5.1: PolicyAgent Implementation
- **Created `policy_agent.py`**: Autonomous regulatory monitor
- **Methods**:
  - `sync_from_web(research_query)` — LLM-based policy research (or graceful no-op)
  - `broadcast_to_global_kg(data)` — writes policy data to GlobalKG
  - `run_policy_broadcast(research_query, timestep, target_segments)` — full broadcast cycle
- **Graceful degradation**: Falls back to empty results when no LLM configured
- **Files Created**: `engines/agent_simulation/agents/policy_agent.py`

#### Task 5.2: ReportAgent Implementation
- **Created `report_agent.py`**: Quantitative-first simulation brief generator
- **Classes**: `ReportConfig`, `SimulationReport`, `ReportAgent`
- **Methods**:
  - `generate_verdict(swarm_result)` — heuristic verdict (approve/conditional/reject) based on congestion %
  - `collect_segment_insights()` — extracts CollectiveTruth history from all SegmentBrains
  - `generate_summary(verdict, segment_insights)` — markdown summary (LLM or fallback rule-based)
  - `generate_report(swarm_result)` — complete `SimulationReport` with verdict, summary, recommendations
- **Files Created**: `engines/agent_simulation/agents/report_agent.py`

#### Task 5.3: Tests for PolicyAgent + ReportAgent
- **Created `test_policy_agent.py`**: 4 tests covering no-LLM fallback, LLM sync, broadcast, and async run
- **Created `test_report_agent.py`**: 5 tests covering verdict generation (approve/reject), segment insights collection, summary fallback, full report generation
- **All 9 tests pass**

### All Phases Complete — Final Test Run
- **Total tests**: 130 tests passing (130 agent_simulation + full suite)
- **New files created this session**:
  - `engines/agent_simulation/agents/surgical_agent.py`
  - `engines/agent_simulation/agents/swarm_agent.py`
  - `engines/agent_simulation/agents/policy_agent.py`
  - `engines/agent_simulation/agents/report_agent.py`
  - `tests/engines/agent_simulation/agents/test_surgical_agent.py`
  - `tests/engines/agent_simulation/agents/test_swarm_agent.py`
  - `tests/engines/agent_simulation/agents/test_policy_agent.py`
  - `tests/engines/agent_simulation/agents/test_report_agent.py`
- **Files modified this session**:
  - `engines/agent_simulation/agents.py` → `engines/agent_simulation/agents/types.py`
  - `engines/agent_simulation/agents/__init__.py` (created)
  - `engines/agent_simulation/swarm.py` (major rewrite)
  - `engines/agent_simulation/engine.py`
- **Remaining work**:
  - Stage B: Connect live data (OpenAQ, TomTom) → Living model of the city

## Session: [2026-04-25]

### Stages C–F Implementation — Subagent-Driven Execution

#### Task C.1 Complete: Sentinel Node Init Bug Fix
- **Fixed** `_create_sentinel_agents()` in `swarm.py`: sentinel agents now pick valid nodes from `self._nodes.keys()` instead of hardcoded `"default_node"`
- **Created test** `tests/engines/agent_simulation/test_sentinel_node_init.py` — verified fix
- **Result**: 136 agent_simulation tests passing

#### Task C.2 Complete: Full Swarm E2E
- **Created** `tests/engines/agent_simulation/test_swarm_e2e.py` — full `UrbanSwarm.run()` E2E test
- **Result**: 1 E2E test passing, full swarm executes without errors

#### Task C.3 Complete: LDRAGO v2 Parser
- **Created** `engines/agent_simulation/ldrago_parser.py`:
  - `ParsedSimulationBrief` dataclass (avg_speed_kmh, congestion_pct, pm25_kg, co2_tonnes, emergent_hotspots, mode_shift_count, etc.)
  - `LDRAGOParser.parse()` — extracts metrics from SwarmResult using `getattr` for graceful missing-field handling
  - `LDRAGOParser.generate_markdown()` — produces human-readable summary
- **Created test** `tests/engines/agent_simulation/test_ldrago_parser.py` — 3 tests (metrics, markdown, hotspots/mode shifts)
- **Files Created**: `engines/agent_simulation/ldrago_parser.py`, `tests/engines/agent_simulation/test_ldrago_parser.py`

#### Tasks D.1, D.2, D.3 Complete: All Downstream Engine Wiring
- **EconomicEngine** (`engines/economic/engine.py`): Added `transport_result` extraction for agents_simulated, agent_speed, agent_congestion. Overrides time_saved_min. Added `agent_sim_used` metadata flag. 2 tests pass.
- **EnergyEngine** (`engines/energy/engine.py`): Added `transport_result.ev_share` override for ev_count. Added `ev_share_source` metric tag ("agent_sim" vs "baseline"). 2 tests pass.
- **InfrastructureEngine**: Already had wiring — verified with test. 1 test pass.
- **PopulationEngine**: Already had `mode_shifts_observed` wiring — verified. 1 test pass.
- **LogisticsEngine** (`engines/logistics/engine.py`): Fixed `new_freight_trips` to use `effective_freight_trips` derived from `baseline_vkt` (from transport_result), not static `freight_trips`. 1 test pass.
- **Files Created**: `tests/engines/economic/test_agent_sim_wiring.py`, `tests/engines/energy/test_energy_agent_wiring.py`, `tests/engines/infrastructure/test_infra_agent_wiring.py`, `tests/engines/population/test_pop_agent_wiring.py`, `tests/engines/logistics/test_log_agent_wiring.py`

#### Test File Rename (Module Collision Fix)
- Renamed all `test_agent_sim_wiring.py` to unique names to avoid pytest import collision:
  - `tests/engines/energy/test_agent_sim_wiring.py` → `test_energy_agent_wiring.py`
  - `tests/engines/infrastructure/test_infra_agent_sim.py` → `test_infra_agent_wiring.py`
  - `tests/engines/population/test_pop_agent_sim.py` → `test_pop_agent_wiring.py`
  - `tests/engines/logistics/test_log_agent_sim.py` → `test_log_agent_wiring.py`

### Stage C + Stage D Complete — Stage E + F Remaining
- **Total: 161 tests passing** (was 149 → 161, +12)
- **New files created**: `tests/engines/agent_simulation/test_sentinel_node_init.py`, `tests/engines/agent_simulation/test_swarm_e2e.py`, `tests/engines/agent_simulation/ldrago_parser.py`, `tests/engines/agent_simulation/test_ldrago_parser.py`, downstream engine test files
- **Files modified**: `swarm.py`, `engine.py` (economic), `engine.py` (energy), `engine.py` (logistics), `CONTEXT.md`, `HISTORY.md`
- **Stage Status**: ✅ C COMPLETE | ✅ D COMPLETE | 🔲 E PENDING | 🔲 F PENDING

#### Task B.3 Complete: Environment Engine Live AQI
- **Created `OpenAQAqiAdapter`** in `data_integration/adapters/api_adapter.py`
  - Fetches real-time PM2.5 from OpenAQ v2 API (free, no API key required)
  - Parses multi-station Delhi data (US Embassy, IIT Delhi, CPCB, etc.)
  - Returns city-average PM2.5, per-station readings, AQI category
  - TTL: 5 minutes
- **Registered in `manager.py`**: `OpenAQAqiAdapter(ttl_seconds=300)` added to adapter registry
- **Created test file**: `tests/data_integration/adapters/test_openaq_adapter.py` — 9 tests
- **Updated `_aqi_category`**: Now accepts `Optional[float]` (was `float`), handles None gracefully
- **Moved `_weather_code_label`**: Relocated above `OpenMeteoWeatherAdapter` to fix forward-reference ordering
- **Dependency fix**: Installed `camel-ai>=0.2.0` and `zep-cloud==3.13.0` into venv via `python3.11 -m pip`
- **Files Created**: `tests/data_integration/adapters/test_openaq_adapter.py`
- **Files Modified**:
  - `data_integration/adapters/api_adapter.py` (added OpenAQAqiAdapter)
  - `data_integration/adapters/manager.py` (registered adapter)
  - `CONTEXT.md` (updated Stage B status, test count 130→142)
  - `HISTORY.md` (this entry)
- **All 142 tests passing** (was 130)

#### Task B.2 Complete: Wire Live Data into AgentSimulationEngine
- **Modified `engines/agent_simulation/engine.py`**:
  - Added imports: `init_adapters`, `get_ncr_context` from `data_integration.adapters.manager`
  - In `_run()`: calls `await init_adapters()` and `await get_ncr_context(city=scenario.city)` before swarm init
  - Extracts `live_pm25` from `live_aqi` → sets `data["baseline_pm25"]`
  - Extracts `live_speed` from `tomtom` → sets `data["baseline_speed_kmh"]`
  - Stores `data["_live_sources"]` for metadata tracking
  - Added `live_data_sources` to result metadata
- **Modified `engines/agent_simulation/swarm.py`**:
  - `UrbanSwarm.__init__()` accepts `live_context: Optional[Dict[str, Any]] = None`
  - `UrbanSwarm.initialize()` accepts `live_context` parameter, passes to `_init_flow_map_from_context()`
  - Added `_init_flow_map_from_context()` method: seeds flow_ratio from TomTom speed ratio (clamped 0.3–0.95), falls back to 0.6 baseline
  - Fixed `SurgicalAgent` call: `segment=` → `segment_name=`, removed `llm_provider=None`
  - Fixed `sentinel.run_step()` call: now passes `state`, `segment_brain`, `global_kg`, `timestep`
  - Fixed `brain.contribute_discovery()` call: now passes `sentinel_id`, `timestep`, `discovery_data`
- **Modified `engines/agent_simulation/config.py`**:
  - Added `live_context: Dict[str, Any] = field(default_factory=dict)` to `SwarmConfig`
- **Files Modified**: `engine.py`, `swarm.py`, `config.py`

#### Task B.4 Complete: Integration Test
- **Created `tests/engines/agent_simulation/test_live_data_integration.py`** — 4 tests, all passing:
  1. `test_engine_fetches_live_context_before_simulation` — verifies `init_adapters()` + `get_ncr_context()` called
  2. `test_live_pm25_seeded_into_data` — verifies OpenAQ PM2.5 flows to metadata
  3. `test_live_speed_calibrates_flow_map` — verifies TomTom speed seeds flow map
  4. `test_graceful_fallback_when_no_live_data` — verifies simulation succeeds with empty context
- **Tests use mocked UrbanSwarm** to avoid full sentinel initialization (pre-existing bugs in swarm init unrelated to live data wiring)
- **Files Created**: `test_live_data_integration.py`

#### Task B.3 Complete: Environment Engine Live AQI
- **Modified `engines/environment/engine.py`**:
  - Added `has_live_data` flag to track whether `baseline_pm25` was provided
  - Added `pm25_data_source` metadata: "live_openaq" when provided, "csv_baseline" when using default
- **Created test file**: `tests/engines/environment/test_live_pm25_override.py` — 3 tests:
  1. `test_environment_engine_uses_live_pm25` — verifies live PM2.5 is used when provided
  2. `test_environment_engine_uses_csv_baseline_when_no_live_data` — verifies fallback to default
  3. `test_metadata_includes_data_source_tag` — verifies metadata tagging
- **Files Created**: `tests/engines/environment/test_live_pm25_override.py`
- **Files Modified**: `engines/environment/engine.py`, `CONTEXT.md`, `HISTORY.md`
- **All 149 tests passing** (was 146, +3)

#### Task B.5 Complete: OpenSky Network Adapter
- **Created `OpenSkyNetworkAdapter`** in `data_integration/adapters/api_adapter.py`
  - Real-time aircraft tracking via OpenSky Network API
  - Bounding box query for Delhi NCR (lamin=28.0, lamax=29.2, lomin=76.5, lomax=77.5)
  - Basic Auth with OPENSKY_USERNAME and OPENSKY_PASSWORD env vars
  - Graceful degradation: returns empty DataResult when no credentials
  - TTL: 60 seconds (high-frequency updates)
  - Parses aircraft state fields: icao24, callsign, altitude, velocity, heading, vertical_rate
  - Comprehensive docstring with design spec, API details, and registration notes
- **Added `AIR_TRAFFIC` to `DataDomain` enum** in `data_integration/adapters/base.py`
- **Files Modified**: `data_integration/adapters/api_adapter.py` (added class), `data_integration/adapters/base.py` (added enum value)

## Session: [2026-05-17]
### Events & Decisions
- **Stage E Verification**: Verified simulation API endpoints (`/simulation/results`, `/simulation/aqi-overlay`, `/simulation/segment-insights`) are implemented and tests are passing. Marked Stage E as COMPLETE.
- **TDD Maintenance**:
    - Fixed `tests/test_expansion.py`: Resolved `fixture 'reg' not found` error and added `@pytest.mark.asyncio` to `test_two_phase`.
    - Resolved `PytestReturnNotNoneWarning` in `test_registry`.
- **Stage F Start**: 
    - Implemented `_build_distillation_prompt` in `SegmentBrain` to handle LLM-driven synthesis of sentinel discoveries.
    - Added test suite `TestSegmentBrainDistillationPrompt` to verify prompt content (segment name, timestep, windowed discoveries).
- **Model Transition**: Attempted subagent-driven execution with multiple cloud models; identified platform-level 403 restriction on subagent API access. Pivoted to direct sequential implementation to maintain velocity.

### Status
- ✅ Stage E Complete
- 🚧 Stage F In Progress (Prompt templates implemented, E2E test pending)
- 177+ Tests Passing

### Stage B Complete — All Tasks Finished
- **Total: 149 tests passing** (was 142 → 146 → 149)
- **New files created**: `tests/engines/agent_simulation/test_live_data_integration.py`, `tests/engines/environment/test_live_pm25_override.py`
- **Files modified**: `engine.py`, `swarm.py`, `config.py`, `api_adapter.py`, `manager.py`, `engines/environment/engine.py`, `base.py` (DataDomain enum), `CONTEXT.md`, `HISTORY.md`
- **Stage B Status**: ✅ ALL 5 TASKS COMPLETE (B.1, B.2, B.3, B.4, B.5)

## Session: [2026-05-28]
### Events & Decisions
- **LLM Brain Upgrade**: Transitioned the core reasoning stack to use **Kimi k2.6** (Analysis), **GPT-OSS-120B** (Validation), and **Gemini 3.1 Pro** (Orchestration). Updated `.env`, `llm/config.py`, and `llm/chat.py`.
- **UI Pivot**: Shifted visual direction from "Linear-minimal" to a **"Surgical Command Center"**.
    - Goal: A high-density, modern tactical interface focused on systemic flow and agent visualization, taking inspiration from Palantir's dot/node representation but with a more modern, cohesive aesthetic matching the home page.
    - Key Visuals: 3D particle flow for the 2000 Swarm agents, high-fidelity pulsing "Probes" for 50 Sentinels, and geometric Hive-connectivity lines.
- **Technical Fixes**: Removed problematic `camel-oasis` dependency from `requirements.txt` to stabilize the environment.
- **Infrastructure**: Successfully launched the backend and frontend (Vite) in background processes.
- **UI Implementation**: Created `HiveCommand.jsx` as the primary interface for visualizing the Sentinel-Swarm-Hive dynamics.

## Session: [2026-06-30 → 07-01] — Hive Engine Made Real + Project Cleanup

### The cognitive loop is now genuinely LLM-driven (was theater)
Implemented the approved "make it real, in-place" plan. Verified the 2026-06-03 audit findings against live code, then fixed them:
- **`reasoning/` package** — the `ReasoningGateway`: coalesces ≤8 sentinels into one `llm_chat_json` call, consistent-hash shards agent→model, TTL cache + trigger-gate, per-account token-bucket rate limiter, per-provider circuit breaker, and **strict edge-ID coercion** (LLM output forced onto the 28 real `u->v` edges or dropped — the anti-theater guard). Wraps the real `llm/chat.py`; `get_gateway()` singleton.
- **`memory/` package** — `get_kg_backend(GRAPH_BACKEND)` factory (in_memory default, zep optional); re-exports the existing KG ABC without moving it.
- **`shared/contracts/`** — `SimulationState` JSON schema + Pydantic v2 mirror; used as the `/simulate/hive` `response_model` (kills the historical /chat-vs-frontend field drift).
- **`swarm.py` rewrite** — fixed the `collective_truth.suggested_route` `AttributeError` that silently emptied every run; removed the double discovery write; `enable_llm` flag injects the gateway provider at the two old `llm_provider=None` sites; **parallel** `asyncio.gather` sentinel reasoning + `distill_many`; added `SegmentBrain.record_truth`, optional `PolicyAgent` broadcast, configurable `sentinel_count_per_segment`, and `build_hive_state()`.
- **`POST /simulate/hive`** (`app.py`) — NL parse via `build_scenario_from_prompt` → hive run → 7 engines via the registry → `ReportAgent` + a single Gemini narrative → schema-valid `SimulationState`. Also fixed `agents/ldrago_orchestrator.py` `llama_chat_text`→`kimi_chat_text` (unblocked the `/chat` fast path) and a `PopulationEngine` `int.items()` crash.
- **Frontend** — `HiveCommand.jsx` routed at `/hive` in `main.jsx`, `Math.random()` sentinels removed, repointed from `/chat` to `/simulate/hive`, renders real `brains[]`/`sentinels[]`/congestion `geojson` + a live telemetry panel; brutalist theme preserved.
- **Tests** — `tests/test_reasoning_gateway.py` (deterministic, offline, monkeypatched) proves the loop is LLM-driven (sentinels reason, brains distill real edge IDs, swarm inherits); `tests/test_hive_e2e.py` (live, skips without keys). **180 passing, 1 skipped.**

### Real-world finding: free-tier LLM limits
Live testing showed OpenRouter **free** model endpoints are heavily rate-limited and flap (`qwen3-4b:free`/`kimi-k2.6:free` lost free endpoints; gpt-oss-120b/gemma-4-31b were live), and Gemini's free quota was exhausted. The gateway degrades to physics and **always completes**; a live `/simulate/hive` run returned a valid `SimulationState` with `fallbacks=0` (real reasoning) at small scale. **Recommendation: add ~$5–10 OpenRouter credit** for reliable full-LLM demos at 49 sentinels. Repinned model IDs in `.env`/config to currently-live free models. Wrote `HIVE_ENGINE.md` (run guide).

### Project cleanup (legacy removal)
Removed (verified zero live imports first; all git-recoverable): `rendering-engine/` (357 MB standalone Cesium app), `archive/` (149 MB), `traffic-god/` legacy CV + its `/traffic-god/perception` endpoint + `traffic_god_bridge.py`, `services/` microservices + `docker-compose.yml` + the orphaned `tests/api/` suite, `external/` (F1 predictor), root `demo2/`, `llm_client.py`/`privacy_guard.py`/`train_models.py`, 201 `(file).md` code-graph artifacts, caches, and dead deps (camel-ai, sumolib, traci, opencv, ultralytics, norfair, stable-baselines3, gym, tensorboard, chromadb, gsap, maplibre-gl). **Kept** (user decision): `/demo`, `/demo2`, `/flyover` + `ai-flyover-sim/`, and `new_traffic_god` (the separate `/traffic-god-llm`). Structure left flat and documented in a rewritten `README.md`. **~520 MB freed.** Deploy configs (`Dockerfile`/`Procfile`/`render.yaml`, all `app:app` monolith) kept. Nothing committed.

### Standing rule: living docs (2026-07-01)
User set a global OVERHAUL convention: **every code/structure change updates `CONTEXT.md` + `HISTORY.md`; every discussion/decision adds a dated note to `CONTEXT.md`.** Saved as `feedback-doc-maintenance` in memory and as a `📋 MAINTENANCE PROTOCOL` banner at the top of `CONTEXT.md`.

### SSE live progress for /simulate/hive (2026-07-01)
Made the long (60–240 s) hive run watchable instead of an indeterminate bar:
- **`UrbanSwarm.on_event`** async callback + `_emit()` fire per-phase events inside `run()`/`_run_timestep_hive` (`start`, `sentinels`, `distill`, `timestep`).
- **`GET /simulate/hive/stream`** (SSE via `StreamingResponse`) runs `_run_hive` in a background task, drains an `asyncio.Queue`, and streams `data:` JSON per phase then a final `{"phase":"done","state":<SimulationState>}` (or `error`). `/simulate/hive` (POST) refactored to share `_run_hive(req, on_event)`.
- **`HiveCommand.jsx`** uses `EventSource` to drive the surgical trace + a pulsing live status line (`Step 2/4: 14 sentinels reasoned…`), applies the full `SimulationState` on `done`. Safe fallback: blocking POST only if SSE never connects (no double-spend); a mid-run drop reports instead of restarting.
- Verified: offline event-order test (`start → [sentinels·distill·timestep]×N → engines → report`), 180 tests still pass, frontend builds. Nothing committed.

### Surgical Command Center visuals — deck.gl rebuild (2026-07-01)
User picked "jaw-dropping visuals" as the next focus. Rebuilt `/hive` (`HiveCommand.jsx` + `HiveCommand.css`) into a GPU tactical interface:
- **deck.gl** (`deck.gl@9.3.5`) added to `landing-react`; used via `MapboxOverlay` (framework-agnostic control over the Mapbox dark map, pitched 55°, with fog).
- **Swarm particle-flow** (`ScatterplotLayer`, rAF-animated): particles flow along real congested corridors — **count ∝ real edge `flow`, speed ∝ real congestion, colour ∝ congestion**. Backend `swarm.py:_build_geojson` now emits `flow` + `capacity` per edge so density is honest (not a random count). ~2000 particles, `updateTriggers` re-reads positions each frame.
- **Surgical probes** (`ScatterplotLayer` halo + core): mood-colored, pulsing; `pickable` → click sets `selectedSentinel` → a floating **reasoning-trace panel** (why / route / mood / confidence).
- **Hive-mesh** (`ArcLayer`): each sentinel arcs to its segment-brain centroid, mood-colored — visualizes hive connectivity.
- **Panels**: glass-morphism (`backdrop-filter: blur`), per-brain SVG **confidence gauges**, a **HIVE MOOD** nav readout (dominant mood + % consensus), scanline overlay. Brutalist lime brand + Bebas Neue/Space Mono preserved.
- deck.gl loads only on `/hive` (lazy route) — no landing-page bloat. Frontend builds clean; 158 backend tests pass. Nothing committed.

### Browser verification (2026-07-02)
Ran `/hive` in a real browser (Playwright, backend+vite live). Confirmed: shell/glass-panels/gauges/HIVE-MOOD render to spec, **0 console errors**, deck.gl overlay canvas active (2 canvases), SSE live progress advances (SENSING→REASONING…), backend hive executes with real LLM 200s interleaved with graceful 429 backoff. **Bug found + fixed:** `dark-v11` style loaded but rendered light on this Mapbox token → added `.hive-command .mapboxgl-canvas { filter: brightness(0.32) saturate(0.55) contrast(1.12) }` (darkens only the base map, not the deck overlay) → proper dark tactical void. Swarm-particle render not screenshot-captured (a live run stayed mid-flight for minutes under free-tier 429 throttling — the known constraint; particle pipeline is unit-tested). Left dev servers running (uvicorn :8000, vite :5173). Nothing committed.

### UI redesign v2 — cinematic + editorial (2026-07-02)
User was not satisfied with the v1 dashboard (boxy panels / cheap / wrong aesthetic / generic layout). Chose a mix of "cinematic command-palette" + "editorial split". Fully rebuilt `HiveCommand.jsx` + `HiveCommand.css` (new `hc-*` system): full-bleed dark map hero + vignette/grain depth; thin quiet top bar; a glass **spotlight command bar** (bottom-center) as the single input; a big **Bebas display idle hero** ("Simulate reality / before you change it", lime used only on the italic word + kicker + RUN); on-result an **editorial briefing** aside — huge verdict headline (color by approve/conditional/reject), big-number metrics, the LLM brief in Inter body, recommendations, and a compact 7-segment "hive strip"; restyled floating probe card. Palette restrained (near-black, lime sparingly), 3-font system (Bebas display / Inter body / Space Mono labels). Removed the chat log (result = the briefing). **Browser-verified the idle state** (Playwright, 0 console errors — dramatically more premium); production build clean. Editorial-briefing state pending a completed run to screenshot. Nothing committed.
