"""Batched-prompt builders + response splitters.

Coalescing K agents (or K segments) into ONE ``llm_chat_json`` call is what
turns 50 sentinel calls into ~7, and 7 distillations into ~1 — the difference
between surviving and 429-ing on a free tier. Each builder returns
``(system, prompt)``; each splitter maps the model's JSON array back to the
original request order by an explicit integer/segment key.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _edge_menu(valid_edges: Sequence[str]) -> str:
    return ", ".join(sorted(valid_edges))


def _congestion_line(congestion: Dict[str, float]) -> str:
    if not congestion:
        return "nominal"
    top = sorted(congestion.items(), key=lambda kv: -kv[1])[:6]
    return ", ".join(f"{eid}={int(round(ratio * 100))}%" for eid, ratio in top)


def build_sentinel_batch(reqs: Sequence[Any], world: dict) -> tuple[str, str]:
    """Build one prompt that decides routes for up to K commuter sentinels."""
    valid = world.get("valid_edges", [])
    system = (
        "You are the routing cortex for individual Delhi-NCR commuters. For each "
        "agent choose a realistic route as an ORDERED list of edge IDs from "
        "origin to destination, plus any edges to avoid. "
        f"USE ONLY THESE EDGE IDS (format 'origin->dest'): {_edge_menu(valid)}. "
        "Reason like a frustrated human in traffic. Respond with STRICT JSON only:\n"
        '{"decisions":[{"i":0,"route":["a->b","b->c"],"avoid":["x->y"],'
        '"mood":"frustrated|adaptive|stable|optimistic","confidence":0.0-1.0,'
        '"why":"one short sentence"}]}\n'
        "Return exactly one object per agent, keyed by its integer index i."
    )
    lines = [
        f"Live congestion: {_congestion_line(world.get('congestion', {}))}.",
        f"Decide for {len(reqs)} agents:",
    ]
    for idx, r in enumerate(reqs):
        c = r.context
        lines.append(
            f"i={idx} segment={c.get('segment')} from={c.get('origin')} "
            f"to={c.get('destination')} hive_mood={c.get('mood', 'stable')} "
            f"hive_prefers={list(c.get('preferred', []))[:2]}"
        )
    return system, "\n".join(lines)


def split_sentinel_batch(resp: Any, n: int) -> List[Optional[dict]]:
    out: List[Optional[dict]] = [None] * n
    decisions = resp.get("decisions") if isinstance(resp, dict) else None
    if isinstance(decisions, list):
        for d in decisions:
            if not isinstance(d, dict):
                continue
            try:
                i = int(d.get("i"))
            except (TypeError, ValueError):
                continue
            if 0 <= i < n:
                out[i] = d
    return out


def build_distill_batch(items: Sequence[Any], world: dict) -> tuple[str, str]:
    """Build one prompt that distills CollectiveTruth for up to 7 segments.

    Each item is ``(segment_name, discoveries_text)``.
    """
    valid = world.get("valid_edges", [])
    system = (
        "You are the Hive distiller. For each Delhi-NCR population segment, "
        "synthesize its sentinels' discoveries into a collective truth: which "
        "edges to prefer, which to avoid, the segment's mood, a confidence, and "
        "any dissenting signals. "
        f"USE ONLY THESE EDGE IDS: {_edge_menu(valid)}. "
        "Respond with STRICT JSON only:\n"
        '{"truths":[{"segment":"office_workers","preferred_routes":["a->b"],'
        '"avoid_zones":["x->y"],"segment_mood":"frustrated|adaptive|stable|optimistic",'
        '"confidence":0.0-1.0,"dissenting_signals":["..."]}]}\n'
        "Return exactly one object per segment, keyed by its segment name."
    )
    blocks = [f"Live congestion: {_congestion_line(world.get('congestion', {}))}."]
    for seg, text in items:
        blocks.append(f"\n### segment={seg}\n{text}")
    return system, "\n".join(blocks)


def split_distill_batch(resp: Any, segments: Sequence[str]) -> Dict[str, Optional[dict]]:
    out: Dict[str, Optional[dict]] = {s: None for s in segments}
    truths = resp.get("truths") if isinstance(resp, dict) else None
    if isinstance(truths, list):
        for t in truths:
            if isinstance(t, dict) and t.get("segment") in out:
                out[t["segment"]] = t
    return out


def chunks(seq: Sequence[Any], size: int) -> List[List[Any]]:
    return [list(seq[i : i + size]) for i in range(0, len(seq), max(size, 1))]
