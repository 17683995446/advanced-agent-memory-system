"""
Abstract base class for vector store backends.

All concrete backends must implement the :class:`VectorStoreBackend`
interface so that the memory system can swap storage engines transparently.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import MemoryRecord, SearchResult


class VectorStoreBackend(ABC):
    """Abstract base class for vector store backends.

    All concrete backends must implement the methods defined here so that
    the memory system can swap storage engines transparently.
    """

    @abstractmethod
    def add(self, record: MemoryRecord) -> str:
        """Add a single memory record to the store.

        Args:
            record: The memory record to add.

        Returns:
            The id of the added record.
        """
        ...

    @abstractmethod
    def add_batch(self, records: list[MemoryRecord]) -> list[str]:
        """Add multiple memory records to the store.

        Args:
            records: List of memory records to add.

        Returns:
            List of ids for the added records, in the same order.
        """
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search for the most similar records to the query embedding.

        Args:
            query_embedding: The embedding vector to search against.
            top_k: Maximum number of results to return.
            filter: Optional filter dict (e.g. ``{"category": "task"}``).

        Returns:
            List of search results sorted by descending similarity score.
        """
        ...

    @abstractmethod
    def get(self, id: str) -> Optional[MemoryRecord]:
        """Retrieve a record by its id.

        Args:
            id: The unique identifier of the record.

        Returns:
            The matching record, or ``None`` if not found.
        """
        ...

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete a record by its id.

        Args:
            id: The unique identifier of the record.

        Returns:
            ``True`` if the record was deleted, ``False`` if it was not found.
        """
        ...

    @abstractmethod
    def update(self, id: str, **kwargs: Any) -> bool:
        """Update fields of an existing record.

        Args:
            id: The unique identifier of the record.
            **kwargs: Fields to update (e.g. ``content="new text"``).

        Returns:
            ``True`` if the record was updated, ``False`` if not found.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the total number of records in the store."""
        ...

    @abstractmethod
    def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[MemoryRecord]:
        """List records with pagination.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            A list of memory records.
        """
        ...


__all__ = ["VectorStoreBackend"]
