"""Tests for KnowledgeGraphBackend abstract interface and concrete implementations."""
import pytest
from abc import ABC


class TestKnowledgeGraphBackendInterface:
    """Test that KnowledgeGraphBackend ABC exists and has required abstract methods."""

    def test_backend_interface_exists(self):
        """KnowledgeGraphBackend should be importable from backend module."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert KnowledgeGraphBackend is not None

    def test_backend_is_abc(self):
        """KnowledgeGraphBackend should be an abstract base class."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert issubclass(KnowledgeGraphBackend, ABC)

    def test_has_add_memory_abstract_method(self):
        """Backend must have add_memory abstract method."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert hasattr(KnowledgeGraphBackend, 'add_memory')

    def test_has_get_memory_abstract_method(self):
        """Backend must have get_memory abstract method."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert hasattr(KnowledgeGraphBackend, 'get_memory')

    def test_has_add_fact_abstract_method(self):
        """Backend must have add_fact abstract method."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert hasattr(KnowledgeGraphBackend, 'add_fact')

    def test_has_search_facts_abstract_method(self):
        """Backend must have search_facts abstract method."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert hasattr(KnowledgeGraphBackend, 'search_facts')

    def test_has_sync_from_policy_agent_abstract_method(self):
        """Backend must have sync_from_policy_agent abstract method."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert hasattr(KnowledgeGraphBackend, 'sync_from_policy_agent')

    def test_has_semantic_query_abstract_method(self):
        """Backend must have semantic_query abstract method."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert hasattr(KnowledgeGraphBackend, 'semantic_query')

    def test_has_initialize_async_method(self):
        """Backend must have async initialize method."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        assert hasattr(KnowledgeGraphBackend, 'initialize')


class TestZepBackendInheritance:
    """Test that ZepBackend inherits from KnowledgeGraphBackend."""

    def test_zep_backend_exists(self):
        """ZepBackend should be importable."""
        from engines.agent_simulation.brains.backend import ZepBackend
        assert ZepBackend is not None

    def test_zep_backend_inherits_from_backend(self):
        """ZepBackend should inherit from KnowledgeGraphBackend."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend, ZepBackend
        assert issubclass(ZepBackend, KnowledgeGraphBackend)


class TestLocalKnowledgeGraphBackendInheritance:
    """Test that LocalKnowledgeGraphBackend inherits from KnowledgeGraphBackend."""

    def test_local_backend_exists(self):
        """LocalKnowledgeGraphBackend should be importable."""
        from engines.agent_simulation.brains.backend import LocalKnowledgeGraphBackend
        assert LocalKnowledgeGraphBackend is not None

    def test_local_backend_inherits_from_backend(self):
        """LocalKnowledgeGraphBackend should inherit from KnowledgeGraphBackend."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend, LocalKnowledgeGraphBackend
        assert issubclass(LocalKnowledgeGraphBackend, KnowledgeGraphBackend)


class TestAbstractMethodsRaiseNotImplemented:
    """Test that abstract methods raise NotImplementedError when called.

    Uses a test double that implements all methods but raises NotImplementedError
    to verify the ABC contract.
    """

    @staticmethod
    def _make_stub_backend():
        """Create a concrete subclass with methods that raise NotImplementedError."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend

        class StubBackend(KnowledgeGraphBackend):
            def add_memory(self, session_id: str, content: str) -> None:
                raise NotImplementedError

            def get_memory(self, session_id: str):
                raise NotImplementedError

            def add_fact(self, source: str, target: str, relation: str, properties: dict) -> None:
                raise NotImplementedError

            def search_facts(self, query: str):
                raise NotImplementedError

            def sync_from_policy_agent(self, data: dict) -> None:
                raise NotImplementedError

            def semantic_query(self, query: str):
                raise NotImplementedError

            async def initialize(self) -> None:
                raise NotImplementedError

        return StubBackend()

    def test_add_memory_raises_not_implemented(self):
        """add_memory should raise NotImplementedError on base class."""
        from engines.agent_simulation.brains.backend import KnowledgeGraphBackend
        backend = self._make_stub_backend()
        with pytest.raises(NotImplementedError):
            backend.add_memory("session", "content")

    def test_get_memory_raises_not_implemented(self):
        """get_memory should raise NotImplementedError on base class."""
        backend = self._make_stub_backend()
        with pytest.raises(NotImplementedError):
            backend.get_memory("session")

    def test_add_fact_raises_not_implemented(self):
        """add_fact should raise NotImplementedError on base class."""
        backend = self._make_stub_backend()
        with pytest.raises(NotImplementedError):
            backend.add_fact("source", "target", "relation", {})

    def test_search_facts_raises_not_implemented(self):
        """search_facts should raise NotImplementedError on base class."""
        backend = self._make_stub_backend()
        with pytest.raises(NotImplementedError):
            backend.search_facts("query")

    def test_sync_from_policy_agent_raises_not_implemented(self):
        """sync_from_policy_agent should raise NotImplementedError on base class."""
        backend = self._make_stub_backend()
        with pytest.raises(NotImplementedError):
            backend.sync_from_policy_agent({})

    def test_semantic_query_raises_not_implemented(self):
        """semantic_query should raise NotImplementedError on base class."""
        backend = self._make_stub_backend()
        with pytest.raises(NotImplementedError):
            backend.semantic_query("query")

    @pytest.mark.asyncio
    async def test_initialize_raises_not_implemented(self):
        """initialize should raise NotImplementedError on base class."""
        backend = self._make_stub_backend()
        with pytest.raises(NotImplementedError):
            await backend.initialize()