"""
Data models for the vector store module.

Provides :class:`MemoryRecord` and :class:`SearchResult` -- the core
data classes used by all vector store backends.
"""

from __future__ import annotations

import hashlib
import time

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """A single memory record stored in the vector store.

    Attributes:
        id: Unique identifier for the record.
        content: The text content of the memory.
        embedding: Optional pre-computed embedding vector.
        memory_type: Type classification (e.g. "semantic", "episodic").
        category: Logical category for filtering (e.g. "general", "task").
        importance: Importance score in [0.0, 1.0].
        tags: Free-form list of tags for filtering.
        metadata: Arbitrary key-value metadata.
        source: Origin of the memory (e.g. "user", "system", "unknown").
        timestamp: Unix timestamp of when the record was created.
        access_count: Number of times this record has been accessed.
        last_access: Unix timestamp of the most recent access.
    """

    id: str
    content: str
    embedding: list[float] | None = None
    memory_type: str = "semantic"
    category: str = "general"
    importance: float = 0.5
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    source: str = "unknown"
    timestamp: float = Field(default_factory=time.time)
    access_count: int = 0
    last_access: float = Field(default_factory=time.time)

    @property
    def content_hash(self) -> str:
        """Return a deterministic SHA-256 hash of the content for deduplication."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class SearchResult(BaseModel):
    """Result returned from a vector similarity search.

    Attributes:
        record: The matched memory record.
        score: Similarity score (higher is more similar).
    """

    record: MemoryRecord
    score: float


__all__ = ["MemoryRecord", "SearchResult"]
