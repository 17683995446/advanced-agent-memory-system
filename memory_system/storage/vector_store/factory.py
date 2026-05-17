"""
Factory for creating vector store backend instances.

Provides :class:`VectorStoreFactory` for easy backend switching via
configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_backend import VectorStoreBackend
from .chromadb_backend import ChromaDBBackend
from .faiss_backend import FAISSBackend
from .in_memory_backend import MemoryVectorStore

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Factory for creating :class:`VectorStoreBackend` instances.

    Usage::

        store = VectorStoreFactory.create("memory")
        store = VectorStoreFactory.create("chroma", persist_directory="./db")
        store = VectorStoreFactory.create("faiss", dimension=768)
    """

    _registry: dict[str, type[VectorStoreBackend]] = {
        "memory": MemoryVectorStore,
        "chroma": ChromaDBBackend,
        "chromadb": ChromaDBBackend,
        "faiss": FAISSBackend,
    }

    @classmethod
    def create(
        cls, backend: str = "memory", **kwargs: Any
    ) -> VectorStoreBackend:
        """Create a vector store backend instance.

        Args:
            backend: Name of the backend to create.  Supported values:
                ``"memory"``, ``"chroma"``, ``"chromadb"``, ``"faiss"``.
            **kwargs: Additional keyword arguments forwarded to the backend
                constructor.

        Returns:
            An instance of the requested vector store backend.

        Raises:
            ValueError: If *backend* is not a recognised name.
        """
        backend_lower = backend.lower()
        backend_cls = cls._registry.get(backend_lower)
        if backend_cls is None:
            supported = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(
                f"Unknown vector store backend '{backend}'. "
                f"Supported backends: {supported}"
            )
        logger.info("Creating vector store backend: %s", backend_lower)
        return backend_cls(**kwargs)

    @classmethod
    def register(
        cls, name: str, backend_cls: type[VectorStoreBackend]
    ) -> None:
        """Register a custom backend class under a given name.

        Args:
            name: The name to register the backend under.
            backend_cls: The backend class (must be a subclass of
                :class:`VectorStoreBackend`).
        """
        if not issubclass(backend_cls, VectorStoreBackend):
            raise TypeError(
                f"{backend_cls.__name__} is not a subclass of VectorStoreBackend"
            )
        cls._registry[name.lower()] = backend_cls


__all__ = ["VectorStoreFactory"]
