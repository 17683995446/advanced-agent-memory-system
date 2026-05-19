"""
记忆管理器 - 统一入口

整合短期记忆、长期记忆、嵌入、向量存储、知识图谱、结构化存储等所有模块。
提供简洁的API供Agent使用。
"""

import time
import logging
from typing import List, Dict, Any, Optional, Union

from pydantic import BaseModel, Field

from memory_system.core.short_term_working_memory import ShortTermMemory, MemoryItem, WorkingMemoryBuffer
from memory_system.core.long_term_persistent_memory import LongTermMemory, LongTermMemoryConfig, LongTermMemoryItem
from memory_system.processing.text_embedding_provider import EmbeddingProvider, EmbeddingFactory, EmbeddingConfig
from memory_system.storage.vector_store import VectorStoreBackend, VectorStoreFactory, MemoryRecord, SearchResult
from memory_system.processing.knowledge_graph_engine import KnowledgeGraph, KnowledgeGraphBuilder, Entity, Relation
from memory_system.storage.structured_sqlite_store import StructuredStore, MemoryTable
from memory_system.processing.chinese_english_tokenizer import tokenize_for_search

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Master Configuration
# ---------------------------------------------------------------------------

class AgentMemoryConfig(BaseModel):
    """Agent记忆系统主配置，组合所有子模块配置。

    Attributes:
        short_term: 短期记忆配置字典，传递给 ShortTermMemory 构造器。
        long_term: 长期记忆配置，使用 LongTermMemoryConfig 模型。
        knowledge_graph: 知识图谱配置字典。
        structured_store: 结构化存储配置字典。
        consolidation_threshold: 记忆巩固的重要性阈值。
        auto_consolidate: 是否启用自动巩固。
        default_top_k: 默认检索返回数量。
    """

    short_term: dict = Field(
        default_factory=lambda: {"working_memory_capacity": 7, "history_limit": 50}
    )
    long_term: LongTermMemoryConfig = Field(default_factory=LongTermMemoryConfig)
    knowledge_graph: dict = Field(default_factory=lambda: {"enabled": True})
    structured_store: dict = Field(
        default_factory=lambda: {"db_path": ":memory:", "enabled": True}
    )
    consolidation_threshold: float = 0.6
    auto_consolidate: bool = True
    default_top_k: int = 5


# ---------------------------------------------------------------------------
# Inline Memory Consolidator (轻量级，不依赖旧模块)
# ---------------------------------------------------------------------------

class _MemoryConsolidator:
    """内联记忆巩固器。

    将短期记忆中重要性超过阈值的内容迁移到长期记忆，
    并清理已巩固的低优先级短期记忆。
    """

    def __init__(
        self,
        short_term: ShortTermMemory,
        long_term: LongTermMemory,
        threshold: float = 0.6,
    ) -> None:
        self.short_term = short_term
        self.long_term = long_term
        self.threshold = threshold
        self._last_consolidation: float = 0.0

    def consolidate(self) -> Dict[str, Any]:
        """执行一次巩固：将工作记忆中高重要性内容写入长期记忆。"""
        consolidated_count = 0
        skipped_count = 0

        items = self.short_term.working_memory.get_all()
        for key, item in items:
            if item.importance >= self.threshold:
                self.long_term.remember(
                    content=item.content,
                    memory_type=item.memory_type,
                    importance=item.importance,
                    metadata={
                        "consolidated_from": "working_memory",
                        "original_key": key,
                        "access_count": item.access_count,
                    },
                )
                consolidated_count += 1
            else:
                skipped_count += 1

        self._last_consolidation = time.time()
        return {
            "consolidated": consolidated_count,
            "skipped": skipped_count,
            "threshold": self.threshold,
            "timestamp": self._last_consolidation,
        }

    def cleanup_short_term(self) -> int:
        """清理已巩固的工作记忆条目。"""
        removed = 0
        items = self.short_term.working_memory.get_all()
        for key, item in items:
            if item.importance >= self.threshold:
                self.short_term.working_memory.remove(key)
                removed += 1
        return removed


# ---------------------------------------------------------------------------
# AgentMemory - 主编排器
# ---------------------------------------------------------------------------

class AgentMemory:
    """Agent记忆系统主类。

    提供统一的记忆管理接口，编排短期记忆、长期记忆、知识图谱和结构化存储。
    """

    def __init__(self, config: AgentMemoryConfig = None, **kwargs):
        """
        初始化Agent记忆系统。

        Args:
            config: 主配置对象，为 None 时使用默认配置。
            **kwargs: 额外配置项，会合并到 config 的对应子配置中。
        """
        if config is None:
            config = AgentMemoryConfig()

        # 合并 kwargs 到配置
        if kwargs:
            if "short_term" in kwargs and isinstance(kwargs["short_term"], dict):
                merged_st = {**config.short_term, **kwargs["short_term"]}
                config.short_term = merged_st
            if "long_term" in kwargs:
                lt = kwargs["long_term"]
                if isinstance(lt, dict):
                    config.long_term = LongTermMemoryConfig(**{**config.long_term.model_dump(), **lt})
                elif isinstance(lt, LongTermMemoryConfig):
                    config.long_term = lt
            if "knowledge_graph" in kwargs and isinstance(kwargs["knowledge_graph"], dict):
                merged_kg = {**config.knowledge_graph, **kwargs["knowledge_graph"]}
                config.knowledge_graph = merged_kg
            if "structured_store" in kwargs and isinstance(kwargs["structured_store"], dict):
                merged_ss = {**config.structured_store, **kwargs["structured_store"]}
                config.structured_store = merged_ss
            if "consolidation_threshold" in kwargs:
                config.consolidation_threshold = kwargs["consolidation_threshold"]
            if "auto_consolidate" in kwargs:
                config.auto_consolidate = kwargs["auto_consolidate"]
            if "default_top_k" in kwargs:
                config.default_top_k = kwargs["default_top_k"]

        self.config = config
        self._closed = False

        # 性能指标收集
        self._metrics = {
            "remember_count": 0,
            "recall_count": 0,
            "update_count": 0,
            "delete_count": 0,
            "remember_total_time": 0.0,
            "recall_total_time": 0.0,
            "update_total_time": 0.0,
            "delete_total_time": 0.0,
            "batch_remember_count": 0,
            "batch_delete_count": 0,
            "batch_update_count": 0,
            "consolidate_count": 0,
            "compress_count": 0,
            "conflict_check_count": 0,
        }

        # 初始化短期记忆
        self.short_term: ShortTermMemory = ShortTermMemory(**config.short_term)

        # 初始化长期记忆
        self.long_term: LongTermMemory = LongTermMemory(config=config.long_term)

        # 初始化知识图谱（可选）
        if config.knowledge_graph.get("enabled", True):
            self.knowledge_graph: Optional[KnowledgeGraph] = KnowledgeGraph()
        else:
            self.knowledge_graph = None

        # 初始化结构化存储 + MemoryTable（可选）
        if config.structured_store.get("enabled", True):
            db_path = config.structured_store.get("db_path", ":memory:")
            self.structured_store: Optional[StructuredStore] = StructuredStore(db_path=db_path)
            self.memory_table: Optional[MemoryTable] = MemoryTable(self.structured_store)
            self.memory_table.init_tables()
        else:
            self.structured_store = None
            self.memory_table = None

        # 初始化内联巩固器
        self._consolidator = _MemoryConsolidator(
            short_term=self.short_term,
            long_term=self.long_term,
            threshold=config.consolidation_threshold,
        )

        # 初始化记忆衰减引擎（v5.1+ 创新功能）
        from memory_system.core.memory_decay_engine import (
            MemoryDecayEngine, DecayConfig, DecayCurve,
        )
        self._decay_engine = MemoryDecayEngine(
            config=DecayConfig(
                enabled=True,
                curve=DecayCurve.EXPONENTIAL,
                half_life=604800.0,  # 7天半衰期
                refresh_interval=600.0,  # 10分钟刷新
            )
        )

        # 初始化混合搜索引擎（v5.2+ 创新功能）
        from memory_system.core.hybrid_search_engine import (
            HybridSearchEngine, VectorSearchStrategy,
            KeywordSearchStrategy, KnowledgeGraphSearchStrategy,
        )
        self._hybrid_engine = HybridSearchEngine(
            fusion_method="rrf",  # Reciprocal Rank Fusion
        )
        # 注册向量搜索策略
        self._hybrid_engine.add_strategy(
            VectorSearchStrategy(
                vector_store=self.long_term.store,
                embedding_provider=self.long_term.embedder,
            ),
            weight=1.0,
        )
        # 注册关键词搜索策略
        self._keyword_strategy = KeywordSearchStrategy()
        self._hybrid_engine.add_strategy(
            self._keyword_strategy,
            weight=0.8,
        )
        # 注册知识图谱搜索策略（如果启用）
        if self.knowledge_graph is not None:
            self._hybrid_engine.add_strategy(
                KnowledgeGraphSearchStrategy(
                    knowledge_graph=self.knowledge_graph,
                ),
                weight=0.6,
            )
        self._hybrid_enabled = True

        # 初始化记忆压缩引擎（v6.0+ 创新功能）
        from memory_system.core.memory_compression_engine import (
            MemoryCompressionEngine, CompressionConfig,
        )
        self._compression_engine = MemoryCompressionEngine(
            config=CompressionConfig(
                min_memories_to_compress=100,
                similarity_threshold=0.85,
                max_summary_length=200,
                min_content_length_to_summarize=500,
                max_age_days=90,
                low_importance_decay_days=30,
                auto_compress=False,
            )
        )

        # 初始化记忆冲突解决器（v6.0+ 创新功能）
        from memory_system.core.memory_conflict_resolver import (
            MemoryConflictResolver, ConflictConfig,
        )
        self._conflict_resolver = MemoryConflictResolver(
            config=ConflictConfig(
                similarity_threshold=0.7,
                contradiction_threshold=0.8,
                auto_resolve=False,
            )
        )

        # 初始化记忆版本控制（v6.0+ 创新功能）
        from memory_system.core.memory_version_control import (
            MemoryVersionControl, VersionControlConfig,
        )
        self._version_control = MemoryVersionControl(
            config=VersionControlConfig(
                max_versions_per_memory=10,
                keep_forever_versions=3,
                auto_cleanup=True,
                audit_all_changes=True,
            )
        )

        # 会话信息
        self.session_id: str = f"session_{int(time.time())}"
        self.interaction_count: int = 0

    # ==================== 记忆存储接口 ====================

    def add_to_working_memory(
        self,
        key: str,
        content: str,
        importance: float = 0.5,
        memory_type: str = "general",
        **metadata,
    ) -> bool:
        """
        添加信息到工作记忆。

        Args:
            key: 记忆键
            content: 记忆内容
            importance: 重要性 (0-1)
            memory_type: 记忆类型
            **metadata: 额外元数据

        Returns:
            是否添加成功
        """
        return self.short_term.add_to_working_memory(
            key=key,
            content=content,
            importance=importance,
            memory_type=memory_type,
            **metadata,
        )

    def remember(
        self,
        content: str,
        memory_type: str = "semantic",
        category: str = "general",
        importance: float = 0.5,
        **kwargs,
    ) -> str:
        """
        记住信息（长期记忆）。

        Args:
            content: 记忆内容
            memory_type: 记忆类型 (episodic/semantic/procedural/fact/conversation)
            category: 类别
            importance: 重要性
            **kwargs: 额外参数（tags, source, metadata 等）

        Returns:
            记忆ID
        """
        self._check_closed()
        t0 = time.monotonic()

        if not content:
            raise ValueError("content must not be empty")

        # 验证 importance 范围
        if not (0.0 <= importance <= 1.0):
            raise ValueError(f"importance must be between 0.0 and 1.0, got {importance}")

        # 检测循环引用（metadata 中可能存在）
        metadata = kwargs.get("metadata")
        if metadata is not None:
            try:
                import json
                json.dumps(metadata)  # 尝试序列化
            except (TypeError, ValueError, RecursionError) as e:
                raise ValueError(f"metadata contains non-serializable data (possible circular reference): {e}")

        # 存入长期记忆
        memory_id = self.long_term.remember(
            content=content,
            memory_type=memory_type,
            category=category,
            importance=importance,
            **kwargs,
        )

        # 同步更新关键词搜索索引（混合搜索引擎）
        if self._hybrid_enabled:
            try:
                self._keyword_strategy.add_document(
                    doc_id=memory_id,
                    content=content,
                )
            except Exception:
                pass  # 索引更新失败不影响主流程

        # 如果是事实类型，自动构建知识图谱
        if memory_type == "fact" and self.knowledge_graph is not None:
            try:
                self.build_knowledge_from_text(content)
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to build knowledge graph from fact: %s", e)

        # 如果是对话类型，自动存入对话历史
        if memory_type == "conversation":
            speaker = kwargs.get("role", kwargs.get("speaker", "unknown"))
            try:
                self.remember_conversation(
                    content=content,
                    speaker=speaker,
                    important=importance >= 0.6,
                )
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to add conversation to history: %s", e)

        # 注册到衰减引擎
        self._decay_engine.register(memory_id, base_importance=importance)

        # 记录到版本控制系统
        try:
            from memory_system.core.memory_version_control import ChangeType
            self._version_control.record_change(
                memory_id=memory_id,
                change_type=ChangeType.CREATE,
                content_before=None,
                content_after=content,
                changed_by="system",
                change_reason="remember",
            )
        except Exception as e:
            logger.debug("Version control record failed: %s", e)

        self._metrics["remember_count"] += 1
        self._metrics["remember_total_time"] += time.monotonic() - t0
        return memory_id

    def remember_fact(
        self,
        fact: str,
        category: str = "knowledge",
        source: str = "user",
        confidence: float = 1.0,
        **kwargs,
    ) -> str:
        """
        记住事实。

        同时存入长期记忆向量存储和结构化存储（如果可用）。

        Args:
            fact: 事实内容
            category: 类别
            source: 来源
            confidence: 置信度
            **kwargs: 额外参数

        Returns:
            记忆ID
        """
        if not fact:
            raise ValueError("fact must not be empty")
        # 存入长期记忆
        memory_id = self.long_term.remember(
            content=fact,
            memory_type="semantic",
            category=category,
            importance=confidence,
            source=source,
            **kwargs,
        )

        # 同时存入结构化存储
        if self.memory_table is not None:
            try:
                self.memory_table.store_fact(
                    fact=fact,
                    source=source,
                    confidence=confidence,
                    category=category,
                )
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to store fact in structured store: %s", e)

        return memory_id

    def remember_conversation(
        self,
        content: str,
        speaker: str = "user",
        important: bool = False,
        **kwargs,
    ) -> Optional[str]:
        """
        记住对话内容。

        添加到交互历史；如果标记为重要，同时编码到长期记忆。

        Args:
            content: 对话内容
            speaker: 说话者
            important: 是否重要
            **kwargs: 额外参数

        Returns:
            长期记忆ID（重要内容时），否则 None
        """
        if not content:
            raise ValueError("content must not be empty")
        self.interaction_count += 1

        # 添加到交互历史
        self.short_term.add_interaction(
            role=speaker,
            content=content,
            important=important,
            **kwargs,
        )

        # 记录到结构化存储
        if self.memory_table is not None:
            try:
                self.memory_table.log_interaction(
                    agent_id=self.session_id,
                    role=speaker,
                    content=content,
                    metadata=kwargs,
                )
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to log interaction in structured store: %s", e)

        # 如果是重要内容，同时存入长期记忆
        memory_id = None
        if important:
            memory_id = self.long_term.remember(
                content=content,
                memory_type="episodic",
                category="conversations",
                importance=0.7,
                source=speaker,
                metadata={
                    "conversation_id": self.session_id,
                    "turn_number": self.interaction_count,
                },
            )

        return memory_id

    # ==================== 知识图谱接口 ====================

    def add_entity(
        self,
        name: str,
        entity_type: str = "concept",
        description: str = "",
        **properties,
    ) -> str:
        """
        添加实体到知识图谱。

        Args:
            name: 实体名称（唯一标识）
            entity_type: 实体类型
            description: 描述
            **properties: 额外属性

        Returns:
            实体名称
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")

        entity = Entity(
            name=name,
            entity_type=entity_type,
            description=description,
            properties=properties,
        )
        return self.knowledge_graph.add_entity(entity)

    def add_relation(
        self,
        source: str,
        target: str,
        relation_type: str,
        weight: float = 1.0,
        **metadata,
    ) -> str:
        """
        添加关系到知识图谱。

        Args:
            source: 源实体名称
            target: 目标实体名称
            relation_type: 关系类型
            weight: 关系权重
            **metadata: 额外元数据

        Returns:
            关系标识字符串
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")

        relation = Relation(
            source=source,
            target=target,
            relation_type=relation_type,
            weight=weight,
            metadata=metadata,
        )
        return self.knowledge_graph.add_relation(relation)

    def search_entities(self, query: str, top_k: int = 5) -> list:
        """
        搜索知识图谱中的实体。

        Args:
            query: 搜索查询
            top_k: 返回数量

        Returns:
            [(Entity, score), ...] 列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")

        return self.knowledge_graph.search_entities(query, top_k=top_k)

    def find_related(self, entity_name: str, top_k: int = 5) -> list:
        """
        查找与指定实体相关的实体。

        Args:
            entity_name: 实体名称
            top_k: 返回数量

        Returns:
            [GraphSearchResult, ...] 列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")

        return self.knowledge_graph.find_related(entity_name, top_k=top_k)

    def get_entity(self, name: str) -> Optional[Entity]:
        """
        获取指定实体。

        Args:
            name: 实体名称

        Returns:
            Entity 对象，未找到时返回 None
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")

        return self.knowledge_graph.get_entity(name)

    def build_knowledge_from_text(self, text: str) -> KnowledgeGraph:
        """
        从文本中提取实体和关系并构建知识图谱。

        Args:
            text: 输入文本

        Returns:
            更新后的 KnowledgeGraph 实例
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")

        return KnowledgeGraphBuilder.build_from_text(text, kg=self.knowledge_graph)

    def get_knowledge_graph_stats(self) -> dict:
        """
        获取知识图谱统计信息。

        Returns:
            统计字典，包含 entity_count, relation_count 等
        """
        if self.knowledge_graph is None:
            return {"enabled": False}

        return self.knowledge_graph.get_statistics()

    def get_all_entities(self) -> list:
        """获取知识图谱中所有实体。

        Returns:
            Entity 对象列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        return [
            self.knowledge_graph.get_entity(name)
            for name in self.knowledge_graph.graph.nodes
        ]

    def get_entity_relationships(
        self, entity_name: str = None, direction: str = "both"
    ) -> list:
        """获取实体的关系列表。

        Args:
            entity_name: 实体名称，为 None 时返回所有关系
            direction: 方向 ("outgoing", "incoming", "both")

        Returns:
            Relation 对象列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        if entity_name is not None:
            return self.knowledge_graph.get_relations(entity_name, direction=direction)
        # 返回所有关系
        all_relations = []
        for name in self.knowledge_graph.graph.nodes:
            all_relations.extend(
                self.knowledge_graph.get_relations(name, direction="outgoing")
            )
        return all_relations

    def delete_entity(self, name: str) -> bool:
        """删除实体及其所有关系。

        Args:
            name: 实体名称

        Returns:
            是否成功删除
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        return self.knowledge_graph.remove_entity(name)

    # ==================== 结构化存储接口 ====================

    def store_preference(
        self,
        key: str,
        value,
        category: str = "general",
    ) -> str:
        """
        存储偏好设置。

        Args:
            key: 偏好键
            value: 偏好值
            category: 类别

        Returns:
            记录ID
        """
        if self.memory_table is None:
            raise RuntimeError("Structured store is not enabled.")

        # 将 value 序列化为字符串
        import json
        value_str = json.dumps(value) if not isinstance(value, str) else value
        return self.memory_table.store_preference(key=key, value=value_str, category=category)

    def set_preference(
        self,
        key: str,
        value,
        category: str = "general",
    ) -> str:
        """
        设置偏好设置（store_preference 的别名）。

        提供更直观的 API 命名，与 get_preference 对应。

        Args:
            key: 偏好键
            value: 偏好值
            category: 类别

        Returns:
            记录ID
        """
        return self.store_preference(key=key, value=value, category=category)

    def get_preference(self, key: str, raw: bool = False):
        """
        获取偏好设置。

        Args:
            key: 偏好键
            raw: 如果为True，返回完整记录字典；否则仅返回值

        Returns:
            偏好值（raw=False时）或完整记录字典（raw=True时），未找到时返回 None
        """
        if self.memory_table is None:
            raise RuntimeError("Structured store is not enabled.")

        record = self.memory_table.get_preference(key)
        if record is None:
            return None
        if raw:
            return record
        return record.get("value")

    def log_interaction(
        self,
        role: str,
        content: str,
        **metadata,
    ) -> str:
        """
        记录交互到结构化存储。

        Args:
            role: 角色（user/assistant/system）
            content: 内容
            **metadata: 额外元数据

        Returns:
            记录ID
        """
        if self.memory_table is None:
            raise RuntimeError("Structured store is not enabled.")

        return self.memory_table.log_interaction(
            agent_id=self.session_id,
            role=role,
            content=content,
            metadata=metadata,
        )

    def get_interaction_history(self, limit: int = 50) -> list:
        """
        获取结构化存储中的交互历史。

        Args:
            limit: 最大返回数量

        Returns:
            交互记录字典列表
        """
        if self.memory_table is None:
            raise RuntimeError("Structured store is not enabled.")

        return self.memory_table.get_interactions(
            agent_id=self.session_id,
            limit=limit,
        )

    # ==================== 记忆检索接口 ====================

    def recall(
        self,
        query: str,
        top_k: int = None,
        from_short_term: bool = True,
        from_long_term: bool = True,
        exclude_sources: list = None,
        use_hybrid: bool = None,
        **filters,
    ) -> list:
        """
        回忆信息。

        Args:
            query: 查询内容
            top_k: 返回数量
            from_short_term: 是否检索短期记忆
            from_long_term: 是否检索长期记忆
            exclude_sources: 排除的来源列表（如 ["structured"] 排除结构化存储数据）
            use_hybrid: 是否使用混合搜索引擎（RRF融合），None表示自动判断
            **filters: 过滤条件（category, tags, memory_type, threshold, time_range, min_importance）

        Returns:
            检索结果列表
        """
        if top_k is None:
            top_k = self.config.default_top_k

        # 验证 top_k 范围
        if not isinstance(top_k, int) or top_k < 0:
            raise ValueError(f"top_k must be a non-negative integer, got {top_k}")
        
        # top_k 为 0 时直接返回空结果
        if top_k == 0:
            return []

        self._check_closed()
        if exclude_sources is None:
            exclude_sources = []

        t0 = time.monotonic()

        # 空查询保护：空字符串或纯空白查询返回空结果
        if not query or not query.strip():
            return []

        # v5.2+: 混合搜索引擎路径
        # 自动判断：如果混合引擎启用且请求长期记忆，使用混合搜索
        hybrid_active = (
            use_hybrid is True
            or (use_hybrid is None and self._hybrid_enabled and from_long_term)
        )

        if hybrid_active:
            try:
                results = self._recall_hybrid(
                    query=query,
                    top_k=top_k,
                    from_short_term=from_short_term,
                    exclude_sources=exclude_sources,
                    **filters,
                )
                self._metrics["recall_count"] += 1
                self._metrics["recall_total_time"] += time.monotonic() - t0
                return results
            except Exception as e:
                logger.warning("Hybrid search failed, falling back to legacy: %s", e)
                # 降级到传统搜索

        results = []

        # 从长期记忆检索
        if from_long_term:
            lt_results = self.long_term.recall(
                query=query,
                top_k=top_k,
                category=filters.get("category"),
                tags=filters.get("tags"),
                memory_type=filters.get("memory_type"),
                threshold=filters.get("threshold", 0.0),
            )
            for record, score in lt_results:
                # 如果指定了排除来源，跳过匹配的记录
                # source 为 "unknown" 时视为长期记忆来源
                source = record.source if record.source != "unknown" else "long_term"
                if source in exclude_sources:
                    continue
                # 排除明显的结构化键值对格式（如 "key: value"）
                content = record.content
                if "structured" in exclude_sources and ": " in content and len(content.split(": ")) == 2:
                    key_part = content.split(": ")[0]
                    # 如果冒号前是单个单词（无空格），可能是结构化键值对
                    if " " not in key_part and len(key_part) < 30:
                        continue

                results.append({
                    "content": content,
                    "score": score,
                    "source": source,
                    "memory_type": record.memory_type,
                    "category": record.category,
                    "importance": record.importance,
                    "timestamp": record.timestamp,
                    "metadata": record.metadata,
                    "id": record.id,
                })

        # 按分数排序
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        # 应用 time_range 过滤
        time_range = filters.get("time_range")
        if time_range and isinstance(time_range, (tuple, list)) and len(time_range) == 2:
            t_start, t_end = time_range
            results = [
                r for r in results
                if t_start <= r.get("timestamp", 0) <= t_end
            ]

        # 应用 min_importance 过滤
        min_importance = filters.get("min_importance")
        if min_importance is not None:
            results = [
                r for r in results
                if r.get("importance", 0) >= min_importance
            ]

        # 应用过滤条件（memory_type, category, tags）— 仅对长期记忆结果
        filter_memory_type = filters.get("memory_type")
        filter_category = filters.get("category")
        filter_tags = filters.get("tags")
        if filter_memory_type or filter_category or filter_tags:
            filtered = []
            for r in results:
                if filter_memory_type and r.get("memory_type") != filter_memory_type:
                    continue
                if filter_category and r.get("category") != filter_category:
                    continue
                if filter_tags:
                    r_tags = set(r.get("metadata", {}).get("tags", []))
                    if not r_tags.intersection(set(filter_tags)):
                        continue
                filtered.append(r)
            results = filtered

        # 从短期记忆检索（在过滤之后添加，短期记忆不受 memory_type 过滤）
        if from_short_term:
            st_results = self._search_short_term(query, top_k=top_k)
            if exclude_sources:
                st_results = [
                    r for r in st_results
                    if r.get("source", "short_term") not in exclude_sources
                ]
            results.extend(st_results)

        final_results = results[:top_k]

        # 记录访问到衰减引擎
        for r in final_results:
            mid = r.get("id")
            if mid:
                self._decay_engine.record_access(mid)

        return final_results

    def _recall_hybrid(
        self,
        query: str,
        top_k: int = 5,
        from_short_term: bool = True,
        exclude_sources: Optional[list] = None,
        **filters,
    ) -> list:
        """使用混合搜索引擎执行检索（RRF 融合）。

        内部方法，由 recall() 在混合模式激活时调用。
        融合向量搜索、关键词搜索（BM25）和知识图谱搜索的结果。

        Args:
            query: 查询内容
            top_k: 返回数量
            from_short_term: 是否同时检索短期记忆
            exclude_sources: 排除的来源列表
            **filters: 过滤条件

        Returns:
            检索结果列表（与 recall() 返回格式一致）
        """
        exclude_sources = exclude_sources or []

        # 当有过滤条件时，增大检索量以确保过滤后有足够结果
        has_filters = filters.get("memory_type") or filters.get("category") or filters.get("tags")
        search_top_k = top_k * 10 if has_filters else top_k * 2

        # 使用混合搜索引擎检索
        hybrid_hits = self._hybrid_engine.search(query, top_k=search_top_k)

        results = []
        for hit in hybrid_hits:
            # 跳过知识图谱来源的结果（格式不同，单独处理）
            if hit.source == "graph":
                continue

            # 跳过结构化键值对
            content = hit.content
            if "structured" in exclude_sources and ": " in content and len(content.split(": ")) == 2:
                key_part = content.split(": ")[0]
                if " " not in key_part and len(key_part) < 30:
                    continue

            # 跳过已删除的记忆（向量/关键词索引可能滞后）
            try:
                if not self.long_term.get(hit.id):
                    continue
            except Exception:
                continue

            # 获取完整记录信息（memory_type, category, importance, timestamp, source）
            memory_type = hit.metadata.get("memory_type")
            category = hit.metadata.get("category")
            importance = hit.metadata.get("importance", 0.5)
            timestamp = hit.metadata.get("timestamp", 0)
            source = hit.metadata.get("source", "unknown")
            try:
                original = self.long_term.get(hit.id)
                if original:
                    if not memory_type:
                        memory_type = getattr(original, "memory_type", "semantic")
                    if not category:
                        category = getattr(original, "category", "general")
                    importance = getattr(original, "importance", importance)
                    timestamp = getattr(original, "timestamp", timestamp)
                    # 从原始记录获取真实 source
                    original_source = getattr(original, "source", None)
                    if original_source and original_source != "unknown":
                        source = original_source
            except Exception:
                pass
            if not memory_type:
                memory_type = "semantic"
            if not category:
                category = "general"
            if source == "unknown":
                source = "long_term"

            # 在获取真实 source 之后，再检查排除来源
            if source in exclude_sources:
                continue

            results.append({
                "content": content,
                "score": hit.score,
                "source": source,
                "memory_type": memory_type,
                "category": category,
                "importance": importance,
                "timestamp": timestamp,
                "metadata": hit.metadata,
                "id": hit.id,
            })

        # 从短期记忆检索
        if from_short_term:
            st_results = self._search_short_term(query, top_k=top_k)
            if exclude_sources:
                st_results = [
                    r for r in st_results
                    if r.get("source", "short_term") not in exclude_sources
                ]
            results.extend(st_results)

        # 按分数排序
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        # 应用过滤条件（memory_type, category, tags, time_range, min_importance）
        filter_memory_type = filters.get("memory_type")
        filter_category = filters.get("category")
        filter_tags = filters.get("tags")
        filter_time_range = filters.get("time_range")
        filter_min_importance = filters.get("min_importance")
        if filter_memory_type or filter_category or filter_tags or filter_time_range or filter_min_importance:
            filtered = []
            for r in results:
                if filter_memory_type and r.get("memory_type") != filter_memory_type:
                    continue
                if filter_category and r.get("category") != filter_category:
                    continue
                if filter_tags:
                    r_tags = set(r.get("metadata", {}).get("tags", []))
                    if not r_tags.intersection(set(filter_tags)):
                        continue
                if filter_time_range and isinstance(filter_time_range, (tuple, list)) and len(filter_time_range) == 2:
                    t_start, t_end = filter_time_range
                    if not (t_start <= r.get("timestamp", 0) <= t_end):
                        continue
                if filter_min_importance is not None and r.get("importance", 0) < filter_min_importance:
                    continue
                filtered.append(r)
            results = filtered

        final_results = results[:top_k]

        # 记录访问到衰减引擎
        for r in final_results:
            mid = r.get("id")
            if mid:
                self._decay_engine.record_access(mid)

        return final_results

    def _search_short_term(self, query: str, top_k: int = 5) -> list:
        """在短期记忆中搜索，基于关键词匹配（支持中文分词）。"""
        results = []
        query_terms = set(tokenize_for_search(query))

        items = self.short_term.working_memory.get_all()
        for key, item in items:
            # 计算简单的词汇重叠分数
            content_terms = set(tokenize_for_search(item.content))
            overlap = len(query_terms & content_terms)
            score = overlap / max(len(query_terms), 1) if query_terms else 0.0

            if score > 0:
                results.append({
                    "content": item.content,
                    "score": score,
                    "source": "short_term",
                    "memory_type": item.memory_type,
                    "key": key,
                    "importance": item.importance,
                    "metadata": item.metadata,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def recall_for_prompt(
        self,
        query: str,
        max_short_term: int = 3,
        max_long_term: int = 3,
    ) -> str:
        """
        回忆信息并格式化为提示文本。

        Args:
            query: 查询内容
            max_short_term: 短期记忆最大数量
            max_long_term: 长期记忆最大数量

        Returns:
            格式化的记忆文本
        """
        parts = []

        # 短期记忆
        if max_short_term > 0:
            st_results = self._search_short_term(query, top_k=max_short_term)
            if st_results:
                lines = []
                for r in st_results:
                    lines.append(f"- [工作记忆] {r['content']} (相关度: {r['score']:.2f})")
                parts.append("【工作记忆】\n" + "\n".join(lines))

        # 长期记忆
        if max_long_term > 0:
            lt_results = self.long_term.recall(query=query, top_k=max_long_term)
            if lt_results:
                lines = []
                for record, score in lt_results:
                    lines.append(f"- [长期记忆] {record.content} (相关度: {score:.2f})")
                parts.append("【长期记忆】\n" + "\n".join(lines))

        return "\n\n".join(parts)

    def get_relevant_context(
        self,
        query: str,
        max_items: int = 5,
    ) -> str:
        """
        获取与查询相关的上下文。

        这是主要的上下文获取接口，用于构建LLM提示。

        Args:
            query: 查询内容
            max_items: 最大条目数

        Returns:
            格式化的上下文文本
        """
        # 获取工作记忆上下文
        working_context = self.short_term.working_memory.get_context_string(
            max_items=max_items
        )

        # 获取检索到的相关记忆
        max_lt = max(0, max_items - 2)
        retrieved_context = self.recall_for_prompt(
            query=query,
            max_short_term=2,
            max_long_term=max_lt,
        )

        # 组合上下文
        parts = []
        if working_context:
            parts.append("【当前焦点】\n" + working_context)
        if retrieved_context:
            parts.append(retrieved_context)

        return "\n\n".join(parts)

    # ==================== 会话管理接口 ====================

    def add_interaction(self, role: str, content: str, **metadata):
        """
        添加交互记录。

        Args:
            role: 角色
            content: 内容
            **metadata: 额外元数据
        """
        self.interaction_count += 1
        self.short_term.add_interaction(role, content, **metadata)

    def get_conversation_history(self, n: int = 10) -> list:
        """
        获取对话历史。

        Args:
            n: 返回最近n条

        Returns:
            对话记录列表
        """
        return self.short_term.get_recent_history(n)

    def get_conversation_context(self, max_turns: int = 5) -> str:
        """
        获取对话上下文。

        Args:
            max_turns: 最大轮数

        Returns:
            格式化的对话文本
        """
        return self.short_term.get_conversation_context(max_turns)

    def set_session_context(self, key: str, value: Any):
        """
        设置会话上下文。

        Args:
            key: 上下文键
            value: 上下文值
        """
        self.short_term.set_session_context(key, value)

    def get_session_context(self, key: str) -> Optional[Any]:
        """
        获取会话上下文。

        Args:
            key: 上下文键

        Returns:
            上下文值
        """
        return self.short_term.get_session_context(key)

    def clear_session(self):
        """清空会话。"""
        self.short_term.clear_session()
        self.interaction_count = 0
        self.session_id = f"session_{int(time.time())}"
        self._closed = False

    # ==================== 记忆巩固接口 ====================

    def consolidate(self, auto: bool = True) -> dict:
        """
        执行记忆巩固。

        Args:
            auto: 是否自动模式（仅在 auto_consolidate 开启时执行）

        Returns:
            巩固结果字典
        """
        if auto and not self.config.auto_consolidate:
            return {"status": "skipped", "reason": "auto_consolidate is disabled"}

        result = self._consolidator.consolidate()
        result["cleanup_removed"] = self._consolidator.cleanup_short_term()
        result["status"] = "completed"
        return result

    def force_consolidate(self) -> dict:
        """
        强制执行记忆巩固。

        Returns:
            巩固结果字典
        """
        result = self._consolidator.consolidate()
        result["cleanup_removed"] = self._consolidator.cleanup_short_term()
        result["status"] = "forced"
        return result

    # ==================== 统计和监控接口 ====================

    # ==================== v6.0+ 创新功能接口 ====================

    def compress_memories(self, strategies=None) -> dict:
        """执行记忆压缩（去重、合并相似、过期清理、摘要生成）。

        Args:
            strategies: 压缩策略列表，None 表示全部策略。
                可选值: "summarize", "merge", "dedup", "expire"

        Returns:
            压缩结果统计字典
        """
        self._check_closed()
        from memory_system.core.memory_compression_engine import CompressionStrategy
        strategy_map = {
            "summarize": CompressionStrategy.SUMMARIZE,
            "merge": CompressionStrategy.MERGE_SIMILAR,
            "dedup": CompressionStrategy.REMOVE_DUPLICATES,
            "expire": CompressionStrategy.EXPIRE_OLD,
        }
        resolved = None
        if strategies:
            resolved = [strategy_map[s] for s in strategies if s in strategy_map]

        memories = self.long_term.get_all(limit=10000)
        result = self._compression_engine.compress_memories(memories, strategies=resolved)
        return {
            "compressed_count": result.compressed_count,
            "removed_count": result.removed_count,
            "merged_groups": len(result.merged_groups),
            "summaries_generated": len(result.summaries_generated),
            "saved_bytes_estimate": result.saved_bytes_estimate,
            "duration_ms": round(result.duration_ms, 2),
        }

    def detect_conflicts(self, conflict_types=None) -> dict:
        """检测记忆冲突（事实矛盾、时间冲突、来源冲突、语义矛盾）。

        Args:
            conflict_types: 冲突类型列表，None 表示全部类型。
                可选值: "factual", "temporal", "source", "semantic"

        Returns:
            冲突检测结果字典
        """
        self._check_closed()
        from memory_system.core.memory_conflict_resolver import ConflictType
        type_map = {
            "factual": ConflictType.FACTUAL,
            "temporal": ConflictType.TEMPORAL,
            "source": ConflictType.SOURCE,
            "semantic": ConflictType.SEMANTIC,
        }
        resolved = None
        if conflict_types:
            resolved = [type_map[t] for t in conflict_types if t in type_map]

        memories = self.long_term.get_all(limit=10000)
        result = self._conflict_resolver.detect_conflicts(memories, conflict_types=resolved)
        return {
            "conflicts_found": len(result.conflicts_found),
            "auto_resolved": len(result.auto_resolved),
            "manual_review": len(result.manual_review),
            "duration_ms": round(result.duration_ms, 2),
            "conflicts": [
                {
                    "id": c.conflict_id,
                    "type": c.conflict_type.value,
                    "memory_ids": c.memory_ids,
                    "description": c.description,
                    "resolved": c.resolved,
                }
                for c in result.conflicts_found
            ],
        }

    def get_version_history(self, memory_id: str) -> list:
        """获取指定记忆的版本历史。

        Args:
            memory_id: 记忆ID

        Returns:
            版本历史列表
        """
        self._check_closed()
        versions = self._version_control.get_version_history(memory_id)
        return [
            {
                "version_id": v.version_id,
                "change_type": v.change_type.value,
                "timestamp": v.timestamp,
                "content_before": v.content_before,
                "content_after": v.content_after,
                "changed_by": v.changed_by,
                "change_reason": v.change_reason,
            }
            for v in versions
        ]

    def rollback_memory(self, memory_id: str, version_id: str) -> Optional[str]:
        """回滚指定记忆到历史版本。

        Args:
            memory_id: 记忆ID
            version_id: 目标版本ID

        Returns:
            回滚后的内容，失败返回None
        """
        self._check_closed()
        content = self._version_control.rollback_to_version(
            memory_id, version_id, changed_by="user",
        )
        if content is not None:
            self.long_term.update(memory_id, content=content)
        return content

    def get_audit_log(self, memory_id=None, change_type=None) -> list:
        """获取审计日志。

        Args:
            memory_id: 筛选特定记忆
            change_type: 筛选变更类型 ("create"/"update"/"delete"/"merge"/"compress")

        Returns:
            审计日志列表
        """
        self._check_closed()
        from memory_system.core.memory_version_control import ChangeType
        ct = None
        if change_type:
            ct = ChangeType(change_type)
        return self._version_control.get_audit_log(
            memory_id=memory_id, change_type=ct,
        )

    # ==================== 统计与管理 ====================

    def get_metrics(self) -> dict:
        """获取性能指标统计。

        Returns:
            dict: 包含各操作的调用次数、总耗时、平均耗时等指标。
        """
        m = dict(self._metrics)
        # 计算平均值
        for op in ["remember", "recall", "update", "delete"]:
            count_key = f"{op}_count"
            time_key = f"{op}_total_time"
            if m.get(count_key, 0) > 0:
                m[f"{op}_avg_time"] = m[time_key] / m[count_key]
            else:
                m[f"{op}_avg_time"] = 0.0
        return m

    def reset_metrics(self):
        """重置所有性能指标。"""
        for key in self._metrics:
            self._metrics[key] = 0 if isinstance(self._metrics[key], int) else 0.0

    def get_stats(self) -> dict:
        """
        获取记忆系统综合统计信息。

        Returns:
            包含所有子模块统计的字典
        """
        self._check_closed()
        stats: Dict[str, Any] = {
            "session": {
                "session_id": self.session_id,
                "interaction_count": self.interaction_count,
            },
            "short_term": {
                "working_memory_size": len(self.short_term.working_memory),
                "history_size": len(self.short_term._history),
                "session_context_keys": len(self.short_term._session_context),
            },
            "long_term": self.long_term.get_stats(),
        }

        if self.knowledge_graph is not None:
            stats["knowledge_graph"] = self.knowledge_graph.get_statistics()

        if self.structured_store is not None:
            stats["structured_store"] = {
                "tables": self.structured_store.list_tables(),
            }

        # v6.0+ 创新功能统计
        stats["compression"] = self._compression_engine.get_statistics()
        stats["conflict_resolver"] = self._conflict_resolver.get_statistics()
        stats["version_control"] = self._version_control.get_statistics()
        stats["decay_engine"] = self._decay_engine.get_stats()

        return stats

    def get_working_memory_snapshot(self) -> dict:
        """
        获取工作记忆快照。

        Returns:
            工作记忆完整上下文快照
        """
        return self.short_term.get_full_context()

    def save(self, directory: str = "."):
        """保存所有持久化存储。

        Args:
            directory: 保存目录路径，默认当前目录
        """
        from pathlib import Path as _Path
        save_dir = _Path(directory)
        save_dir.mkdir(parents=True, exist_ok=True)

        # 长期记忆（向量存储）
        if hasattr(self.long_term.store, "save_index"):
            try:
                self.long_term.store.save_index(str(save_dir / "memory_index.faiss"))
            except (IOError, OSError, RuntimeError) as e:
                logger.warning("Failed to save vector store index: %s", e)

        # 知识图谱
        if self.knowledge_graph is not None:
            try:
                self.knowledge_graph.save_to_json(str(save_dir / "knowledge_graph.json"))
            except (IOError, OSError, TypeError) as e:
                logger.warning("Failed to save knowledge graph: %s", e)

        # 结构化存储（SQLite 自身持久化，此处可做备份）
        if self.structured_store is not None:
            try:
                self.structured_store.backup(str(save_dir / "structured_store_backup.db"))
            except (IOError, OSError, RuntimeError) as e:
                logger.warning("Failed to backup structured store: %s", e)

    # ================================================================
    # 批量操作 API
    # ================================================================

    def batch_remember(self, items: list, skip_errors: bool = True) -> dict:
        """批量记忆多条信息。

        Args:
            items: 记忆项列表，每项为 dict，支持以下键：
                - content (str, 必需): 记忆内容
                - memory_type (str): 记忆类型，默认 "semantic"
                - category (str): 类别，默认 "general"
                - importance (float): 重要性 0-1，默认 0.5
                - tags (list): 标签列表
                - metadata (dict): 元数据
            skip_errors: 是否跳过错误继续执行，默认 True

        Returns:
            dict: {"success": int, "failed": int, "ids": list, "errors": list}
        """
        self._check_closed()
        success = 0
        failed = 0
        ids = []
        errors = []

        for i, item in enumerate(items):
            try:
                if not isinstance(item, dict) or "content" not in item:
                    raise ValueError(f"item[{i}] must be a dict with 'content' key")

                mid = self.remember(
                    content=item["content"],
                    memory_type=item.get("memory_type", "semantic"),
                    category=item.get("category", "general"),
                    importance=item.get("importance", 0.5),
                    tags=item.get("tags"),
                    source=item.get("source", "batch"),
                    metadata=item.get("metadata"),
                )
                ids.append(mid)
                success += 1
            except Exception as e:
                failed += 1
                errors.append({"index": i, "error": str(e)})
                if not skip_errors:
                    break

        self._metrics["batch_remember_count"] += 1
        return {"success": success, "failed": failed, "ids": ids, "errors": errors}

    def batch_delete(self, memory_ids: list, skip_errors: bool = True) -> dict:
        """批量删除记忆。

        Args:
            memory_ids: 记忆ID列表
            skip_errors: 是否跳过错误继续执行

        Returns:
            dict: {"deleted": int, "not_found": int, "errors": list}
        """
        self._check_closed()
        deleted = 0
        not_found = 0
        errors = []

        for i, mid in enumerate(memory_ids):
            try:
                result = self.delete_memory(mid)
                if result:
                    deleted += 1
                else:
                    not_found += 1
            except Exception as e:
                errors.append({"index": i, "id": mid, "error": str(e)})
                if not skip_errors:
                    break

        self._metrics["batch_delete_count"] += 1
        return {"deleted": deleted, "not_found": not_found, "errors": errors}

    def batch_update(self, updates: list, skip_errors: bool = True) -> dict:
        """批量更新记忆。

        Args:
            updates: 更新项列表，每项为 dict，支持以下键：
                - id (str, 必需): 记忆ID
                - content (str): 新内容
                - importance (float): 新重要性
                - category (str): 新类别
                - tags (list): 新标签
                - metadata (dict): 新元数据
            skip_errors: 是否跳过错误继续执行

        Returns:
            dict: {"updated": int, "not_found": int, "errors": list}
        """
        self._check_closed()
        updated = 0
        not_found = 0
        errors = []

        for i, item in enumerate(updates):
            try:
                if not isinstance(item, dict) or "id" not in item:
                    raise ValueError(f"update[{i}] must be a dict with 'id' key")

                kwargs = {k: v for k, v in item.items() if k != "id"}
                result = self.update_memory(item["id"], **kwargs)
                if result:
                    updated += 1
                else:
                    not_found += 1
            except Exception as e:
                errors.append({"index": i, "error": str(e)})
                if not skip_errors:
                    break

        self._metrics["batch_update_count"] += 1
        return {"updated": updated, "not_found": not_found, "errors": errors}

    def close(self):
        """释放所有资源（SQLite连接、向量存储等）"""
        if self._closed:
            return
        self._closed = True
        # 停止衰减引擎后台线程
        try:
            self._decay_engine.stop()
        except Exception:
            pass
        if self.structured_store is not None:
            self.structured_store.close()
        logger.info("AgentMemory resources released")

    def _check_closed(self):
        """检查实例是否已关闭，已关闭则抛出异常"""
        if getattr(self, "_closed", False):
            raise RuntimeError("AgentMemory instance has been closed. "
                               "Create a new instance to continue.")

    # ==================== 上下文管理器 ====================

    def __enter__(self):
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，自动保存并释放资源。"""
        self.save()
        self.close()

    # ==================== 长期记忆 CRUD ====================

    def get_memory(self, memory_id: str) -> Optional["MemoryRecord"]:
        """获取指定ID的长期记忆。

        Args:
            memory_id: 记忆ID

        Returns:
            MemoryRecord 对象，未找到时返回 None
        """
        self._check_closed()
        return self.long_term.get(memory_id)

    def update_memory(self, memory_id: str, **kwargs) -> bool:
        """更新指定ID的长期记忆。

        Args:
            memory_id: 记忆ID
            **kwargs: 要更新的字段（如 content, importance, category 等）

        Returns:
            是否更新成功
        """
        self._check_closed()
        t0 = time.monotonic()

        # 记录更新前的内容（版本控制）
        old_content = None
        try:
            old_record = self.long_term.get(memory_id)
            if old_record:
                old_content = getattr(old_record, "content", None)
        except Exception:
            pass

        success = self.long_term.update(memory_id, **kwargs)

        # 记录版本变更
        if success:
            try:
                from memory_system.core.memory_version_control import ChangeType
                new_content = kwargs.get("content", old_content)
                self._version_control.record_change(
                    memory_id=memory_id,
                    change_type=ChangeType.UPDATE,
                    content_before=old_content,
                    content_after=new_content,
                    changed_by="system",
                    change_reason="update_memory",
                    metadata_changes=kwargs,
                )
            except Exception as e:
                logger.debug("Version control record failed: %s", e)

        self._metrics["update_count"] += 1
        self._metrics["update_total_time"] += time.monotonic() - t0
        return success

    def delete_memory(self, memory_id: str) -> bool:
        """删除指定ID的长期记忆。

        Args:
            memory_id: 记忆ID

        Returns:
            是否删除成功
        """
        self._check_closed()
        t0 = time.monotonic()

        # 记录删除前的内容（版本控制）
        old_content = None
        try:
            old_record = self.long_term.get(memory_id)
            if old_record:
                old_content = getattr(old_record, "content", None)
        except Exception:
            pass

        success = self.long_term.delete(memory_id)

        # 记录删除变更
        if success:
            try:
                from memory_system.core.memory_version_control import ChangeType
                self._version_control.record_change(
                    memory_id=memory_id,
                    change_type=ChangeType.DELETE,
                    content_before=old_content,
                    content_after=None,
                    changed_by="system",
                    change_reason="delete_memory",
                )
            except Exception as e:
                logger.debug("Version control record failed: %s", e)

        self._metrics["delete_count"] += 1
        self._metrics["delete_total_time"] += time.monotonic() - t0
        return success

    def forget_memory(self, memory_id: str) -> bool:
        """遗忘指定ID的长期记忆（delete_memory 的别名）。

        Args:
            memory_id: 记忆ID

        Returns:
            是否遗忘成功
        """
        self._check_closed()
        return self.long_term.forget(memory_id)

    def get_memories_by_category(self, category: str) -> list:
        """按类别获取长期记忆。

        Args:
            category: 类别名称

        Returns:
            MemoryRecord 列表
        """
        self._check_closed()
        return self.long_term.get_by_category(category)

    def get_memories_by_tag(self, tag: str) -> list:
        """按标签获取长期记忆。

        Args:
            tag: 标签名称

        Returns:
            MemoryRecord 列表
        """
        self._check_closed()
        return self.long_term.get_by_tag(tag)

    def get_all_memories(self, limit: int = 100) -> list:
        """获取所有长期记忆。

        Args:
            limit: 最大返回数量

        Returns:
            MemoryRecord 列表
        """
        self._check_closed()
        return self.long_term.get_all(limit=limit)

    def count_memories(self) -> int:
        """获取长期记忆总数。

        Returns:
            记忆数量
        """
        self._check_closed()
        return self.long_term.count()

    # ==================== 知识图谱高级查询 ====================

    def find_path(self, source: str, target: str) -> Optional[list[str]]:
        """查找两个实体之间的最短路径。

        Args:
            source: 起始实体名称
            target: 目标实体名称

        Returns:
            实体名称路径列表，不存在路径时返回 None
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        return self.knowledge_graph.find_path(source, target)

    def get_neighbors(
        self, entity_name: str, max_depth: int = 1
    ) -> list:
        """获取与指定实体相连的邻居实体。

        Args:
            entity_name: 实体名称
            max_depth: 最大跳数

        Returns:
            Entity 对象列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        return self.knowledge_graph.get_neighbors(entity_name, max_depth=max_depth)

    def get_most_connected_entities(self, top_k: int = 10) -> list:
        """获取连接数最多的实体。

        Args:
            top_k: 返回数量

        Returns:
            [(实体名称, 连接数), ...] 列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        return self.knowledge_graph.most_connected_entities(top_k=top_k)

    def get_entity_types(self) -> list[str]:
        """获取知识图谱中所有实体类型。

        Returns:
            实体类型列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        return self.knowledge_graph.get_entity_types()

    def get_relation_types(self) -> list[str]:
        """获取知识图谱中所有关系类型。

        Returns:
            关系类型列表
        """
        if self.knowledge_graph is None:
            raise RuntimeError("Knowledge graph is not enabled.")
        return self.knowledge_graph.get_relation_types()

    # ==================== 工作记忆焦点管理 ====================

    def set_focus(self, key: str) -> bool:
        """设置工作记忆焦点。

        Args:
            key: 要聚焦的工作记忆键

        Returns:
            是否设置成功
        """
        self._check_closed()
        return self.short_term.working_memory.set_focus(key)

    def get_focus(self) -> Optional[str]:
        """获取当前工作记忆焦点键。

        Returns:
            焦点键，无焦点时返回 None
        """
        self._check_closed()
        return self.short_term.working_memory.get_focus()

    def get_focus_content(self) -> Optional[str]:
        """获取当前工作记忆焦点内容。

        Returns:
            焦点内容，无焦点时返回 None
        """
        self._check_closed()
        return self.short_term.working_memory.get_focus_content()

    def pop_focus(self) -> Optional[str]:
        """弹出并返回当前工作记忆焦点内容。

        Returns:
            焦点内容，无焦点时返回 None
        """
        self._check_closed()
        return self.short_term.working_memory.pop_focus()

    # ==================== 记忆生命周期管理 ====================

    def lifecycle_maintenance(self, auto_compress: bool = False) -> dict:
        """执行完整的记忆生命周期维护。

        包括：冲突检测、压缩（可选）、统计汇总。
        建议定期调用（如每天一次）以保持记忆系统健康。

        Args:
            auto_compress: 是否执行自动压缩（可能较耗时）

        Returns:
            维护报告字典
        """
        self._check_closed()
        report = {
            "timestamp": time.time(),
            "memory_count": self.count_memories(),
            "conflicts": None,
            "compression": None,
            "decay_stats": None,
            "version_stats": None,
        }

        # 1. 冲突检测
        try:
            conflict_result = self.detect_conflicts()
            report["conflicts"] = conflict_result
        except Exception as e:
            logger.warning("Lifecycle conflict detection failed: %s", e)
            report["conflicts"] = {"error": str(e)}

        # 2. 自动压缩（可选）
        if auto_compress:
            try:
                compress_result = self.compress_memories()
                report["compression"] = compress_result
            except Exception as e:
                logger.warning("Lifecycle compression failed: %s", e)
                report["compression"] = {"error": str(e)}

        # 3. 衰减统计
        try:
            report["decay_stats"] = self._decay_engine.get_stats()
        except Exception:
            pass

        # 4. 版本控制统计
        try:
            report["version_stats"] = self._version_control.get_statistics()
        except Exception:
            pass

        logger.info(
            "Lifecycle maintenance complete: memories=%d, conflicts=%s, compressed=%s",
            report["memory_count"],
            report["conflicts"].get("conflicts_found", "N/A") if report["conflicts"] else "N/A",
            report["compression"].get("removed_count", "N/A") if report["compression"] else "N/A",
        )

        return report

    def health_check(self) -> dict:
        """执行记忆系统健康检查。

        Returns:
            健康状态报告
        """
        self._check_closed()
        issues = []

        # 检查记忆数量
        count = self.count_memories()
        if count == 0:
            issues.append({"level": "info", "message": "No memories stored"})

        # 检查压缩需求
        if self._compression_engine.should_compress(count):
            issues.append({
                "level": "warning",
                "message": f"Memory count ({count}) exceeds compression threshold",
                "action": "Run lifecycle_maintenance(auto_compress=True)",
            })

        # 检查冲突
        try:
            conflict_result = self.detect_conflicts()
            if conflict_result.get("conflicts_found", 0) > 0:
                issues.append({
                    "level": "warning",
                    "message": f"{conflict_result['conflicts_found']} conflicts detected",
                    "action": "Review and resolve conflicts",
                })
        except Exception:
            pass

        return {
            "status": "healthy" if not issues else "needs_attention",
            "memory_count": count,
            "issues": issues,
            "engines": {
                "compression": "active",
                "conflict_resolver": "active",
                "version_control": "active",
                "decay_engine": "active",
                "hybrid_search": "active" if self._hybrid_enabled else "disabled",
            },
        }

    # ==================== 事实查询 ====================

    def get_facts(self, category: str = None, limit: int = 50) -> list:
        """从结构化存储中获取事实。

        Args:
            category: 按类别过滤，为 None 时返回所有
            limit: 最大返回数量

        Returns:
            事实字典列表
        """
        if self.memory_table is None:
            raise RuntimeError("Structured store is not enabled.")
        return self.memory_table.get_facts(category=category, limit=limit)

    # ==================== 导出/导入管道 ====================

    def export_memories(
        self,
        filepath: str,
        format: str = "json",
        category: str = None,
        include_embeddings: bool = False,
    ) -> dict:
        """导出记忆到文件。

        Args:
            filepath: 输出文件路径
            format: 格式 ("json" 或 "yaml")
            category: 按类别过滤，None 表示全部
            include_embeddings: 是否包含嵌入向量

        Returns:
            导出统计 {"exported": int, "filepath": str}
        """
        self._check_closed()
        from memory_system.processing.memory_data_serializer import (
            MemorySerializer, ExportFormat,
        )

        memories = self.long_term.get_all(limit=10000)
        if category:
            memories = [m for m in memories if m.category == category]

        export_data = []
        for m in memories:
            record = {
                "id": m.id,
                "content": m.content,
                "memory_type": m.memory_type,
                "category": m.category,
                "importance": m.importance,
                "tags": m.tags,
                "source": m.source,
                "metadata": m.metadata,
                "timestamp": m.timestamp,
                "access_count": m.access_count,
            }
            if include_embeddings and m.embedding:
                record["embedding"] = m.embedding
            export_data.append(record)

        fmt = ExportFormat.JSON if format == "json" else ExportFormat.YAML
        serializer = MemorySerializer()
        serializer.export_to_file(export_data, filepath, format=fmt)
        return {"exported": len(export_data), "filepath": filepath}

    def import_memories(
        self,
        filepath: str,
        format: str = None,
        overwrite: bool = False,
    ) -> dict:
        """从文件导入记忆。

        Args:
            filepath: 输入文件路径
            format: 格式 ("json" 或 "yaml")，None 自动检测
            overwrite: 是否覆盖已存在的记忆（按ID）

        Returns:
            导入统计 {"imported": int, "skipped": int, "errors": int}
        """
        self._check_closed()
        from memory_system.processing.memory_data_serializer import (
            MemorySerializer,
        )

        serializer = MemorySerializer()
        records = serializer.import_from_file(filepath)

        stats = {"imported": 0, "skipped": 0, "errors": 0}
        for record in records:
            try:
                memory_id = record.get("id")
                content = record.get("content", "")
                if not content:
                    stats["skipped"] += 1
                    continue

                # 检查是否已存在
                if not overwrite and memory_id:
                    existing = self.long_term.get(memory_id)
                    if existing is not None:
                        stats["skipped"] += 1
                        continue

                self.remember(
                    content=content,
                    memory_type=record.get("memory_type", "semantic"),
                    category=record.get("category", "general"),
                    importance=record.get("importance", 0.5),
                    tags=record.get("tags", []),
                    source=record.get("source", "import"),
                    metadata=record.get("metadata", {}),
                )
                stats["imported"] += 1
            except Exception:
                stats["errors"] += 1

        return stats

    def export_preferences(self, filepath: str, format: str = "json") -> str:
        """导出偏好设置到文件。

        Args:
            filepath: 输出文件路径
            format: 格式 ("json" 或 "yaml")

        Returns:
            导出的文件路径
        """
        self._check_closed()
        import json

        # 从结构化存储获取所有偏好
        prefs = {}
        if self.structured_store:
            try:
                # 获取所有偏好记录
                all_prefs = self.structured_store.get_preferences()
                for key, value in all_prefs.items():
                    prefs[key] = value
            except Exception as e:
                logger.warning("Failed to get preferences from structured store: %s", e)

        export_data = {
            "version": "3.0",
            "exported_at": time.time(),
            "type": "preferences",
            "preferences": prefs,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            if format == "json":
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            else:
                import yaml
                yaml.dump(export_data, f, allow_unicode=True)

        return filepath

    def import_preferences(self, filepath: str) -> dict:
        """从文件导入偏好设置。

        Args:
            filepath: 输入文件路径

        Returns:
            导入统计 {"imported": int, "errors": int}
        """
        self._check_closed()
        import json

        imported = 0
        errors = 0

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            prefs = data.get("preferences", {})
            for key, value in prefs.items():
                try:
                    self.store_preference(key, value)
                    imported += 1
                except Exception as e:
                    logger.warning("Failed to import preference %s: %s", key, e)
                    errors += 1

        except Exception as e:
            logger.error("Failed to import preferences: %s", e)
            errors += 1

        return {"imported": imported, "errors": errors}


# ---------------------------------------------------------------------------
# MemoryManager - 向后兼容包装器
# ---------------------------------------------------------------------------

class MemoryManager:
    """记忆管理器（兼容层）。

    提供与 AgentMemory 相同的接口，用于向后兼容。
    所有方法调用代理到内部 AgentMemory 实例。
    """

    def __init__(self, config=None, **kwargs):
        if config is not None and not isinstance(config, AgentMemoryConfig):
            # 旧版 MemoryConfig (dataclass) 兼容
            config = AgentMemoryConfig(
                short_term={
                    "working_memory_capacity": getattr(config, "working_memory_capacity", 7),
                    "history_limit": getattr(config, "history_limit", 50),
                },
                consolidation_threshold=getattr(config, "consolidation_threshold", 0.6),
                auto_consolidate=getattr(config, "auto_consolidate", True),
                default_top_k=getattr(config, "default_top_k", 5),
            )
        self.memory = AgentMemory(config=config, **kwargs)

    def __getattr__(self, name):
        """代理到 AgentMemory。"""
        return getattr(self.memory, name)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "AgentMemoryConfig",
    "AgentMemory",
    "MemoryManager",
    "ShortTermMemory",
    "MemoryItem",
    "WorkingMemoryBuffer",
    "LongTermMemory",
    "LongTermMemoryConfig",
    "LongTermMemoryItem",
    "EmbeddingProvider",
    "EmbeddingFactory",
    "EmbeddingConfig",
    "VectorStoreBackend",
    "VectorStoreFactory",
    "MemoryRecord",
    "SearchResult",
    "KnowledgeGraph",
    "KnowledgeGraphBuilder",
    "Entity",
    "Relation",
    "StructuredStore",
    "MemoryTable",
]
