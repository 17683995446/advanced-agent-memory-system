"""Integration tests for Agent Memory System v3.6.

Tests cross-module interactions and end-to-end workflows.
"""
import pytest
import sys
import os
import time
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.processing.text_embedding_provider import (
    FakeEmbeddingProvider,
    EmbeddingFactory,
    EmbeddingConfig,
)
from memory_system.storage.vector_store import (
    MemoryVectorStore,
    MemoryRecord,
    VectorStoreFactory,
)
from memory_system.processing.knowledge_graph_engine import (
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    Entity,
    Relation,
)
from memory_system.storage.structured_sqlite_store import StructuredStore, MemoryTable
from memory_system.core.short_term_working_memory import ShortTermMemory
from memory_system.core.long_term_persistent_memory import LongTermMemory, LongTermMemoryConfig
from memory_system.core.agent_memory_manager import (
    AgentMemory,
    AgentMemoryConfig,
)
from memory_system.infra.blinker_event_bus import (
    EventBus,
    StorageEventType,
    StorageSource,
    get_event_bus,
    reset_event_bus,
)
from memory_system.core.memory_importance_scorer import ImportanceScorer, ScoringStrategy
from memory_system.processing.simhash_deduplicator import MemoryDeduplicator, SimHash
from memory_system.infra.api_rate_limiter import RateLimiter, RateLimitStrategy
from memory_system.core.session_context_manager import SessionManager
from memory_system.processing.memory_data_serializer import MemorySerializer, ExportFormat
from memory_system.processing.memory_content_compressor import MemoryCompressor, CompressionStrategy
from memory_system.infra.memory_version_controller import MemoryVersionControl, SnapshotTrigger
from memory_system.core.streaming_memory_reader import MemoryStreamer, StreamBuffer, StreamConfig
from memory_system.infra.schema_migration_manager import MigrationManager, Migration, MigrationRecord
from memory_system.infra.circuit_breaker_pattern import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerRegistry,
    reset_circuit_registry,
)
from memory_system.storage.multi_level_memory_cache import (
    MemoryCache,
    CacheConfig,
    CacheKeyGenerator,
    CacheSerializer,
)
from memory_system.infra.dynamic_config_manager import (
    ConfigManager,
    DictConfigSource,
    JsonFileConfigSource,
    EnvConfigSource,
    create_config_manager,
)


class TestEmbeddingVectorStoreIntegration:
    """Test embedding + vector store end-to-end."""

    def test_encode_store_search(self):
        """Full pipeline: encode → store → search."""
        provider = FakeEmbeddingProvider(dimension=64)
        store = MemoryVectorStore()

        # Encode and store
        texts = ["hello world", "foo bar baz qux some extra words here", "completely different topic about astronomy"]
        for i, text in enumerate(texts):
            embedding = provider.encode(text)
            record = MemoryRecord(
                id=f"rec_{i}",
                content=text,
                embedding=embedding,
                timestamp=time.time(),
            )
            store.add(record)

        # Search
        query = provider.encode("hello world")
        results = store.search(query, top_k=2)
        assert len(results) >= 1
        assert results[0].record.id == "rec_0"

    def test_batch_encode_store(self):
        """Batch encode and store."""
        provider = FakeEmbeddingProvider(dimension=64)
        store = MemoryVectorStore()

        texts = [f"text number {i}" for i in range(10)]
        embeddings = provider.encode_batch(texts)

        records = [
            MemoryRecord(id=f"rec_{i}", content=texts[i], embedding=embeddings[i], timestamp=time.time())
            for i in range(10)
        ]
        store.add_batch(records)
        assert store.count() == 10

    def test_similarity_search_accuracy(self):
        """Similar texts should rank higher."""
        provider = FakeEmbeddingProvider(dimension=128)
        store = MemoryVectorStore()

        similar_texts = [
            "The cat sat on the mat and looked around the room",
            "A cat is sitting on a mat in the living room",
            "The dog played in the park with a ball and frisbee",
        ]
        for i, text in enumerate(similar_texts):
            embedding = provider.encode(text)
            store.add(MemoryRecord(id=f"rec_{i}", content=text, embedding=embedding, timestamp=time.time()))

        query = provider.encode("A cat on a mat in the room")
        results = store.search(query, top_k=3)
        top_ids = [r.record.id for r in results]
        # Cat-related texts should rank higher than dog
        assert "rec_2" not in top_ids[:2]


class TestMemoryManagerEndToEnd:
    """Test AgentMemory full workflow."""

    def setup_method(self):
        self.memory = AgentMemory(
            config=AgentMemoryConfig(
                long_term=LongTermMemoryConfig(
                    embedding=EmbeddingConfig(provider="fake", fake_dimension=64),
                ),
            )
        )

    def teardown_method(self):
        self.memory.close()

    def test_remember_and_recall(self):
        """Remember a fact and recall it."""
        memory_id = self.memory.remember(
            content="Python is a programming language",
            category="knowledge",
            importance=0.9,
        )
        assert memory_id is not None

        results = self.memory.recall("Python programming", top_k=3)
        assert len(results) >= 1
        assert any("Python" in r["content"] for r in results)

    def test_working_memory_and_consolidation(self):
        """Add to working memory and consolidate."""
        self.memory.add_to_working_memory("key1", "important info", importance=0.9)
        self.memory.add_to_working_memory("key2", "trivial info", importance=0.3)

        snapshot = self.memory.get_working_memory_snapshot()
        assert "key1" in snapshot or len(snapshot) > 0

    def test_knowledge_graph_workflow(self):
        """Add entities and relations, then search."""
        self.memory.add_entity("Python", entity_type="language", description="A programming language")
        self.memory.add_entity("Guido", entity_type="person", description="Creator of Python")
        self.memory.add_relation("Guido", "Python", "created")

        related = self.memory.find_related("Python")
        assert len(related) >= 1

    def test_conversation_flow(self):
        """Simulate a conversation."""
        self.memory.remember_conversation("Hello", speaker="user")
        self.memory.remember_conversation("Hi there!", speaker="assistant")
        self.memory.remember_conversation("What is AI?", speaker="user", important=True)

        history = self.memory.get_conversation_history(n=5)
        assert len(history) >= 3

    def test_context_for_prompt(self):
        """Get context for LLM prompt."""
        self.memory.remember("The sky is blue", category="fact", importance=0.8)
        self.memory.add_to_working_memory("current_task", "Answering questions")

        context = self.memory.get_relevant_context("What color is the sky?", max_items=5)
        assert "sky" in context.lower() or "blue" in context.lower()

    def test_structured_store_preference(self):
        """Store and retrieve preferences."""
        self.memory.store_preference("theme", "dark", category="ui")
        pref = self.memory.get_preference("theme")
        assert pref is not None


class TestEventBusIntegration:
    """Test event bus with storage operations."""

    def setup_method(self):
        reset_event_bus()

    def teardown_method(self):
        reset_event_bus()

    def test_events_on_vector_store_operations(self):
        """Vector store operations should emit events."""
        bus = get_event_bus()
        events = []
        bus.subscribe(StorageEventType.MEMORY_ADD, lambda e: events.append(e))

        from memory_system.storage.unified_storage_backend import UnifiedStorage
        storage = UnifiedStorage(enable_events=True)
        storage.put(content="test content", embedding=[0.1] * 64)

        assert len(events) >= 1

    def test_multiple_event_subscribers(self):
        """Multiple subscribers should all receive events."""
        bus = get_event_bus()
        received1 = []
        received2 = []
        bus.subscribe(StorageEventType.MEMORY_ADD, lambda e: received1.append(e))
        bus.subscribe(StorageEventType.MEMORY_ADD, lambda e: received2.append(e))

        bus.emit(StorageEventType.MEMORY_ADD, source=StorageSource.LONG_TERM, data={"test": True})

        assert len(received1) == 1
        assert len(received2) == 1


class TestDedupImportanceIntegration:
    """Test dedup + importance scoring together."""

    def test_dedup_before_scoring(self):
        """Deduplicate memories then score importance."""
        dedup = MemoryDeduplicator()
        scorer = ImportanceScorer(strategy=ScoringStrategy.TFIDF)

        texts = [
            "The cat sat on the mat",
            "The cat sat on the mat",  # Duplicate
            "Dogs are loyal animals",
        ]

        # Dedup using check() method
        unique_texts = []
        for text in texts:
            result = dedup.check(text)
            if not result.is_duplicate:
                unique_texts.append(text)
                dedup.add(f"mem_{len(unique_texts)}", text)

        assert len(unique_texts) == 2

        # Score
        for text in unique_texts:
            score = scorer.score(text)
            assert score.score >= 0.0


class TestCircuitBreakerIntegration:
    """Test circuit breaker with memory operations."""

    def setup_method(self):
        reset_circuit_registry()

    def test_protect_embedding_call(self):
        """Circuit breaker should protect embedding provider calls."""
        call_count = 0
        fail = True

        def unreliable_embed(text):
            nonlocal call_count
            call_count += 1
            if fail:
                raise ConnectionError("Service unavailable")
            return [0.1] * 64

        breaker = CircuitBreaker(
            "embedding_api",
            config=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=0.1),
        )

        # Should fail 3 times then open
        for _ in range(3):
            with pytest.raises(ConnectionError):
                breaker.execute(unreliable_embed, "test")

        assert breaker.state == CircuitState.OPEN

        # Should reject immediately
        with pytest.raises(Exception):  # CircuitBreakerError
            breaker.execute(unreliable_embed, "test")

    def test_registry_with_multiple_breakers(self):
        """Registry should manage multiple circuit breakers."""
        registry = CircuitBreakerRegistry()
        b1 = registry.register("embedding", CircuitBreakerConfig(failure_threshold=5))
        b2 = registry.register("redis", CircuitBreakerConfig(failure_threshold=3))

        all_stats = registry.list_all()
        assert "embedding" in all_stats
        assert "redis" in all_stats


class TestCacheIntegration:
    """Test cache with memory operations."""

    def test_cache_embedding_results(self):
        """Cache should store and retrieve embedding results."""
        cache = MemoryCache(config=CacheConfig(max_size=100, ttl=60.0))
        provider = FakeEmbeddingProvider(dimension=64)

        # First call: cache miss
        result1 = cache.get_or_set("embed:hello", lambda: provider.encode("hello"))
        # Second call: cache hit
        result2 = cache.get_or_set("embed:hello", lambda: provider.encode("hello"))

        assert result1 == result2
        stats = cache.get_stats()
        assert stats.l1_hits == 1

    def test_cached_decorator_for_expensive_ops(self):
        """Decorator should cache expensive operations."""
        cache = MemoryCache(config=CacheConfig(max_size=100, ttl=60.0))
        call_count = 0

        @cache.cached(ttl=60)
        def expensive_search(query):
            nonlocal call_count
            call_count += 1
            return f"result_for_{query}"

        assert expensive_search("test") == "result_for_test"
        assert expensive_search("test") == "result_for_test"
        assert call_count == 1


class TestConfigManagerIntegration:
    """Test config manager with memory system."""

    def test_config_drives_memory_setup(self):
        """Config manager should drive memory system configuration."""
        manager = ConfigManager()
        manager.add_source(DictConfigSource({
            "short_term": {"working_memory_capacity": 5},
            "consolidation_threshold": 0.7,
        }))
        manager.load()

        capacity = manager.get("short_term.working_memory_capacity")
        assert capacity == 5
        threshold = manager.get("consolidation_threshold")
        assert threshold == 0.7

    def test_config_with_json_file(self, tmp_path):
        """Load config from JSON file."""
        config_file = tmp_path / "memory_config.json"
        config_file.write_text(json.dumps({
            "long_term": {
                "embedding": {
                    "provider": "fake",
                    "fake_dimension": 128,
                }
            },
            "default_top_k": 10,
        }))

        manager = create_config_manager(config_path=config_file)
        assert manager.get("long_term.embedding.provider") == "fake"
        assert manager.get("default_top_k") == 10

    def test_config_change_callback(self):
        """Config changes should trigger callbacks."""
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"debug": False}))
        manager.load()

        changes = []
        manager.on_change("debug", lambda e: changes.append(e))
        manager.set("debug", True)

        assert len(changes) == 1
        assert changes[0].new_value is True


class TestStreamingVersioningIntegration:
    """Test streaming with versioning."""

    def test_stream_and_version(self):
        """Stream memories and create version snapshots."""
        # Create version control
        vc = MemoryVersionControl()

        # Stream data
        data = [f"memory_{i}" for i in range(10)]
        streamer = MemoryStreamer(data, config=StreamConfig(batch_size=3))

        collected = []
        async def collect():
            async for batch in streamer.stream():
                collected.extend(batch.items)

        import asyncio
        asyncio.run(collect())
        assert len(collected) == 10

        # Create snapshot
        snapshot = vc.create_snapshot("stream_result", {"memories": collected})
        assert snapshot is not None


class TestSerializerMigrationIntegration:
    """Test serializer with migration."""

    def test_export_and_import_cycle(self):
        """Export memories and verify format."""
        serializer = MemorySerializer()

        records = [
            {"id": "1", "content": "hello", "category": "general"},
            {"id": "2", "content": "world", "category": "task"},
        ]

        # JSON export
        json_data = serializer.export(records, format=ExportFormat.JSON)
        assert json_data is not None
        imported = serializer.import_data(json_data, format=ExportFormat.JSON)
        assert len(imported) == 2


class TestRateLimiterSessionIntegration:
    """Test rate limiter with session management."""

    def test_rate_limited_session_access(self):
        """Session access should be rate-limited."""
        limiter = RateLimiter(strategy=RateLimitStrategy.TOKEN_BUCKET, rate=10, capacity=10)
        session_mgr = SessionManager(session_timeout=60)

        session = session_mgr.create_session("user1")
        assert session is not None

        # Should allow requests within limit
        for _ in range(10):
            result = limiter.check()
            assert result.allowed is True


class TestFullPipelineIntegration:
    """Full end-to-end pipeline test."""

    def test_complete_memory_lifecycle(self):
        """Test the complete memory lifecycle with all modules."""
        # 1. Configure
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding=EmbeddingConfig(provider="fake", fake_dimension=64),
            ),
            consolidation_threshold=0.8,
        )

        # 2. Initialize
        memory = AgentMemory(config=config)

        try:
            # 3. Store knowledge
            memory.remember("Python was created by Guido van Rossum", category="knowledge", importance=0.9)
            memory.remember("The earth is round", category="fact", importance=0.95)

            # 4. Build knowledge graph
            memory.add_entity("Python", entity_type="language")
            memory.add_entity("Guido van Rossum", entity_type="person")
            memory.add_relation("Guido van Rossum", "Python", "created_by")

            # 5. Store preferences
            memory.store_preference("language", "Python")

            # 6. Have a conversation
            memory.remember_conversation("What is Python?", speaker="user")
            memory.remember_conversation("Python is a programming language", speaker="assistant", important=True)

            # 7. Recall
            results = memory.recall("Python programming", top_k=3)
            assert len(results) >= 1

            # 8. Get context
            context = memory.get_relevant_context("Tell me about Python", max_items=5)
            assert len(context) > 0

            # 9. Get stats
            stats = memory.get_stats()
            assert stats["session"]["interaction_count"] >= 2
            assert stats["knowledge_graph"]["entity_count"] >= 2

            # 10. Working memory
            memory.add_to_working_memory("task", "Explain Python", importance=0.7)
            snapshot = memory.get_working_memory_snapshot()
            assert "task" in snapshot or len(snapshot) > 0

        finally:
            memory.close()
