"""Bridge between the gateway and the agent/hive domain types.

Provides:
  * the **edge-ID vocabulary** (the 28 directed Delhi-NCR edges) that every LLM
    output is constrained to — without this the model emits prose route names
    that silently no-op, which is exactly the "theater" we are removing;
  * **strict coercion** of raw LLM JSON into a sentinel decision dict or a
    ``CollectiveTruth`` (drops out-of-vocab edges, clamps confidence, maps mood
    into ``VALID_MOODS`` so ``CollectiveTruth.__post_init__`` never raises);
  * ``make_sentinel_provider`` — a per-agent ``async (context) -> decision``
    callable that satisfies ``SurgicalAgent``'s provider contract by deferring
    to the gateway (used as a fallback path; the swarm primarily batches via
    ``gateway.reason_many``).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from engines.transport.engine import _DEFAULT_NODES, _DEFAULT_EDGES
from engines.agent_simulation.brains.collective_truth import CollectiveTruth, VALID_MOODS

_VALID_EDGES: frozenset[str] = frozenset(
    f"{e['u']}->{e['v']}" for e in _DEFAULT_EDGES
)


def valid_edge_ids() -> frozenset[str]:
    """The frozen set of legal ``origin->dest`` edge IDs (28 directed edges)."""
    return _VALID_EDGES


def node_coords(node_id: str) -> Optional[List[float]]:
    """Return ``[lon, lat]`` for a node id (GeoJSON order), or None."""
    n = _DEFAULT_NODES.get(node_id)
    if not n:
        return None
    return [n["lon"], n["lat"]]


def _clean_edges(items: Any, valid: frozenset[str]) -> List[str]:
    out: List[str] = []
    if isinstance(items, str):
        items = [items]
    if not isinstance(items, (list, tuple)):
        return out
    for x in items:
        if isinstance(x, str) and x in valid and x not in out:
            out.append(x)
    return out


def _clamp_conf(value: Any, default: float = 0.5) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _clean_mood(value: Any) -> str:
    return value if value in VALID_MOODS else "stable"


def coerce_decision(parsed: Optional[dict], valid: frozenset[str]) -> Dict[str, Any]:
    """Coerce a raw per-agent LLM object into a safe sentinel decision dict."""
    parsed = parsed or {}
    route = _clean_edges(parsed.get("route"), valid)
    avoid = _clean_edges(parsed.get("avoid") or parsed.get("avoid_zones"), valid)
    return {
        "action": "take_route",
        "route": route,
        "avoid": avoid,
        "mood": _clean_mood(parsed.get("mood") or parsed.get("segment_mood")),
        "confidence": _clamp_conf(parsed.get("confidence")),
        "why": str(parsed.get("why") or parsed.get("reason") or "")[:240],
        "fallback": not route,
    }


def coerce_truth(parsed: Optional[dict], timestep: int, valid: frozenset[str]) -> CollectiveTruth:
    """Coerce a raw per-segment LLM object into a valid ``CollectiveTruth``."""
    parsed = parsed or {}
    dissent = [str(d)[:120] for d in (parsed.get("dissenting_signals") or []) if d][:5]
    return CollectiveTruth(
        timestep=timestep,
        preferred_routes=_clean_edges(parsed.get("preferred_routes"), valid),
        avoid_zones=_clean_edges(parsed.get("avoid_zones"), valid),
        segment_mood=_clean_mood(parsed.get("segment_mood") or parsed.get("mood")),
        confidence=_clamp_conf(parsed.get("confidence")),
        dissenting_signals=dissent,
        stale=False,
    )


def make_sentinel_provider(gateway, valid: Optional[frozenset[str]] = None) -> Callable:
    """Return an ``async (context) -> decision`` provider backed by the gateway.

    Matches ``SurgicalAgent.llm_provider``'s contract. The swarm mostly uses the
    batched ``gateway.reason_many`` path directly; this single-agent provider is
    retained so ``SurgicalAgent.think()`` still works standalone (and in tests).
    """
    edges = valid or _VALID_EDGES

    async def provider(context: dict) -> Dict[str, Any]:
        agent_id = context.get("agent_id", 0)
        return await gateway.reason(agent_id=agent_id, context=context, kind="sentinel", valid_edges=edges)

    return provider
