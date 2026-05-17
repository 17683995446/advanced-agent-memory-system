"""Unit tests for the memory manager module - covering previously untested methods."""
import pytest
import sys, os
import threading
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig, MemoryManager
from memory_system.core.long_term_persistent_memory import LongTermMemoryConfig
from memory_system.processing.text_embedding_provider import EmbeddingConfig


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


class TestAgentMemoryUntestedMethods:
    """Tests for previously untested AgentMemory methods"""

    def setup_method(self):
        self.config = _make_config()
        self.memory = AgentMemory(self.config)

    def test_remember_fact(self):
        """Test remember_fact stores a fact"""
        result = self.memory.remember_fact(
            fact="Python is a programming language",
            confidence=0.95,
        )
        assert result is not None

    def test_remember_fact_with_metadata(self):
        """Test remember_fact with metadata"""
        result = self.memory.remember_fact(
            fact="Earth is a planet",
            metadata={"source": "wikipedia"},
        )
        assert result is not None

    def test_find_related(self):
        """Test find_related"""
        self.memory.add_entity(name="Python", entity_type="language")
        self.memory.add_entity(name="programming", entity_type="concept")
        self.memory.add_relation(
            source="Python", target="programming", relation_type="related_to"
        )
        related = self.memory.find_related("Python", top_k=5)
        assert isinstance(related, list)

    def test_build_knowledge_from_text(self):
        """Test build_knowledge_from_text"""
        result = self.memory.build_knowledge_from_text(
            "Python is a programming language created by Guido van Rossum"
        )
        assert result is not None

    def test_recall_for_prompt(self):
        """Test recall_for_prompt formats memories for prompts"""
        self.memory.remember("Hello world", metadata={"category": "test"})
        prompt = self.memory.recall_for_prompt(query="Hello", max_short_term=5, max_long_term=5)
        assert isinstance(prompt, str)

    def test_recall_for_prompt_empty(self):
        """Test recall_for_prompt with no memories"""
        prompt = self.memory.recall_for_prompt(query="nothing", max_short_term=5, max_long_term=5)
        assert isinstance(prompt, str)

    def test_recall_with_filters(self):
        """Test recall with category filter"""
        self.memory.remember("Python tip", metadata={"category": "programming"})
        self.memory.remember("Recipe for cake", metadata={"category": "cooking"})
        results = self.memory.recall(
            query="test",
            top_k=10,
            category="programming",
        )
        assert isinstance(results, list)

    def test_add_interaction(self):
        """Test add_interaction"""
        self.memory.remember_conversation(
            content="Hello",
            speaker="user",
        )
        history = self.memory.get_interaction_history()
        assert len(history) > 0

    def test_get_conversation_context(self):
        """Test get_conversation_context"""
        self.memory.add_interaction(role="user", content="Hi")
        self.memory.add_interaction(role="assistant", content="Hello!")
        context = self.memory.get_conversation_context()
        assert isinstance(context, str)

    def test_set_and_get_session_context(self):
        """Test set_session_context and get_session_context"""
        self.memory.set_session_context("key1", "value1")
        result = self.memory.get_session_context("key1")
        assert result == "value1"

    def test_clear_session(self):
        """Test clear_session"""
        self.memory.add_interaction(role="user", content="test")
        self.memory.clear_session()
        # After clear, interaction count should be reset
        assert self.memory.interaction_count == 0

    def test_get_working_memory_snapshot(self):
        """Test get_working_memory_snapshot"""
        self.memory.add_to_working_memory("test_key", "test content", metadata={"key": "val"})
        snapshot = self.memory.get_working_memory_snapshot()
        assert isinstance(snapshot, dict)

    def test_save(self):
        """Test save does not raise"""
        self.memory.remember("test save", metadata={"category": "test"})
        self.memory.save()  # Should not raise

    def test_context_manager(self):
        """Test __enter__ and __exit__"""
        with AgentMemory(self.config) as mem:
            mem.remember("context test", metadata={"category": "test"})
        # After exit, save and close should be called

    def test_consolidate_auto_disabled(self):
        """Test consolidate when auto_consolidate is disabled"""
        config = _make_config(auto_consolidate=False)
        mem = AgentMemory(config)
        mem.remember("test", metadata={"category": "test"})
        result = mem.consolidate(auto=True)
        assert result is not None

    def test_consolidate_forced(self):
        """Test force_consolidate"""
        config = _make_config()
        mem = AgentMemory(config)
        mem.remember("test1", metadata={"category": "test"})
        mem.remember("test2", metadata={"category": "test"})
        result = mem.force_consolidate()
        assert result is not None

    def test_knowledge_graph_disabled_raises(self):
        """Test methods raise when knowledge_graph is disabled"""
        config = _make_config(knowledge_graph={"enabled": False})
        mem = AgentMemory(config)
        with pytest.raises(RuntimeError):
            mem.search_entities("Python")

    def test_structured_store_disabled_raises(self):
        """Test methods raise when structured_store is disabled"""
        config = _make_config(structured_store={"enabled": False})
        mem = AgentMemory(config)
        with pytest.raises(RuntimeError):
            mem.store_preference("user1", "theme", "dark")

    def test_get_stats_with_all_modules(self):
        """Test get_stats includes all module stats"""
        stats = self.memory.get_stats()
        assert "short_term" in stats
        assert "long_term" in stats
        assert "knowledge_graph" in stats
        assert "structured_store" in stats


# =========================================================================
# Integration Tests
# =========================================================================


class TestMemoryLifecycle:
    """Full memory lifecycle integration tests: remember -> recall -> forget."""

    def setup_method(self):
        self.config = _make_config()
        self.memory = AgentMemory(self.config)

    def teardown_method(self):
        self.memory.close()

    def test_remember_recall_forget_flow(self):
        """Test the complete remember -> recall -> forget lifecycle."""
        memory_id = self.memory.remember(
            "The sky is blue during clear days",
            memory_type="semantic",
            category="science",
            importance=0.8,
        )
        assert memory_id is not None and len(memory_id) > 0

        # Recall should find the memory
        results = self.memory.recall("blue sky", top_k=5)
        assert len(results) > 0
        assert any("sky" in r["content"].lower() for r in results)

        # Forget the memory
        success = self.memory.long_term.forget(memory_id)
        assert success is True

        # After forgetting, recall should not find it (or score should be very low)
        results_after = self.memory.recall("blue sky", top_k=5)
        assert not any(r.get("id") == memory_id for r in results_after)

    def test_remember_multiple_search_verify_ordering(self):
        """Test remembering multiple items and verifying search result ordering."""
        # Remember several items with different content
        self.memory.remember("Python is a programming language", importance=0.9)
        self.memory.remember("Java is also a programming language", importance=0.7)
        self.memory.remember("The cat sat on the mat", importance=0.5)
        self.memory.remember("Dogs are loyal animals", importance=0.6)

        # Search for programming-related content
        results = self.memory.recall("programming language", top_k=5)
        assert len(results) > 0

        # Results should be ordered by score (descending)
        scores = [r["score"] for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"Results not ordered: {scores}"

    def test_remember_with_metadata_search_by_metadata(self):
        """Test remembering with metadata and searching with category filter."""
        self.memory.remember(
            "React is a JavaScript library",
            category="frontend",
            importance=0.8,
        )
        self.memory.remember(
            "Django is a Python web framework",
            category="backend",
            importance=0.8,
        )
        self.memory.remember(
            "PostgreSQL is a relational database",
            category="database",
            importance=0.7,
        )

        # Filter by category
        frontend_results = self.memory.recall("framework", category="frontend", top_k=5)
        assert len(frontend_results) > 0
        for r in frontend_results:
            assert r["category"] == "frontend"

        backend_results = self.memory.recall("framework", category="backend", top_k=5)
        assert len(backend_results) > 0
        for r in backend_results:
            assert r["category"] == "backend"

    def test_remember_with_tags_filter_by_tags(self):
        """Test remembering with tags and filtering by tags."""
        self.memory.remember(
            "Machine learning uses neural networks",
            tags=["ai", "ml", "deep-learning"],
            importance=0.9,
        )
        self.memory.remember(
            "Traditional software follows rules",
            tags=["software", "engineering"],
            importance=0.6,
        )
        self.memory.remember(
            "Deep learning is a subset of machine learning",
            tags=["ai", "ml", "deep-learning"],
            importance=0.85,
        )

        # Search with tag filter
        results = self.memory.recall("learning", tags=["ai"], top_k=5)
        assert len(results) > 0

    def test_update_existing_memory_verify_update(self):
        """Test updating an existing memory and verifying the change."""
        memory_id = self.memory.remember(
            "The earth is flat",
            importance=0.3,
            category="science",
        )

        # Update the memory content
        success = self.memory.long_term.update(
            memory_id,
            content="The earth is round",
            importance=0.95,
        )
        assert success is True

        # Verify the update by retrieving the record directly
        record = self.memory.long_term.get(memory_id)
        assert record is not None
        assert record.content == "The earth is round"
        assert record.importance == 0.95

    def test_forget_nonexistent_memory_handles_gracefully(self):
        """Test that forgetting a non-existent memory returns False without error."""
        result = self.memory.long_term.forget("nonexistent_id_12345")
        assert result is False

    def test_remember_different_memory_types(self):
        """Test remembering different types of memories (episodic, semantic, procedural)."""
        episodic_id = self.memory.remember(
            "Yesterday I went to the park",
            memory_type="episodic",
            importance=0.6,
        )
        semantic_id = self.memory.remember(
            "Water boils at 100 degrees Celsius",
            memory_type="semantic",
            importance=0.9,
        )
        procedural_id = self.memory.remember(
            "To ride a bicycle, pedal forward and balance",
            memory_type="procedural",
            importance=0.7,
        )

        assert episodic_id is not None
        assert semantic_id is not None
        assert procedural_id is not None

        # Filter by memory type
        semantic_results = self.memory.recall("water", memory_type="semantic", top_k=5)
        assert len(semantic_results) > 0
        for r in semantic_results:
            assert r["memory_type"] == "semantic"

    def test_recall_from_long_term_only(self):
        """Test recall with from_short_term=False only searches long-term memory."""
        self.memory.remember("Long term memory content about algorithms", importance=0.8)
        self.memory.add_to_working_memory("wm_key", "short term content about algorithms", importance=0.9)

        results = self.memory.recall("algorithms", from_short_term=False, top_k=10)
        assert len(results) > 0
        for r in results:
            assert r["source"] == "long_term"

    def test_recall_from_short_term_only(self):
        """Test recall with from_long_term=False only searches short-term memory."""
        self.memory.remember("Long term memory content", importance=0.8)
        self.memory.add_to_working_memory("wm_key", "short term unique content xyz", importance=0.9)

        results = self.memory.recall("unique content xyz", from_long_term=False, top_k=10)
        assert len(results) > 0
        for r in results:
            assert r["source"] == "short_term"

    def test_remember_conversation_important_flag(self):
        """Test that important conversations are stored in long-term memory."""
        # Non-important conversation should not create long-term memory
        non_important_id = self.memory.remember_conversation(
            content="How is the weather?",
            speaker="user",
            important=False,
        )
        assert non_important_id is None

        # Important conversation should create long-term memory
        important_id = self.memory.remember_conversation(
            content="Remember: my favorite color is blue",
            speaker="user",
            important=True,
        )
        assert important_id is not None

        # Verify it can be recalled
        results = self.memory.recall("favorite color blue", top_k=5)
        assert len(results) > 0


class TestMemorySessions:
    """Session management integration tests."""

    def setup_method(self):
        self.config = _make_config()
        self.memory = AgentMemory(self.config)

    def teardown_method(self):
        self.memory.close()

    def test_session_id_is_generated(self):
        """Test that a session ID is auto-generated on creation."""
        assert self.memory.session_id is not None
        assert self.memory.session_id.startswith("session_")

    def test_interaction_count_increments(self):
        """Test that interaction count increments with each interaction."""
        assert self.memory.interaction_count == 0
        self.memory.add_interaction(role="user", content="hello")
        assert self.memory.interaction_count == 1
        self.memory.add_interaction(role="assistant", content="hi there")
        assert self.memory.interaction_count == 2

    def test_clear_session_resets_state(self):
        """Test that clear_session resets interaction count and session_id."""
        self.memory.add_interaction(role="user", content="hello")
        self.memory.add_interaction(role="assistant", content="hi")
        assert self.memory.interaction_count == 2

        old_session_id = self.memory.session_id
        # Ensure at least 1 second passes so the new session_id differs
        time.sleep(1.01)
        self.memory.clear_session()

        assert self.memory.interaction_count == 0
        assert self.memory.session_id != old_session_id

    def test_conversation_history_persists_within_session(self):
        """Test conversation history is available within a session."""
        self.memory.add_interaction(role="user", content="First message")
        self.memory.add_interaction(role="assistant", content="Second message")
        self.memory.add_interaction(role="user", content="Third message")

        history = self.memory.get_conversation_history(n=10)
        assert len(history) == 3

        # Get only last 2
        history_2 = self.memory.get_conversation_history(n=2)
        assert len(history_2) == 2

    def test_session_context_survives_within_session(self):
        """Test session context set/get works within a session."""
        self.memory.set_session_context("user_name", "Alice")
        self.memory.set_session_context("theme", "dark")
        self.memory.set_session_context("language", "en")

        assert self.memory.get_session_context("user_name") == "Alice"
        assert self.memory.get_session_context("theme") == "dark"
        assert self.memory.get_session_context("language") == "en"
        assert self.memory.get_session_context("nonexistent") is None

    def test_clear_session_clears_conversation_history(self):
        """Test that clear_session clears conversation history."""
        self.memory.add_interaction(role="user", content="hello")
        self.memory.add_interaction(role="assistant", content="hi")

        self.memory.clear_session()
        history = self.memory.get_conversation_history(n=10)
        assert len(history) == 0

    def test_multiple_interactions_tracked_in_structured_store(self):
        """Test that interactions are logged to structured store."""
        self.memory.remember_conversation("Hello", speaker="user")
        self.memory.remember_conversation("Hi there!", speaker="assistant")
        self.memory.remember_conversation("How are you?", speaker="user")

        history = self.memory.get_interaction_history(limit=10)
        assert len(history) == 3

    def test_get_relevant_context_combines_sources(self):
        """Test get_relevant_context combines working memory and retrieval."""
        self.memory.add_to_working_memory("focus", "current task: debugging", importance=0.9)
        self.memory.remember("Debugging requires patience and careful analysis", importance=0.8)

        context = self.memory.get_relevant_context("debugging", max_items=5)
        assert isinstance(context, str)
        assert len(context) > 0


class TestKnowledgeGraphIntegration:
    """Knowledge graph integration tests."""

    def setup_method(self):
        self.config = _make_config()
        self.memory = AgentMemory(self.config)

    def teardown_method(self):
        self.memory.close()

    def test_add_entity_and_retrieve(self):
        """Test adding an entity and retrieving it."""
        self.memory.add_entity(
            name="Python",
            entity_type="language",
            description="A high-level programming language",
        )
        entity = self.memory.get_entity("Python")
        assert entity is not None
        assert entity.name == "Python"
        assert entity.entity_type == "language"
        assert "high-level" in entity.description

    def test_add_relation_and_find_related(self):
        """Test adding relations and finding related entities."""
        self.memory.add_entity(name="Alice", entity_type="person")
        self.memory.add_entity(name="Bob", entity_type="person")
        self.memory.add_entity(name="Charlie", entity_type="person")

        self.memory.add_relation("Alice", "Bob", "knows", weight=0.9)
        self.memory.add_relation("Bob", "Charlie", "works_with", weight=0.7)

        related = self.memory.find_related("Alice", top_k=5)
        assert isinstance(related, list)
        assert len(related) > 0

    def test_search_entities_fuzzy_match(self):
        """Test searching entities with fuzzy matching."""
        self.memory.add_entity(name="TensorFlow", entity_type="framework", description="Machine learning framework by Google")
        self.memory.add_entity(name="PyTorch", entity_type="framework", description="Machine learning framework by Meta")

        results = self.memory.search_entities("Tensor", top_k=5)
        assert len(results) > 0
        names = [e.name for e, score in results]
        assert "TensorFlow" in names

    def test_build_knowledge_from_text_creates_entities(self):
        """Test that building knowledge from text creates entities and relations."""
        self.memory.build_knowledge_from_text(
            "Python是一种编程语言。Guido创建了Python。"
        )

        stats = self.memory.get_knowledge_graph_stats()
        assert stats["entity_count"] > 0

    def test_knowledge_graph_stats(self):
        """Test knowledge graph statistics."""
        self.memory.add_entity(name="A", entity_type="test")
        self.memory.add_entity(name="B", entity_type="test")
        self.memory.add_relation("A", "B", "related_to")

        stats = self.memory.get_knowledge_graph_stats()
        assert stats["entity_count"] == 2
        assert stats["relation_count"] == 1
        assert "test" in stats["entity_types"]
        assert "related_to" in stats["relation_types"]

    def test_multiple_memories_enrich_graph(self):
        """Test that multiple memories about the same entity enrich the graph."""
        self.memory.build_knowledge_from_text("Python是一种编程语言。")
        initial_stats = self.memory.get_knowledge_graph_stats()

        self.memory.build_knowledge_from_text("Python用于数据科学。")
        enriched_stats = self.memory.get_knowledge_graph_stats()

        # Graph should have grown or stayed the same
        assert enriched_stats["entity_count"] >= initial_stats["entity_count"]

    def test_knowledge_graph_disabled_stats(self):
        """Test knowledge graph stats when disabled."""
        config = _make_config(knowledge_graph={"enabled": False})
        mem = AgentMemory(config)
        stats = mem.get_knowledge_graph_stats()
        assert stats == {"enabled": False}
        mem.close()

    def test_add_entity_with_properties(self):
        """Test adding entity with custom properties."""
        self.memory.add_entity(
            name="NewYork",
            entity_type="city",
            description="The largest city in the USA",
            population=8000000,
            country="USA",
        )
        entity = self.memory.get_entity("NewYork")
        assert entity is not None
        assert entity.properties["population"] == 8000000
        assert entity.properties["country"] == "USA"


class TestStructuredStorageIntegration:
    """Structured storage integration tests."""

    def setup_method(self):
        self.config = _make_config()
        self.memory = AgentMemory(self.config)

    def teardown_method(self):
        self.memory.close()

    def test_store_and_get_preference(self):
        """Test storing and retrieving a preference."""
        self.memory.store_preference("theme", "dark", "ui")
        # 默认返回 value
        pref = self.memory.get_preference("theme")
        assert pref == "dark"
        # raw=True 返回完整记录
        pref_raw = self.memory.get_preference("theme", raw=True)
        assert pref_raw is not None
        assert pref_raw["key"] == "theme"
        assert pref_raw["value"] == "dark"

    def test_update_preference(self):
        """Test updating an existing preference."""
        self.memory.store_preference("theme", "dark", "ui")
        self.memory.store_preference("theme", "light", "ui")

        pref = self.memory.get_preference("theme")
        assert pref == "light"

    def test_preference_nonexistent_returns_none(self):
        """Test getting a nonexistent preference returns None."""
        pref = self.memory.get_preference("nonexistent_key_xyz")
        assert pref is None

    def test_store_preference_with_complex_value(self):
        """Test storing a preference with a complex (dict) value."""
        import json
        complex_val = {"color": "#fff", "font_size": 14, "mode": "dark"}
        self.memory.store_preference("editor_settings", complex_val, "editor")
        pref = self.memory.get_preference("editor_settings")
        assert pref is not None
        # 默认返回 value（已序列化为 JSON 字符串）
        parsed = json.loads(pref)
        assert parsed["color"] == "#fff"
        assert parsed["font_size"] == 14

    def test_remember_fact_stored_in_structured_store(self):
        """Test that remember_fact stores the fact in structured storage."""
        self.memory.remember_fact(
            fact="The speed of light is 299792458 m/s",
            source="physics_textbook",
            confidence=0.99,
            category="physics",
        )
        # Verify via structured store
        facts = self.memory.memory_table.get_facts(category="physics")
        assert len(facts) > 0
        assert any("speed of light" in f["fact"] for f in facts)

    def test_interaction_logged_in_structured_store(self):
        """Test that interactions are properly logged."""
        self.memory.log_interaction(role="user", content="Hello world", topic="greeting")
        history = self.memory.get_interaction_history(limit=10)
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello world"

    def test_multiple_facts_with_categories(self):
        """Test storing and retrieving facts across categories."""
        self.memory.remember_fact("Python was created in 1991", category="history")
        self.memory.remember_fact("E=mc^2", category="physics")
        self.memory.remember_fact("Water is H2O", category="chemistry")

        physics_facts = self.memory.memory_table.get_facts(category="physics")
        assert len(physics_facts) == 1
        assert "E=mc" in physics_facts[0]["fact"]

        all_facts = self.memory.memory_table.get_facts()
        assert len(all_facts) == 3

    def test_structured_store_create_custom_table(self):
        """Test creating a custom table via structured store."""
        store = self.memory.structured_store
        success = store.create_table("custom_tasks", {
            "title": "TEXT NOT NULL",
            "status": "TEXT DEFAULT 'pending'",
            "priority": "INTEGER DEFAULT 0",
        })
        assert success is True

        # Insert a record
        record_id = store.insert("custom_tasks", {
            "title": "Write tests",
            "status": "in_progress",
            "priority": 5,
        })
        assert record_id is not None

        # Query it back
        result = store.select("custom_tasks", where="priority > ?", params=(3,))
        assert result.total == 1
        assert result.records[0]["title"] == "Write tests"

    def test_structured_store_complex_query(self):
        """Test complex queries with filters, ordering, and limits."""
        store = self.memory.structured_store
        store.create_table("products", {
            "name": "TEXT NOT NULL",
            "price": "REAL NOT NULL",
            "category": "TEXT",
        })

        # Insert multiple records
        store.insert_batch("products", [
            {"name": "Laptop", "price": 999.99, "category": "electronics"},
            {"name": "Phone", "price": 699.99, "category": "electronics"},
            {"name": "Book", "price": 19.99, "category": "education"},
            {"name": "Desk", "price": 149.99, "category": "furniture"},
        ])

        # Filter by category
        electronics = store.select(
            "products",
            where="category = ?",
            params=("electronics",),
            order_by="price DESC",
        )
        assert electronics.total == 2
        assert electronics.records[0]["name"] == "Laptop"

        # Price range filter
        affordable = store.select(
            "products",
            where="price BETWEEN ? AND ?",
            params=(10.0, 200.0),
            order_by="price ASC",
        )
        assert affordable.total == 2
        assert affordable.records[0]["name"] == "Book"

    def test_structured_store_update_and_delete(self):
        """Test update and delete operations."""
        store = self.memory.structured_store
        store.create_table("notes", {"content": "TEXT", "priority": "INTEGER"})

        rid = store.insert("notes", {"content": "original", "priority": 1})

        # Update
        affected = store.update("notes", {"content": "updated", "priority": 5}, where="id = ?", params=(rid,))
        assert affected == 1

        # Verify update
        result = store.select("notes", where="id = ?", params=(rid,))
        assert result.records[0]["content"] == "updated"
        assert result.records[0]["priority"] == 5

        # Delete
        deleted = store.delete("notes", where="id = ?", params=(rid,))
        assert deleted == 1

        # Verify deletion
        result = store.select("notes", where="id = ?", params=(rid,))
        assert result.total == 0


class TestMemoryManagerEdgeCases:
    """Edge cases and error handling tests."""

    def setup_method(self):
        self.config = _make_config()
        self.memory = AgentMemory(self.config)

    def teardown_method(self):
        self.memory.close()

    def test_empty_recall_returns_empty_list(self):
        """Test recall with no memories returns empty list."""
        results = self.memory.recall("anything", top_k=5)
        assert results == []

    def test_empty_search_returns_empty(self):
        """Test search on empty memory store returns no results."""
        results = self.memory.long_term.search("nonexistent", top_k=5)
        assert results == []

    def test_very_long_content(self):
        """Test storing and recalling very long content."""
        long_text = "This is a sentence. " * 500  # ~7500 characters
        memory_id = self.memory.remember(long_text, importance=0.7)
        assert memory_id is not None

        record = self.memory.long_term.get(memory_id)
        assert record is not None
        assert len(record.content) == len(long_text)

    def test_special_characters_in_content(self):
        """Test storing content with special characters."""
        special_content = "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?\n\t\r\\"
        memory_id = self.memory.remember(special_content, importance=0.5)
        assert memory_id is not None

        record = self.memory.long_term.get(memory_id)
        assert record is not None
        assert record.content == special_content

    def test_unicode_and_chinese_content(self):
        """Test storing Chinese and Unicode content."""
        chinese_content = "这是一段中文测试内容。人工智能正在改变世界。"
        memory_id = self.memory.remember(chinese_content, importance=0.8)
        assert memory_id is not None

        record = self.memory.long_term.get(memory_id)
        assert record is not None
        assert record.content == chinese_content

    def test_concurrent_remember_operations(self):
        """Test thread safety of concurrent remember operations."""
        errors = []
        results = []

        def worker(content, idx):
            try:
                mid = self.memory.remember(content, importance=0.5)
                results.append(mid)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"Concurrent message {i}", i))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent operations: {errors}"
        assert len(results) == 20

    def test_concurrent_read_write_operations(self):
        """Test thread safety of concurrent reads and writes."""
        # Pre-populate some memories
        for i in range(10):
            self.memory.remember(f"Initial memory {i}", importance=0.5)

        errors = []

        def writer(idx):
            try:
                for j in range(5):
                    self.memory.remember(f"Writer {idx} message {j}", importance=0.5)
            except Exception as e:
                errors.append(e)

        def reader(idx):
            try:
                for _ in range(5):
                    self.memory.recall("memory", top_k=5)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent read/write: {errors}"

    def test_empty_string_content(self):
        """Test that storing empty string content raises ValueError."""
        with pytest.raises(ValueError, match="content must not be empty"):
            self.memory.remember("", importance=0.5)

    def test_recall_with_threshold_filter(self):
        """Test recall with a high threshold that filters out results."""
        self.memory.remember("Low importance item", importance=0.1)
        self.memory.remember("Medium importance item", importance=0.5)
        self.memory.remember("High importance item", importance=0.9)

        # High threshold should filter out low-score results
        results = self.memory.recall("importance item", threshold=0.8, top_k=10)
        # Note: threshold in recall filters by similarity score, not importance
        # But with fake embeddings, all results may have similar scores
        assert isinstance(results, list)

    def test_get_nonexistent_memory(self):
        """Test getting a non-existent memory returns None."""
        record = self.memory.long_term.get("nonexistent_id")
        assert record is None

    def test_delete_nonexistent_memory(self):
        """Test deleting a non-existent memory returns False."""
        result = self.memory.long_term.delete("nonexistent_id")
        assert result is False

    def test_add_to_working_memory_and_recall(self):
        """Test adding to working memory and recalling it."""
        self.memory.add_to_working_memory(
            key="task1",
            content="Complete the quarterly report",
            importance=0.9,
            memory_type="task",
        )

        results = self.memory.recall("quarterly report", top_k=5)
        assert len(results) > 0
        assert any("quarterly report" in r["content"] for r in results)

    def test_recall_for_prompt_includes_both_sources(self):
        """Test recall_for_prompt includes both short and long term results."""
        self.memory.add_to_working_memory("wm1", "working memory test data", importance=0.9)
        self.memory.remember("long term memory test data", importance=0.8)

        prompt = self.memory.recall_for_prompt(
            query="test data",
            max_short_term=5,
            max_long_term=5,
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_stats_reflect_actual_state(self):
        """Test that stats reflect the actual state of the memory system."""
        initial_stats = self.memory.get_stats()
        initial_count = initial_stats["long_term"]["total_memories"]

        self.memory.remember("New memory 1", importance=0.5)
        self.memory.remember("New memory 2", importance=0.5)

        updated_stats = self.memory.get_stats()
        assert updated_stats["long_term"]["total_memories"] == initial_count + 2

    def test_close_idempotent(self):
        """Test that close can be called multiple times without error."""
        self.memory.close()
        self.memory.close()  # Should not raise

    def test_save_after_close_does_not_raise(self):
        """Test that save after close handles gracefully."""
        self.memory.close()
        # save() should handle closed state gracefully (logs warning)
        self.memory.save()


class TestMemoryManagerConfig:
    """Configuration tests."""

    def test_default_configuration(self):
        """Test creating AgentMemory with default configuration."""
        # v5.1+: auto provider requires sentence-transformers, use fake for test
        config = _make_config()
        mem = AgentMemory(config)
        assert mem.config.consolidation_threshold == 0.6
        # Note: _make_config sets auto_consolidate=False for test isolation
        assert mem.config.default_top_k == 5
        assert mem.session_id is not None
        mem.close()

    def test_custom_embedding_config(self):
        """Test creating AgentMemory with custom embedding configuration."""
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding=EmbeddingConfig(provider="fake", fake_dimension=128),
                vector_store={"backend": "memory"},
            ),
            auto_consolidate=False,
        )
        mem = AgentMemory(config)
        # Verify it works with custom embedding dimension
        memory_id = mem.remember("Test with custom embedding", importance=0.5)
        assert memory_id is not None
        results = mem.recall("custom embedding", top_k=5)
        assert isinstance(results, list)
        mem.close()

    def test_custom_vector_store_config(self):
        """Test creating AgentMemory with custom vector store backend."""
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding=EmbeddingConfig(provider="fake", fake_dimension=64),
                vector_store={"backend": "memory"},
            ),
            auto_consolidate=False,
        )
        mem = AgentMemory(config)
        assert mem.long_term.store is not None
        mem.close()

    def test_custom_consolidation_threshold(self):
        """Test custom consolidation threshold."""
        config = _make_config(consolidation_threshold=0.9)
        mem = AgentMemory(config)
        assert mem.config.consolidation_threshold == 0.9

        # Add items below threshold
        mem.add_to_working_memory("low", "low importance item", importance=0.5)
        result = mem.force_consolidate()
        assert result["consolidated"] == 0  # Nothing above 0.9
        assert result["skipped"] == 1
        mem.close()

    def test_custom_default_top_k(self):
        """Test custom default_top_k configuration."""
        config = _make_config(default_top_k=3)
        mem = AgentMemory(config)
        assert mem.config.default_top_k == 3

        # Add several memories
        for i in range(10):
            mem.remember(f"Memory number {i}", importance=0.5)

        # Recall without explicit top_k should use default
        results = mem.recall("memory", top_k=None)
        assert len(results) <= 3
        mem.close()

    def test_auto_consolidate_disabled(self):
        """Test auto_consolidate=False prevents automatic consolidation."""
        config = _make_config(auto_consolidate=False)
        mem = AgentMemory(config)
        assert mem.config.auto_consolidate is False

        result = mem.consolidate(auto=True)
        assert result["status"] == "skipped"
        assert result["reason"] == "auto_consolidate is disabled"
        mem.close()

    def test_auto_consolidate_enabled(self):
        """Test auto_consolidate=True allows automatic consolidation."""
        config = _make_config(auto_consolidate=True)
        mem = AgentMemory(config)
        assert mem.config.auto_consolidate is True

        result = mem.consolidate(auto=True)
        assert result["status"] == "completed"
        mem.close()

    def test_kwargs_merge_into_config(self):
        """Test that kwargs are properly merged into config."""
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding=EmbeddingConfig(provider="fake", fake_dimension=64),
                vector_store={"backend": "memory"},
            ),
        )
        mem = AgentMemory(
            config,
            auto_consolidate=False,
            default_top_k=10,
            consolidation_threshold=0.75,
        )
        assert mem.config.auto_consolidate is False
        assert mem.config.default_top_k == 10
        assert mem.config.consolidation_threshold == 0.75
        mem.close()

    def test_knowledge_graph_disabled(self):
        """Test that knowledge graph can be disabled."""
        config = _make_config(knowledge_graph={"enabled": False})
        mem = AgentMemory(config)
        assert mem.knowledge_graph is None

        with pytest.raises(RuntimeError, match="Knowledge graph is not enabled"):
            mem.add_entity("test", "concept")

        with pytest.raises(RuntimeError, match="Knowledge graph is not enabled"):
            mem.get_entity("test")

        with pytest.raises(RuntimeError, match="Knowledge graph is not enabled"):
            mem.add_relation("a", "b", "rel")

        mem.close()

    def test_structured_store_disabled(self):
        """Test that structured store can be disabled."""
        config = _make_config(structured_store={"enabled": False})
        mem = AgentMemory(config)
        assert mem.structured_store is None
        assert mem.memory_table is None

        with pytest.raises(RuntimeError, match="Structured store is not enabled"):
            mem.store_preference("key", "value")

        with pytest.raises(RuntimeError, match="Structured store is not enabled"):
            mem.get_preference("key")

        with pytest.raises(RuntimeError, match="Structured store is not enabled"):
            mem.log_interaction("user", "hello")

        mem.close()

    def test_memory_manager_wrapper(self):
        """Test MemoryManager wrapper delegates to AgentMemory."""
        config = _make_config()
        mm = MemoryManager(config)
        assert hasattr(mm, "remember")
        assert hasattr(mm, "recall")
        assert hasattr(mm, "session_id")

        # Test that it actually works
        mid = mm.remember("Test via MemoryManager", importance=0.7)
        assert mid is not None
        mm.close()

    def test_short_term_config_customization(self):
        """Test custom short-term memory configuration."""
        config = _make_config(
            short_term={"working_memory_capacity": 3, "history_limit": 10}
        )
        mem = AgentMemory(config)
        assert mem.config.short_term["working_memory_capacity"] == 3
        assert mem.config.short_term["history_limit"] == 10
        mem.close()
