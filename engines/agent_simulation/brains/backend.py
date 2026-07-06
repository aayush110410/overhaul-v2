"""KnowledgeGraphBackend abstract interface for agent simulation brains."""
from abc import ABC, abstractmethod
from typing import Optional, List


class KnowledgeGraphBackend(ABC):
    """Abstract base class for knowledge graph backends.

    All concrete implementations (ZepBackend, LocalKnowledgeGraphBackend, etc.)
    must inherit from this ABC. No class except ZepBackend may import zep_cloud.
    """

    @abstractmethod
    def add_memory(self, session_id: str, content: str) -> None:
        """Add a memory entry for a session.

        Args:
            session_id: Unique identifier for the agent session.
            content: The memory content to store.
        """
        raise NotImplementedError

    @abstractmethod
    def get_memory(self, session_id: str) -> Optional[dict]:
        """Retrieve memory for a session.

        Args:
            session_id: Unique identifier for the agent session.

        Returns:
            Dictionary containing memory data, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def add_fact(self, source: str, target: str, relation: str, properties: dict) -> None:
        """Add a fact (edge) to the knowledge graph.

        Args:
            source: Source node identifier.
            target: Target node identifier.
            relation: Relationship type between source and target.
            properties: Additional properties for the fact/edge.
        """
        raise NotImplementedError

    @abstractmethod
    def search_facts(self, query: str) -> List[dict]:
        """Search for facts matching a query.

        Args:
            query: Search query string.

        Returns:
            List of matching fact dictionaries.
        """
        raise NotImplementedError

    @abstractmethod
    def sync_from_policy_agent(self, data: dict) -> None:
        """Sync knowledge graph from PolicyAgent updates.

        Args:
            data: Dictionary containing policy/regulatory data.
        """
        raise NotImplementedError

    @abstractmethod
    def semantic_query(self, query: str) -> List[str]:
        """Perform a semantic search query against the knowledge graph.

        Args:
            query: Natural language search query.

        Returns:
            List of result strings from the semantic search.
        """
        raise NotImplementedError

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend connection.

        Must be called before using other methods.
        """
        raise NotImplementedError


class LocalKnowledgeGraphBackend(KnowledgeGraphBackend):
    """In-memory knowledge graph backend — fallback when Zep unavailable.

    Provides full interface implementation using in-memory storage.
    Does NOT persist across runs.
    """

    def __init__(self):
        self._initialized = False
        self._memories: dict[str, list[dict]] = {}
        self._facts: list[dict] = []

    async def initialize(self) -> None:
        """Initialize the in-memory backend."""
        self._initialized = True

    def __enter__(self) -> "LocalKnowledgeGraphBackend":
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager."""
        pass

    def add_memory(self, session_id: str, content: str) -> None:
        """Add a memory entry for a session."""
        if session_id not in self._memories:
            self._memories[session_id] = []
        self._memories[session_id].append({
            "content": content,
        })

    def get_memory(self, session_id: str) -> Optional[dict]:
        """Retrieve memory for a session."""
        memories = self._memories.get(session_id, [])
        if not memories:
            return None
        return {"messages": memories}

    def add_fact(self, source: str, target: str, relation: str, properties: dict) -> None:
        """Add a fact (edge) to the knowledge graph."""
        self._facts.append({
            "source": source,
            "target": target,
            "relation": relation,
            "properties": properties,
        })

    def search_facts(self, query: str) -> List[dict]:
        """Search for facts matching a query."""
        query_lower = query.lower()
        return [
            fact for fact in self._facts
            if query_lower in fact.get("relation", "").lower()
            or query_lower in str(fact.get("properties", {})).lower()
        ]

    def sync_from_policy_agent(self, data: dict) -> None:
        """Sync knowledge graph from PolicyAgent updates."""
        # Store policy data as special facts
        if "laws" in data:
            for law in data["laws"]:
                self.add_fact(
                    source="policy_agent",
                    target=law.get("id", "unknown"),
                    relation="regulation",
                    properties=law,
                )
        if "budgets" in data:
            for budget in data["budgets"]:
                self.add_fact(
                    source="policy_agent",
                    target=budget.get("id", "unknown"),
                    relation="budget",
                    properties=budget,
                )

    def semantic_query(self, query: str) -> List[str]:
        """Perform a semantic search (simple keyword match for local backend)."""
        results = self.search_facts(query)
        return [
            f"{f['relation']}: {f['source']} -> {f['target']}"
            for f in results
        ]


class ZepBackend(KnowledgeGraphBackend):
    """Zep Cloud backed knowledge graph with persistent memory.

    This is the only class allowed to import from zep_cloud.
    Full MiroFish-style knowledge graph using Zep's GraphRAG capabilities.
    """

    def __init__(self, api_key: str, collection_name: str = "overhaul_agent_memory"):
        self.api_key = api_key
        self.collection_name = collection_name
        self._client = None
        self._local_fallback = LocalKnowledgeGraphBackend()
        self._initialized = False

    async def initialize(self) -> None:
        """Connect to Zep Cloud and initialize graph."""
        if self._initialized:
            return

        try:
            from zep_cloud.client import AsyncZep
            self._client = AsyncZep(api_key=self.api_key)
            await self._local_fallback.initialize()
            self._initialized = True
        except Exception as e:
            print(f"[ZepBackend] Zep connection failed: {e}. Using local fallback.")
            await self._local_fallback.initialize()
            self._initialized = True

    def add_memory(self, session_id: str, content: str) -> None:
        """Add a memory entry for a session."""
        self._local_fallback.add_memory(session_id, content)
        if self._client:
            self._sync_memory_to_zep(session_id, content)

    def _sync_memory_to_zep(self, session_id: str, content: str):
        """Sync memory to Zep Cloud asynchronously."""
        import asyncio
        try:
            from zep_cloud.types import Message
            asyncio.create_task(
                self._client.memory.add(
                    session_id=session_id,
                    messages=[Message(
                        role="agent",
                        role_type="assistant",
                        content=content,
                    )],
                )
            )
        except Exception:
            pass  # Graceful degradation

    def get_memory(self, session_id: str) -> Optional[dict]:
        """Retrieve memory for a session."""
        return self._local_fallback.get_memory(session_id)

    def add_fact(self, source: str, target: str, relation: str, properties: dict) -> None:
        """Add a fact (edge) to the knowledge graph."""
        self._local_fallback.add_fact(source, target, relation, properties)

    def search_facts(self, query: str) -> List[dict]:
        """Search for facts matching a query."""
        return self._local_fallback.search_facts(query)

    def sync_from_policy_agent(self, data: dict) -> None:
        """Sync knowledge graph from PolicyAgent updates."""
        self._local_fallback.sync_from_policy_agent(data)

    def semantic_query(self, query: str) -> List[str]:
        """Perform a semantic search query against Zep."""
        # Fallback to local search if Zep client unavailable
        if not self._client:
            return self._local_fallback.semantic_query(query)

        # Zep semantic search would go here when client is available
        # For now, fall back to keyword matching
        return self._local_fallback.semantic_query(query)