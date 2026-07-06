# Design Spec: MiroFish Integration (Stage A)
Date: 2026-04-13
Status: APPROVED

## 1. Goal
Transition OVERHAUL from a deterministic physics calculator to an emergent reasoning world. Implement "Thinking Agents" using the Sentinel-Swarm-Hive architecture to enable high-fidelity stress testing and systemic flow analysis.

## 2. Architecture: The Sentinel-Swarm-Hive Model

### 2.1 The Hive Loop (Logic Flow)
The simulation proceeds in a cycle of discovery, distillation, and execution:

1. **Policy Broadcast**: `PolicyAgent` (Autonomous Regulatory Monitor) $\rightarrow$ Global KG + Segment Brains.
2. **Sentinel Reasoning**: $\approx 50$ `SurgicalAgents` read physics state + Segment Brain $\rightarrow$ LLM Reason $\rightarrow$ Act $\rightarrow$ write {action, why, result} to Segment Brain.
3. **Hive Distillation (Sync LLM)**: `SegmentBrain` synthesizes recent discoveries into a `CollectiveTruth` for the timestep.
4. **Swarm Execution**: $2000+$ `SwarmAgents` read `CollectiveTruth` $\rightarrow$ Dijkstra + Weight Adjustments $\rightarrow$ Move.
4. **Swarm Feedback Write (Stats)**: Aggregate swarm choices $\rightarrow$ write collective movement stats back to Segment Brain (no LLM).
5. **Physics Update**: BPR recomputes travel times based on new flows $\rightarrow$ state updated for next cycle.

### 2.2 Component Specifications

#### A. The Brains (Zep/Graphiti Backed)
**`SegmentBrain`**:
- `contribute_discovery(sentinel_id: int, timestep: int, discovery_data: dict)`: Tags and stores discoveries.
- `distill_collective_truth(timestep: int, lookback: int = 1) -> CollectiveTruth`: LLM synthesis of the current window.
- `update_swarm_stats(timestep: int, stats_data: dict)`: Records aggregate swarm behavior.
- `get_current_truth() -> CollectiveTruth`: Returns cached latest distilled truth.
- `get_history(from_timestep: int, to_timestep: int) -> List[CollectiveTruth]`: Timeline for `ReportAgent`.

**`CollectiveTruth` (Pydantic/Dataclass)**:
- `timestep`: `int`
- `preferred_routes`: `List[str]` (Ranked edge IDs)
- `avoid_zones`: `List[str]` (Edge IDs to penalize)
- `segment_mood`: `str` (frustrated/adaptive/stable/optimistic)
- `confidence`: `float` (0-1)
- `dissenting_signals`: `List[str]` (Contradictory findings)

**`GlobalKnowledgeGraph`**:
- `sync_from_policy_agent(data)`: Updates laws/budgets.
- `semantic_query(query)`: GraphRAG entry point for Sentinels.

#### B. The Agents
**`SurgicalAgent` (Sentinel)**:
- **Brain**: Full LLM + Zep Persona + Personal Memory.
- **Loop**: `asyncio.gather(kg_query, brain_query)` $\rightarrow$ LLM Reason $\rightarrow$ Act $\rightarrow$ write to `SegmentBrain`.

**`SwarmAgent` (Collective)**:
- **Brain**: Physics + Hive-Inheritance.
- **Loop**: Read physics state $\rightarrow$ Read `SegmentBrain.get_current_truth()` $\rightarrow$ apply weights $\rightarrow$ move.

---

## 3. Error Handling & Degradation

- **Zep Connection Failure**: Fallback to `LocalKnowledgeGraph` and `LocalSegmentBrain` (in-memory). Sets `BACKEND_DEGRADED` flag.
- **LLM Timeout/Rate Limit**:
    - **Sentinels**: Fallback to physics-only Dijkstra move. Log `NON_FATAL_ERROR`.
    - **Distillation**: Retain `CollectiveTruth` from previous timestep; mark as `stale=True`.
- **Sentinel Crash**: Agent is removed from current pool. Logged as `SENTINEL_DROPPED`.

---

## 4. Testing Strategy (TDD)

No production code without a failing test for:
1. **Distillation Conflict**: 2 "Fast" vs 1 "Blocked" $\rightarrow$ preferred_routes has Route A, but `dissenting_signals` is non-empty.
2. **Swarm Inheritance**: `avoid_zones` in `CollectiveTruth` $\rightarrow$ `SwarmAgent` avoids the edge.
3. **Async Convergence**: 50 concurrent Sentinel queries $\rightarrow$ resolve within 2s without deadlocks.
4. **Cross-run Persistence**: Terminate at T5 $\rightarrow$ Start new run $\rightarrow$ Sentinel inherits memory.

---

## 5. Backend Strategy

### 5.1 Interface Isolation
All Zep/Graphiti interactions must be behind a `KnowledgeGraphBackend` abstract base class.
`SurgicalAgent` and `SegmentBrain` must only interact with the interface, never the SDK.

### 5.2 Migration Path
1. **Current**: Use `ZepBackend` (Zep Cloud) for initial validation and TDD.
2. **Validation**: All 4 TDD tests pass against Zep.
3. **Swap**: Replace `ZepBackend` with `GraphitiBackend` (Graphiti + Kuzu) for a fully local, zero-cost production deployment.
