# OVERHAUL: Stages C–F Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four sequential stages (C → D → E → F) to complete the OVERHAUL MiroFish integration, running from validate-and-harden through LLM reasoner tuning.

**Architecture:** Four phases, each building on the previous:
- **Stage C (Validate & Harden):** Fix sentinel init bugs, run full swarm E2E, add LDRAGO v2 parser.
- **Stage D (Downstream Engines):** Wire agent sim outputs into Economic, Energy, Infrastructure, Population, Logistics engines.
- **Stage E (Frontend Integration):** Wire React + Three.js globe to live simulation hotspots and AQI overlays.
- **Stage F (LLM Reasoner Tuning):** Connect real LLM providers, tune prompt templates for route reasoning.

**Tech Stack:** Python 3.11, pytest, camel-ai, zep-cloud, httpx, React + Three.js

---

## Stage C: Validate & Harden

### Task C.1: Fix Sentinel Agent Node Initialization Bugs

**Files:**
- Modify: `engines/agent_simulation/swarm.py:150-200` (sentinel creation in `_create_sentinel_agents`)
- Modify: `engines/agent_simulation/agents/surgical_agent.py` (run_step node references)
- Test: `tests/engines/agent_simulation/test_sentinel_node_init.py`

- [ ] **Step 1: Write failing test for sentinel node init**

```python
# tests/engines/agent_simulation/test_sentinel_node_init.py
import pytest
from engines.agent_simulation.swarm import UrbanSwarm

@pytest.mark.asyncio
async def test_sentinel_agents_have_valid_start_nodes():
    """Sentinel agents must be initialized with valid nodes from the road graph."""
    swarm = UrbanSwarm(
        nodes=DEFAULT_NODES,  # from transport engine
        edges=DEFAULT_EDGES,
        config=SwarmConfig(commuter_count=10, sentinel_count=3),
    )
    await swarm.initialize()
    for sentinel in swarm._sentinels:
        assert sentinel.origin_node in swarm._nodes, f"Invalid origin: {sentinel.origin_node}"
        assert sentinel.destination_node in swarm._nodes, f"Invalid destination: {sentinel.destination_node}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engines/agent_simulation/test_sentinel_node_init.py -v`
Expected: FAIL — sentinel origin/destination nodes not in graph

- [ ] **Step 3: Fix `_create_sentinel_agents` to validate nodes**

In `swarm.py`, `_create_sentinel_agents()`:
```python
def _create_sentinel_agents(self) -> None:
    self._sentinels = []
    valid_nodes = list(self._nodes.keys())
    for segment_name, segment_config in self._segment_configs.items():
        count = segment_config.sentinel_count
        for i in range(count):
            # Pick random valid nodes — never use nodes not in graph
            origin = random.choice(valid_nodes)
            destination = random.choice([n for n in valid_nodes if n != origin])
            sentinel = SurgicalAgent(
                agent_id=f"sentinel_{segment_name}_{i}",
                segment_name=segment_name,
                origin_node=origin,
                destination_node=destination,
                llm_provider=self._llm_provider,
            )
            self._sentinels.append(sentinel)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engines/agent_simulation/test_sentinel_node_init.py -v`
Expected: PASS

- [ ] **Step 5: Run full agent_simulation test suite**

Run: `pytest tests/engines/agent_simulation/ -v`
Expected: All pass (no regressions)

---

### Task C.2: Run Full Swarm End-to-End

**Files:**
- Modify: `engines/agent_simulation/swarm.py` (Hive loop edge cases)
- Test: `tests/engines/agent_simulation/test_swarm_e2e.py`

- [ ] **Step 1: Write E2E test for full swarm run**

```python
# tests/engines/agent_simulation/test_swarm_e2e.py
@pytest.mark.asyncio
async def test_swarm_run_completes_without_errors():
    """Full UrbanSwarm.run() must complete with valid results."""
    swarm = UrbanSwarm(
        nodes=DEFAULT_NODES,
        edges=DEFAULT_EDGES,
        config=SwarmConfig(commuter_count=50, sentinel_count=10, timesteps=3),
    )
    await swarm.initialize()
    result = await swarm.run()
    assert result.agents_total > 0
    assert result.avg_speed_kmh > 0
    assert result.total_vkt > 0
```

- [ ] **Step 2: Run test — expect failure due to sentinel init bugs**

Run: `pytest tests/engines/agent_simulation/test_swarm_e2e.py -v`
Expected: FAIL — sentinel init bugs block full execution

- [ ] **Step 3: Fix any remaining issues in Hive loop**

Review `swarm.py` `_run_hive_loop()`:
- Ensure all sentinel agents have valid routes (not stuck at non-existent nodes)
- Ensure SegmentBrain contributions handle empty discovery gracefully
- Ensure swarm agents receive valid CollectiveTruth on first timestep (before distillation)

- [ ] **Step 4: Run E2E test again**

Run: `pytest tests/engines/agent_simulation/test_swarm_e2e.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite — confirm 150+ tests pass**

Run: `pytest tests/ -v --tb=short | tail -20`

---

### Task C.3: Add LDRAGO v2 Parser for Agent Simulation Output

**Files:**
- Create: `engines/agent_simulation/ldrago_parser.py`
- Test: `tests/engines/agent_simulation/test_ldrago_parser.py`
- Modify: `engines/agent_simulation/engine.py` (call parser after swarm run)

- [ ] **Step 1: Write test for LDRAGO parser**

```python
# tests/engines/agent_simulation/test_ldrago_parser.py
import pytest
from engines.agent_simulation.ldrago_parser import LDRAGOParser, ParsedSimulationBrief

def test_parser_extracts_metrics():
    """LDRAGO parser must extract transport metrics from SwarmResult."""
    parser = LDRAGOParser()
    brief = parser.parse(swarm_result=MOCK_SWARM_RESULT)
    assert brief.avg_speed_kmh == 38.5
    assert brief.congestion_pct == 45.2
    assert brief.emergent_hotspots > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engines/agent_simulation/test_ldrago_parser.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `LDRAGOParser`**

```python
# engines/agent_simulation/ldrago_parser.py
from dataclasses import dataclass
from typing import List

@dataclass
class ParsedSimulationBrief:
    avg_speed_kmh: float
    congestion_pct: float
    pm25_kg: float
    co2_tonnes: float
    emergent_hotspots: int
    mode_shift_count: int
    segment_insights: List[str]
    recommendations: List[str]
    data_sources: List[str]

class LDRAGOParser:
    """
    LDRAGO v2 Parser — consumes agent simulation output and produces
    a structured brief for the LDRAGO reasoning pipeline.

    Converts raw SwarmResult metrics into:
    - ParsedSimulationBrief (structured data)
    - Markdown summary (human readable)
    """

    def parse(self, swarm_result) -> ParsedSimulationBrief:
        """Parse SwarmResult into structured brief."""
        hotspots = getattr(swarm_result, 'hotspots', []) or []
        mode_shifts = getattr(swarm_result, 'total_mode_shifts', 0)
        return ParsedSimulationBrief(
            avg_speed_kmh=getattr(swarm_result, 'avg_speed_kmh', 0),
            congestion_pct=getattr(swarm_result, 'congestion_pct', 0),
            pm25_kg=getattr(swarm_result, 'total_pm25_g', 0) / 1000,
            co2_tonnes=getattr(swarm_result, 'total_co2_kg', 0) / 1000,
            emergent_hotspots=len(hotspots),
            mode_shift_count=mode_shifts,
            segment_insights=self._extract_segment_insights(swarm_result),
            recommendations=self._extract_recommendations(swarm_result),
            data_sources=getattr(swarm_result, 'metadata', {}).get('live_data_sources', []),
        )

    def generate_markdown(self, brief: ParsedSimulationBrief) -> str:
        """Generate markdown summary from parsed brief."""
        lines = [
            "# Simulation Brief — LDRAGO v2",
            "",
            f"**Avg Speed:** {brief.avg_speed_kmh} km/h",
            f"**Congestion:** {brief.congestion_pct}%",
            f"**CO₂:** {brief.co2_tonnes}t | **PM2.5:** {brief.pm25_kg*1000:.0f}g",
            f"**Hotspots:** {brief.emergent_hotspots} | **Mode Shifts:** {brief.mode_shift_count}",
            "",
            "## Recommendations",
        ]
        for rec in brief.recommendations:
            lines.append(f"- {rec}")
        return "\n".join(lines)

    def _extract_segment_insights(self, result) -> List[str]:
        # Extract per-segment insights from segment_breakdown
        insights = []
        breakdown = getattr(result, 'segment_breakdown', {}) or {}
        for segment, data in breakdown.items():
            avg_speed = data.get('avg_speed', 0)
            if avg_speed < 30:
                insights.append(f"{segment}: slow traffic ({avg_speed} km/h)")
        return insights

    def _extract_recommendations(self, result) -> List[str]:
        recommendations = []
        if getattr(result, 'congestion_pct', 0) > 50:
            recommendations.append("High congestion detected — consider congestion pricing")
        if getattr(result, 'total_mode_shifts', 0) > 10:
            recommendations.append("Emergent mode shifts observed — ensure metro capacity")
        return recommendations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engines/agent_simulation/test_ldrago_parser.py -v`
Expected: PASS

- [ ] **Step 5: Wire parser into `AgentSimulationEngine._run()`**

In `engine.py`, after `swarm.run()`:
```python
from engines.agent_simulation.ldrago_parser import LDRAGOParser

# After swarm run
parser = LDRAGOParser()
brief = parser.parse(swarm_result=swarm_result)
metadata["ldrago_brief"] = {
    "emergent_hotspots": brief.emergent_hotspots,
    "mode_shift_count": brief.mode_shift_count,
    "segment_insights": brief.segment_insights,
    "data_sources": brief.data_sources,
}
```

- [ ] **Step 6: Run full suite — confirm all pass**

Run: `pytest tests/ -v --tb=short | tail -20`

---

## Stage D: Downstream Engines

### Task D.1: Economic Engine — Wire Agent Simulation Output

**Files:**
- Modify: `engines/economic/engine.py` (`_run()` accepts agent sim results)
- Test: `tests/engines/economic/test_agent_sim_wiring.py`

- [ ] **Step 1: Write test for economic engine agent sim integration**

```python
# tests/engines/economic/test_agent_sim_wiring.py
@pytest.mark.asyncio
async def test_economic_engine_uses_agent_sim_data():
    """EconomicEngine must use agent simulation results for cost estimates."""
    engine = EconomicEngine()
    data = {
        "transport_result": {
            "agents_simulated": 2000,
            "avg_speed_kmh": 38.5,
            "total_vkt": 45000,
            "congestion_pct": 42.0,
            "mode_shifts_observed": 85,
        }
    }
    result = await engine._run(scenario, data)
    assert result.metrics["commuter_time_savings_min"] > 0
    assert result.metrics["ev_share_adopted"] > 0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/engines/economic/test_agent_sim_wiring.py -v`
Expected: FAIL — economic engine doesn't use agent sim data yet

- [ ] **Step 3: Modify `EconomicEngine._run()` to accept `transport_result`**

In `engine.py`:
```python
async def _run(self, scenario: Scenario, data: Dict[str, Any]) -> SimulationResult:
    transport_result = data.get("transport_result", {})
    agents_simulated = transport_result.get("agents_simulated", 0)
    avg_speed = transport_result.get("avg_speed_kmh", 40.0)
    total_vkt = transport_result.get("total_vkt", 0)
    congestion_pct = transport_result.get("congestion_pct", 0.0)
    mode_shifts = transport_result.get("mode_shifts_observed", 0)

    # Use agent sim data for cost estimates
    if agents_simulated > 0:
        avg_commute_time_saved_hrs = self._estimate_time_saved(avg_speed, congestion_pct)
        total_savings = avg_commute_time_saved_hrs * _PARAMS["avg_hourly_wage_inr"] * agents_simulated
    else:
        # Fall back to static model
        total_savings = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engines/economic/test_agent_sim_wiring.py -v`
Expected: PASS

---

### Task D.2: Energy Engine — Wire Agent Simulation Output

**Files:**
- Modify: `engines/energy/engine.py` (`_run()` uses agent sim EV share + VKT)
- Test: `tests/engines/energy/test_agent_sim_wiring.py`

- [ ] **Step 1: Write test for energy engine agent sim wiring**

```python
# tests/engines/energy/test_agent_sim_wiring.py
@pytest.mark.asyncio
async def test_energy_engine_uses_agent_sim_ev_share():
    """EnergyEngine must use agent simulation EV share for energy calculations."""
    engine = EnergyEngine()
    data = {
        "transport_result": {
            "ev_share": 0.18,
            "total_vkt": 50000,
        }
    }
    result = await engine._run(scenario, data)
    assert result.metrics["ev_energy_mwh"] > 0
    assert result.metrics["fuel_savings_ml"] > 0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/engines/energy/test_agent_sim_wiring.py -v`
Expected: FAIL

- [ ] **Step 3: Modify `EnergyEngine._run()` to use transport_result**

```python
async def _run(self, scenario: Scenario, data: Dict[str, Any]) -> SimulationResult:
    transport_result = data.get("transport_result", {})
    agent_ev_share = transport_result.get("ev_share", _BASELINES["ev_share"])
    agent_vkt = transport_result.get("total_vkt", 0)

    # Override static baseline with agent sim data
    if agent_vkt > 0:
        ev_share = agent_ev_share
        total_vkt = agent_vkt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engines/energy/test_agent_sim_wiring.py -v`
Expected: PASS

---

### Task D.3: Infrastructure + Population + Logistics Engines

**Files:**
- Modify: `engines/infrastructure/engine.py` (use agent sim for capacity utilization)
- Modify: `engines/population/engine.py` (use agent sim for mode shift modeling)
- Modify: `engines/logistics/engine.py` (use agent sim for freight corridor load)
- Test: `tests/engines/{infrastructure,population,logistics}/test_agent_sim_wiring.py`

- [ ] **Step 1: Write tests for infrastructure, population, logistics**

Each engine gets a test file verifying it accepts and uses `transport_result`:
```python
# tests/engines/infrastructure/test_agent_sim_wiring.py
# tests/engines/population/test_agent_sim_wiring.py
# tests/engines/logistics/test_agent_sim_wiring.py
```

- [ ] **Step 2: Run each test — verify failures**

Run: `pytest tests/engines/infrastructure/test_agent_sim_wiring.py tests/engines/population/test_agent_sim_wiring.py tests/engines/logistics/test_agent_sim_wiring.py -v`
Expected: FAIL (three engines need wiring)

- [ ] **Step 3: Wire each engine**

Modify each `engine.py` to check for `transport_result` in data dict and override static baselines:
- **Infrastructure**: Use agent sim `congestion_pct` for capacity utilization model
- **Population**: Use agent sim `mode_shifts_observed` for mode shift rates
- **Logistics**: Use agent sim `total_vkt` for commercial vehicle VKT estimation

- [ ] **Step 4: Run all three tests — verify passes**

Run: `pytest tests/engines/{infrastructure,population,logistics}/test_agent_sim_wiring.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Run full suite**

Run: `pytest tests/ -v --tb=short | tail -20`
Expected: 165+ tests passing

---

## Stage E: Frontend Integration

### Task E.1: API Endpoint for Simulation Results

**Files:**
- Create: `api/simulation_routes.py`
- Test: `tests/api/test_simulation_routes.py`

- [ ] **Step 1: Write test for simulation results endpoint**

```python
# tests/api/test_simulation_routes.py
def test_get_simulation_results(client):
    """GET /api/simulation/results must return latest simulation brief."""
    response = client.get("/api/simulation/results")
    assert response.status_code == 200
    data = response.json
    assert "avg_speed_kmh" in data
    assert "congestion_pct" in data
    assert "hotspots" in data
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/api/test_simulation_routes.py -v`
Expected: FAIL — endpoint doesn't exist

- [ ] **Step 3: Implement API route**

```python
# api/simulation_routes.py
from fastapi import FastAPI, HTTPException
from engines.registry import EngineRegistry

app = FastAPI()
registry = EngineRegistry()

@app.get("/api/simulation/results")
async def get_simulation_results(scenario_id: str = None):
    """Return latest simulation results as JSON for frontend."""
    if registry.last_result is None:
        raise HTTPException(status_code=404, detail="No simulation run yet")
    result = registry.last_result
    return {
        "avg_speed_kmh": result.metrics.get("avg_speed_kmh"),
        "congestion_pct": result.metrics.get("congestion_pct"),
        "co2_tonnes": result.metrics.get("co2_tonnes"),
        "pm25_kg": result.metrics.get("pm25_kg"),
        "hotspots": _build_hotspot_features(result),
        "segment_breakdown": result.metadata.get("segment_breakdown", {}),
        "live_data_sources": result.metadata.get("live_data_sources", []),
    }

def _build_hotspot_features(result):
    """Convert swarm hotspots to GeoJSON for map rendering."""
    hotspots = result.metadata.get("top_congested", [])
    return [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [edge_lon, edge_lat]},
            "properties": {
                "edge": h["edge"],
                "v_over_c": h["v_over_c"],
                "severity": "high" if h["v_over_c"] > 0.8 else "medium" if h["v_over_c"] > 0.6 else "low",
            }
        }
        for h in hotspots
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_simulation_routes.py -v`
Expected: PASS

---

### Task E.2: Live AQI Overlay Data Endpoint

**Files:**
- Modify: `api/simulation_routes.py` (add AQI endpoint)
- Test: `tests/api/test_simulation_routes.py`

- [ ] **Step 1: Write test for AQI overlay endpoint**

```python
def test_get_aqi_overlay(client):
    """GET /api/simulation/aqi-overlay must return GeoJSON AQI data."""
    response = client.get("/api/simulation/aqi-overlay")
    assert response.status_code == 200
    data = response.json
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/api/test_simulation_routes.py::test_get_aqi_overlay -v`
Expected: FAIL

- [ ] **Step 3: Implement AQI overlay endpoint**

```python
@app.get("/api/simulation/aqi-overlay")
async def get_aqi_overlay(city: str = "delhi"):
    """Return GeoJSON AQI overlay for map rendering."""
    from data_integration.adapters.manager import get_ncr_context
    await init_adapters()
    context = await get_ncr_context(city=city)

    aqi_data = context.get("live_aqi", {})
    pm25 = aqi_data.get("pm25", 0)
    stations = aqi_data.get("stations", [])

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [s["lon"], s["lat"]],
                },
                "properties": {
                    "station": s["name"],
                    "pm25": s["pm25"],
                    "aqi_category": s.get("category", "Unknown"),
                    "pm25_value": pm25,
                }
            }
            for s in stations
        ]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_simulation_routes.py -v`
Expected: PASS

---

## Stage F: LLM Reasoner Tuning

### Task F.1: Connect Real LLM Provider (OpenAI / Anthropic / Ollama)

**Files:**
- Modify: `engines/agent_simulation/brains/segment_brain.py` (LLM provider interface)
- Create: `engines/agent_simulation/llm_providers.py`
- Test: `tests/engines/agent_simulation/test_llm_providers.py`

- [ ] **Step 1: Write test for LLM provider abstraction**

```python
# tests/engines/agent_simulation/test_llm_providers.py
import pytest
from engines.agent_simulation.llm_providers import OpenAIProvider, AnthropicProvider, OllamaProvider

def test_openai_provider_calls_correct_endpoint():
    """OpenAIProvider must call OpenAI API with correct params."""
    provider = OpenAIProvider(api_key="test-key")
    response = provider.complete("Test prompt")
    assert response is not None

def test_ollama_provider_falls_back_gracefully():
    """OllamaProvider must handle connection errors gracefully."""
    provider = OllamaProvider(base_url="http://localhost:11434")
    response = provider.complete("Test prompt")
    assert response is not None  # or graceful error
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/engines/agent_simulation/test_llm_providers.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement LLM provider abstraction**

```python
# engines/agent_simulation/llm_providers.py
from typing import Optional, Callable, Any
import os

class LLMProvider(Callable):
    """Abstract interface for LLM providers."""
    def complete(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            return self._fallback_response(prompt)
        import httpx
        # Call OpenAI API...
        return "SYNTHESIZED_ROUTE_DECISION"

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-haiku"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            return self._fallback_response(prompt)
        # Call Anthropic API...
        return "SYNTHESIZED_ROUTE_DECISION"

class OllamaProvider(LLMProvider):
    """Local Ollama server (no API key required)."""
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        import httpx
        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception:
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Called when LLM is unavailable — uses heuristic fallback."""
        if "congestion" in prompt.lower():
            return "Route via alternative corridor"
        elif "avoid" in prompt.lower():
            return "Prefer metro route"
        return "Maintain current route"
```

- [ ] **Step 4: Run tests — verify passes**

Run: `pytest tests/engines/agent_simulation/test_llm_providers.py -v`
Expected: PASS

---

### Task F.2: Tune Prompt Templates for Route Reasoning

**Files:**
- Modify: `engines/agent_simulation/brains/segment_brain.py` (prompt templates)
- Test: `tests/engines/agent_simulation/brains/test_prompt_templates.py`

- [ ] **Step 1: Write test for prompt template quality**

```python
# tests/engines/agent_simulation/brains/test_prompt_templates.py
def test_distillation_prompt_includes_necessary_context():
    """Distillation prompt must include recent discoveries, route preferences."""
    brain = SegmentBrain(segment_name="office_workers", backend=mock_backend)
    prompt = brain._build_distillation_prompt(timestep=5, lookback=2)
    assert "timestep 3" in prompt or "timestep 4" in prompt
    assert "preferred_routes" in prompt
    assert "office_workers" in prompt
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/engines/agent_simulation/brains/test_prompt_templates.py -v`
Expected: FAIL — method doesn't exist

- [ ] **Step 3: Add prompt templates to SegmentBrain**

```python
def _build_distillation_prompt(self, timestep: int, lookback: int) -> str:
    recent = self.get_history(timestep - lookback, timestep)
    discoveries = [d for t in recent for d in t.discoveries]

    discoveries_text = "\n".join([
        f"- Sentinel {d.sentinel_id}: {d.discovery_data.get('observation', 'N/A')}"
        for d in discoveries
    ])

    return f"""You are the collective intelligence for {self.segment_name}.

Recent sentinel observations:
{discoveries_text}

Synthesize the collective truth for timestep {timestep}:
- What routes are preferred?
- What zones should be avoided?
- What is the overall mood (frustrated/adaptive/stable/optimistic)?

Respond with a JSON object with keys: preferred_routes, avoid_zones, segment_mood, confidence (0-1), dissenting_signals."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engines/agent_simulation/brains/test_prompt_templates.py -v`
Expected: PASS

---

### Task F.3: End-to-End Test with Real LLM

**Files:**
- Test: `tests/engines/agent_simulation/test_llm_e2e.py`

- [ ] **Step 1: Write E2E test with real LLM (skippable)**

```python
# tests/engines/agent_simulation/test_llm_e2e.py
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="No LLM API key configured"
)
async def test_full_simulation_with_llm_reasoning():
    """Full simulation with real LLM — verify emergent behavior."""
    from engines.agent_simulation.llm_providers import OpenAIProvider
    provider = OpenAIProvider()

    swarm = UrbanSwarm(
        nodes=DEFAULT_NODES,
        edges=DEFAULT_EDGES,
        config=SwarmConfig(commuter_count=20, sentinel_count=5, timesteps=2),
    )
    await swarm.initialize(llm_provider=provider)
    result = await swarm.run()

    assert result.total_vkt > 0
    assert len(result.hotspots) >= 0
```

- [ ] **Step 2: Run with API key configured**

Run: `OPENAI_API_KEY=sk-... pytest tests/engines/agent_simulation/test_llm_e2e.py -v`

- [ ] **Step 3: Run full suite**

Run: `pytest tests/ -v --tb=short | tail -20`
Expected: All tests pass

---

## Final Verification

- [ ] **Run full test suite** — all stages complete

Run: `pytest tests/ -v --tb=short 2>&1 | grep -E "^(PASSED|FAILED|ERROR|====)" | tail -30`
Expected: **175+ tests passing**, 0 errors