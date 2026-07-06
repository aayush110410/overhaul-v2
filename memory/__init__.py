"""OVERHAUL Memory Layer (L2) — swappable knowledge-graph backend (PATH.md §6).

Callsites import the ABC + factory from here, never a concrete backend directly.
"""
from engines.agent_simulation.brains.backend import (
    KnowledgeGraphBackend,
    LocalKnowledgeGraphBackend,
    ZepBackend,
)
from memory.factory import get_kg_backend

__all__ = [
    "KnowledgeGraphBackend",
    "LocalKnowledgeGraphBackend",
    "ZepBackend",
    "get_kg_backend",
]
