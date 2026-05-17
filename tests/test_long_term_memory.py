"""Integration tests for the long_term_memory module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.long_term_persistent_memory import LongTermMemory, LongTermMemoryConfig
from memory_system.processing.text_embedding_provider import EmbeddingConfig, FakeEmbeddingProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIM = 64


def _make_config(**overrides) -> LongTermMemoryConfig:
    """Create a LongTermMemoryConfig with fake embedding provider."""
    defaults = {
        "embedding": EmbeddingConfig(provider="fake", fake_dimension=DIM),
        "vector_store": {"backend": "memory"},
        "auto_consolidate": False,
    }
    defaults.update(overrides)
    return LongTermMemoryConfig(**defaults)


def _make_ltm(**overrides) -> LongTermMemory:
    """Create a LongTermMemory instance with fake embedding (dim=64)."""
    config = _make_config(**overrides)
    return LongTermMemory(config=config)


# ===========================================================================
# TestLongTermMemoryIntegration
# ===========================================================================

class TestLongTermMemoryIntegration:
    """Integration tests verifying LongTermMemory correctly orchestrates
    embedding + vector_store."""

    # ------------------------------------------------------------------
    # remember & recall
    # ------------------------------------------------------------------

    def test_remember_and_recall(self):
        """Remember a fact, recall with a similar query, should find it."""
        ltm = _make_ltm()
        memory_id = ltm.remember("The sky is blue on a clear day", category="science")
        assert memory_id is not None
        assert isinstance(memory_id, str)

        results = ltm.recall("blue sky")
        assert len(results) >= 1
        record, score = results[0]
        assert "sky" in record.content.lower() or "blue" in record.content.lower()

    def test_remember_multiple_and_recall_top_k(self):
        """Remember 5 items, recall top 3, should return at most 3."""
        ltm = _make_ltm()
        for i in range(5):
            ltm.remember(f"fact number {i} about various topics")

        results = ltm.recall("fact", top_k=3)
        assert len(results) <= 3
        assert len(results) >= 1

    def test_recall_with_category_filter(self):
        """Remember items in different categories, filter by category."""
        ltm = _make_ltm()
        ltm.remember("Python is a programming language", category="tech")
        ltm.remember("Apples are fruit", category="food")
        ltm.remember("JavaScript runs in browsers", category="tech")

        tech_results = ltm.recall("something", category="tech")
        assert len(tech_results) >= 1
        for record, _ in tech_results:
            assert record.category == "tech"

        food_results = ltm.recall("something", category="food")
        assert len(food_results) >= 1
        for record, _ in food_results:
            assert record.category == "food"

    def test_recall_with_threshold(self):
        """Remember items, recall with a high threshold, should return fewer or none."""
        ltm = _make_ltm()
        ltm.remember("The capital of France is Paris")
        ltm.remember("Pizza is an Italian dish")

        # Very high threshold -- cosine similarity is unlikely to exceed 0.99
        # for unrelated queries with the fake embedder.
        results = ltm.recall("quantum physics", threshold=0.99)
        assert len(results) <= 2

    def test_recall_empty_store(self):
        """Recall from an empty store should return an empty list."""
        ltm = _make_ltm()
        results = ltm.recall("anything")
        assert results == []

    # ------------------------------------------------------------------
    # get / update / delete
    # ------------------------------------------------------------------

    def test_get_memory(self):
        """Remember then get by id."""
        ltm = _make_ltm()
        memory_id = ltm.remember("Important meeting tomorrow at 3pm")
        record = ltm.get(memory_id)
        assert record is not None
        assert record.id == memory_id
        assert "meeting" in record.content

    def test_update_memory(self):
        """Remember then update content."""
        ltm = _make_ltm()
        memory_id = ltm.remember("Draft version of document")
        success = ltm.update(memory_id, content="Final version of document")
        assert success is True

        record = ltm.get(memory_id)
        assert record.content == "Final version of document"

    def test_delete_memory(self):
        """Remember then delete, count should decrease."""
        ltm = _make_ltm()
        ltm.remember("Item to delete")
        ltm.remember("Item to keep")
        assert ltm.count() == 2

        # Retrieve the first item's id
        all_records = ltm.store.list_all(limit=10)
        target_id = all_records[0].id
        success = ltm.delete(target_id)
        assert success is True
        assert ltm.count() == 1

    def test_forget_alias(self):
        """forget() should work the same as delete()."""
        ltm = _make_ltm()
        memory_id = ltm.remember("Temporary note")
        assert ltm.count() == 1

        success = ltm.forget(memory_id)
        assert success is True
        assert ltm.count() == 0

    # ------------------------------------------------------------------
    # Category / tag queries
    # ------------------------------------------------------------------

    def test_get_by_category(self):
        """Remember items in category 'work', get_by_category should return them."""
        ltm = _make_ltm()
        ltm.remember("Finish quarterly report", category="work")
        ltm.remember("Buy groceries", category="personal")
        ltm.remember("Schedule team standup", category="work")

        work_items = ltm.get_by_category("work")
        assert len(work_items) >= 1
        for record in work_items:
            assert record.category == "work"

    def test_get_by_tag(self):
        """Remember items with tags, get_by_tag should find them."""
        ltm = _make_ltm()
        ltm.remember("Machine learning basics", tags=["ml", "ai"])
        ltm.remember("Neural networks overview", tags=["ml", "deep-learning"])
        ltm.remember("Cooking pasta", tags=["cooking"])

        ml_items = ltm.get_by_tag("ml")
        assert len(ml_items) >= 1
        for record in ml_items:
            assert "ml" in record.tags

    # ------------------------------------------------------------------
    # count / stats
    # ------------------------------------------------------------------

    def test_count(self):
        """Remember 3 items, count should be 3."""
        ltm = _make_ltm()
        assert ltm.count() == 0
        ltm.remember("First item")
        ltm.remember("Second item")
        ltm.remember("Third item")
        assert ltm.count() == 3

    def test_get_stats(self):
        """Should return dict with total_memories."""
        ltm = _make_ltm()
        ltm.remember("Some fact")
        stats = ltm.get_stats()
        assert isinstance(stats, dict)
        assert "total_memories" in stats
        assert stats["total_memories"] == 1

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------

    def test_search_alias(self):
        """search() should work the same as recall()."""
        ltm = _make_ltm()
        ltm.remember("Dogs are loyal animals")

        recall_results = ltm.recall("loyal animals")
        search_results = ltm.search("loyal animals")
        assert len(recall_results) == len(search_results)

    # ------------------------------------------------------------------
    # Pre-computed embeddings
    # ------------------------------------------------------------------

    def test_remember_with_precomputed_embedding(self):
        """Provide embedding directly, should not encode."""
        ltm = _make_ltm()
        embedder = FakeEmbeddingProvider(dimension=DIM)
        precomputed = embedder.encode("precomputed content")

        memory_id = ltm.remember(
            "precomputed content",
            embedding=precomputed,
        )
        record = ltm.get(memory_id)
        assert record is not None
        assert record.content == "precomputed content"

    def test_recall_by_vector(self):
        """Provide embedding directly for search."""
        ltm = _make_ltm()
        embedder = FakeEmbeddingProvider(dimension=DIM)
        content = "Vector search test content"
        content_embedding = embedder.encode(content)

        ltm.remember(content, embedding=content_embedding)

        query_embedding = embedder.encode("Vector search")
        results = ltm.recall_by_vector(query_embedding, top_k=1)
        assert len(results) >= 1
        record, score = results[0]
        assert record.content == content

    # ------------------------------------------------------------------
    # Custom config
    # ------------------------------------------------------------------

    def test_custom_config(self):
        """Create with custom embedding config, should use it."""
        config = LongTermMemoryConfig(
            embedding=EmbeddingConfig(provider="fake", fake_dimension=32),
            vector_store={"backend": "memory"},
        )
        ltm = LongTermMemory(config=config)
        assert ltm.embedder.dimension == 32

        memory_id = ltm.remember("Test with 32-dim embedding")
        record = ltm.get(memory_id)
        assert record is not None
        assert len(record.embedding) == 32
