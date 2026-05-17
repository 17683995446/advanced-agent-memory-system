"""
ChromaDB vector store backend.

Provides :class:`ChromaDBBackend`, a backend powered by ChromaDB with
support for both persistent and ephemeral clients.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from .base_backend import VectorStoreBackend
from .models import MemoryRecord, SearchResult

logger = logging.getLogger(__name__)


class ChromaDBBackend(VectorStoreBackend):
    """Vector store backend powered by ChromaDB.

    Supports both persistent and ephemeral clients.  When
    *persist_directory* is provided a :class:`PersistentClient` is used;
    otherwise an :class:`EphemeralClient` is created.

    Args:
        persist_directory: Optional path for persistent storage on disk.
        collection_name: Name of the ChromaDB collection.
        embedding_function: Optional custom embedding function compatible
            with ChromaDB's ``EmbeddingFunction`` interface.  When ``None``,
            ChromaDB's default embedding function is used.
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "agent_memory",
        embedding_function: Optional[Any] = None,
    ) -> None:
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for ChromaDBBackend. "
                "Install it with: pip install chromadb"
            )

        self._collection_name = collection_name

        if persist_directory is not None:
            self._client = chromadb.PersistentClient(path=persist_directory)
        else:
            self._client = chromadb.EphemeralClient()

        self._embedding_function = embedding_function

        # Determine the embedding function argument for get_or_create_collection
        if embedding_function is not None:
            ef_arg = embedding_function
        else:
            ef_arg = chromadb.utils.embedding_functions.DefaultEmbeddingFunction()

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=ef_arg,
            metadata={"hnsw:space": "cosine"},
        )

    # -- helpers -------------------------------------------------------------

    def _record_to_metadata(self, record: MemoryRecord) -> dict:
        """Convert a MemoryRecord to a ChromaDB-compatible metadata dict.

        ChromaDB metadata values must be str, int, float, or bool.
        Lists and dicts are serialised as JSON strings.
        """
        meta: dict[str, Any] = {
            "memory_type": record.memory_type,
            "category": record.category,
            "importance": record.importance,
            "timestamp": record.timestamp,
            "access_count": record.access_count,
            "last_access": record.last_access,
            "tags": json.dumps(record.tags),
        }
        # Flatten top-level metadata (only simple types)
        for k, v in record.metadata.items():
            if isinstance(v, (str, int, float, bool)):
                meta[k] = v
            else:
                meta[k] = json.dumps(v)
        return meta

    def _metadata_to_record_fields(self, meta: dict) -> dict:
        """Extract record fields from ChromaDB metadata."""
        tags_raw = meta.pop("tags", "[]")
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        except (json.JSONDecodeError, TypeError):
            tags = []

        record_fields: dict[str, Any] = {
            "memory_type": meta.pop("memory_type", "semantic"),
            "category": meta.pop("category", "general"),
            "importance": meta.pop("importance", 0.5),
            "timestamp": meta.pop("timestamp", time.time()),
            "access_count": meta.pop("access_count", 0),
            "last_access": meta.pop("last_access", time.time()),
            "tags": tags,
            "metadata": meta,
        }
        return record_fields

    def _build_where_filter(self, filter: Optional[dict]) -> Optional[dict]:
        """Translate a generic filter dict to ChromaDB ``where`` syntax."""
        if filter is None:
            return None

        conditions: list[dict] = []

        for key, value in filter.items():
            if key == "tags":
                # ChromaDB $contains works for string fields; our tags are
                # stored as a JSON array string, so we use $contains with the
                # serialised form.
                if isinstance(value, list):
                    for tag in value:
                        conditions.append(
                            {"tags": {"$contains": json.dumps(tag)}}
                        )
                else:
                    conditions.append(
                        {"tags": {"$contains": json.dumps(value)}}
                    )
            else:
                conditions.append({key: value})

        if len(conditions) == 0:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    # -- public API ----------------------------------------------------------

    def add(self, record: MemoryRecord) -> str:
        """Add a single record to the ChromaDB collection."""
        metadata = self._record_to_metadata(record)
        embedding = (
            record.embedding if record.embedding is not None else None
        )

        self._collection.upsert(
            ids=[record.id],
            documents=[record.content],
            embeddings=[embedding] if embedding is not None else None,
            metadatas=[metadata],
        )
        return record.id

    def add_batch(self, records: list[MemoryRecord]) -> list[str]:
        """Add multiple records to the ChromaDB collection."""
        if not records:
            return []

        ids = [r.id for r in records]
        documents = [r.content for r in records]
        metadatas = [self._record_to_metadata(r) for r in records]

        embeddings: Optional[list[list[float]]] = None
        if records[0].embedding is not None:
            embeddings = [r.embedding for r in records]

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return ids

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search the ChromaDB collection for similar records."""
        where = self._build_where_filter(filter)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        search_results: list[SearchResult] = []

        if results is None:
            return search_results

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, rec_id in enumerate(ids):
            content = documents[i] if i < len(documents) else ""
            meta = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 0.0

            # ChromaDB with cosine space returns distance (1 - similarity)
            score = 1.0 - distance

            record_fields = self._metadata_to_record_fields(
                dict(meta) if meta else {}
            )
            record = MemoryRecord(
                id=rec_id,
                content=content,
                **record_fields,
            )
            search_results.append(SearchResult(record=record, score=score))

        return search_results

    def get(self, id: str) -> Optional[MemoryRecord]:
        """Retrieve a record by id from ChromaDB."""
        results = self._collection.get(
            ids=[id], include=["documents", "metadatas"]
        )
        if results is None or not results.get("ids"):
            return None

        rec_id = results["ids"][0]
        content = results.get("documents", [None])[0] or ""
        meta = results.get("metadatas", [{}])[0] or {}

        record_fields = self._metadata_to_record_fields(dict(meta))
        return MemoryRecord(id=rec_id, content=content, **record_fields)

    def delete(self, id: str) -> bool:
        """Delete a record from the ChromaDB collection."""
        try:
            existing = self._collection.get(ids=[id])
            if not existing or not existing.get("ids"):
                return False
            self._collection.delete(ids=[id])
            return True
        except (ValueError, RuntimeError, AttributeError):
            logger.exception("Failed to delete record %s from ChromaDB", id)
            return False

    def update(self, id: str, **kwargs: Any) -> bool:
        """Update a record in the ChromaDB collection."""
        existing = self.get(id)
        if existing is None:
            return False

        # Merge updates into the existing record
        update_data = existing.model_copy(update=kwargs)
        metadata = self._record_to_metadata(update_data)

        chroma_update: dict[str, Any] = {
            "ids": [id],
            "metadatas": [metadata],
        }

        if "content" in kwargs:
            chroma_update["documents"] = [kwargs["content"]]
        if "embedding" in kwargs:
            chroma_update["embeddings"] = [kwargs["embedding"]]

        self._collection.update(**chroma_update)
        return True

    def count(self) -> int:
        """Return the number of records in the collection."""
        return self._collection.count()

    def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[MemoryRecord]:
        """List all records with pagination."""
        total = self._collection.count()
        fetch_count = min(limit, total - offset) if offset < total else 0
        if fetch_count <= 0:
            return []

        results = self._collection.get(
            include=["documents", "metadatas"],
        )

        records: list[MemoryRecord] = []
        if results is None or not results.get("ids"):
            return records

        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        for i, rec_id in enumerate(ids):
            content = documents[i] if i < len(documents) else ""
            meta = metadatas[i] if i < len(metadatas) else {}
            record_fields = self._metadata_to_record_fields(dict(meta))
            records.append(
                MemoryRecord(id=rec_id, content=content, **record_fields)
            )

        return records[offset : offset + limit]


__all__ = ["ChromaDBBackend"]
