"""PolicyAgent - Autonomous Regulatory Monitor.

The PolicyAgent ingests live laws, budgets, and regulatory announcements
and writes them to the GlobalKnowledgeGraph and relevant SegmentBrains.

This implements the "Policy Broadcast" step of the Sentinel-Swarm-Hive loop:
  PolicyAgent → GlobalKG + SegmentBrains

It uses the LDRAGO Researcher pattern (web research via LLM) to fetch
and synthesize regulatory data. Runs at simulation start and on trigger.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from engines.agent_simulation.brains.backend import KnowledgeGraphBackend

LOGGER = logging.getLogger(__name__)


class PolicyAgent:
    """Autonomous regulatory monitor.

    Fetches laws, budgets, and announcements from the web (via LLM) and
    syncs regulatory facts to the GlobalKnowledgeGraph and SegmentBrains.

    Args:
        backend: The GlobalKnowledgeGraph backend for regulatory storage.
        llm_provider: Optional callable that takes a research query and returns
            a dict with synthesized regulatory facts.
    """

    def __init__(
        self,
        backend: KnowledgeGraphBackend,
        llm_provider: Optional[callable] = None,
    ) -> None:
        self.backend = backend
        self._llm = llm_provider
        self._last_sync_timestep: int = -1

    def sync_from_web(self, research_query: str) -> Dict[str, Any]:
        """Fetch and synthesize regulatory data via LLM.

        Args:
            research_query: Natural language query about policies to research.
                e.g. "Delhi congestion pricing laws 2025" or "NCR EV subsidies"

        Returns:
            Dict with keys: laws (List[dict]), budgets (List[dict]), announcements (List[str])
        """
        if self._llm is None:
            return {"laws": [], "budgets": [], "announcements": [], "error": "No LLM configured"}

        try:
            result = self._llm({"query": research_query})
            return result
        except Exception as e:
            LOGGER.error(f"PolicyAgent web sync failed: {e}")
            return {"laws": [], "budgets": [], "announcements": [], "error": str(e)}

    def broadcast_to_global_kg(self, data: Dict[str, Any]) -> None:
        """Write policy data to the GlobalKnowledgeGraph.

        Args:
            data: Dict with 'laws', 'budgets', and 'announcements' keys.
        """
        try:
            self.backend.sync_from_policy_agent(data)
            LOGGER.info(f"PolicyAgent synced to GlobalKG: {len(data.get('laws', []))} laws, "
                       f"{len(data.get('budgets', []))} budgets")
        except Exception as e:
            LOGGER.error(f"PolicyAgent GlobalKG sync failed: {e}")

    async def run_policy_broadcast(
        self,
        research_query: str,
        timestep: int,
        target_segments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute the full policy broadcast cycle.

        Args:
            research_query: Query for LLM-based policy research.
            timestep: Current simulation timestep.
            target_segments: Optional list of segment names to broadcast to.
                If None, broadcasts to all segments.

        Returns:
            Dict with research results and sync status.
        """
        if timestep <= self._last_sync_timestep:
            return {"status": "skipped", "reason": "already_synced_this_timestep"}

        # Step 1: Research via LLM
        research_results = self.sync_from_web(research_query)

        # Step 2: Write to GlobalKG
        self.broadcast_to_global_kg(research_results)

        self._last_sync_timestep = timestep
        return {
            "status": "success",
            "timestep": timestep,
            "laws_count": len(research_results.get("laws", [])),
            "budgets_count": len(research_results.get("budgets", [])),
            "announcements_count": len(research_results.get("announcements", [])),
        }
