"""Agent simulation brains package.

Provides knowledge graph backends, CollectiveTruth dataclass, and SegmentBrain
for Sentinel and Swarm agents.
"""
from engines.agent_simulation.brains.backend import (
    KnowledgeGraphBackend,
    LocalKnowledgeGraphBackend,
    ZepBackend,
)
from engines.agent_simulation.brains.collective_truth import CollectiveTruth
from engines.agent_simulation.brains.segment_brain import SegmentBrain

__all__ = [
    "CollectiveTruth",
    "KnowledgeGraphBackend",
    "LocalKnowledgeGraphBackend",
    "SegmentBrain",
    "ZepBackend",
]
