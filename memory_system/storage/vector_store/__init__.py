"""
Pluggable Vector Store Sub-Package for Agent Memory System.

Provides abstract base class and multiple backend implementations for
storing and searching memory embeddings, including in-memory (numpy),
ChromaDB, and FAISS backends. A factory class enables easy backend
switching via configuration.

This sub-package was refactored from the monolithic
``vector_similarity_store.py`` module.  All public symbols are
re-exported here for backward compatibility.
"""

from .models import MemoryRecord, SearchResult
from .base_backend import VectorStoreBackend
from .in_memory_backend import MemoryVectorStore
from .chromadb_backend import ChromaDBBackend
from .faiss_backend import FAISSBackend
from .factory import VectorStoreFactory

__all__ = [
    "MemoryRecord",
    "SearchResult",
    "VectorStoreBackend",
    "MemoryVectorStore",
    "ChromaDBBackend",
    "FAISSBackend",
    "VectorStoreFactory",
]
