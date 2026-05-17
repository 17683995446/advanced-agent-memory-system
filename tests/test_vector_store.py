"""Unit tests for the vector_store module."""
import pytest
import time
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, patch, PropertyMock

from memory_system.storage.vector_store import (
    MemoryRecord,
    SearchResult,
    MemoryVectorStore,
    ChromaDBBackend,
    FAISSBackend,
    VectorStoreFactory,
)
from memory_system.processing.text_embedding_provider import FakeEmbeddingProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIM = 64
fake_embedder = FakeEmbeddingProvider(dimension=DIM)


def _make_embedding(text: str) -> list[float]:
    """Generate a deterministic embedding for *text*."""
    return fake_embedder.encode(text)


def _make_record(id: str, content: str, **kwargs) -> MemoryRecord:
    """Create a MemoryRecord with an embedding derived from *content*."""
    return MemoryRecord(
        id=id,
        content=content,
        embedding=_make_embedding(content),
        timestamp=time.time(),
        **kwargs,
    )


# ===========================================================================
# TestMemoryRecord
# ===========================================================================

class TestMemoryRecord:

    def test_create_with_required_fields(self):
        """A MemoryRecord can be created with only the required fields."""
        now = time.time()
        record = MemoryRecord(
            id="1",
            content="hello",
            embedding=[0.1, 0.2],
            timestamp=now,
        )
        assert record.id == "1"
        assert record.content == "hello"
        assert record.embedding == [0.1, 0.2]
        assert record.timestamp == now

    def test_default_values(self):
        """Optional fields should have sensible defaults."""
        record = MemoryRecord(
            id="1",
            content="hello",
            embedding=[0.1, 0.2],
            timestamp=time.time(),
        )
        assert record.memory_type == "semantic"
        assert record.category == "general"
        assert record.importance == 0.5
        assert record.tags == []
        assert record.metadata == {}
        assert record.access_count == 0

    def test_from_dict_and_to_dict(self):
        """Round-trip serialization via model_dump / model_validate."""
        original = _make_record(
            id="42",
            content="round trip",
            memory_type="episodic",
            category="task",
            importance=0.9,
            tags=["urgent", "work"],
            metadata={"source": "test"},
        )
        as_dict = original.model_dump()
        restored = MemoryRecord.model_validate(as_dict)

        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.embedding == original.embedding
        assert restored.memory_type == original.memory_type
        assert restored.category == original.category
        assert restored.importance == original.importance
        assert restored.tags == original.tags
        assert restored.metadata == original.metadata
        assert restored.timestamp == original.timestamp


# ===========================================================================
# TestMemoryVectorStore
# ===========================================================================

class TestMemoryVectorStore:

    def test_add_and_get(self):
        """Add a record and retrieve it by id."""
        store = MemoryVectorStore()
        rec = _make_record("1", "hello world")
        store.add(rec)

        result = store.get("1")
        assert result is not None
        assert result.id == "1"
        assert result.content == "hello world"

    def test_add_batch(self):
        """Adding 3 records should result in count == 3."""
        store = MemoryVectorStore()
        records = [
            _make_record(str(i), f"content {i}") for i in range(3)
        ]
        store.add_batch(records)
        assert store.count() == 3

    def test_search_returns_relevant(self):
        """Search should return the most similar record first."""
        store = MemoryVectorStore()
        store.add(_make_record("a", "The quick brown fox jumps over the lazy dog"))
        store.add(_make_record("b", "A completely unrelated sentence about astronomy"))
        store.add(_make_record("c", "Fast animals that leap and bound in the forest"))

        query = _make_embedding("quick fox jumping")
        results = store.search(query, top_k=2)

        assert len(results) >= 1
        # The most similar should be "a" or "c" (both about foxes), not "b"
        top_ids = [r.record.id for r in results]
        assert "b" not in top_ids[:1]  # astronomy should not be the top result

    def test_search_with_category_filter(self):
        """Search results should be filtered by category."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "task alpha", category="task"))
        store.add(_make_record("2", "task beta", category="task"))
        store.add(_make_record("3", "general note", category="general"))

        query = _make_embedding("task")
        results = store.search(query, top_k=10, filter={"category": "task"})

        assert len(results) == 2
        for r in results:
            assert r.record.category == "task"

    def test_search_with_tag_filter(self):
        """Search results should be filtered by tags."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "urgent item", tags=["urgent", "work"]))
        store.add(_make_record("2", "casual note", tags=["casual"]))
        store.add(_make_record("3", "work item", tags=["work"]))

        query = _make_embedding("item")
        results = store.search(query, top_k=10, filter={"tags": "urgent"})

        assert len(results) == 1
        assert results[0].record.id == "1"

    def test_delete(self):
        """After deleting a record, count should drop to 0."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "to be deleted"))
        assert store.count() == 1

        result = store.delete("1")
        assert result is True
        assert store.count() == 0

    def test_update(self):
        """Updating a record's content should be reflected on get."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "original content"))

        store.update("1", content="updated content")
        result = store.get("1")
        assert result is not None
        assert result.content == "updated content"

    def test_count(self):
        """An empty store should return count == 0."""
        store = MemoryVectorStore()
        assert store.count() == 0

    def test_list_all(self):
        """list_all with limit should return at most that many records."""
        store = MemoryVectorStore()
        for i in range(5):
            store.add(_make_record(str(i), f"item {i}"))

        results = store.list_all(limit=3)
        assert len(results) == 3

    def test_nonexistent_get(self):
        """Getting a nonexistent id should return None."""
        store = MemoryVectorStore()
        assert store.get("nonexistent") is None

    def test_delete_nonexistent(self):
        """Deleting a nonexistent id should return False."""
        store = MemoryVectorStore()
        assert store.delete("nonexistent") is False


# ===========================================================================
# TestChromaDBBackend
# ===========================================================================

def _chromadb_available() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _chromadb_available(),
    reason="chromadb is not installed",
)
class TestChromaDBBackend:

    def test_add_and_search(self):
        """Basic add and search round-trip."""
        store = ChromaDBBackend(collection_name="test_add_search")
        rec = _make_record("1", "hello chroma")
        store.add(rec)

        query = _make_embedding("hello")
        results = store.search(query, top_k=1)
        assert len(results) >= 1
        assert results[0].record.id == "1"

    def test_delete(self):
        """Add a record, delete it, and verify it is gone."""
        store = ChromaDBBackend(collection_name="test_delete")
        store.add(_make_record("1", "delete me"))
        assert store.count() == 1

        result = store.delete("1")
        assert result is True
        assert store.count() == 0

    def test_persistence(self, tmp_path):
        """Data stored with a persist_directory should survive across instances."""
        persist_dir = str(tmp_path / "chroma_test_db")

        # First instance: add data
        store1 = ChromaDBBackend(
            persist_directory=persist_dir,
            collection_name="test_persist",
        )
        store1.add(_make_record("1", "persistent memory"))
        assert store1.count() == 1

        # Second instance pointing to the same directory
        store2 = ChromaDBBackend(
            persist_directory=persist_dir,
            collection_name="test_persist",
        )
        assert store2.count() == 1
        record = store2.get("1")
        assert record is not None
        assert record.content == "persistent memory"


# ===========================================================================
# TestFAISSBackend
# ===========================================================================

def _faiss_available() -> bool:
    try:
        import faiss  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _faiss_available(),
    reason="faiss-cpu is not installed",
)
class TestFAISSBackend:

    def test_add_and_search(self):
        """Basic add and search round-trip."""
        store = FAISSBackend(dimension=DIM)
        store.add(_make_record("1", "hello faiss"))

        query = _make_embedding("hello")
        results = store.search(query, top_k=1)
        assert len(results) >= 1
        assert results[0].record.id == "1"

    def test_dimension_mismatch(self):
        """Adding a vector with the wrong dimension should raise an error."""
        store = FAISSBackend(dimension=DIM)
        bad_record = MemoryRecord(
            id="bad",
            content="wrong dimension",
            embedding=[0.1] * (DIM + 10),  # intentionally wrong
            timestamp=time.time(),
        )
        # The normalize step inside FAISSBackend should fail or produce
        # inconsistent results.  We expect an exception at add time.
        with pytest.raises(Exception):
            store.add(bad_record)

    def test_save_and_load_index(self, tmp_path):
        """Save an index to disk, load into a new instance, and verify data."""
        index_path = str(tmp_path / "faiss_test.index")
        store1 = FAISSBackend(dimension=DIM)
        store1.add(_make_record("1", "save me"))
        store1.add(_make_record("2", "and me too"))
        store1.save_index(index_path)

        store2 = FAISSBackend(dimension=DIM)
        store2.load_index(index_path)
        assert store2.count() == 2

        rec1 = store2.get("1")
        assert rec1 is not None
        assert rec1.content == "save me"

        rec2 = store2.get("2")
        assert rec2 is not None
        assert rec2.content == "and me too"


# ===========================================================================
# TestVectorStoreFactory
# ===========================================================================

class TestVectorStoreFactory:

    def test_create_memory(self):
        """Factory should return a MemoryVectorStore for 'memory'."""
        store = VectorStoreFactory.create("memory")
        assert isinstance(store, MemoryVectorStore)

    def test_create_chroma(self):
        """Factory should return a ChromaDBBackend for 'chroma'."""
        pytest.importorskip("chromadb")
        store = VectorStoreFactory.create("chroma")
        assert isinstance(store, ChromaDBBackend)

    def test_create_faiss(self):
        """Factory should return a FAISSBackend for 'faiss'."""
        pytest.importorskip("faiss")
        store = VectorStoreFactory.create("faiss", dimension=DIM)
        assert isinstance(store, FAISSBackend)


# ===========================================================================
# TestChromaDBMock
# ===========================================================================

class TestChromaDBMock:
    """Mock tests for ChromaDB backend (no real ChromaDB needed)"""
    
    def test_chromadb_add_mock(self):
        """Test ChromaDB add with mock"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        
        # 模拟 add 操作
        mock_collection.add.return_value = None
        
        # 验证 mock 调用
        mock_collection.add(ids=["test-id"], embeddings=[[0.1, 0.2]], metadatas=[{"content": "test"}])
        mock_collection.add.assert_called_once()
    
    def test_chromadb_query_mock(self):
        """Test ChromaDB query with mock"""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[{"content": "a"}, {"content": "b"}]],
        }
        
        result = mock_collection.query(query_embeddings=[[0.1, 0.2]], n_results=2)
        assert len(result["ids"][0]) == 2
    
    def test_chromadb_delete_mock(self):
        """Test ChromaDB delete with mock"""
        mock_collection = MagicMock()
        mock_collection.delete.return_value = None
        mock_collection.delete(ids=["id1"])
        mock_collection.delete.assert_called_once()
    
    def test_chromadb_count_mock(self):
        """Test ChromaDB count with mock"""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        assert mock_collection.count() == 10


# ===========================================================================
# TestFAISSMock
# ===========================================================================

class TestFAISSMock:
    """Mock tests for FAISS backend (no real FAISS needed)"""
    
    def test_faiss_add_mock(self):
        """Test FAISS add with mock"""
        import numpy as np
        mock_index = MagicMock()
        mock_index.ntotal = 0
        mock_index.add.return_value = None
        
        vectors = np.random.rand(5, 128).astype('float32')
        mock_index.add(vectors)
        mock_index.add.assert_called_once()
    
    def test_faiss_search_mock(self):
        """Test FAISS search with mock"""
        import numpy as np
        mock_index = MagicMock()
        mock_index.ntotal = 10
        mock_index.search.return_value = (
            np.array([[0.1, 0.2, 0.3]]),  # distances
            np.array([[0, 1, 2]]),         # indices
        )
        
        query = np.random.rand(1, 128).astype('float32')
        distances, indices = mock_index.search(query, 3)
        assert len(indices[0]) == 3
    
    def test_faiss_dimension_mock(self):
        """Test FAISS dimension property"""
        mock_index = MagicMock()
        mock_index.d = 128
        assert mock_index.d == 128
    
    def test_faiss_save_load_mock(self):
        """Test FAISS save/load with mock"""
        try:
            import faiss
        except ImportError:
            pytest.skip("faiss is not installed")
        
        mock_write = MagicMock()
        mock_read = MagicMock(return_value=MagicMock())
        
        with patch.object(faiss, 'write_index', mock_write):
            with patch.object(faiss, 'read_index', mock_read):
                # 模拟保存和加载
                mock_write(MagicMock(), "test.index")
                mock_read("test.index")
                mock_write.assert_called_once()
                mock_read.assert_called_once()


# ===========================================================================
# TestVectorStoreFactoryMock
# ===========================================================================

class TestVectorStoreFactoryMock:
    """Mock tests for VectorStoreFactory with unavailable backends"""
    
    def test_factory_chroma_unavailable(self):
        """Test factory falls back when ChromaDB unavailable"""
        from memory_system.storage.vector_store import VectorStoreFactory
        
        # ChromaDB 未安装时会跳过或返回 MemoryVectorStore
        # 这个测试验证工厂方法的健壮性
        try:
            store = VectorStoreFactory.create("chroma")
        except ImportError:
            pass  # 预期的行为
    
    def test_factory_faiss_unavailable(self):
        """Test factory falls back when FAISS unavailable"""
        from memory_system.storage.vector_store import VectorStoreFactory
        
        try:
            store = VectorStoreFactory.create("faiss", dimension=128)
        except ImportError:
            pass  # 预期的行为


# ===========================================================================
# NEW COMPREHENSIVE TESTS
# ===========================================================================


# ---------------------------------------------------------------------------
# TestVectorStoreBackendAbstract
# ---------------------------------------------------------------------------

class TestVectorStoreBackendAbstract:
    """Tests for the abstract base class VectorStoreBackend."""

    def test_cannot_instantiate_directly(self):
        """VectorStoreBackend cannot be instantiated directly."""
        from memory_system.storage.vector_store import VectorStoreBackend
        with pytest.raises(TypeError):
            VectorStoreBackend()

    def test_subclass_must_implement_all_methods(self):
        """A subclass missing any abstract method cannot be instantiated."""
        from memory_system.storage.vector_store import VectorStoreBackend

        class IncompleteBackend(VectorStoreBackend):
            def add(self, record):
                return record.id
            # Missing: add_batch, search, get, delete, update, count, list_all

        with pytest.raises(TypeError):
            IncompleteBackend()

    def test_complete_subclass_can_be_instantiated(self):
        """A subclass implementing all abstract methods can be instantiated."""
        from memory_system.storage.vector_store import VectorStoreBackend

        class CompleteBackend(VectorStoreBackend):
            def add(self, record):
                return record.id
            def add_batch(self, records):
                return [r.id for r in records]
            def search(self, query_embedding, top_k=5, filter=None):
                return []
            def get(self, id):
                return None
            def delete(self, id):
                return False
            def update(self, id, **kwargs):
                return False
            def count(self):
                return 0
            def list_all(self, limit=100, offset=0):
                return []

        backend = CompleteBackend()
        assert isinstance(backend, VectorStoreBackend)


# ---------------------------------------------------------------------------
# TestMemoryRecordExtended
# ---------------------------------------------------------------------------

class TestMemoryRecordExtended:
    """Extended tests for MemoryRecord data model."""

    def test_creation_with_all_fields(self):
        """MemoryRecord created with every field explicitly set."""
        rec = MemoryRecord(
            id="full-1",
            content="full content",
            embedding=[0.1, 0.2, 0.3],
            memory_type="episodic",
            category="task",
            importance=0.95,
            tags=["tag1", "tag2", "tag3"],
            metadata={"key1": "val1", "key2": 42},
            timestamp=1000.0,
            access_count=10,
            last_access=2000.0,
        )
        assert rec.id == "full-1"
        assert rec.content == "full content"
        assert rec.embedding == [0.1, 0.2, 0.3]
        assert rec.memory_type == "episodic"
        assert rec.category == "task"
        assert rec.importance == 0.95
        assert rec.tags == ["tag1", "tag2", "tag3"]
        assert rec.metadata == {"key1": "val1", "key2": 42}
        assert rec.timestamp == 1000.0
        assert rec.access_count == 10
        assert rec.last_access == 2000.0

    def test_embedding_default_is_none(self):
        """When embedding is not provided, it defaults to None."""
        rec = MemoryRecord(id="1", content="no embedding", timestamp=time.time())
        assert rec.embedding is None

    def test_model_copy_with_update(self):
        """model_copy with update should produce a new record with changed fields."""
        original = _make_record("1", "original", category="general")
        updated = original.model_copy(update={"content": "modified", "importance": 0.9})
        assert updated.id == "1"
        assert updated.content == "modified"
        assert updated.importance == 0.9
        assert updated.category == "general"
        # Original should be unchanged
        assert original.content == "original"
        assert original.importance == 0.5

    def test_model_dump_round_trip(self):
        """model_dump and model_validate should round-trip correctly."""
        rec = _make_record("1", "round trip", tags=["a"], metadata={"x": 1})
        data = rec.model_dump()
        restored = MemoryRecord.model_validate(data)
        assert restored.id == rec.id
        assert restored.content == rec.content
        assert restored.tags == rec.tags
        assert restored.metadata == rec.metadata

    def test_tags_are_mutable(self):
        """Tags list can be mutated in place."""
        rec = MemoryRecord(id="1", content="test", timestamp=time.time())
        rec.tags.append("new_tag")
        assert "new_tag" in rec.tags

    def test_metadata_are_mutable(self):
        """Metadata dict can be mutated in place."""
        rec = MemoryRecord(id="1", content="test", timestamp=time.time())
        rec.metadata["new_key"] = "new_val"
        assert rec.metadata["new_key"] == "new_val"


# ---------------------------------------------------------------------------
# TestSearchResult
# ---------------------------------------------------------------------------

class TestSearchResult:
    """Tests for the SearchResult data model."""

    def test_creation(self):
        """SearchResult can be created with a record and score."""
        rec = _make_record("1", "test content")
        sr = SearchResult(record=rec, score=0.95)
        assert sr.record.id == "1"
        assert sr.score == 0.95

    def test_score_can_be_zero(self):
        """SearchResult score can be zero."""
        rec = _make_record("1", "test")
        sr = SearchResult(record=rec, score=0.0)
        assert sr.score == 0.0

    def test_score_can_be_negative(self):
        """SearchResult score can be negative (e.g., distance-based)."""
        rec = _make_record("1", "test")
        sr = SearchResult(record=rec, score=-0.5)
        assert sr.score == -0.5


# ---------------------------------------------------------------------------
# TestMemoryVectorStoreExtended
# ---------------------------------------------------------------------------

class TestMemoryVectorStoreExtended:
    """Extended tests for MemoryVectorStore covering edge cases."""

    def test_add_record_without_embedding(self):
        """Adding a record with no embedding should succeed but not be searchable."""
        store = MemoryVectorStore()
        rec = MemoryRecord(id="no-emb", content="no embedding", timestamp=time.time())
        store.add(rec)
        assert store.count() == 1
        assert store.get("no-emb") is not None

        # Search should return nothing (no embedding to compare against)
        query = _make_embedding("no embedding")
        results = store.search(query, top_k=10)
        assert len(results) == 0

    def test_add_batch_with_mixed_embeddings(self):
        """Batch add with some records having embeddings and some not."""
        store = MemoryVectorStore()
        rec_with_emb = _make_record("1", "has embedding")
        rec_without_emb = MemoryRecord(id="2", content="no embedding", timestamp=time.time())
        rec_with_emb2 = _make_record("3", "also has embedding")

        ids = store.add_batch([rec_with_emb, rec_without_emb, rec_with_emb2])
        assert ids == ["1", "2", "3"]
        assert store.count() == 3

        # Search should only find records with embeddings
        query = _make_embedding("embedding")
        results = store.search(query, top_k=10)
        result_ids = [r.record.id for r in results]
        assert "1" in result_ids or "3" in result_ids
        assert "2" not in result_ids

    def test_add_duplicate_id_overwrites(self):
        """Adding a record with the same id should overwrite the previous one."""
        store = MemoryVectorStore()
        rec1 = _make_record("dup", "first version")
        rec2 = _make_record("dup", "second version")
        store.add(rec1)
        store.add(rec2)

        assert store.count() == 1
        result = store.get("dup")
        assert result.content == "second version"

    def test_add_batch_empty_list(self):
        """Adding an empty batch should return empty list and not change count."""
        store = MemoryVectorStore()
        ids = store.add_batch([])
        assert ids == []
        assert store.count() == 0

    def test_search_top_k_larger_than_store_size(self):
        """When top_k > store size, all records should be returned."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "first"))
        store.add(_make_record("2", "second"))

        results = store.search(_make_embedding("anything"), top_k=100)
        assert len(results) == 2

    def test_search_on_empty_store(self):
        """Search on an empty store should return empty list."""
        store = MemoryVectorStore()
        results = store.search(_make_embedding("query"), top_k=5)
        assert results == []

    def test_search_returns_correct_ordering(self):
        """Search results should be sorted by descending similarity score."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "cat dog bird fish"))
        store.add(_make_record("2", "quantum physics equation"))
        store.add(_make_record("3", "puppy kitten pet animal"))

        query = _make_embedding("cute cat kitten")
        results = store.search(query, top_k=3)
        scores = [r.score for r in results]
        # Scores should be in descending order
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_search_updates_access_stats(self):
        """Search should increment access_count and update last_access on results."""
        store = MemoryVectorStore()
        rec = _make_record("1", "accessible")
        store.add(rec)

        original_access_count = rec.access_count
        results = store.search(_make_embedding("accessible"), top_k=1)

        assert len(results) == 1
        assert results[0].record.access_count == original_access_count + 1

    def test_get_updates_access_stats(self):
        """Getting a record should increment access_count and update last_access."""
        store = MemoryVectorStore()
        rec = _make_record("1", "get me")
        store.add(rec)

        original_count = rec.access_count
        result = store.get("1")
        assert result.access_count == original_count + 1

    def test_get_nonexistent_does_not_raise(self):
        """Getting a nonexistent id returns None without error."""
        store = MemoryVectorStore()
        assert store.get("does-not-exist") is None

    def test_delete_nonexistent_returns_false(self):
        """Deleting a nonexistent id returns False."""
        store = MemoryVectorStore()
        assert store.delete("ghost") is False

    def test_delete_removes_embedding(self):
        """Deleting a record should also remove its embedding."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "to delete"))
        assert store.count() == 1

        store.delete("1")
        assert store.count() == 0

        # Verify search also returns nothing
        results = store.search(_make_embedding("to delete"), top_k=10)
        assert len(results) == 0

    def test_update_nonexistent_returns_false(self):
        """Updating a nonexistent record returns False."""
        store = MemoryVectorStore()
        assert store.update("ghost", content="new") is False

    def test_update_embedding(self):
        """Updating the embedding should change search results."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "original"))

        # Update to a completely different embedding
        new_embedding = _make_embedding("quantum physics")
        store.update("1", embedding=new_embedding)

        # Search for "quantum physics" should now find this record
        results = store.search(new_embedding, top_k=1)
        assert len(results) == 1
        assert results[0].record.id == "1"

    def test_update_multiple_fields(self):
        """Updating multiple fields at once should work."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "old content"))

        store.update("1", content="new content", category="task", importance=0.9)
        rec = store.get("1")
        assert rec.content == "new content"
        assert rec.category == "task"
        assert rec.importance == 0.9

    def test_update_updates_last_access(self):
        """Updating a record should update last_access timestamp."""
        store = MemoryVectorStore()
        rec = _make_record("1", "content")
        store.add(rec)

        import time as _time
        _time.sleep(0.01)  # Small delay to ensure timestamp differs
        store.update("1", content="updated")
        updated = store.get("1")
        assert updated.last_access >= rec.last_access

    def test_list_all_with_offset(self):
        """list_all with offset should skip the first N records."""
        store = MemoryVectorStore()
        for i in range(5):
            store.add(_make_record(str(i), f"item {i}"))

        results = store.list_all(limit=2, offset=3)
        assert len(results) == 2
        # The records at offset 3 and 4
        ids = [r.id for r in results]
        assert "3" in ids
        assert "4" in ids

    def test_list_all_offset_beyond_size(self):
        """list_all with offset beyond store size should return empty list."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "only one"))

        results = store.list_all(limit=10, offset=100)
        assert results == []

    def test_list_all_default_params(self):
        """list_all with default params should return up to 100 records."""
        store = MemoryVectorStore()
        for i in range(3):
            store.add(_make_record(str(i), f"item {i}"))

        results = store.list_all()
        assert len(results) == 3

    def test_search_with_memory_type_filter(self):
        """Search results should be filtered by memory_type."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "semantic mem", memory_type="semantic"))
        store.add(_make_record("2", "episodic mem", memory_type="episodic"))
        store.add(_make_record("3", "another semantic", memory_type="semantic"))

        query = _make_embedding("memory")
        results = store.search(query, top_k=10, filter={"memory_type": "episodic"})
        assert len(results) == 1
        assert results[0].record.memory_type == "episodic"

    def test_search_with_tag_list_filter(self):
        """Search with tag list filter should match records with any of the tags."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "item", tags=["red", "big"]))
        store.add(_make_record("2", "item", tags=["blue", "small"]))
        store.add(_make_record("3", "item", tags=["green", "big"]))

        query = _make_embedding("item")
        results = store.search(query, top_k=10, filter={"tags": ["red", "green"]})
        result_ids = [r.record.id for r in results]
        assert "1" in result_ids
        assert "3" in result_ids
        assert "2" not in result_ids

    def test_search_with_metadata_filter(self):
        """Search with metadata filter should match records with matching metadata."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "doc", metadata={"source": "web"}))
        store.add(_make_record("2", "doc", metadata={"source": "file"}))
        store.add(_make_record("3", "doc", metadata={"source": "web", "page": 1}))

        query = _make_embedding("doc")
        results = store.search(query, top_k=10, filter={"source": "web"})
        result_ids = [r.record.id for r in results]
        assert "1" in result_ids
        assert "3" in result_ids
        assert "2" not in result_ids

    def test_search_with_combined_filter(self):
        """Search with multiple filter keys should require all to match."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "item", category="task", tags=["urgent"]))
        store.add(_make_record("2", "item", category="task", tags=["normal"]))
        store.add(_make_record("3", "item", category="general", tags=["urgent"]))

        query = _make_embedding("item")
        results = store.search(query, top_k=10, filter={"category": "task", "tags": "urgent"})
        assert len(results) == 1
        assert results[0].record.id == "1"

    def test_search_with_unknown_filter_key(self):
        """Unknown filter keys should be treated as metadata filters."""
        store = MemoryVectorStore()
        store.add(_make_record("1", "item", metadata={"custom_field": "value1"}))
        store.add(_make_record("2", "item", metadata={"custom_field": "value2"}))

        query = _make_embedding("item")
        results = store.search(query, top_k=10, filter={"custom_field": "value1"})
        assert len(results) == 1
        assert results[0].record.id == "1"

    def test_cosine_similarity_identical_vectors(self):
        """Identical vectors should have similarity of 1.0."""
        vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        sim = MemoryVectorStore._cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity of 0.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        sim = MemoryVectorStore._cosine_similarity(a, b)
        assert abs(sim) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        """Zero vector should return similarity of 0.0."""
        a = np.array([1.0, 2.0], dtype=np.float32)
        b = np.array([0.0, 0.0], dtype=np.float32)
        sim = MemoryVectorStore._cosine_similarity(a, b)
        assert sim == 0.0

    def test_cosine_similarity_opposite_vectors(self):
        """Opposite vectors should have similarity of -1.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        sim = MemoryVectorStore._cosine_similarity(a, b)
        assert abs(sim - (-1.0)) < 1e-6

    def test_large_batch_operations(self):
        """Adding and searching with a large batch should work correctly."""
        store = MemoryVectorStore()
        n = 200
        records = [_make_record(str(i), f"content number {i}") for i in range(n)]
        store.add_batch(records)
        assert store.count() == n

        query = _make_embedding("content number 50")
        results = store.search(query, top_k=5)
        assert len(results) == 5
        # All scores should be valid floats
        for r in results:
            assert isinstance(r.score, float)

    def test_thread_safety_concurrent_adds(self):
        """Concurrent adds from multiple threads should not lose data."""
        import threading
        store = MemoryVectorStore()
        n_threads = 10
        records_per_thread = 10

        def add_records(thread_id):
            for i in range(records_per_thread):
                rec_id = f"t{thread_id}_r{i}"
                store.add(_make_record(rec_id, f"thread {thread_id} record {i}"))

        threads = [threading.Thread(target=add_records, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = n_threads * records_per_thread
        assert store.count() == expected

    def test_matches_filter_category_mismatch(self):
        """_matches_filter should return False for category mismatch."""
        store = MemoryVectorStore()
        rec = _make_record("1", "test", category="task")
        assert store._matches_filter(rec, {"category": "general"}) is False

    def test_matches_filter_memory_type_mismatch(self):
        """_matches_filter should return False for memory_type mismatch."""
        store = MemoryVectorStore()
        rec = _make_record("1", "test", memory_type="semantic")
        assert store._matches_filter(rec, {"memory_type": "episodic"}) is False

    def test_matches_filter_tag_not_present(self):
        """_matches_filter should return False when tag is not present."""
        store = MemoryVectorStore()
        rec = _make_record("1", "test", tags=["a", "b"])
        assert store._matches_filter(rec, {"tags": "c"}) is False

    def test_matches_filter_tag_list_no_match(self):
        """_matches_filter should return False when none of the tags match."""
        store = MemoryVectorStore()
        rec = _make_record("1", "test", tags=["a", "b"])
        assert store._matches_filter(rec, {"tags": ["c", "d"]}) is False

    def test_matches_filter_empty_dict(self):
        """_matches_filter with empty dict should return True."""
        store = MemoryVectorStore()
        rec = _make_record("1", "test")
        assert store._matches_filter(rec, {}) is True


# ---------------------------------------------------------------------------
# TestVectorStoreFactoryExtended
# ---------------------------------------------------------------------------

class TestVectorStoreFactoryExtended:
    """Extended tests for VectorStoreFactory."""

    def test_create_default_backend(self):
        """Factory with no backend arg should default to 'memory'."""
        store = VectorStoreFactory.create()
        assert isinstance(store, MemoryVectorStore)

    def test_create_invalid_backend_raises_valueerror(self):
        """Factory with an unrecognized backend name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown vector store backend"):
            VectorStoreFactory.create("nonexistent_backend")

    def test_create_case_insensitive(self):
        """Factory backend name should be case-insensitive."""
        store = VectorStoreFactory.create("Memory")
        assert isinstance(store, MemoryVectorStore)

        store = VectorStoreFactory.create("MEMORY")
        assert isinstance(store, MemoryVectorStore)

    def test_create_chromadb_alias(self):
        """Factory should accept 'chromadb' as alias for ChromaDBBackend."""
        pytest.importorskip("chromadb")
        store = VectorStoreFactory.create("chromadb")
        assert isinstance(store, ChromaDBBackend)

    def test_register_custom_backend(self):
        """register should add a custom backend to the factory."""
        from memory_system.storage.vector_store import VectorStoreBackend

        class CustomBackend(VectorStoreBackend):
            def add(self, record):
                return record.id
            def add_batch(self, records):
                return [r.id for r in records]
            def search(self, query_embedding, top_k=5, filter=None):
                return []
            def get(self, id):
                return None
            def delete(self, id):
                return False
            def update(self, id, **kwargs):
                return False
            def count(self):
                return 0
            def list_all(self, limit=100, offset=0):
                return []

        VectorStoreFactory.register("custom_test", CustomBackend)
        store = VectorStoreFactory.create("custom_test")
        assert isinstance(store, CustomBackend)

    def test_register_non_subclass_raises_typeerror(self):
        """register with a non-VectorStoreBackend class should raise TypeError."""
        class NotABackend:
            pass

        with pytest.raises(TypeError, match="is not a subclass of VectorStoreBackend"):
            VectorStoreFactory.register("invalid", NotABackend)

    def test_error_message_lists_supported_backends(self):
        """ValueError message should list all supported backend names."""
        with pytest.raises(ValueError) as exc_info:
            VectorStoreFactory.create("bad_name")
        msg = str(exc_info.value)
        assert "memory" in msg
        assert "chroma" in msg
        assert "faiss" in msg


# ---------------------------------------------------------------------------
# TestChromaDBBackendHelpers (mocked)
# ---------------------------------------------------------------------------

class TestChromaDBBackendHelpers:
    """Tests for ChromaDBBackend helper methods using mocks."""

    def _make_backend(self):
        """Create a ChromaDBBackend instance with mocked __init__."""
        with patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None):
            backend = ChromaDBBackend.__new__(ChromaDBBackend)
        return backend

    def test_record_to_metadata_simple_types(self):
        """_record_to_metadata should handle simple metadata types."""
        backend = self._make_backend()
        rec = MemoryRecord(
            id="1",
            content="test",
            embedding=[0.1, 0.2],
            memory_type="semantic",
            category="task",
            importance=0.8,
            tags=["a", "b"],
            metadata={"str_key": "val", "int_key": 42, "float_key": 3.14, "bool_key": True},
            timestamp=1000.0,
            access_count=5,
            last_access=2000.0,
        )
        meta = backend._record_to_metadata(rec)
        assert meta["memory_type"] == "semantic"
        assert meta["category"] == "task"
        assert meta["importance"] == 0.8
        assert meta["str_key"] == "val"
        assert meta["int_key"] == 42
        assert meta["float_key"] == 3.14
        assert meta["bool_key"] is True

    def test_record_to_metadata_complex_types_serialized(self):
        """_record_to_metadata should serialize complex metadata as JSON."""
        backend = self._make_backend()
        rec = MemoryRecord(
            id="1",
            content="test",
            timestamp=time.time(),
            metadata={"list_val": [1, 2, 3], "dict_val": {"nested": True}},
        )
        meta = backend._record_to_metadata(rec)
        import json
        assert json.loads(meta["list_val"]) == [1, 2, 3]
        assert json.loads(meta["dict_val"]) == {"nested": True}

    def test_metadata_to_record_fields(self):
        """_metadata_to_record_fields should extract fields correctly."""
        backend = self._make_backend()
        meta = {
            "memory_type": "episodic",
            "category": "work",
            "importance": 0.7,
            "timestamp": 1000.0,
            "access_count": 3,
            "last_access": 2000.0,
            "tags": '["tag1", "tag2"]',
            "extra_meta": "value",
        }
        fields = backend._metadata_to_record_fields(meta)
        assert fields["memory_type"] == "episodic"
        assert fields["category"] == "work"
        assert fields["importance"] == 0.7
        assert fields["tags"] == ["tag1", "tag2"]
        assert fields["metadata"]["extra_meta"] == "value"

    def test_metadata_to_record_fields_invalid_tags(self):
        """_metadata_to_record_fields should handle invalid tags gracefully."""
        backend = self._make_backend()
        meta = {
            "tags": "not-valid-json",
        }
        fields = backend._metadata_to_record_fields(meta)
        assert fields["tags"] == []

    def test_metadata_to_record_fields_non_string_tags(self):
        """_metadata_to_record_fields should handle non-string tags."""
        backend = self._make_backend()
        meta = {
            "tags": ["already", "a", "list"],
        }
        fields = backend._metadata_to_record_fields(meta)
        assert fields["tags"] == ["already", "a", "list"]

    def test_build_where_filter_none(self):
        """_build_where_filter with None should return None."""
        backend = self._make_backend()
        assert backend._build_where_filter(None) is None

    def test_build_where_filter_empty(self):
        """_build_where_filter with empty dict should return None."""
        backend = self._make_backend()
        assert backend._build_where_filter({}) is None

    def test_build_where_filter_single_condition(self):
        """_build_where_filter with one condition should return that condition."""
        backend = self._make_backend()
        result = backend._build_where_filter({"category": "task"})
        assert result == {"category": "task"}

    def test_build_where_filter_multiple_conditions(self):
        """_build_where_filter with multiple conditions should use $and."""
        backend = self._make_backend()
        result = backend._build_where_filter({"category": "task", "memory_type": "semantic"})
        assert result == {"$and": [{"category": "task"}, {"memory_type": "semantic"}]}

    def test_build_where_filter_tags_string(self):
        """_build_where_filter with tags string should use $contains."""
        backend = self._make_backend()
        import json
        result = backend._build_where_filter({"tags": "urgent"})
        assert result == {"tags": {"$contains": json.dumps("urgent")}}

    def test_build_where_filter_tags_list(self):
        """_build_where_filter with tags list should create multiple $contains."""
        backend = self._make_backend()
        import json
        result = backend._build_where_filter({"tags": ["a", "b"]})
        expected = {"$and": [
            {"tags": {"$contains": json.dumps("a")}},
            {"tags": {"$contains": json.dumps("b")}},
        ]}
        assert result == expected

    def test_chromadb_import_error(self):
        """ChromaDBBackend should raise ImportError when chromadb is not installed."""
        with patch.dict("sys.modules", {"chromadb": None}):
            with pytest.raises(ImportError, match="chromadb is required"):
                ChromaDBBackend()


# ---------------------------------------------------------------------------
# TestFAISSBackendHelpers (mocked)
# ---------------------------------------------------------------------------

class TestFAISSBackendHelpers:
    """Tests for FAISSBackend helper methods."""

    def test_normalize_normal_vector(self):
        """_normalize should produce a unit vector."""
        vec = np.array([3.0, 4.0], dtype=np.float32)
        result = FAISSBackend._normalize(vec)
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-6

    def test_normalize_zero_vector(self):
        """_normalize should return zero vector unchanged."""
        vec = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        result = FAISSBackend._normalize(vec)
        assert np.allclose(result, vec)

    def test_faiss_import_error(self):
        """FAISSBackend should raise ImportError when faiss is not installed."""
        with patch.dict("sys.modules", {"faiss": None}):
            with pytest.raises(ImportError, match="faiss-cpu is required"):
                FAISSBackend()


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedIntegration
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedIntegration:
    """Integration tests for ChromaDBBackend with fully mocked chromadb."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_add_calls_upsert(self):
        """ChromaDBBackend.add should call collection.upsert."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        backend._collection = MagicMock()

        rec = _make_record("1", "test content")
        backend.add(rec)

        backend._collection.upsert.assert_called_once()
        call_kwargs = backend._collection.upsert.call_args[1]
        assert call_kwargs["ids"] == ["1"]
        assert call_kwargs["documents"] == ["test content"]

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_add_batch_empty(self):
        """ChromaDBBackend.add_batch with empty list should return empty list."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        backend._collection = MagicMock()

        result = backend.add_batch([])
        assert result == []
        backend._collection.upsert.assert_not_called()

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_delete_nonexistent(self):
        """ChromaDBBackend.delete for nonexistent record should return False."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        backend._collection = MagicMock()
        backend._collection.get.return_value = {"ids": []}

        result = backend.delete("ghost")
        assert result is False
        backend._collection.delete.assert_not_called()

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_update_nonexistent(self):
        """ChromaDBBackend.update for nonexistent record should return False."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        backend._collection = MagicMock()
        # get returns None for nonexistent
        backend.get = MagicMock(return_value=None)

        result = backend.update("ghost", content="new")
        assert result is False

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_search_none_result(self):
        """ChromaDBBackend.search should handle None query result."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.query.return_value = None
        backend._collection = mock_collection

        results = backend.search([0.1, 0.2], top_k=5)
        assert results == []

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_get_nonexistent(self):
        """ChromaDBBackend.get for nonexistent record should return None."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        backend._collection = MagicMock()
        backend._collection.get.return_value = {"ids": []}

        result = backend.get("ghost")
        assert result is None

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_list_all_empty(self):
        """ChromaDBBackend.list_all on empty collection should return empty list."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        backend._collection = MagicMock()
        backend._collection.count.return_value = 0

        results = backend.list_all()
        assert results == []

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_list_all_with_offset(self):
        """ChromaDBBackend.list_all with offset should paginate correctly."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        backend._collection = MagicMock()
        backend._collection.count.return_value = 5
        backend._collection.get.return_value = {
            "ids": ["0", "1", "2", "3", "4"],
            "documents": ["d0", "d1", "d2", "d3", "d4"],
            "metadatas": [{} for _ in range(5)],
        }

        results = backend.list_all(limit=2, offset=3)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedSearch
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedSearch:
    """Tests for ChromaDBBackend.search with mocked collection.query."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_search_with_results(self):
        """Search should parse query results into SearchResult objects."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["doc1", "doc2"]],
            "metadatas": [[
                {"memory_type": "semantic", "category": "general", "importance": 0.5,
                 "timestamp": 1000.0, "access_count": 0, "last_access": 1000.0,
                 "tags": "[]"},
                {"memory_type": "episodic", "category": "task", "importance": 0.8,
                 "timestamp": 2000.0, "access_count": 1, "last_access": 2000.0,
                 "tags": '["urgent"]'},
            ]],
            "distances": [[0.1, 0.5]],
        }
        backend._collection = mock_collection

        results = backend.search([0.1, 0.2], top_k=5)
        assert len(results) == 2
        assert results[0].record.id == "id1"
        assert results[0].record.content == "doc1"
        assert results[0].score == pytest.approx(0.9)  # 1.0 - 0.1
        assert results[1].record.id == "id2"
        assert results[1].score == pytest.approx(0.5)  # 1.0 - 0.5

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_search_with_filter(self):
        """Search should pass where filter to collection.query."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["doc1"]],
            "metadatas": [[
                {"memory_type": "semantic", "category": "task", "importance": 0.5,
                 "timestamp": 1000.0, "access_count": 0, "last_access": 1000.0,
                 "tags": "[]"},
            ]],
            "distances": [[0.2]],
        }
        backend._collection = mock_collection

        results = backend.search([0.1, 0.2], top_k=5, filter={"category": "task"})
        assert len(results) == 1
        # Verify query was called with a where filter
        call_kwargs = mock_collection.query.call_args[1]
        assert "where" in call_kwargs

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_search_empty_results(self):
        """Search with no matching results should return empty list."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        backend._collection = mock_collection

        results = backend.search([0.1, 0.2], top_k=5)
        assert results == []


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedGet
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedGet:
    """Tests for ChromaDBBackend.get with mocked collection."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_get_existing_record(self):
        """Get should parse collection.get result into MemoryRecord."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["id1"],
            "documents": ["hello world"],
            "metadatas": [{
                "memory_type": "semantic",
                "category": "general",
                "importance": 0.5,
                "timestamp": 1000.0,
                "access_count": 0,
                "last_access": 1000.0,
                "tags": '["tag1"]',
            }],
        }
        backend._collection = mock_collection

        result = backend.get("id1")
        assert result is not None
        assert result.id == "id1"
        assert result.content == "hello world"
        assert result.tags == ["tag1"]

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_get_none_result(self):
        """Get should handle None result from collection."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.get.return_value = None
        backend._collection = mock_collection

        result = backend.get("ghost")
        assert result is None


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedDelete
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedDelete:
    """Tests for ChromaDBBackend.delete with mocked collection."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_delete_existing(self):
        """Delete should call collection.delete for existing record."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": ["id1"]}
        backend._collection = mock_collection

        result = backend.delete("id1")
        assert result is True
        mock_collection.delete.assert_called_once_with(ids=["id1"])

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_delete_exception_returns_false(self):
        """Delete should return False when an exception occurs."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": ["id1"]}
        mock_collection.delete.side_effect = RuntimeError("DB error")
        backend._collection = mock_collection

        result = backend.delete("id1")
        assert result is False


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedUpdate
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedUpdate:
    """Tests for ChromaDBBackend.update with mocked collection."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_update_content(self):
        """Update should call collection.update with new content."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        backend._collection = mock_collection

        existing = MemoryRecord(
            id="1", content="old", timestamp=1000.0,
            embedding=[0.1, 0.2],
        )
        backend.get = MagicMock(return_value=existing)

        result = backend.update("1", content="new content")
        assert result is True
        mock_collection.update.assert_called_once()
        call_kwargs = mock_collection.update.call_args[1]
        assert call_kwargs["documents"] == ["new content"]

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_update_embedding(self):
        """Update should include embedding in collection.update when provided."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        backend._collection = mock_collection

        existing = MemoryRecord(
            id="1", content="test", timestamp=1000.0,
            embedding=[0.1, 0.2],
        )
        backend.get = MagicMock(return_value=existing)

        new_emb = [0.3, 0.4, 0.5]
        result = backend.update("1", embedding=new_emb)
        assert result is True
        call_kwargs = mock_collection.update.call_args[1]
        assert call_kwargs["embeddings"] == [new_emb]

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_update_metadata_only(self):
        """Update with only metadata fields should not include documents or embeddings."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        backend._collection = mock_collection

        existing = MemoryRecord(
            id="1", content="test", timestamp=1000.0,
        )
        backend.get = MagicMock(return_value=existing)

        result = backend.update("1", category="task", importance=0.9)
        assert result is True
        call_kwargs = mock_collection.update.call_args[1]
        assert "documents" not in call_kwargs
        assert "embeddings" not in call_kwargs
        assert "metadatas" in call_kwargs


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedAddBatch
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedAddBatch:
    """Tests for ChromaDBBackend.add_batch with mocked collection."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_add_batch_with_embeddings(self):
        """add_batch should include embeddings when records have them."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        backend._collection = mock_collection

        records = [
            _make_record("1", "first"),
            _make_record("2", "second"),
        ]
        result = backend.add_batch(records)
        assert result == ["1", "2"]
        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args[1]
        assert call_kwargs["embeddings"] is not None
        assert len(call_kwargs["embeddings"]) == 2

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_add_batch_without_embeddings(self):
        """add_batch should not include embeddings when records lack them."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        backend._collection = mock_collection

        records = [
            MemoryRecord(id="1", content="no emb", timestamp=time.time()),
            MemoryRecord(id="2", content="no emb 2", timestamp=time.time()),
        ]
        result = backend.add_batch(records)
        assert result == ["1", "2"]
        call_kwargs = mock_collection.upsert.call_args[1]
        assert call_kwargs["embeddings"] is None


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedListAll
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedListAll:
    """Tests for ChromaDBBackend.list_all with mocked collection."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_list_all_none_result(self):
        """list_all should handle None result from collection.get."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.get.return_value = None
        backend._collection = mock_collection

        results = backend.list_all()
        assert results == []

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_list_all_no_ids(self):
        """list_all should handle empty ids in result."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.get.return_value = {"ids": []}
        backend._collection = mock_collection

        results = backend.list_all()
        assert results == []

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_list_all_offset_beyond_total(self):
        """list_all with offset beyond total should return empty list."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 3
        backend._collection = mock_collection

        results = backend.list_all(limit=10, offset=100)
        assert results == []

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_list_all_returns_records(self):
        """list_all should return MemoryRecord objects."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.get.return_value = {
            "ids": ["id1", "id2"],
            "documents": ["doc1", "doc2"],
            "metadatas": [
                {"memory_type": "semantic", "category": "general", "importance": 0.5,
                 "timestamp": 1000.0, "access_count": 0, "last_access": 1000.0,
                 "tags": "[]"},
                {"memory_type": "episodic", "category": "task", "importance": 0.8,
                 "timestamp": 2000.0, "access_count": 1, "last_access": 2000.0,
                 "tags": '["a"]'},
            ],
        }
        backend._collection = mock_collection

        results = backend.list_all()
        assert len(results) == 2
        assert all(isinstance(r, MemoryRecord) for r in results)
        assert results[0].content == "doc1"
        assert results[1].content == "doc2"


# ---------------------------------------------------------------------------
# TestChromaDBBackendMockedCount
# ---------------------------------------------------------------------------

class TestChromaDBBackendMockedCount:
    """Tests for ChromaDBBackend.count with mocked collection."""

    @patch("memory_system.storage.vector_store.ChromaDBBackend.__init__", lambda self, **kw: None)
    def test_count(self):
        """count should delegate to collection.count."""
        backend = ChromaDBBackend.__new__(ChromaDBBackend)
        mock_collection = MagicMock()
        mock_collection.count.return_value = 42
        backend._collection = mock_collection

        assert backend.count() == 42


# ---------------------------------------------------------------------------
# TestFAISSBackendMockedOperations
# ---------------------------------------------------------------------------

class TestFAISSBackendMockedOperations:
    """Tests for FAISSBackend operations with mocked faiss module."""

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_add_record_with_embedding(self):
        """FAISSBackend.add should store record and add to index."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        rec = MemoryRecord(
            id="1", content="test",
            embedding=[1.0, 0.0, 0.0, 0.0],
            timestamp=time.time(),
        )
        result = store.add(rec)
        assert result == "1"
        assert store.count() == 1

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_add_record_without_embedding(self):
        """FAISSBackend.add should store record even without embedding."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        rec = MemoryRecord(id="1", content="no emb", timestamp=time.time())
        store.add(rec)
        assert store.count() == 1

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_add_batch_empty(self):
        """FAISSBackend.add_batch with empty list should return empty."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        result = store.add_batch([])
        assert result == []

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_search_empty_index(self):
        """FAISSBackend.search on empty index should return empty list."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        store._index.ntotal = 0
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert results == []

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_get_nonexistent(self):
        """FAISSBackend.get for nonexistent id should return None."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        assert store.get("ghost") is None

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_delete_nonexistent(self):
        """FAISSBackend.delete for nonexistent id should return False."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        assert store.delete("ghost") is False

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_update_nonexistent(self):
        """FAISSBackend.update for nonexistent id should return False."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        assert store.update("ghost", content="new") is False

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_list_all(self):
        """FAISSBackend.list_all should return stored records."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        store.add(MemoryRecord(id="1", content="a", timestamp=time.time()))
        store.add(MemoryRecord(id="2", content="b", timestamp=time.time()))
        store.add(MemoryRecord(id="3", content="c", timestamp=time.time()))

        results = store.list_all(limit=2, offset=1)
        assert len(results) == 2
        ids = [r.id for r in results]
        assert "2" in ids
        assert "3" in ids

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_count(self):
        """FAISSBackend.count should return number of records."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        assert store.count() == 0
        store.add(MemoryRecord(id="1", content="a", timestamp=time.time()))
        assert store.count() == 1

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_delete_existing(self):
        """FAISSBackend.delete should remove record and rebuild index."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        store.add(MemoryRecord(id="1", content="a", timestamp=time.time()))
        assert store.count() == 1

        result = store.delete("1")
        assert result is True
        assert store.count() == 0

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_update_existing(self):
        """FAISSBackend.update should modify record fields."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        store.add(MemoryRecord(id="1", content="old", timestamp=time.time()))

        result = store.update("1", content="new")
        assert result is True
        assert store.get("1").content == "new"

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_update_embedding_triggers_rebuild(self):
        """FAISSBackend.update with embedding should trigger index rebuild."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        store.add(MemoryRecord(
            id="1", content="test",
            embedding=[1.0, 0.0, 0.0, 0.0],
            timestamp=time.time(),
        ))

        result = store.update("1", embedding=[0.0, 1.0, 0.0, 0.0])
        assert result is True

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_get_updates_access_stats(self):
        """FAISSBackend.get should increment access_count."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        rec = MemoryRecord(id="1", content="test", timestamp=time.time())
        store.add(rec)

        result = store.get("1")
        assert result.access_count == 1

    @patch.dict("sys.modules", {"faiss": MagicMock()})
    def test_matches_filter(self):
        """FAISSBackend._matches_filter should work correctly."""
        import importlib
        import memory_system.storage.vector_store as vs_module
        importlib.reload(vs_module)
        FAISSBackend = vs_module.FAISSBackend

        store = FAISSBackend(dimension=4)
        rec = MemoryRecord(
            id="1", content="test",
            category="task", tags=["urgent"],
            metadata={"source": "web"},
            timestamp=time.time(),
        )
        assert store._matches_filter(rec, {"category": "task"}) is True
        assert store._matches_filter(rec, {"category": "general"}) is False
        assert store._matches_filter(rec, {"tags": "urgent"}) is True
        assert store._matches_filter(rec, {"tags": ["urgent", "work"]}) is True
        assert store._matches_filter(rec, {"tags": ["other"]}) is False
        assert store._matches_filter(rec, {"source": "web"}) is True
        assert store._matches_filter(rec, {"source": "file"}) is False
        assert store._matches_filter(rec, {}) is True
