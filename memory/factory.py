"""Swappable knowledge-graph backend factory (PATH.md §6, D6).

Selecting a backend is a *config change, never a code change*: callers ask
``get_kg_backend()`` and get whatever ``GRAPH_BACKEND`` names. The concrete
classes still live in ``engines/agent_simulation/brains/backend.py`` (no churn);
this module is the single selection seam.

    GRAPH_BACKEND=in_memory   -> LocalKnowledgeGraphBackend   (default, zero-cost)
    GRAPH_BACKEND=zep         -> ZepBackend                   (needs ZEP_API_KEY)
"""
from __future__ import annotations

import os
from typing import Optional

from engines.agent_simulation.brains.backend import (
    KnowledgeGraphBackend,
    LocalKnowledgeGraphBackend,
    ZepBackend,
)


def get_kg_backend(kind: Optional[str] = None) -> KnowledgeGraphBackend:
    """Return a backend instance selected by ``kind`` or the GRAPH_BACKEND env."""
    kind = (kind or os.getenv("GRAPH_BACKEND", "in_memory")).lower()
    if kind in ("zep", "zep_cloud"):
        api_key = os.getenv("ZEP_API_KEY")
        if api_key:
            return ZepBackend(api_key=api_key)
        # Fail soft to the free backend rather than crash a demo.
        return LocalKnowledgeGraphBackend()
    return LocalKnowledgeGraphBackend()
