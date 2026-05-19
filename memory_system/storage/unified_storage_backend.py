"""
统一存储接口 - 多后端抽象层

提供统一的存储接口，支持:
- 向量存储 (Memory/ChromaDB/FAISS/Redis)
- 结构化存储 (SQLite/SQLModel)
- 缓存层 (Memory/Redis)
- 事件驱动的数据同步

通过配置灵活切换后端，无需修改业务代码。
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

import numpy as np
from pydantic import BaseModel

try:
    from memory_system.infra.blinker_event_bus import (
        EventBus,
        StorageEvent,
        StorageEventType,
        StorageSource,
        get_event_bus,
    )
    _event_bus_available = True
except ImportError:
    _event_bus_available = False
    EventBus = None
    StorageEvent = None
    StorageEventType = None
    StorageSource = None
    get_event_bus = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class UnifiedRecord(BaseModel):
    """
    统一记录模型
    
    所有存储后端通用的数据结构。
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    importance: float = 0.5
    timestamp: float = field(default_factory=time.time)
    
    # 向量存储字段
    memory_type: str = "semantic"
    access_count: int = 0
    last_access: float = field(default_factory=time.time)


class SearchResult(BaseModel):
    """搜索结果"""
    record: UnifiedRecord
    score: float
    source: str  # 来源后端


# ---------------------------------------------------------------------------
# 后端类型枚举
# ---------------------------------------------------------------------------

class VectorBackendType(Enum):
    """向量存储后端类型"""
    MEMORY = "memory"
    CHROMA = "chroma"
    FAISS = "faiss"
    REDIS = "redis"


class StructuredBackendType(Enum):
    """结构化存储后端类型"""
    SQLITE = "sqlite"
    SQLMODEL = "sqlmodel"


class CacheBackendType(Enum):
    """缓存后端类型"""
    MEMORY = "memory"
    REDIS = "redis"


# ---------------------------------------------------------------------------
# 统一存储接口
# ---------------------------------------------------------------------------

class UnifiedStorage:
    """
    统一存储接口
    
    整合向量存储、结构化存储、缓存和事件总线，
    提供一站式存储服务。
    
    Args:
        vector_backend: 向量存储后端
        structured_backend: 结构化存储后端
        cache_backend: 缓存后端
        event_bus: 事件总线
        enable_events: 是否启用事件
    
    Example:
        storage = UnifiedStorage.create(
            vector="memory",
            structured="sqlite",
            cache="memory",
        )
        
        # 存储数据（自动同步到向量存储和结构化存储）
        record = storage.put(
            content="Hello world",
            metadata={"source": "user"},
        )
        
        # 向量搜索
        results = storage.search(query_embedding, top_k=5)
        
        # 结构化查询
        records = storage.query(category="general", limit=10)
    """
    
    def __init__(
        self,
        vector_backend: Optional[Any] = None,
        structured_backend: Optional[Any] = None,
        cache_backend: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        enable_events: bool = True,
    ):
        self._vector = vector_backend
        self._structured = structured_backend
        self._cache = cache_backend
        self._event_bus = None
        self._enable_events = enable_events and _event_bus_available
        if self._enable_events and event_bus:
            self._event_bus = event_bus
        elif self._enable_events and get_event_bus:
            self._event_bus = get_event_bus()
        
        # 内存缓存（默认）
        if self._cache is None:
            self._memory_cache: dict[str, UnifiedRecord] = {}
        
        logger.info(
            "UnifiedStorage initialized (vector=%s, structured=%s, cache=%s)",
            type(vector_backend).__name__ if vector_backend else "None",
            type(structured_backend).__name__ if structured_backend else "None",
            type(cache_backend).__name__ if cache_backend else "memory",
        )
    
    # ------------------------------------------------------------------
    # 核心操作
    # ------------------------------------------------------------------
    
    def put(
        self,
        content: str,
        embedding: Optional[list[float]] = None,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        category: str = "general",
        importance: float = 0.5,
        id: Optional[str] = None,
        **kwargs,
    ) -> UnifiedRecord:
        """
        存储数据
        
        自动同步到向量存储、结构化存储和缓存。
        
        Args:
            content: 内容
            embedding: 可选的预计算向量
            metadata: 元数据
            tags: 标签
            category: 分类
            importance: 重要性
            id: 可选的 ID
            
        Returns:
            存储的记录
        """
        record = UnifiedRecord(
            id=id or str(uuid.uuid4()),
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            tags=tags or [],
            category=category,
            importance=importance,
            **kwargs,
        )
        
        # 存储到向量后端
        if self._vector is not None and embedding is not None:
            self._store_to_vector(record)
        
        # 存储到结构化后端
        if self._structured is not None:
            self._store_to_structured(record)
        
        # 存储到缓存
        self._store_to_cache(record)
        
        # 发送事件
        if self._enable_events and self._event_bus is not None and _event_bus_available:
            try:
                self._event_bus.emit(
                    StorageEventType.MEMORY_ADD,
                    source=StorageSource.LONG_TERM,
                    data=record.model_dump(),
                )
            except Exception:
                pass
        
        logger.debug("Stored record %s", record.id)
        return record
    
    def get(self, id: str) -> Optional[UnifiedRecord]:
        """
        获取记录
        
        优先从缓存获取，缓存未命中则从存储获取。
        """
        # 尝试从缓存获取
        cached = self._get_from_cache(id)
        if cached is not None:
            if self._enable_events and self._event_bus is not None and _event_bus_available:
                try:
                    self._event_bus.emit(
                        StorageEventType.CACHE_HIT,
                        source=StorageSource.CACHE,
                        data={"id": id},
                    )
                except Exception:
                    pass
            return cached
        
        if self._enable_events and self._event_bus is not None and _event_bus_available:
            try:
                self._event_bus.emit(
                    StorageEventType.CACHE_MISS,
                    source=StorageSource.CACHE,
                    data={"id": id},
                )
            except Exception:
                pass
        
        # 从向量存储获取
        if self._vector is not None:
            record = self._get_from_vector(id)
            if record is not None:
                self._store_to_cache(record)
                return record
        
        # 从结构化存储获取
        if self._structured is not None:
            record = self._get_from_structured(id)
            if record is not None:
                self._store_to_cache(record)
                return record
        
        return None
    
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        category: Optional[str] = None,
        min_importance: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        向量搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            category: 分类过滤
            min_importance: 最小重要性过滤
            
        Returns:
            搜索结果列表
        """
        if self._vector is None:
            return []
        
        # 构建过滤条件
        filter_dict = {}
        if category:
            filter_dict["category"] = category
        if min_importance:
            filter_dict["min_importance"] = min_importance
        
        results = self._search_vector(query_embedding, top_k, filter_dict)
        
        # 发送事件
        if self._enable_events and self._event_bus is not None and _event_bus_available:
            try:
                self._event_bus.emit(
                    StorageEventType.VECTOR_SEARCH,
                    source=StorageSource.VECTOR_STORE,
                    data={"top_k": top_k, "results_count": len(results)},
                )
            except Exception:
                pass
        
        return results
    
    def delete(self, id: str) -> bool:
        """删除记录"""
        deleted = False
        
        # 从向量存储删除
        if self._vector is not None:
            deleted = self._delete_from_vector(id) or deleted
        
        # 从结构化存储删除
        if self._structured is not None:
            deleted = self._delete_from_structured(id) or deleted
        
        # 从缓存删除
        self._delete_from_cache(id)
        
        # 发送事件
        if self._enable_events and self._event_bus is not None and _event_bus_available and deleted:
            try:
                self._event_bus.emit(
                    StorageEventType.MEMORY_DELETE,
                    source=StorageSource.LONG_TERM,
                    data={"id": id},
                )
            except Exception:
                pass
        
        return deleted
    
    def update(self, id: str, **kwargs) -> bool:
        """更新记录"""
        record = self.get(id)
        if record is None:
            return False
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        
        record.timestamp = time.time()
        
        # 同步到各存储
        if self._vector is not None and record.embedding is not None:
            self._update_vector(id, kwargs)
        
        if self._structured is not None:
            self._update_structured(id, kwargs)
        
        self._store_to_cache(record)
        
        # 发送事件
        if self._enable_events and self._event_bus is not None and _event_bus_available:
            try:
                self._event_bus.emit(
                    StorageEventType.MEMORY_UPDATE,
                    source=StorageSource.LONG_TERM,
                    data={"id": id, "changes": kwargs},
                )
            except Exception:
                pass
        
        return True
    
    # ------------------------------------------------------------------
    # 后端适配方法
    # ------------------------------------------------------------------
    
    def _store_to_vector(self, record: UnifiedRecord):
        """存储到向量后端"""
        try:
            # 适配不同后端接口
            if hasattr(self._vector, 'add'):
                record_dict = record.model_dump()
                if hasattr(self._vector, '_records'):
                    # MemoryVectorStore
                    from memory_system.storage.vector_store import MemoryRecord
                    mem_record = MemoryRecord(**record_dict)
                    self._vector.add(mem_record)
                else:
                    # RedisVectorStore 或其他
                    self._vector.add(record_dict)
        except (AttributeError, TypeError, ValueError, ImportError) as e:
            logger.warning("Failed to store to vector backend: %s", e)
    
    def _store_to_structured(self, record: UnifiedRecord):
        """存储到结构化后端"""
        try:
            if hasattr(self._structured, 'insert'):
                self._structured.insert("memories", record.model_dump())
            elif hasattr(self._structured, 'add'):
                from memory_system.storage.sqlmodel_orm_store import MemoryRecordORM
                orm_record = MemoryRecordORM(
                    id=record.id,
                    content=record.content,
                    memory_type=record.memory_type,
                    category=record.category,
                    importance=record.importance,
                )
                orm_record.tags = record.tags
                orm_record.metadata = record.metadata
                self._structured.add(orm_record)
        except (AttributeError, TypeError, ValueError, ImportError, sqlite3.OperationalError) as e:
            logger.warning("Failed to store to structured backend: %s", e)
    
    def _store_to_cache(self, record: UnifiedRecord):
        """存储到缓存"""
        if self._cache is not None:
            try:
                if hasattr(self._cache, 'set'):
                    self._cache.set(record.id, record.model_dump())
            except (AttributeError, TypeError, OSError) as e:
                logger.warning("Failed to store to cache: %s", e)
        else:
            self._memory_cache[record.id] = record
    
    def _get_from_cache(self, id: str) -> Optional[UnifiedRecord]:
        """从缓存获取"""
        if self._cache is not None:
            try:
                data = self._cache.get(id)
                if data:
                    return UnifiedRecord(**data)
            except (AttributeError, TypeError, KeyError, ValueError) as e:
                logger.warning("Failed to get from cache for id %s: %s", id, e)
        else:
            return self._memory_cache.get(id)
        return None
    
    def _get_from_vector(self, id: str) -> Optional[UnifiedRecord]:
        """从向量存储获取"""
        try:
            result = self._vector.get(id)
            if result:
                if hasattr(result, 'model_dump'):
                    return UnifiedRecord(**result.model_dump())
                return UnifiedRecord(**result)
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            logger.warning("Failed to get from vector store for id %s: %s", id, e)
        return None
    
    def _get_from_structured(self, id: str) -> Optional[UnifiedRecord]:
        """从结构化存储获取"""
        try:
            if hasattr(self._structured, 'select'):
                results = self._structured.select("memories", where="id = ?", params=(id,))
                if results.records:
                    return UnifiedRecord(**results.records[0])
            elif hasattr(self._structured, 'get'):
                from memory_system.storage.sqlmodel_orm_store import MemoryRecordORM
                result = self._structured.get(MemoryRecordORM, id)
                if result:
                    return UnifiedRecord(
                        id=result.id,
                        content=result.content,
                        memory_type=result.memory_type,
                        category=result.category,
                        importance=result.importance,
                        tags=result.tags,
                        metadata=result.metadata,
                    )
        except (AttributeError, TypeError, KeyError, ValueError, ImportError, sqlite3.OperationalError) as e:
            logger.warning("Failed to get from structured store for id %s: %s", id, e)
        return None
    
    def _search_vector(
        self,
        query_embedding: list[float],
        top_k: int,
        filter_dict: dict,
    ) -> list[SearchResult]:
        """向量搜索"""
        try:
            results = self._vector.search(query_embedding, top_k, filter_dict or None)
            search_results = []
            for item in results:
                if isinstance(item, tuple):
                    record_dict, score = item
                    record = UnifiedRecord(**record_dict) if isinstance(record_dict, dict) else UnifiedRecord(**record_dict.model_dump())
                else:
                    record = UnifiedRecord(**item.record.model_dump())
                    score = item.score
                search_results.append(SearchResult(
                    record=record,
                    score=score,
                    source=type(self._vector).__name__,
                ))
            return search_results
        except (AttributeError, TypeError, ValueError, KeyError) as e:
            logger.warning("Vector search failed: %s", e)
            return []
    
    def _delete_from_vector(self, id: str) -> bool:
        """从向量存储删除"""
        try:
            return self._vector.delete(id)
        except (AttributeError, TypeError, KeyError) as e:
            logger.warning("Failed to delete from vector store for id %s: %s", id, e)
            return False
    
    def _delete_from_structured(self, id: str) -> bool:
        """从结构化存储删除"""
        try:
            if hasattr(self._structured, 'delete'):
                return self._structured.delete("memories", where="id = ?", params=(id,))
            elif hasattr(self._structured, 'delete_by_id'):
                from memory_system.storage.sqlmodel_orm_store import MemoryRecordORM
                return self._structured.delete_by_id(MemoryRecordORM, id)
        except (AttributeError, TypeError, KeyError, ImportError) as e:
            logger.warning("Failed to delete from structured store for id %s: %s", id, e)
            return False
    
    def _delete_from_cache(self, id: str):
        """从缓存删除"""
        if self._cache is not None:
            try:
                self._cache.delete(id)
            except (AttributeError, TypeError, KeyError) as e:
                logger.warning("Failed to delete from cache for id %s: %s", id, e)
        else:
            self._memory_cache.pop(id, None)
    
    def _update_vector(self, id: str, kwargs: dict):
        """更新向量存储"""
        try:
            self._vector.update(id, **kwargs)
        except (AttributeError, TypeError, KeyError) as e:
            logger.warning("Failed to update vector backend: %s", e)
    
    def _update_structured(self, id: str, kwargs: dict):
        """更新结构化存储"""
        try:
            if hasattr(self._structured, 'update'):
                self._structured.update("memories", kwargs, where="id = ?", params=(id,))
        except (AttributeError, TypeError, KeyError, ValueError, sqlite3.OperationalError) as e:
            logger.warning("Failed to update structured backend: %s", e)
    
    # ------------------------------------------------------------------
    # 工厂方法
    # ------------------------------------------------------------------
    
    @classmethod
    def create(
        cls,
        vector: str = "memory",
        structured: str = "sqlite",
        cache: str = "memory",
        vector_config: Optional[dict] = None,
        structured_config: Optional[dict] = None,
        cache_config: Optional[dict] = None,
        enable_events: bool = True,
    ) -> "UnifiedStorage":
        """
        创建统一存储实例
        
        Args:
            vector: 向量存储后端 ("memory", "chroma", "faiss", "redis")
            structured: 结构化存储后端 ("sqlite", "sqlmodel")
            cache: 缓存后端 ("memory", "redis")
            vector_config: 向量存储配置
            structured_config: 结构化存储配置
            cache_config: 缓存配置
            enable_events: 是否启用事件
            
        Returns:
            UnifiedStorage 实例
        """
        vector_backend = None
        structured_backend = None
        cache_backend = None
        
        # 创建向量存储后端
        if vector == "memory":
            from memory_system.storage.vector_store import MemoryVectorStore
            vector_backend = MemoryVectorStore(**(vector_config or {}))
        elif vector == "chroma":
            try:
                from memory_system.storage.vector_store import ChromaDBBackend
                vector_backend = ChromaDBBackend(**(vector_config or {}))
            except ImportError:
                logger.warning("ChromaDB not available, falling back to memory")
                from memory_system.storage.vector_store import MemoryVectorStore
                vector_backend = MemoryVectorStore()
        elif vector == "redis":
            try:
                from memory_system.storage.redis_distributed_store import RedisVectorStore
                vector_backend = RedisVectorStore(**(vector_config or {}))
            except ImportError:
                logger.warning("Redis not available, falling back to memory")
                from memory_system.storage.vector_store import MemoryVectorStore
                vector_backend = MemoryVectorStore()
        
        # 创建结构化存储后端
        if structured == "sqlite":
            from memory_system.storage.structured_sqlite_store import StructuredStore
            db_path = (structured_config or {}).get("db_path", ":memory:")
            structured_backend = StructuredStore(db_path)
            # 创建表
            structured_backend.create_table(
                "memories",
                {
                    "content": "TEXT",
                    "memory_type": "TEXT",
                    "category": "TEXT",
                    "importance": "REAL",
                    "tags_json": "TEXT",
                    "metadata_json": "TEXT",
                    "timestamp": "REAL",
                }
            )
        elif structured == "sqlmodel":
            try:
                from memory_system.storage.sqlmodel_orm_store import ORMStore
                db_url = (structured_config or {}).get("db_url", "sqlite::memory:")
                structured_backend = ORMStore(db_url)
            except ImportError:
                logger.warning("SQLModel not available, falling back to SQLite")
                from memory_system.storage.structured_sqlite_store import StructuredStore
                structured_backend = StructuredStore(":memory:")
        
        # 创建缓存后端
        if cache == "redis":
            try:
                from memory_system.storage.redis_distributed_store import RedisCache
                cache_backend = RedisCache(**(cache_config or {}))
            except ImportError:
                logger.warning("Redis not available, using memory cache")
        
        return cls(
            vector_backend=vector_backend,
            structured_backend=structured_backend,
            cache_backend=cache_backend,
            enable_events=enable_events,
        )
    
    # ------------------------------------------------------------------
    # 统计和监控
    # ------------------------------------------------------------------
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {
            "vector_backend": type(self._vector).__name__ if self._vector else None,
            "structured_backend": type(self._structured).__name__ if self._structured else None,
            "cache_backend": type(self._cache).__name__ if self._cache else "memory",
            "events_enabled": self._enable_events,
        }
        
        if self._vector is not None:
            try:
                stats["vector_count"] = self._vector.count() if hasattr(self._vector, 'count') else 0
            except (AttributeError, TypeError) as e:
                logger.warning("Failed to get vector count: %s", e)
                stats["vector_count"] = 0
        
        if self._cache is None:
            stats["cache_count"] = len(self._memory_cache)
        
        if self._enable_events:
            stats["event_stats"] = self._event_bus.get_stats()
        
        return stats


__all__ = [
    "UnifiedStorage",
    "UnifiedRecord",
    "SearchResult",
    "VectorBackendType",
    "StructuredBackendType",
    "CacheBackendType",
]
