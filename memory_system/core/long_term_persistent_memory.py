"""
长期记忆模块 - 薄编排层

长期记忆模拟人类的长期记忆，特点：
- 容量理论上无限
- 基于语义相似度检索
- 持久化存储
- 支持多种记忆类型（情景记忆、语义记忆、程序记忆）

本模块为薄编排层，实际功能委托给 embedding 和 vector_store 子模块实现。
"""

import hashlib
import time
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from memory_system.processing.text_embedding_provider import EmbeddingProvider, EmbeddingFactory, EmbeddingConfig
from memory_system.storage.vector_store import VectorStoreBackend, VectorStoreFactory, MemoryRecord, SearchResult


class LongTermMemoryConfig(BaseModel):
    """长期记忆系统配置"""

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: dict = Field(default_factory=lambda: {"backend": "memory"})
    auto_consolidate: bool = False


class LongTermMemory:
    """
    长期记忆系统

    管理Agent的持久化知识。本类为薄编排层，将嵌入生成委托给
    EmbeddingProvider，将向量存储与检索委托给 VectorStoreBackend。
    """

    def __init__(self, config: LongTermMemoryConfig = None, **kwargs):
        """
        Args:
            config: 长期记忆配置，为 None 时使用默认配置
            **kwargs: 额外配置项，会合并到 config 中
        """
        if config is None:
            config = LongTermMemoryConfig()

        # 如果传入了 kwargs，尝试将已知字段合并到配置中
        if kwargs:
            if "embedding" in kwargs and isinstance(kwargs["embedding"], dict):
                config.embedding = EmbeddingConfig(**kwargs["embedding"])
            if "vector_store" in kwargs and isinstance(kwargs["vector_store"], dict):
                config.vector_store = kwargs["vector_store"]
            if "auto_consolidate" in kwargs:
                config.auto_consolidate = kwargs["auto_consolidate"]

        self.config = config
        # 从 EmbeddingConfig 提取 provider 和参数
        emb_cfg = config.embedding
        if isinstance(emb_cfg, dict):
            provider = emb_cfg.get("provider", "auto")
            emb_kwargs = {k: v for k, v in emb_cfg.items() if k != "provider"}
            # 兼容: dimension -> fake_dimension
            if "dimension" in emb_kwargs and "fake_dimension" not in emb_kwargs:
                emb_kwargs["fake_dimension"] = emb_kwargs.pop("dimension")
        else:
            provider = emb_cfg.provider
            emb_kwargs = emb_cfg.model_dump(exclude={"provider"})
        self.embedder: EmbeddingProvider = EmbeddingFactory.create(provider=provider, **emb_kwargs)
        
        # 从 vector_store config 提取 backend 和参数
        vs_cfg = config.vector_store
        if isinstance(vs_cfg, dict):
            backend = vs_cfg.get("backend", "memory")
            vs_kwargs = {k: v for k, v in vs_cfg.items() if k != "backend"}
        else:
            backend = "memory"
            vs_kwargs = {}
        self.store: VectorStoreBackend = VectorStoreFactory.create(backend=backend, **vs_kwargs)
        # 内容哈希索引：content_hash -> record_id，O(1) 去重查找
        self._content_hash_index: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def remember(
        self,
        content: str,
        memory_type: str = "semantic",
        category: str = "general",
        importance: float = 0.5,
        tags: list[str] = None,
        source: str = "unknown",
        metadata: dict = None,
        embedding: list[float] = None,
    ) -> str:
        """
        记住信息

        Args:
            content: 记忆内容
            memory_type: 记忆类型 (episodic/semantic/procedural)
            category: 类别
            importance: 重要性 (0-1)
            tags: 标签列表
            source: 来源
            metadata: 额外元数据
            embedding: 预计算的嵌入向量，为 None 时自动编码

        Returns:
            记忆ID
        """
        if embedding is None:
            embedding = self.embedder.encode(content)

        # 内容去重检查：O(1) 哈希索引查找
        target_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing_id = self._content_hash_index.get(target_hash)
        if existing_id is not None:
            # 验证记录确实存在（可能已被外部删除）
            existing_record = self.store.get(existing_id)
            if existing_record is not None:
                return existing_id
            else:
                # 索引不一致，清理
                del self._content_hash_index[target_hash]

        import uuid
        record_id = uuid.uuid4().hex[:16]

        record = MemoryRecord(
            id=record_id,
            content=content,
            embedding=embedding,
            memory_type=memory_type,
            category=category,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
            source=source,
        )
        stored_id = self.store.add(record)
        # 维护哈希索引
        self._content_hash_index[target_hash] = stored_id
        return stored_id

    def _find_by_content(self, content: str):
        """通过内容哈希查找已有记忆，用于去重。O(1) 复杂度。"""
        target_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing_id = self._content_hash_index.get(target_hash)
        if existing_id is None:
            return None
        record = self.store.get(existing_id)
        if record is None:
            del self._content_hash_index[target_hash]
            return None
        return record

    def recall(
        self,
        query: str,
        top_k: int = 5,
        category: str = None,
        tags: list[str] = None,
        memory_type: str = None,
        threshold: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        """
        回忆信息（语义检索）

        Args:
            query: 查询内容
            top_k: 返回数量
            category: 按类别过滤
            tags: 按标签过滤
            memory_type: 按记忆类型过滤
            threshold: 相似度阈值

        Returns:
            [(MemoryRecord, 相关度分数), ...]
        """
        query_embedding = self.embedder.encode(query)
        # 构建过滤条件
        filter_dict = {}
        if category:
            filter_dict["category"] = category
        if memory_type:
            filter_dict["memory_type"] = memory_type
        if tags:
            filter_dict["tags"] = tags
        
        results: list[SearchResult] = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter=filter_dict if filter_dict else None,
        )
        # Apply threshold filtering
        if threshold > 0:
            results = [r for r in results if r.score >= threshold]
        return [(r.record, r.score) for r in results]

    def recall_by_vector(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[MemoryRecord, float]]:
        """
        通过向量回忆信息

        Args:
            embedding: 查询向量
            top_k: 返回数量

        Returns:
            [(MemoryRecord, 相关度分数), ...]
        """
        results: list[SearchResult] = self.store.search(
            query_embedding=embedding,
            top_k=top_k,
        )
        return [(r.record, r.score) for r in results]

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        """获取指定记忆"""
        return self.store.get(memory_id)

    def update(self, memory_id: str, **kwargs) -> bool:
        """更新记忆"""
        return self.store.update(memory_id, **kwargs)

    def delete(self, memory_id: str) -> bool:
        """删除指定记忆"""
        # 清理内容哈希索引
        record = self.store.get(memory_id)
        if record is not None:
            content_hash = record.content_hash
            if self._content_hash_index.get(content_hash) == memory_id:
                del self._content_hash_index[content_hash]
        return self.store.delete(memory_id)

    def forget(self, memory_id: str) -> bool:
        """遗忘指定记忆（delete 的别名）"""
        return self.delete(memory_id)

    # ------------------------------------------------------------------
    # 查询方法
    # ------------------------------------------------------------------

    def get_by_category(self, category: str) -> list[MemoryRecord]:
        """按类别获取记忆"""
        results = self.store.search(
            query_embedding=self.embedder.encode(""),
            top_k=self.store.count(),
            filter={"category": category},
        )
        return [r.record for r in results]

    def get_by_tag(self, tag: str) -> list[MemoryRecord]:
        """按标签获取记忆"""
        results = self.store.search(
            query_embedding=self.embedder.encode(""),
            top_k=self.store.count(),
            filter={"tags": [tag]},
        )
        return [r.record for r in results]

    def get_all(self, limit: int = 100) -> list[MemoryRecord]:
        """获取所有记忆（可限制数量）"""
        return self.store.list_all(limit=limit)

    def count(self) -> int:
        """获取记忆总数"""
        return self.store.count()

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {
            "total_memories": self.store.count(),
        }
        # 尝试获取更详细的统计（如果后端支持）
        if hasattr(self.store, 'get_stats'):
            stats.update(self.store.get_stats())
        return stats

    def search(
        self,
        query: str,
        top_k: int = 5,
        **filters,
    ) -> list[tuple[MemoryRecord, float]]:
        """语义搜索（recall 的别名）"""
        return self.recall(query, top_k=top_k, **filters)


# ------------------------------------------------------------------
# 向后兼容：旧代码中 LongTermMemoryItem 现在由 MemoryRecord 替代
# ------------------------------------------------------------------
LongTermMemoryItem = MemoryRecord

__all__ = [
    "LongTermMemory",
    "LongTermMemoryConfig",
    "LongTermMemoryItem",
    "MemoryRecord",
    "EmbeddingProvider",
    "EmbeddingFactory",
    "EmbeddingConfig",
    "VectorStoreBackend",
    "VectorStoreFactory",
    "SearchResult",
]
