"""Unit tests for the exceptions module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.exceptions import (
    MemoryError,
    EmbeddingError,
    EmbeddingModelNotFoundError,
    EmbeddingDimensionError,
    VectorStoreError,
    VectorStoreConnectionError,
    MemoryNotFoundError,
    KnowledgeGraphError,
    EntityNotFoundError,
    StructuredStoreError,
    TableNotFoundError,
    ConfigurationError,
    ConsolidationError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_memory_error(self):
        """所有自定义异常都应继承自 MemoryError"""
        subclasses = [
            EmbeddingError, EmbeddingModelNotFoundError, EmbeddingDimensionError,
            VectorStoreError, VectorStoreConnectionError, MemoryNotFoundError,
            KnowledgeGraphError, EntityNotFoundError,
            StructuredStoreError, TableNotFoundError,
            ConfigurationError, ConsolidationError,
        ]
        for cls in subclasses:
            assert issubclass(cls, MemoryError), f"{cls.__name__} should inherit from MemoryError"

    def test_catch_all_with_memory_error(self):
        """可以用 MemoryError 统一捕获所有子异常"""
        exceptions = [
            EmbeddingError("test"),
            VectorStoreError("test"),
            KnowledgeGraphError("test"),
            StructuredStoreError("test"),
            ConfigurationError("test"),
        ]
        for exc in exceptions:
            with pytest.raises(MemoryError):
                raise exc


class TestSpecificExceptions:
    def test_embedding_dimension_error(self):
        """EmbeddingDimensionError 应包含期望和实际维度"""
        exc = EmbeddingDimensionError(expected=128, actual=64)
        assert exc.expected == 128
        assert exc.actual == 64
        assert "128" in str(exc)
        assert "64" in str(exc)

    def test_memory_not_found_error(self):
        """MemoryNotFoundError 应包含记忆ID"""
        exc = MemoryNotFoundError(memory_id="abc123")
        assert exc.memory_id == "abc123"
        assert "abc123" in str(exc)

    def test_entity_not_found_error(self):
        """EntityNotFoundError 应包含实体名"""
        exc = EntityNotFoundError(entity_name="Python")
        assert exc.entity_name == "Python"
        assert "Python" in str(exc)

    def test_table_not_found_error(self):
        """TableNotFoundError 应包含表名"""
        exc = TableNotFoundError(table_name="users")
        assert exc.table_name == "users"
        assert "users" in str(exc)


class TestExceptionInheritanceChains:
    def test_embedding_chain(self):
        assert issubclass(EmbeddingModelNotFoundError, EmbeddingError)
        assert issubclass(EmbeddingDimensionError, EmbeddingError)

    def test_vector_store_chain(self):
        assert issubclass(VectorStoreConnectionError, VectorStoreError)
        assert issubclass(MemoryNotFoundError, VectorStoreError)

    def test_knowledge_graph_chain(self):
        assert issubclass(EntityNotFoundError, KnowledgeGraphError)

    def test_structured_store_chain(self):
        assert issubclass(TableNotFoundError, StructuredStoreError)
