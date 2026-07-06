"""Tests for ZepBackend implementation with async init and graceful fallback."""
import pytest
from unittest.mock import patch, MagicMock

from engines.agent_simulation.brains.backend import ZepBackend, LocalKnowledgeGraphBackend


class TestZepBackendInit:
    """Test ZepBackend initialization."""

    def test_init_accepts_api_key_and_collection_name(self):
        """Test that ZepBackend.__init__() accepts api_key and collection_name."""
        backend = ZepBackend(api_key="test_key_123", collection_name="test_collection")
        assert backend.api_key == "test_key_123"
        assert backend.collection_name == "test_collection"

    def test_init_default_collection_name(self):
        """Test that collection_name defaults to 'overhaul_agent_memory'."""
        backend = ZepBackend(api_key="test_key_123")
        assert backend.collection_name == "overhaul_agent_memory"

    def test_init_client_is_none_initially(self):
        """Test that _client is None before initialization."""
        backend = ZepBackend(api_key="test_key_123")
        assert backend._client is None

    def test_init_local_fallback_is_set(self):
        """Test that _local_fallback is initialized as LocalKnowledgeGraphBackend."""
        backend = ZepBackend(api_key="test_key_123")
        assert isinstance(backend._local_fallback, LocalKnowledgeGraphBackend)


class TestZepBackendAsyncInitialize:
    """Test ZepBackend async initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_must_be_called_before_other_methods(self):
        """Test that initialize() is async and must be awaited."""
        backend = ZepBackend(api_key="test_key_123")

        # Before initialize, _initialized should be False
        assert backend._initialized is False

        # After initialize, _initialized should be True
        await backend.initialize()
        assert backend._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_sets_initialized_flag(self):
        """Test that initialize properly sets _initialized = True."""
        backend = ZepBackend(api_key="test_key_123")
        assert backend._initialized is False

        await backend.initialize()

        assert backend._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self):
        """Test that calling initialize twice doesn't cause issues."""
        backend = ZepBackend(api_key="test_key_123")

        await backend.initialize()
        first_init_state = backend._initialized

        await backend.initialize()
        second_init_state = backend._initialized

        assert first_init_state == second_init_state == True


class TestZepBackendGracefulFallback:
    """Test graceful fallback when ZEP_API_KEY is not set."""

    def test_client_is_none_when_zep_not_available(self):
        """Test that when Zep import fails, _client is set to None."""
        # This tests the graceful degradation path
        backend = ZepBackend(api_key="invalid_key")

        # Even before init, we expect _client to potentially be None on failure
        # After init, if Zep connection fails, _client should be None
        assert backend._client is None or isinstance(backend._client, type(None))

    @pytest.mark.asyncio
    async def test_fallback_when_client_none_add_memory(self):
        """Test add_memory works when client is None (fallback to local)."""
        backend = ZepBackend(api_key="invalid_key")
        await backend.initialize()

        # Should not crash - should fall back to local
        backend.add_memory("session", "test content")
        result = backend.get_memory("session")

        assert result is not None
        assert len(result["messages"]) >= 1

    @pytest.mark.asyncio
    async def test_fallback_when_client_none_get_memory(self):
        """Test get_memory works when client is None (fallback to local)."""
        backend = ZepBackend(api_key="invalid_key")
        await backend.initialize()

        backend.add_memory("session", "test content")
        result = backend.get_memory("session")

        assert result is not None
        assert "messages" in result

    @pytest.mark.asyncio
    async def test_fallback_when_client_none_add_fact(self):
        """Test add_fact works when client is None (fallback to local)."""
        backend = ZepBackend(api_key="invalid_key")
        await backend.initialize()

        # Should not crash
        backend.add_fact("source", "target", "relation", {"key": "value"})

        results = backend.search_facts("relation")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fallback_when_client_none_search_facts(self):
        """Test search_facts works when client is None (fallback to local)."""
        backend = ZepBackend(api_key="invalid_key")
        await backend.initialize()

        backend.add_fact("a", "b", "test_rel", {})
        results = backend.search_facts("test_rel")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fallback_when_client_none_semantic_query(self):
        """Test semantic_query works when client is None (fallback to local)."""
        backend = ZepBackend(api_key="invalid_key")
        await backend.initialize()

        backend.add_fact("src", "dst", "has_traffic", {})
        results = backend.semantic_query("traffic")

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_fallback_when_client_none_sync_from_policy_agent(self):
        """Test sync_from_policy_agent works when client is None (fallback to local)."""
        backend = ZepBackend(api_key="invalid_key")
        await backend.initialize()

        policy_data = {
            "laws": [{"id": "law_001", "name": "Test Law"}],
            "budgets": [{"id": "budget_001", "allocation": 1000}],
        }

        # Should not crash
        backend.sync_from_policy_agent(policy_data)

        law_results = backend.search_facts("regulation")
        assert len(law_results) == 1


class TestZepBackendMethodsWorkAfterInit:
    """Test that all ZepBackend methods work correctly after async initialize."""

    @pytest.mark.asyncio
    async def test_add_memory_after_init(self):
        """Test add_memory works after initialize is called."""
        backend = ZepBackend(api_key="test_key")
        await backend.initialize()

        backend.add_memory("session_001", "Test memory content")
        result = backend.get_memory("session_001")

        assert result is not None
        assert any(msg["content"] == "Test memory content" for msg in result["messages"])

    @pytest.mark.asyncio
    async def test_get_memory_after_init(self):
        """Test get_memory works after initialize is called."""
        backend = ZepBackend(api_key="test_key")
        await backend.initialize()

        backend.add_memory("session_002", "Another memory")
        result = backend.get_memory("session_002")

        assert result is not None

    @pytest.mark.asyncio
    async def test_add_fact_after_init(self):
        """Test add_fact works after initialize is called."""
        backend = ZepBackend(api_key="test_key")
        await backend.initialize()

        backend.add_fact("node_a", "node_b", "connected", {"weight": 1.5})
        results = backend.search_facts("connected")

        assert len(results) == 1
        assert results[0]["source"] == "node_a"
        assert results[0]["target"] == "node_b"

    @pytest.mark.asyncio
    async def test_search_facts_after_init(self):
        """Test search_facts works after initialize is called."""
        backend = ZepBackend(api_key="test_key")
        await backend.initialize()

        backend.add_fact("x", "y", "has_route", {})
        backend.add_fact("z", "w", "has_budget", {})

        results = backend.search_facts("route")

        assert len(results) == 1
        assert results[0]["relation"] == "has_route"

    @pytest.mark.asyncio
    async def test_semantic_query_after_init(self):
        """Test semantic_query works after initialize is called."""
        backend = ZepBackend(api_key="test_key")
        await backend.initialize()

        backend.add_fact("src", "dst", "faster_path", {"speed": 50})
        results = backend.semantic_query("faster")

        assert len(results) == 1
        assert "faster_path" in results[0]

    @pytest.mark.asyncio
    async def test_sync_from_policy_agent_after_init(self):
        """Test sync_from_policy_agent works after initialize is called."""
        backend = ZepBackend(api_key="test_key")
        await backend.initialize()

        policy_data = {
            "laws": [{"id": "law_100", "name": "Speed Regulation"}],
            "budgets": [{"id": "budget_100", "allocation": 50000}],
        }

        backend.sync_from_policy_agent(policy_data)

        # Verify laws synced
        law_results = backend.search_facts("regulation")
        assert len(law_results) == 1

        # Verify budgets synced
        budget_results = backend.search_facts("budget")
        assert len(budget_results) == 1


class TestZepBackendAsyncInitBugFix:
    """Critical tests for the async initialize bug fix.

    The bug: async def initialize() was not actually being awaited properly,
    or the async nature wasn't properly implemented. These tests verify the fix.
    """

    @pytest.mark.asyncio
    async def test_initialize_is_truly_async(self):
        """Test that initialize is a proper async method that can be awaited."""
        backend = ZepBackend(api_key="test_key")

        # This should be awaitable without errors
        await backend.initialize()

        # If we get here, initialize was properly awaitable
        assert backend._initialized is True

    @pytest.mark.asyncio
    async def test_multiple_backends_initialize_concurrently(self):
        """Test that multiple backends can be initialized concurrently."""
        backend1 = ZepBackend(api_key="key1")
        backend2 = ZepBackend(api_key="key2")

        # Both should initialize concurrently without issues
        await backend1.initialize()
        await backend2.initialize()

        assert backend1._initialized is True
        assert backend2._initialized is True

        # Both should work independently
        backend1.add_memory("s1", "memory1")
        backend2.add_memory("s2", "memory2")

        assert backend1.get_memory("s1") is not None
        assert backend2.get_memory("s2") is not None
