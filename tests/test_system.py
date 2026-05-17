"""System tests - end-to-end AgentMemory tests."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig, MemoryManager
from memory_system.core.long_term_persistent_memory import LongTermMemoryConfig
from memory_system.processing.text_embedding_provider import EmbeddingConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIM = 64


def _make_config(**overrides) -> AgentMemoryConfig:
    """Create an AgentMemoryConfig with fake embedding provider."""
    defaults = {
        "long_term": LongTermMemoryConfig(
            embedding=EmbeddingConfig(provider="fake", fake_dimension=DIM),
            vector_store={"backend": "memory"},
            auto_consolidate=False,
        ),
        "auto_consolidate": False,
        "structured_store": {"db_path": ":memory:", "enabled": True},
        "knowledge_graph": {"enabled": True},
    }
    defaults.update(overrides)
    return AgentMemoryConfig(**defaults)


def _make_agent(**overrides) -> AgentMemory:
    """Create an AgentMemory instance with fake embedding (dim=64)."""
    config = _make_config(**overrides)
    return AgentMemory(config=config)


# ===========================================================================
# TestAgentMemorySystem
# ===========================================================================

class TestAgentMemorySystem:
    """End-to-end tests verifying the complete AgentMemory system."""

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def test_init_with_defaults(self):
        """AgentMemory() should create without error."""
        # v5.1+: auto provider requires sentence-transformers, use fake for test
        config = _make_config()
        agent = AgentMemory(config)
        assert agent is not None
        assert agent.short_term is not None
        assert agent.long_term is not None
        agent.close()

    def test_init_with_custom_config(self):
        """Custom config should be applied."""
        config = _make_config(
            consolidation_threshold=0.8,
            default_top_k=10,
        )
        agent = AgentMemory(config=config)
        assert agent.config.consolidation_threshold == 0.8
        assert agent.config.default_top_k == 10
        agent.close()

    # ------------------------------------------------------------------
    # Full workflow
    # ------------------------------------------------------------------

    def test_full_workflow(self):
        """Exercise all major subsystems in a single end-to-end flow."""
        agent = _make_agent()

        # 1. Add to working memory
        ok = agent.add_to_working_memory(
            key="current_task",
            content="Help user with data analysis",
            importance=0.8,
        )
        assert ok is True

        # 2. Remember (long-term)
        memory_id = agent.remember(
            content="User prefers Python for data analysis",
            category="preferences",
            importance=0.9,
        )
        assert memory_id is not None

        # 3. Recall
        results = agent.recall("Python data analysis")
        assert len(results) >= 1

        # 4. Add entity + relation (knowledge graph)
        entity_name = agent.add_entity(
            name="Python",
            entity_type="language",
            description="A programming language",
        )
        assert entity_name == "Python"

        relation_id = agent.add_relation(
            source="User",
            target="Python",
            relation_type="prefers",
        )
        assert relation_id is not None

        # 5. Store preference (structured store)
        pref_id = agent.store_preference(
            key="language",
            value="Python",
            category="coding",
        )
        assert pref_id is not None

        # 6. Remember conversation
        conv_id = agent.remember_conversation(
            content="Can you help me analyze this dataset?",
            speaker="user",
            important=True,
        )
        assert conv_id is not None

        # 7. Get conversation history
        history = agent.get_conversation_history(n=5)
        assert len(history) >= 1

        # 8. Get relevant context
        context = agent.get_relevant_context("data analysis", max_items=5)
        assert isinstance(context, str)

        # 9. Get stats
        stats = agent.get_stats()
        assert isinstance(stats, dict)
        assert "session" in stats
        assert "short_term" in stats
        assert "long_term" in stats

        agent.close()

    # ------------------------------------------------------------------
    # Working memory
    # ------------------------------------------------------------------

    def test_working_memory_operations(self):
        """Add items, check count, check focus."""
        agent = _make_agent()

        agent.add_to_working_memory("task1", "First task", importance=0.7)
        agent.add_to_working_memory("task2", "Second task", importance=0.9)
        agent.add_to_working_memory("task3", "Third task", importance=0.5)

        assert len(agent.short_term.working_memory) == 3

        # Focus should be on the most recently added item
        focus = agent.short_term.working_memory.get_focus()
        assert focus == "task3"

        # Set focus explicitly
        agent.short_term.working_memory.set_focus("task1")
        assert agent.short_term.working_memory.get_focus() == "task1"

        agent.close()

    # ------------------------------------------------------------------
    # Long-term memory
    # ------------------------------------------------------------------

    def test_long_term_memory_operations(self):
        """Remember, recall, count."""
        agent = _make_agent()

        assert agent.long_term.count() == 0

        id1 = agent.remember("Fact one about science")
        id2 = agent.remember("Fact two about history")
        id3 = agent.remember("Fact three about math")

        assert agent.long_term.count() == 3

        results = agent.long_term.recall("science fact")
        assert len(results) >= 1

        agent.close()

    # ------------------------------------------------------------------
    # Knowledge graph
    # ------------------------------------------------------------------

    def test_knowledge_graph_operations(self):
        """add_entity, add_relation, search_entities, get_entity, get_knowledge_graph_stats."""
        agent = _make_agent()

        agent.add_entity("Alice", entity_type="person", description="A software engineer")
        agent.add_entity("Bob", entity_type="person", description="A data scientist")
        agent.add_relation("Alice", "Bob", relation_type="colleague")

        # Search entities
        results = agent.search_entities("Alice", top_k=5)
        assert len(results) >= 1
        entity, score = results[0]
        assert entity.name == "Alice"

        # Get entity
        entity = agent.get_entity("Alice")
        assert entity is not None
        assert entity.entity_type == "person"

        # Stats
        stats = agent.get_knowledge_graph_stats()
        assert stats["entity_count"] >= 2
        assert stats["relation_count"] >= 1

        agent.close()

    # ------------------------------------------------------------------
    # Structured store
    # ------------------------------------------------------------------

    def test_structured_store_operations(self):
        """store_preference, get_preference, log_interaction, get_interaction_history."""
        agent = _make_agent()

        # Preferences
        pref_id = agent.store_preference("theme", "dark", "ui")
        assert pref_id is not None

        pref = agent.get_preference("theme")
        assert pref is not None
        assert pref == "dark"

        # Interactions
        int_id = agent.log_interaction("user", "Hello agent!")
        assert int_id is not None

        history = agent.get_interaction_history(limit=10)
        assert len(history) >= 1
        assert history[0]["role"] == "user"

        agent.close()

    # ------------------------------------------------------------------
    # Conversation flow
    # ------------------------------------------------------------------

    def test_conversation_flow(self):
        """Multiple remember_conversation calls, get history, get context."""
        agent = _make_agent()

        agent.remember_conversation("Hi there!", speaker="user")
        agent.remember_conversation("Hello! How can I help?", speaker="assistant")
        agent.remember_conversation("Tell me about Python", speaker="user", important=True)

        # Conversation history (from short-term)
        history = agent.get_conversation_history(n=5)
        assert len(history) == 3

        # Recall should find the important conversation
        results = agent.recall("Python", top_k=5)
        assert len(results) >= 1

        # Context
        context = agent.get_relevant_context("Python", max_items=5)
        assert isinstance(context, str)

        agent.close()

    # ------------------------------------------------------------------
    # Consolidation
    # ------------------------------------------------------------------

    def test_consolidation(self):
        """Add items to working memory, force_consolidate, verify some moved to long-term."""
        agent = _make_agent(consolidation_threshold=0.5)

        # Add high-importance items to working memory
        agent.add_to_working_memory("important1", "Critical task A", importance=0.9)
        agent.add_to_working_memory("important2", "Critical task B", importance=0.8)
        agent.add_to_working_memory("trivial", "Low priority note", importance=0.2)

        initial_lt_count = agent.long_term.count()

        result = agent.force_consolidate()
        assert result["status"] == "forced"
        assert result["consolidated"] >= 2  # At least the two high-importance items

        # Verify some items were moved to long-term
        assert agent.long_term.count() > initial_lt_count

        agent.close()

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def test_close(self):
        """close() should not raise."""
        agent = _make_agent()
        agent.add_to_working_memory("key", "value")
        agent.remember("some fact")
        agent.close()  # Should not raise
        # Double close should also be safe
        agent.close()

    # ------------------------------------------------------------------
    # Backend-specific tests
    # ------------------------------------------------------------------

    def test_chroma_backend(self):
        """Create with chroma backend, remember, recall."""
        pytest.importorskip("chromadb")

        config = _make_config()
        config.long_term = LongTermMemoryConfig(
            embedding=EmbeddingConfig(provider="fake", fake_dimension=DIM),
            vector_store={"backend": "chroma"},
            auto_consolidate=False,
        )
        agent = AgentMemory(config=config)

        memory_id = agent.remember("ChromaDB test memory", category="test")
        assert memory_id is not None

        results = agent.recall("ChromaDB test", top_k=3)
        assert len(results) >= 1

        agent.close()

    def test_faiss_backend(self):
        """Create with faiss backend, remember, recall."""
        pytest.importorskip("faiss")

        config = _make_config()
        config.long_term = LongTermMemoryConfig(
            embedding=EmbeddingConfig(provider="fake", fake_dimension=DIM),
            vector_store={"backend": "faiss", "dimension": DIM},
            auto_consolidate=False,
        )
        agent = AgentMemory(config=config)

        memory_id = agent.remember("FAISS test memory", category="test")
        assert memory_id is not None

        results = agent.recall("FAISS test", top_k=3)
        assert len(results) >= 1

        agent.close()

    # ------------------------------------------------------------------
    # MemoryManager compatibility
    # ------------------------------------------------------------------

    def test_memory_manager_compat(self):
        """MemoryManager should proxy to AgentMemory."""
        config = _make_config()
        mm = MemoryManager(config=config)

        # Verify MemoryManager delegates to AgentMemory
        assert hasattr(mm, "remember")
        assert hasattr(mm, "recall")
        assert hasattr(mm, "add_to_working_memory")
        assert hasattr(mm, "get_stats")

        # Exercise core methods through the proxy
        memory_id = mm.remember("MemoryManager proxy test")
        assert memory_id is not None

        results = mm.recall("proxy test")
        assert len(results) >= 1

        stats = mm.get_stats()
        assert isinstance(stats, dict)

        mm.close()
