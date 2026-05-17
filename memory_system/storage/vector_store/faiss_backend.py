"""
FAISS vector store backend.

Provides :class:`FAISSBackend`, a backend powered by Facebook AI
Similarity Search (FAISS) with L2-normalised inner-product indexing.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Optional

import numpy as np

from .base_backend import VectorStoreBackend
from .models import MemoryRecord, SearchResult

logger = logging.getLogger(__name__)


class FAISSBackend(VectorStoreBackend):
    """Vector store backend powered by FAISS (Facebook AI Similarity Search).

    Uses :class:`faiss.IndexFlatIP` (inner-product index) with L2-normalised
    vectors so that inner product equals cosine similarity.

    The index is kept in memory and can optionally be persisted to / loaded
    from disk.

    Args:
        dimension: Dimensionality of the embedding vectors.
        index_file: Optional path to a pre-existing FAISS index file to load
            on initialisation.
    """

    def __init__(
        self,
        dimension: int = 384,
        index_file: Optional[str] = None,
    ) -> None:
        try:
            import faiss
        except ImportError:
            raise ImportError(
                "faiss-cpu is required for FAISSBackend. "
                "Install it with: pip install faiss-cpu"
            )

        self._dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)
        self._records: dict[str, MemoryRecord] = {}
        self._id_to_pos: dict[str, int] = {}
        self._pos_to_id: dict[int, str] = {}
        self._lock = threading.RLock()
        self._next_pos: int = 0

        if index_file is not None:
            self.load_index(index_file)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        """L2-normalise a vector so inner product equals cosine similarity."""
        norm = np.linalg.norm(vec)
        if norm == 0.0:
            return vec
        return vec / norm

    def _rebuild_index(self) -> None:
        """Rebuild the FAISS index from the current records.

        Called after deletions to keep the dense index consistent.
        """
        import faiss

        self._index = faiss.IndexFlatIP(self._dimension)
        self._id_to_pos.clear()
        self._pos_to_id.clear()
        self._next_pos = 0

        if not self._records:
            return

        vectors = []
        ordered_ids = []

        for rec_id, record in self._records.items():
            if record.embedding is not None:
                vec = self._normalize(
                    np.array(record.embedding, dtype=np.float32)
                )
                vectors.append(vec)
                ordered_ids.append(rec_id)

        if vectors:
            vectors_np = np.vstack(vectors).astype(np.float32)
            self._index.add(vectors_np)
            for pos, rec_id in enumerate(ordered_ids):
                self._id_to_pos[rec_id] = pos
                self._pos_to_id[pos] = rec_id
            self._next_pos = len(ordered_ids)

    def _matches_filter(self, record: MemoryRecord, filter: dict) -> bool:
        """Check whether *record* satisfies all key-value pairs in *filter*.

        Supported filter keys:
        * ``category`` -- exact match.
        * ``memory_type`` -- exact match.
        * ``tags`` -- list requires at least one match; string requires exact.
        * Any key in ``record.metadata`` -- exact match.
        """
        for key, value in filter.items():
            if key == "category":
                if record.category != value:
                    return False
            elif key == "memory_type":
                if record.memory_type != value:
                    return False
            elif key == "tags":
                if isinstance(value, list):
                    if not any(t in record.tags for t in value):
                        return False
                else:
                    if value not in record.tags:
                        return False
            elif key in record.metadata:
                if record.metadata[key] != value:
                    return False
            else:
                if record.metadata.get(key) != value:
                    return False
        return True

    # -- persistence ---------------------------------------------------------

    def save_index(self, path: str) -> None:
        """Save the FAISS index and associated record metadata to disk.

        The index is written using ``faiss.write_index``.  Record data
        (without embeddings) is stored alongside as a JSON sidecar file.

        Args:
            path: File path for the FAISS index file.  A companion
                ``<path>.records.json`` file will also be created.
        """
        import faiss

        with self._lock:
            faiss.write_index(self._index, path)

            # Save record data (without embeddings) for full restoration
            records_data = {}
            for rec_id, record in self._records.items():
                records_data[rec_id] = record.model_dump()

            records_path = path + ".records.json"
            with open(records_path, "w", encoding="utf-8") as f:
                json.dump(records_data, f, ensure_ascii=False, indent=2)

            logger.info(
                "Saved FAISS index to %s (%d vectors) with records at %s",
                path,
                self._index.ntotal,
                records_path,
            )

    def load_index(self, path: str) -> None:
        """Load a FAISS index and associated record metadata from disk.

        Args:
            path: File path for the FAISS index file.  Expects a companion
                ``<path>.records.json`` file with record data.
        """
        import faiss

        with self._lock:
            self._index = faiss.read_index(path)
            self._dimension = self._index.d

            # Load record data
            records_path = path + ".records.json"
            self._records.clear()
            self._id_to_pos.clear()
            self._pos_to_id.clear()

            try:
                with open(records_path, "r", encoding="utf-8") as f:
                    records_data = json.load(f)
            except FileNotFoundError:
                logger.warning(
                    "No records sidecar file found at %s; loading index only.",
                    records_path,
                )
                records_data = {}

            for rec_id, data in records_data.items():
                record = MemoryRecord(**data)
                self._records[rec_id] = record

            # Rebuild positional mappings based on current index state
            # We re-add all embeddings to ensure consistency
            if self._records:
                self._rebuild_index()

            logger.info(
                "Loaded FAISS index from %s (%d vectors, %d records)",
                path,
                self._index.ntotal,
                len(self._records),
            )

    # -- public API ----------------------------------------------------------

    def add(self, record: MemoryRecord) -> str:
        """Add a single record to the FAISS index."""
        with self._lock:
            self._records[record.id] = record

            if record.embedding is not None:
                vec = self._normalize(
                    np.array(record.embedding, dtype=np.float32).reshape(1, -1)
                )
                pos = self._next_pos
                self._index.add(vec)
                self._id_to_pos[record.id] = pos
                self._pos_to_id[pos] = record.id
                self._next_pos += 1

            return record.id

    def add_batch(self, records: list[MemoryRecord]) -> list[str]:
        """Add multiple records to the FAISS index in one operation."""
        if not records:
            return []

        ids: list[str] = []
        vectors_to_add: list[np.ndarray] = []

        with self._lock:
            for record in records:
                self._records[record.id] = record
                ids.append(record.id)

                if record.embedding is not None:
                    vec = self._normalize(
                        np.array(record.embedding, dtype=np.float32)
                    )
                    vectors_to_add.append(vec)

            if vectors_to_add:
                vectors_np = (
                    np.vstack(vectors_to_add).astype(np.float32)
                )
                self._index.add(vectors_np)

                for i, record in enumerate(records):
                    if record.embedding is not None:
                        pos = self._next_pos + i
                        self._id_to_pos[record.id] = pos
                        self._pos_to_id[pos] = record.id

                self._next_pos += len(vectors_to_add)

        return ids

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search the FAISS index for similar records."""
        with self._lock:
            if self._index.ntotal == 0:
                return []

            query_vec = self._normalize(
                np.array(query_embedding, dtype=np.float32).reshape(1, -1)
            )

            # Search more candidates than needed when filtering
            search_k = min(
                top_k * 3 if filter else top_k,
                self._index.ntotal,
            )
            scores, indices = self._index.search(query_vec, search_k)

            results: list[SearchResult] = []
            seen_ids: set[str] = set()

            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue

                rec_id = self._pos_to_id.get(int(idx))
                if rec_id is None or rec_id in seen_ids:
                    continue

                record = self._records.get(rec_id)
                if record is None:
                    continue

                if filter is not None and not self._matches_filter(record, filter):
                    continue

                seen_ids.add(rec_id)
                results.append(SearchResult(record=record, score=float(score)))

                if len(results) >= top_k:
                    break

            # Update access stats
            for sr in results:
                sr.record.access_count += 1
                sr.record.last_access = time.time()

            return results

    def get(self, id: str) -> Optional[MemoryRecord]:
        """Retrieve a record by id."""
        with self._lock:
            record = self._records.get(id)
            if record is not None:
                record.access_count += 1
                record.last_access = time.time()
            return record

    def delete(self, id: str) -> bool:
        """Delete a record and rebuild the index."""
        with self._lock:
            if id not in self._records:
                return False

            del self._records[id]
            self._rebuild_index()
            return True

    def update(self, id: str, **kwargs: Any) -> bool:
        """Update a record and rebuild the index if the embedding changed."""
        with self._lock:
            record = self._records.get(id)
            if record is None:
                return False

            embedding_changed = "embedding" in kwargs

            for key, value in kwargs.items():
                if hasattr(record, key):
                    setattr(record, key, value)

            record.last_access = time.time()

            if embedding_changed:
                self._rebuild_index()

            return True

    def count(self) -> int:
        """Return the number of stored records."""
        with self._lock:
            return len(self._records)

    def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[MemoryRecord]:
        """Return a paginated list of all records."""
        with self._lock:
            all_records = list(self._records.values())
            return all_records[offset : offset + limit]


__all__ = ["FAISSBackend"]
