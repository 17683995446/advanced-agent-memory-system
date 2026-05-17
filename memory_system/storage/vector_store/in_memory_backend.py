"""
In-memory vector store backend (NumPy-based).

Provides :class:`MemoryVectorStore`, a pure in-memory implementation
suitable for development, testing, and small-scale deployments.

v5.1+: 新增容量管理（LRU 驱逐），支持 max_records 上限和可插拔驱逐策略。
"""

from __future__ import annotations

import heapq
import threading
import time
from enum import Enum
from typing import Any, Callable, Optional

import numpy as np

from .base_backend import VectorStoreBackend
from .models import MemoryRecord, SearchResult


class EvictionPolicy(Enum):
    """驱逐策略类型。"""
    LRU = "lru"          # 最近最少使用
    LFU = "lfu"          # 最不常使用
    FIFO = "fifo"        # 先进先出
    IMPORTANCE = "importance"  # 最低重要性优先


class MemoryVectorStore(VectorStoreBackend):
    """Pure in-memory vector store backed by a Python dict and NumPy arrays.

    Similarity is computed using cosine similarity.  The store is
    thread-safe via :class:`threading.RLock`.

    v5.1+: 支持 max_records 容量上限和可插拔驱逐策略。
    当记录数超过上限时，自动驱逐最低价值的记录。

    Args:
        max_records: 最大记录数，0 表示无限制（默认无限制）
        eviction_policy: 驱逐策略
        on_evict_callback: 驱逐回调 (MemoryRecord)
    """

    def __init__(
        self,
        max_records: int = 0,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
        on_evict_callback: Optional[Callable[[MemoryRecord], None]] = None,
    ) -> None:
        self._records: dict[str, MemoryRecord] = {}
        self._embeddings: dict[str, np.ndarray] = {}
        self._lock = threading.RLock()
        self._next_id_counter: int = 0
        # 预构建的嵌入矩阵和ID列表（用于批量矩阵运算）
        self._matrix_dirty: bool = True
        self._embedding_matrix: Optional[np.ndarray] = None
        self._matrix_ids: list[str] = []
        # 容量管理
        self._max_records = max_records
        self._eviction_policy = eviction_policy
        self._on_evict_callback = on_evict_callback
        self._total_evictions = 0

    # -- helpers -------------------------------------------------------------

    def _rebuild_matrix(self) -> None:
        """重建嵌入矩阵，用于批量矩阵运算。"""
        if not self._matrix_dirty and self._embedding_matrix is not None:
            return
        if not self._embeddings:
            self._embedding_matrix = None
            self._matrix_ids = []
            self._matrix_dirty = False
            return
        ids = list(self._embeddings.keys())
        vectors = np.stack([self._embeddings[rid] for rid in ids])
        self._embedding_matrix = vectors
        self._matrix_ids = ids
        self._matrix_dirty = False

    def _evict_if_needed(self) -> int:
        """检查容量并在需要时驱逐记录。

        Returns:
            驱逐的记录数量
        """
        if self._max_records <= 0:
            return 0
        evicted = 0
        while len(self._records) > self._max_records:
            victim_id = self._select_eviction_candidate()
            if victim_id is None:
                break
            victim = self._records.pop(victim_id, None)
            self._embeddings.pop(victim_id, None)
            self._matrix_dirty = True
            self._total_evictions += 1
            evicted += 1
            if victim is not None and self._on_evict_callback:
                try:
                    self._on_evict_callback(victim)
                except Exception:
                    pass
        return evicted

    def _select_eviction_candidate(self) -> Optional[str]:
        """根据驱逐策略选择要驱逐的记录ID。"""
        if not self._records:
            return None

        policy = self._eviction_policy

        if policy == EvictionPolicy.LRU:
            # 最近最少访问
            return min(
                self._records.keys(),
                key=lambda rid: self._records[rid].last_access,
            )

        elif policy == EvictionPolicy.LFU:
            # 最不常访问
            return min(
                self._records.keys(),
                key=lambda rid: self._records[rid].access_count,
            )

        elif policy == EvictionPolicy.FIFO:
            # 最早创建
            return min(
                self._records.keys(),
                key=lambda rid: self._records[rid].timestamp,
            )

        elif policy == EvictionPolicy.IMPORTANCE:
            # 最低重要性
            return min(
                self._records.keys(),
                key=lambda rid: self._records[rid].importance,
            )

        return next(iter(self._records))

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _matches_filter(self, record: MemoryRecord, filter: dict) -> bool:
        """Check whether *record* satisfies all key-value pairs in *filter*.

        Supported filter keys:
        * ``category`` -- exact match against ``record.category``.
        * ``memory_type`` -- exact match against ``record.memory_type``.
        * ``tags`` -- if the filter value is a list, the record must contain
          at least one of the specified tags; if a string, the record must
          contain that exact tag.
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
                # Unknown filter key -- treat as metadata filter
                if record.metadata.get(key) != value:
                    return False
        return True

    # -- public API ----------------------------------------------------------

    def add(self, record: MemoryRecord) -> str:
        """Add a single record to the in-memory store."""
        with self._lock:
            self._records[record.id] = record
            if record.embedding is not None:
                self._embeddings[record.id] = np.array(
                    record.embedding, dtype=np.float32
                )
            self._matrix_dirty = True
            # 容量管理：检查是否需要驱逐
            self._evict_if_needed()
            return record.id

    def add_batch(self, records: list[MemoryRecord]) -> list[str]:
        """Add multiple records in a single lock acquisition."""
        ids: list[str] = []
        with self._lock:
            for record in records:
                self._records[record.id] = record
                if record.embedding is not None:
                    self._embeddings[record.id] = np.array(
                        record.embedding, dtype=np.float32
                    )
                ids.append(record.id)
        return ids

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search using cosine similarity against stored embeddings.

        Uses NumPy matrix multiplication for batch similarity computation
        and heapq for O(n log k) top-k selection.
        """
        with self._lock:
            self._rebuild_matrix()
            query_vec = np.array(query_embedding, dtype=np.float32)

            if self._embedding_matrix is None or len(self._matrix_ids) == 0:
                return []

            # 批量矩阵运算：计算查询向量与所有存储向量的余弦相似度
            # 对于已归一化向量，点积 = 余弦相似度
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0.0:
                return []

            # 矩阵乘法: (1, dim) @ (dim, n) -> (1, n) 相似度分数
            all_scores = self._embedding_matrix @ query_vec

            # 矩阵范数（预计算每个存储向量的范数）
            matrix_norms = np.linalg.norm(self._embedding_matrix, axis=1)
            # 避免除零
            safe_norms = np.where(matrix_norms == 0.0, 1.0, matrix_norms)
            cosine_scores = all_scores / (safe_norms * query_norm)

            # 使用堆进行 top-k 选择 O(n log k)
            if filter is not None:
                # 有过滤器时需要逐条检查
                heap = []
                for idx, score in enumerate(cosine_scores):
                    rec_id = self._matrix_ids[idx]
                    record = self._records.get(rec_id)
                    if record is None or not self._matches_filter(record, filter):
                        continue
                    if len(heap) < top_k:
                        heapq.heappush(heap, (score, idx))
                    elif score > heap[0][0]:
                        heapq.heapreplace(heap, (score, idx))
                top_indices = [idx for _, idx in sorted(heap, reverse=True)]
            else:
                # 无过滤器时直接用 argpartition（平均 O(n)）
                if len(cosine_scores) <= top_k:
                    top_indices = np.argsort(-cosine_scores)
                else:
                    # argpartition 是 O(n)，比完整排序 O(n log n) 快
                    part_idx = np.argpartition(-cosine_scores, top_k)[:top_k]
                    top_indices = part_idx[np.argsort(-cosine_scores[part_idx])]

            results = []
            for idx in top_indices:
                rec_id = self._matrix_ids[idx]
                record = self._records.get(rec_id)
                if record is not None:
                    score = float(cosine_scores[idx])
                    results.append(SearchResult(record=record, score=score))
                    # Update access stats
                    record.access_count += 1
                    record.last_access = time.time()

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
        """Delete a record by id."""
        with self._lock:
            if id in self._records:
                del self._records[id]
                self._embeddings.pop(id, None)
                self._matrix_dirty = True
                return True
            return False

    def update(self, id: str, **kwargs: Any) -> bool:
        """Update fields of an existing record."""
        with self._lock:
            record = self._records.get(id)
            if record is None:
                return False

            for key, value in kwargs.items():
                if key == "embedding":
                    self._embeddings[id] = np.array(value, dtype=np.float32)
                if hasattr(record, key):
                    setattr(record, key, value)

            record.last_access = time.time()
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


__all__ = ["MemoryVectorStore"]
