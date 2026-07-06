"""Agent simulation agents package.

Subpackages:
  types.py — Agent type definitions (AgentProfile, AgentType, TransportMode, etc.)
  surgical_agent.py — SurgicalAgent (Sentinel, LLM-powered)
  swarm_agent.py — SwarmAgent (Collective, physics-only)
"""
from engines.agent_simulation.agents.types import (
    AgentMemory,
    AgentProfile,
    AgentType,
    TransportMode,
    agent_choose_route,
    agent_update_after_trip,
    share_congestion_within_segment,
    compute_agent_emissions,
    generate_commuter_agents,
    generate_freight_agents,
)
from engines.agent_simulation.agents.surgical_agent import SurgicalAgent
from engines.agent_simulation.agents.swarm_agent import SwarmAgent
from engines.agent_simulation.agents.policy_agent import PolicyAgent
from engines.agent_simulation.agents.report_agent import ReportAgent

__all__ = [
    # types
    "AgentMemory",
    "AgentProfile",
    "AgentType",
    "TransportMode",
    "agent_choose_route",
    "agent_update_after_trip",
    "share_congestion_within_segment",
    "compute_agent_emissions",
    "generate_commuter_agents",
    "generate_freight_agents",
    # agents
    "SurgicalAgent",
    "SwarmAgent",
    "PolicyAgent",
    "ReportAgent",
]
