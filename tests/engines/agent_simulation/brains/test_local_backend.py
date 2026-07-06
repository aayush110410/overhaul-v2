"""Tests for LocalKnowledgeGraphBackend implementation."""
import pytest

from engines.agent_simulation.brains.backend import LocalKnowledgeGraphBackend


class TestLocalBackendBasicOperations:
    """Test basic operations on LocalKnowledgeGraphBackend."""

    def test_add_and_get_memory(self):
        """Test that add_memory and get_memory work correctly within a session."""
        backend = LocalKnowledgeGraphBackend()
        session_id = "test_session_001"

        # Add a memory
        backend.add_memory(session_id, "Agent discovered optimal route A")

        # Retrieve memory
        result = backend.get_memory(session_id)
        assert result is not None
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Agent discovered optimal route A"

    def test_add_multiple_memories(self):
        """Test that multiple memories can be added to the same session."""
        backend = LocalKnowledgeGraphBackend()
        session_id = "test_session_002"

        backend.add_memory(session_id, "First observation")
        backend.add_memory(session_id, "Second observation")

        result = backend.get_memory(session_id)
        assert result is not None
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "First observation"
        assert result["messages"][1]["content"] == "Second observation"

    def test_get_memory_nonexistent_session(self):
        """Test that get_memory returns None for a nonexistent session."""
        backend = LocalKnowledgeGraphBackend()
        result = backend.get_memory("nonexistent_session")
        assert result is None

    def test_add_fact_and_search_facts(self):
        """Test that add_fact stores facts and search_facts can query them."""
        backend = LocalKnowledgeGraphBackend()

        # Add a fact
        backend.add_fact(
            source="segment_A",
            target="segment_B",
            relation="connected_to",
            properties={"distance": 5.0, "capacity": 100}
        )

        # Search for the fact
        results = backend.search_facts("connected")
        assert len(results) == 1
        assert results[0]["source"] == "segment_A"
        assert results[0]["target"] == "segment_B"
        assert results[0]["relation"] == "connected_to"

    def test_search_facts_by_relation(self):
        """Test searching facts by their relation type."""
        backend = LocalKnowledgeGraphBackend()

        backend.add_fact("node1", "node2", "has_route", {})
        backend.add_fact("node3", "node4", "has_budget", {})

        results = backend.search_facts("route")
        assert len(results) == 1
        assert results[0]["relation"] == "has_route"

    def test_search_facts_by_properties(self):
        """Test searching facts by their properties."""
        backend = LocalKnowledgeGraphBackend()

        backend.add_fact("edge1", "edge2", "link", {"speed_limit": 60})
        backend.add_fact("edge3", "edge4", "link", {"speed_limit": 30})

        results = backend.search_facts("60")
        assert len(results) == 1
        assert results[0]["properties"]["speed_limit"] == 60

    def test_search_facts_no_match(self):
        """Test that search_facts returns empty list when no match."""
        backend = LocalKnowledgeGraphBackend()
        backend.add_fact("a", "b", "test_relation", {})

        results = backend.search_facts("nonexistent_query")
        assert results == []

    def test_semantic_query(self):
        """Test that semantic_query returns matching fact contents using substring matching."""
        backend = LocalKnowledgeGraphBackend()

        backend.add_fact("route_A", "route_B", "faster_route", {"travel_time": 10})
        backend.add_fact("zone_1", "zone_2", "congested", {"delay": 5})

        results = backend.semantic_query("faster")
        assert len(results) == 1
        assert "faster_route" in results[0]
        assert "route_A" in results[0]
        assert "route_B" in results[0]

    def test_semantic_query_multiple_matches(self):
        """Test semantic_query with multiple matching facts."""
        backend = LocalKnowledgeGraphBackend()

        backend.add_fact("node1", "node2", "has_traffic", {})
        backend.add_fact("node3", "node4", "has_congestion", {})
        backend.add_fact("node5", "node6", "normal_flow", {})

        results = backend.semantic_query("has")
        assert len(results) == 2

    def test_semantic_query_no_match(self):
        """Test semantic_query returns empty list when no facts match."""
        backend = LocalKnowledgeGraphBackend()
        backend.add_fact("a", "b", "specific_relation", {})

        results = backend.semantic_query("nonexistent_term")
        assert results == []


class TestLocalBackendSyncFromPolicyAgent:
    """Test sync_from_policy_agent functionality."""

    def test_sync_laws(self):
        """Test that sync_from_policy_agent correctly stores law facts."""
        backend = LocalKnowledgeGraphBackend()

        policy_data = {
            "laws": [
                {"id": "law_001", "name": "Speed Limit Regulation", "max_speed": 60},
                {"id": "law_002", "name": "Weight Restriction", "max_weight": 10000},
            ]
        }

        backend.sync_from_policy_agent(policy_data)

        results = backend.search_facts("regulation")
        assert len(results) == 2

        # Verify structure
        law_facts = [f for f in results if f["relation"] == "regulation"]
        assert len(law_facts) == 2

    def test_sync_budgets(self):
        """Test that sync_from_policy_agent correctly stores budget facts."""
        backend = LocalKnowledgeGraphBackend()

        policy_data = {
            "budgets": [
                {"id": "budget_001", "allocation": 50000, "region": "north"},
                {"id": "budget_002", "allocation": 30000, "region": "south"},
            ]
        }

        backend.sync_from_policy_agent(policy_data)

        results = backend.search_facts("budget")
        assert len(results) == 2

        budget_facts = [f for f in results if f["relation"] == "budget"]
        assert len(budget_facts) == 2

    def test_sync_combined(self):
        """Test syncing both laws and budgets."""
        backend = LocalKnowledgeGraphBackend()

        policy_data = {
            "laws": [{"id": "law_001", "name": "Test Law"}],
            "budgets": [{"id": "budget_001", "allocation": 1000}],
        }

        backend.sync_from_policy_agent(policy_data)

        law_results = backend.search_facts("regulation")
        budget_results = backend.search_facts("budget")

        assert len(law_results) == 1
        assert len(budget_results) == 1


class TestLocalBackendInitialize:
    """Test initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_is_noop(self):
        """Test that initialize completes immediately without errors."""
        backend = LocalKnowledgeGraphBackend()

        # Should complete without raising
        await backend.initialize()

        # After initialize, backend should still be usable
        backend.add_memory("session", "test")
        result = backend.get_memory("session")
        assert result is not None


class TestLocalBackendContextManager:
    """Test context manager protocol."""

    def test_context_manager_enter_exit(self):
        """Test that LocalKnowledgeGraphBackend can be used as a context manager."""
        with LocalKnowledgeGraphBackend() as backend:
            # Should be able to use the backend within the context
            backend.add_memory("session", "test content")
            result = backend.get_memory("session")
            assert result is not None
            assert result["messages"][0]["content"] == "test content"

        # After exiting context, no special cleanup needed for local backend

    def test_context_manager_enter_returns_self(self):
        """Test that __enter__ returns the backend instance."""
        backend = LocalKnowledgeGraphBackend()
        result = backend.__enter__()
        assert result is backend


class TestLocalBackendDataPersistence:
    """Test that data persists within a session."""

    def test_memory_persistence(self):
        """Test that memories persist in the same backend instance."""
        backend = LocalKnowledgeGraphBackend()

        backend.add_memory("session_a", "Memory A")
        backend.add_memory("session_b", "Memory B")
        backend.add_memory("session_a", "Memory A2")

        result_a = backend.get_memory("session_a")
        result_b = backend.get_memory("session_b")

        assert len(result_a["messages"]) == 2
        assert len(result_b["messages"]) == 1

    def test_fact_persistence(self):
        """Test that facts persist in the same backend instance."""
        backend = LocalKnowledgeGraphBackend()

        backend.add_fact("a", "b", "rel1", {"key": "value1"})
        backend.add_fact("c", "d", "rel2", {"key": "value2"})

        results = backend.search_facts("rel1")
        assert len(results) == 1

        results = backend.search_facts("rel2")
        assert len(results) == 1
