"""OVERHAUL Reasoning Layer (L2) — the 4-model brain behind one gateway.

Public surface:
    get_gateway()        -> process-wide ReasoningGateway singleton
    ReasoningGateway     -> queue·batch·cache·shard·ratelimit·breaker
    ReasonRequest        -> one logical agent reasoning request
    make_sentinel_provider, valid_edge_ids, coerce_decision, coerce_truth

Everything routes through the gateway; only ``reasoning.providers`` touches the
concrete ``llm/chat.py`` transport (PATH.md invariants #2, #5).
"""
from reasoning.gateway import (
    ReasonRequest,
    ReasoningGateway,
    get_gateway,
    reset_gateway,
)
from reasoning.adapters import (
    coerce_decision,
    coerce_truth,
    make_sentinel_provider,
    node_coords,
    valid_edge_ids,
)

__all__ = [
    "ReasonRequest",
    "ReasoningGateway",
    "get_gateway",
    "reset_gateway",
    "coerce_decision",
    "coerce_truth",
    "make_sentinel_provider",
    "node_coords",
    "valid_edge_ids",
]
