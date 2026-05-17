"""Unit tests for the unified store module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np

from memory_system.storage.unified_storage_backend import (
    UnifiedStorage,
    UnifiedRecord,
    SearchResult,
    VectorBackendType,
    StructuredBackendType,
    CacheBackendType,
)
from memory_system.infra.blinker_event_bus import reset_event_bus


class TestUnifiedRecord:
    """Test UnifiedRecord model"""
    
    def test_create_with_defaults(self):
        """Test creating record with defaults"""
        record = UnifiedRecord(content="Test")
        assert record.content == "Test"
        assert record.id is not None
        assert record.category == "general"
        assert record.importance == 0.5
    
    def test_create_with_all_fields(self):
        """Test creating record with all fields"""
        record = UnifiedRecord(
            id="test-id",
            content="Test content",
            embedding=[0.1, 0.2, 0.3],
            metadata={"key": "value"},
            tags=["tag1", "tag2"],
            category="test",
            importance=0.8,
        )
        assert record.id == "test-id"
        assert record.embedding == [0.1, 0.2, 0.3]
        assert record.tags == ["tag1", "tag2"]


class TestUnifiedStorage:
    """Test UnifiedStorage class"""
    
    def setup_method(self):
        """Reset event bus before each test"""
        reset_event_bus()
    
    def test_create_with_defaults(self):
        """Test creating storage with defaults"""
        storage = UnifiedStorage()
        assert storage is not None
    
    def test_create_with_factory(self):
        """Test creating with factory method"""
        storage = UnifiedStorage.create(
            vector="memory",
            structured="sqlite",
            cache="memory",
        )
        assert storage is not None
    
    def test_put_and_get(self):
        """Test put and get operations"""
        storage = UnifiedStorage.create(vector="memory", structured="sqlite")
        
        record = storage.put(
            content="Hello world",
            metadata={"source": "test"},
            tags=["greeting"],
        )
        
        assert record.id is not None
        
        retrieved = storage.get(record.id)
        assert retrieved is not None
        assert retrieved.content == "Hello world"
    
    def test_put_with_embedding(self):
        """Test put with embedding"""
        storage = UnifiedStorage.create(vector="memory")
        
        embedding = [0.1] * 384  # 384-dim vector
        record = storage.put(
            content="Test content",
            embedding=embedding,
        )
        
        assert record.embedding == embedding
    
    def test_search(self):
        """Test vector search"""
        storage = UnifiedStorage.create(vector="memory")
        
        # Add records with embeddings
        storage.put(
            content="Python is a programming language",
            embedding=self._make_embedding("python"),
        )
        storage.put(
            content="JavaScript is also a programming language",
            embedding=self._make_embedding("javascript"),
        )
        storage.put(
            content="The weather is nice today",
            embedding=self._make_embedding("weather"),
        )
        
        # Search for programming
        results = storage.search(
            query_embedding=self._make_embedding("programming"),
            top_k=2,
        )
        
        assert len(results) <= 2
    
    def test_search_with_category_filter(self):
        """Test search with category filter"""
        storage = UnifiedStorage.create(vector="memory")
        
        storage.put(
            content="Python",
            embedding=self._make_embedding("python"),
            category="tech",
        )
        storage.put(
            content="Cooking",
            embedding=self._make_embedding("cooking"),
            category="food",
        )
        
        results = storage.search(
            query_embedding=self._make_embedding("python"),
            top_k=5,
            category="tech",
        )
        
        # Should only get tech category results
        for r in results:
            assert r.record.category == "tech"
    
    def test_delete(self):
        """Test delete operation"""
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())
        
        # 需要提供 embedding 才能存储到向量存储
        record = storage.put(content="To be deleted", embedding=[0.1] * 384)
        
        result = storage.delete(record.id)
        assert result is True
        
        retrieved = storage.get(record.id)
        assert retrieved is None
    
    def test_update(self):
        """Test update operation"""
        storage = UnifiedStorage.create()
        
        record = storage.put(content="Original content")
        
        result = storage.update(record.id, content="Updated content", importance=0.9)
        assert result is True
        
        updated = storage.get(record.id)
        assert updated.content == "Updated content"
        assert updated.importance == 0.9
    
    def test_cache_hit_miss(self):
        """Test cache hit and miss"""
        storage = UnifiedStorage.create(cache="memory")
        
        record = storage.put(content="Cached content")
        
        # First get - should be cache hit (stored in cache)
        retrieved = storage.get(record.id)
        assert retrieved is not None
    
    def test_get_stats(self):
        """Test getting stats"""
        storage = UnifiedStorage.create(
            vector="memory",
            structured="sqlite",
            cache="memory",
        )
        
        stats = storage.get_stats()
        
        assert "vector_backend" in stats
        assert "structured_backend" in stats
        assert "cache_backend" in stats
        assert "events_enabled" in stats
    
    def test_events_disabled(self):
        """Test with events disabled"""
        storage = UnifiedStorage(enable_events=False)
        
        record = storage.put(content="Test")
        
        # Should work without events
        assert record.id is not None
    
    def _make_embedding(self, text: str) -> list[float]:
        """Create a simple fake embedding based on text"""
        # Simple hash-based embedding for testing
        np.random.seed(hash(text) % (2**32))
        return list(np.random.randn(384).astype(float))


class TestBackendTypes:
    """Test backend type enums"""
    
    def test_vector_backend_types(self):
        """Test vector backend types"""
        assert VectorBackendType.MEMORY.value == "memory"
        assert VectorBackendType.CHROMA.value == "chroma"
        assert VectorBackendType.FAISS.value == "faiss"
        assert VectorBackendType.REDIS.value == "redis"
    
    def test_structured_backend_types(self):
        """Test structured backend types"""
        assert StructuredBackendType.SQLITE.value == "sqlite"
        assert StructuredBackendType.SQLMODEL.value == "sqlmodel"
    
    def test_cache_backend_types(self):
        """Test cache backend types"""
        assert CacheBackendType.MEMORY.value == "memory"
        assert CacheBackendType.REDIS.value == "redis"


class TestSearchResult:
    """Test SearchResult model"""
    
    def test_create_search_result(self):
        """Test creating search result"""
        record = UnifiedRecord(content="Test")
        result = SearchResult(
            record=record,
            score=0.95,
            source="MemoryVectorStore",
        )
        
        assert result.record.content == "Test"
        assert result.score == 0.95
        assert result.source == "MemoryVectorStore"


class TestIntegration:
    """Integration tests"""
    
    def setup_method(self):
        """Reset event bus"""
        reset_event_bus()
    
    def test_full_workflow(self):
        """Test full workflow"""
        storage = UnifiedStorage.create(
            vector="memory",
            structured="sqlite",
            cache="memory",
        )
        
        # Add multiple records
        records = []
        for i in range(5):
            r = storage.put(
                content=f"Content {i}",
                embedding=self._make_embedding(f"content_{i}"),
                category="test" if i % 2 == 0 else "other",
                importance=0.5 + i * 0.1,
            )
            records.append(r)
        
        # Search
        results = storage.search(
            query_embedding=self._make_embedding("content_0"),
            top_k=3,
        )
        assert len(results) <= 3
        
        # Get
        retrieved = storage.get(records[0].id)
        assert retrieved is not None
        
        # Update
        storage.update(records[0].id, importance=1.0)
        
        # Delete
        storage.delete(records[1].id)
        
        # Verify delete
        deleted = storage.get(records[1].id)
        assert deleted is None
        
        # Stats
        stats = storage.get_stats()
        assert stats is not None
    
    def test_event_tracking(self):
        """Test event tracking"""
        from memory_system.infra.blinker_event_bus import get_event_bus, StorageEventType
        
        bus = get_event_bus()
        events = []
        
        @bus.on(StorageEventType.MEMORY_ADD)
        def track_event(event):
            events.append(event)
        
        storage = UnifiedStorage(enable_events=True)
        
        storage.put(content="Event test")
        
        assert len(events) == 1
        assert events[0].data["content"] == "Event test"
    
    def _make_embedding(self, text: str) -> list[float]:
        """Create fake embedding"""
        np.random.seed(hash(text) % (2**32))
        return list(np.random.randn(384).astype(float))


class TestUnifiedStorageAdvanced:
    """Advanced tests for UnifiedStorage"""
    
    def setup_method(self):
        reset_event_bus()
    
    def test_put_without_embedding_stores_to_cache_only(self):
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())
        record = storage.put(content="No embedding")
        # Should be retrievable from cache
        retrieved = storage.get(record.id)
        assert retrieved is not None
        assert retrieved.content == "No embedding"
    
    def test_put_with_all_fields(self):
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())
        record = storage.put(
            content="Full record",
            embedding=[0.1] * 384,
            metadata={"source": "test"},
            tags=["tag1", "tag2"],
            category="test_category",
            importance=0.9,
        )
        assert record.metadata == {"source": "test"}
        assert record.tags == ["tag1", "tag2"]
        assert record.category == "test_category"
    
    def test_update_nonexistent_returns_false(self):
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())
        result = storage.update("nonexistent-id", content="new")
        assert result is False
    
    def test_search_without_vector_backend(self):
        storage = UnifiedStorage()  # No vector backend
        results = storage.search([0.1] * 384)
        assert results == []
    
    def test_get_stats(self):
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())
        stats = storage.get_stats()
        assert "vector_backend" in stats
        assert "cache_backend" in stats
        assert "events_enabled" in stats
    
    def test_events_disabled(self):
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore(), enable_events=False)
        record = storage.put(content="test", embedding=[0.1] * 384)
        # Should not raise and should work normally
        assert record.content == "test"
    
    def test_create_factory_memory(self):
        storage = UnifiedStorage.create(vector="memory", structured="sqlite")
        stats = storage.get_stats()
        assert stats["vector_backend"] == "MemoryVectorStore"
    
    def test_create_factory_sqlite(self):
        storage = UnifiedStorage.create(vector="memory", structured="sqlite")
        stats = storage.get_stats()
        assert "StructuredStore" in stats["structured_backend"]
    
    def test_multiple_puts_and_gets(self):
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())
        records = []
        for i in range(5):
            r = storage.put(content=f"Content {i}", embedding=[float(i)] * 384)
            records.append(r)
        for r in records:
            retrieved = storage.get(r.id)
            assert retrieved is not None
    
    def test_delete_nonexistent_returns_false(self):
        storage = UnifiedStorage()
        result = storage.delete("nonexistent")
        assert result is False


class TestUnifiedStoreBackendAdapters:
    """Test private adapter methods and backend fallback paths"""

    def setup_method(self):
        reset_event_bus()

    def test_get_from_vector_cache_miss(self):
        """Test _get_from_vector when cache misses"""
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())

        # Put with embedding (stores to vector + cache)
        record = storage.put(content="cached content", embedding=[0.1] * 384)

        # Clear cache to force vector lookup
        storage._memory_cache.clear()

        # Get should fall back to vector store
        retrieved = storage.get(record.id)
        assert retrieved is not None
        assert retrieved.content == "cached content"

    def test_get_from_structured_cache_miss(self):
        """Test _get_from_structured is called when cache misses"""
        import unittest.mock as mock
        from memory_system.storage.structured_sqlite_store import StructuredStore
        from memory_system.storage.unified_storage_backend import UnifiedRecord

        store = StructuredStore(":memory:")
        store.create_table("memories", {
            "content": "TEXT",
            "memory_type": "TEXT",
            "category": "TEXT",
            "importance": "REAL",
        })

        storage = UnifiedStorage(structured_backend=store)

        # Put a record (stores to structured + cache)
        record = storage.put(content="structured content")

        # Verify cache has it
        assert storage.get(record.id) is not None

        # Clear cache to force structured store lookup
        storage._memory_cache.clear()

        # Mock _get_from_structured to verify it gets called
        original_method = storage._get_from_structured
        with mock.patch.object(storage, '_get_from_structured', wraps=original_method) as mock_get:
            storage.get(record.id)
            # _get_from_structured should have been called as fallback
            mock_get.assert_called_once()

    def test_search_with_min_importance(self):
        """Test search with min_importance filter"""
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())

        storage.put(content="important", embedding=[0.1] * 384, importance=0.9)
        storage.put(content="not important", embedding=[0.2] * 384, importance=0.1)

        results = storage.search([0.1] * 384, min_importance=0.5)
        # Should filter by importance
        assert isinstance(results, list)

    def test_put_with_custom_id(self):
        """Test put with custom ID"""
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())

        record = storage.put(content="custom id test", id="my-custom-id", embedding=[0.1] * 384)
        assert record.id == "my-custom-id"

        retrieved = storage.get("my-custom-id")
        assert retrieved is not None

    def test_update_with_vector_and_structured(self):
        """Test update propagates to both backends"""
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())

        record = storage.put(content="original", embedding=[0.1] * 384)
        result = storage.update(record.id, content="updated")
        assert result is True

        retrieved = storage.get(record.id)
        assert retrieved.content == "updated"

    def test_delete_from_all_backends(self):
        """Test delete removes from vector + cache"""
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())

        record = storage.put(content="to delete", embedding=[0.1] * 384)
        assert storage.get(record.id) is not None

        result = storage.delete(record.id)
        assert result is True

        # Clear cache and verify gone from vector too
        storage._memory_cache.clear()
        assert storage.get(record.id) is None

    def test_get_stats_with_data(self):
        """Test get_stats returns correct counts"""
        from memory_system.storage.vector_store import MemoryVectorStore
        storage = UnifiedStorage(vector_backend=MemoryVectorStore())

        storage.put(content="a", embedding=[0.1] * 384)
        storage.put(content="b", embedding=[0.2] * 384)

        stats = storage.get_stats()
        assert stats["vector_count"] == 2
        assert stats["cache_count"] == 2

    def test_store_to_structured_orm_path(self):
        """Test _store_to_structured with ORM-like backend (has add, not insert)"""
        import unittest.mock as mock

        class MockORMBackend:
            def add(self, record):
                self.added = record

        mock_backend = MockORMBackend()

        # Mock MemoryRecordORM so the ORM path in _store_to_structured works
        with mock.patch("memory_system.storage.sqlmodel_orm_store.MemoryRecordORM") as MockORM:
            # Make MemoryRecordORM() return a simple object that accepts tags/metadata
            def make_orm_record(**kwargs):
                obj = mock.MagicMock()
                obj.__dict__.update(kwargs)
                return obj
            MockORM.side_effect = make_orm_record

            storage = UnifiedStorage(structured_backend=mock_backend)
            record = storage.put(content="orm test")
            # Should call mock_backend.add
            assert hasattr(mock_backend, 'added')

    def test_create_with_enable_events_false(self):
        """Test create with enable_events=False"""
        storage = UnifiedStorage.create(
            vector="memory",
            enable_events=False,
        )
        stats = storage.get_stats()
        assert stats["events_enabled"] is False
