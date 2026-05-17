"""
记忆巩固模块 (Memory Consolidation Module)

实现心理学中记忆巩固的概念 —— 将新记忆与已有知识进行稳定化和整合的过程。

本模块提供多种可插拔的巩固策略：
- 时间巩固策略 (TemporalConsolidationStrategy): 基于时间窗口分组与合并
- 重要性巩固策略 (ImportanceConsolidationStrategy): 基于重要性评分的保留与归档
- 语义巩固策略 (SemanticConsolidationStrategy): 基于语义相似度的聚类与摘要

所有策略均使用 Python 标准库实现，无需额外依赖。

Example:
    from memory_system.core.memory_consolidation import (
        MemoryConsolidator,
        TemporalConsolidationStrategy,
        ImportanceConsolidationStrategy,
    )

    consolidator = MemoryConsolidator()
    consolidator.add_strategy(TemporalConsolidationStrategy(time_window_hours=12))
    consolidator.add_strategy(ImportanceConsolidationStrategy(keep_ratio=0.8))

    result = consolidator.consolidate(memories)
    print(f"保留: {len(result.consolidated)}, 归档: {len(result.archived)}")
"""

from __future__ import annotations

import copy
import difflib
import logging
import math
import time
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "MemoryItem",
    "ConsolidationResult",
    "SemanticCluster",
    "ConsolidationStrategy",
    "TemporalConsolidationStrategy",
    "ImportanceConsolidationStrategy",
    "SemanticConsolidationStrategy",
    "MemoryConsolidator",
]


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class MemoryItem:
    """
    记忆条目数据模型

    表示系统中的一条记忆，包含内容、元数据和统计信息。

    Attributes:
        id: 记忆唯一标识符
        content: 记忆文本内容
        importance: 重要性分数 (0.0 ~ 1.0)
        access_count: 被访问/检索的次数
        created_at: 创建时间戳 (Unix 秒)
        updated_at: 最后更新时间戳 (Unix 秒)
        tags: 记忆标签列表
        metadata: 额外元数据字典
    """

    id: str
    content: str
    importance: float = 0.5
    access_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "importance": self.importance,
            "access_count": self.access_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryItem":
        """从字典反序列化"""
        return cls(
            id=data["id"],
            content=data["content"],
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SemanticCluster:
    """
    语义聚类结果

    表示一组语义相关的记忆集合及其摘要。

    Attributes:
        cluster_id: 聚类唯一标识符
        memories: 聚类中的记忆条目列表
        summary: 聚类摘要文本
        centroid_content: 质心记忆内容（最接近聚类中心的记忆）
        avg_similarity: 聚类内平均相似度
    """

    cluster_id: str
    memories: list[MemoryItem] = field(default_factory=list)
    summary: str = ""
    centroid_content: str = ""
    avg_similarity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "cluster_id": self.cluster_id,
            "memory_ids": [m.id for m in self.memories],
            "memory_count": len(self.memories),
            "summary": self.summary,
            "centroid_content": self.centroid_content,
            "avg_similarity": self.avg_similarity,
        }


@dataclass
class ConsolidationResult:
    """
    巩固操作结果

    包含一次巩固操作产生的所有输出信息。

    Attributes:
        consolidated: 最终保留的记忆列表
        merged: 被合并的记忆列表（已吸收到其他记忆中）
        archived: 被归档的记忆列表（低重要性）
        clusters: 发现的语义聚类
        stats: 巩固过程的统计信息
    """

    consolidated: list[MemoryItem] = field(default_factory=list)
    merged: list[MemoryItem] = field(default_factory=list)
    archived: list[MemoryItem] = field(default_factory=list)
    clusters: list[SemanticCluster] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "consolidated_count": len(self.consolidated),
            "merged_count": len(self.merged),
            "archived_count": len(self.archived),
            "cluster_count": len(self.clusters),
            "stats": self.stats,
        }

    def summary_text(self) -> str:
        """生成人类可读的摘要文本"""
        parts = [
            f"保留记忆: {len(self.consolidated)} 条",
            f"合并记忆: {len(self.merged)} 条",
            f"归档记忆: {len(self.archived)} 条",
            f"语义聚类: {len(self.clusters)} 个",
        ]
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _compute_similarity(text_a: str, text_b: str) -> float:
    """
    计算两段文本的相似度

    使用 difflib.SequenceMatcher 计算序列相似度比率，
    适用于短文本和中长度文本的快速比较。

    Args:
        text_a: 第一段文本
        text_b: 第二段文本

    Returns:
        相似度分数，范围 [0.0, 1.0]
    """
    if not text_a or not text_b:
        return 0.0
    return difflib.SequenceMatcher(None, text_a, text_b).ratio()


def _merge_two_memories(primary: MemoryItem, secondary: MemoryItem) -> MemoryItem:
    """
    合并两条记忆

    将次要记忆合并到主要记忆中，保留较高的重要性分数，
    累加访问次数，合并标签，并更新时间戳。

    Args:
        primary: 主要记忆（保留）
        secondary: 次要记忆（被吸收）

    Returns:
        合并后的新记忆条目
    """
    merged = copy.deepcopy(primary)
    # 保留更高的重要性
    merged.importance = max(primary.importance, secondary.importance)
    # 累加访问次数
    merged.access_count = primary.access_count + secondary.access_count
    # 合并标签（去重）
    merged.tags = list(set(primary.tags) | set(secondary.tags))
    # 更新时间戳为较新的
    merged.updated_at = max(primary.updated_at, secondary.updated_at)
    # 合并元数据
    merged.metadata["merged_from"] = secondary.id
    merged.metadata["merged_at"] = time.time()
    if "merge_history" not in merged.metadata:
        merged.metadata["merge_history"] = []
    merged.metadata["merge_history"].append(secondary.id)
    # 如果主记忆内容较短，拼接次要及时内容
    if len(secondary.content) > len(merged.content):
        merged.content = secondary.content
    return merged


def _generate_cluster_summary(memories: list[MemoryItem]) -> str:
    """
    为一组记忆生成简单摘要

    通过提取高频关键词和代表性内容片段来生成摘要。

    Args:
        memories: 同一聚类中的记忆列表

    Returns:
        摘要文本字符串
    """
    if not memories:
        return ""
    if len(memories) == 1:
        return memories[0].content[:100]

    # 收集所有内容中的词汇
    all_words: list[str] = []
    for m in memories:
        # 简单分词：按空白字符切分，过滤短词
        words = [w.strip(".,!?;:\"'()[]{}").lower() for w in m.content.split()]
        all_words.extend(w for w in words if len(w) > 2)

    # 取最高频的 5 个关键词
    word_counts = Counter(all_words)
    top_keywords = [w for w, _ in word_counts.most_common(5)]

    # 取内容最长的记忆作为代表
    representative = max(memories, key=lambda m: len(m.content))
    snippet = representative.content[:80]

    summary = f"[{', '.join(top_keywords)}] {snippet}"
    return summary


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------


class ConsolidationStrategy(ABC):
    """
    巩固策略抽象基类

    所有具体的巩固策略都必须继承此类并实现 consolidate 方法。
    策略之间相互独立，可自由组合使用。

    子类需要实现:
        - consolidate(): 执行巩固逻辑
        - name 属性: 返回策略名称
        - description 属性: 返回策略描述
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """策略描述"""
        ...

    @abstractmethod
    def consolidate(
        self, memories: list[MemoryItem], **kwargs: Any
    ) -> ConsolidationResult:
        """
        执行记忆巩固

        Args:
            memories: 待巩固的记忆列表
            **kwargs: 策略特定的额外参数

        Returns:
            ConsolidationResult 巩固结果
        """
        ...


# ---------------------------------------------------------------------------
# 时间巩固策略
# ---------------------------------------------------------------------------


class TemporalConsolidationStrategy(ConsolidationStrategy):
    """
    时间巩固策略

    基于时间窗口对记忆进行分组，并在同一时间窗口内合并
    语义相似度较高的记忆。模拟心理学中记忆随时间巩固的过程。

    工作原理:
        1. 将记忆按创建时间划分到固定长度的时间窗口中
        2. 在每个时间窗口内，计算所有记忆对之间的相似度
        3. 将相似度超过阈值的记忆进行合并
        4. 输出合并后的记忆列表

    Args:
        time_window_hours: 时间窗口长度（小时），默认 24 小时
        similarity_threshold: 合并相似度阈值，默认 0.8

    Example:
        strategy = TemporalConsolidationStrategy(
            time_window_hours=12,
            similarity_threshold=0.75,
        )
        result = strategy.consolidate(memories)
    """

    def __init__(
        self,
        time_window_hours: float = 24.0,
        similarity_threshold: float = 0.8,
    ) -> None:
        if time_window_hours <= 0:
            raise ValueError(f"time_window_hours 必须为正数，当前值: {time_window_hours}")
        if not (0.0 < similarity_threshold <= 1.0):
            raise ValueError(
                f"similarity_threshold 必须在 (0, 1] 范围内，当前值: {similarity_threshold}"
            )
        self.time_window_hours = time_window_hours
        self.similarity_threshold = similarity_threshold

    @property
    def name(self) -> str:
        return "temporal_consolidation"

    @property
    def description(self) -> str:
        return (
            f"时间巩固策略: 窗口={self.time_window_hours}h, "
            f"相似度阈值={self.similarity_threshold}"
        )

    def consolidate(
        self, memories: list[MemoryItem], **kwargs: Any
    ) -> ConsolidationResult:
        """
        执行基于时间的记忆巩固

        Args:
            memories: 待巩固的记忆列表
            **kwargs: 可选参数
                - time_window_hours: 覆盖默认时间窗口
                - similarity_threshold: 覆盖默认相似度阈值

        Returns:
            ConsolidationResult 包含合并后的记忆和统计信息
        """
        if not memories:
            logger.debug("时间巩固: 输入记忆列表为空，直接返回")
            return ConsolidationResult(
                consolidated=[],
                merged=[],
                stats={"strategy": self.name, "input_count": 0},
            )

        window_hours = kwargs.get("time_window_hours", self.time_window_hours)
        threshold = kwargs.get("similarity_threshold", self.similarity_threshold)
        window_seconds = window_hours * 3600.0

        logger.info(
            "时间巩固开始: %d 条记忆, 窗口=%.1fh, 阈值=%.2f",
            len(memories), window_hours, threshold,
        )

        # 按时间窗口分组
        time_windows: dict[int, list[MemoryItem]] = defaultdict(list)
        for memory in memories:
            if window_seconds > 0:
                window_index = int(memory.created_at / window_seconds)
            else:
                window_index = 0
            time_windows[window_index].append(memory)

        logger.debug("时间巩固: 划分为 %d 个时间窗口", len(time_windows))

        # 在每个窗口内合并相似记忆
        consolidated: list[MemoryItem] = []
        merged: list[MemoryItem] = []
        merge_count = 0

        for window_idx in sorted(time_windows.keys()):
            window_memories = time_windows[window_idx]
            kept, absorbed = self._merge_within_window(window_memories, threshold)
            consolidated.extend(kept)
            merged.extend(absorbed)
            merge_count += len(absorbed)

        stats = {
            "strategy": self.name,
            "input_count": len(memories),
            "output_count": len(consolidated),
            "merged_count": merge_count,
            "window_count": len(time_windows),
            "time_window_hours": window_hours,
            "similarity_threshold": threshold,
        }

        logger.info(
            "时间巩固完成: 输入=%d, 输出=%d, 合并=%d",
            stats["input_count"], stats["output_count"], stats["merged_count"],
        )

        return ConsolidationResult(
            consolidated=consolidated,
            merged=merged,
            stats=stats,
        )

    def _merge_within_window(
        self, memories: list[MemoryItem], threshold: float
    ) -> tuple[list[MemoryItem], list[MemoryItem]]:
        """
        在单个时间窗口内合并相似记忆

        使用贪心算法：遍历记忆列表，将每条记忆与已保留的记忆比较，
        若相似度超过阈值则合并，否则作为新记忆保留。

        Args:
            memories: 同一时间窗口内的记忆列表
            threshold: 相似度阈值

        Returns:
            (保留的记忆列表, 被合并的记忆列表)
        """
        kept: list[MemoryItem] = []
        absorbed: list[MemoryItem] = []

        # 按重要性降序排列，确保高重要性记忆优先保留
        sorted_memories = sorted(memories, key=lambda m: m.importance, reverse=True)

        for memory in sorted_memories:
            merged_flag = False
            for i, existing in enumerate(kept):
                sim = _compute_similarity(memory.content, existing.content)
                if sim >= threshold:
                    # 合并到已有记忆中
                    kept[i] = _merge_two_memories(existing, memory)
                    absorbed.append(memory)
                    merged_flag = True
                    logger.debug(
                        "合并记忆: %s -> %s (相似度=%.3f)",
                        memory.id, existing.id, sim,
                    )
                    break
            if not merged_flag:
                kept.append(memory)

        return kept, absorbed


# ---------------------------------------------------------------------------
# 重要性巩固策略
# ---------------------------------------------------------------------------


class ImportanceConsolidationStrategy(ConsolidationStrategy):
    """
    重要性巩固策略

    基于综合评分（近期性 + 频率 + 重要性）对记忆进行排序，
    保留高评分记忆，将低评分记忆标记为归档。

    评分公式:
        score = w_recency * recency + w_frequency * frequency + w_importance * importance

    其中:
        - recency: 基于时间衰减，越新越高
        - frequency: 基于访问次数归一化
        - importance: 记忆自身的重要性标记

    Args:
        keep_ratio: 保留比例，默认 0.7（保留 70% 的记忆）
        min_importance: 最低重要性阈值，低于此值直接归档，默认 0.1
        recency_weight: 时间衰减权重，默认 0.3
        frequency_weight: 访问频率权重，默认 0.2
        importance_weight: 重要性权重，默认 0.5
        recency_half_life: 时间衰减半衰期（秒），默认 7 天

    Example:
        strategy = ImportanceConsolidationStrategy(keep_ratio=0.8, min_importance=0.05)
        result = strategy.consolidate(memories)
    """

    def __init__(
        self,
        keep_ratio: float = 0.7,
        min_importance: float = 0.1,
        recency_weight: float = 0.3,
        frequency_weight: float = 0.2,
        importance_weight: float = 0.5,
        recency_half_life: float = 604800.0,  # 7 天
    ) -> None:
        if not (0.0 < keep_ratio <= 1.0):
            raise ValueError(f"keep_ratio 必须在 (0, 1] 范围内，当前值: {keep_ratio}")
        if not (0.0 <= min_importance <= 1.0):
            raise ValueError(
                f"min_importance 必须在 [0, 1] 范围内，当前值: {min_importance}"
            )
        self.keep_ratio = keep_ratio
        self.min_importance = min_importance
        self.recency_weight = recency_weight
        self.frequency_weight = frequency_weight
        self.importance_weight = importance_weight
        self.recency_half_life = recency_half_life

    @property
    def name(self) -> str:
        return "importance_consolidation"

    @property
    def description(self) -> str:
        return (
            f"重要性巩固策略: 保留比例={self.keep_ratio}, "
            f"最低重要性={self.min_importance}"
        )

    def _compute_score(self, memory: MemoryItem, now: float) -> float:
        """
        计算单条记忆的综合评分

        Args:
            memory: 记忆条目
            now: 当前时间戳

        Returns:
            综合评分，范围 [0.0, 1.0]
        """
        # 时间衰减分: 使用指数衰减
        age = now - memory.created_at
        if age < 0:
            age = 0
        recency = math.exp(-0.693 * age / self.recency_half_life)  # ln(2) ≈ 0.693

        # 频率分: 使用对数归一化，避免极端值
        frequency = math.log1p(memory.access_count) / math.log1p(100)  # 100 次为满分
        frequency = min(frequency, 1.0)

        # 重要性分: 直接使用原始值
        importance = memory.importance

        # 加权求和
        total_weight = (
            self.recency_weight + self.frequency_weight + self.importance_weight
        )
        if total_weight == 0:
            return 0.0

        score = (
            self.recency_weight * recency
            + self.frequency_weight * frequency
            + self.importance_weight * importance
        ) / total_weight

        return max(0.0, min(1.0, score))

    def consolidate(
        self, memories: list[MemoryItem], **kwargs: Any
    ) -> ConsolidationResult:
        """
        执行基于重要性的记忆巩固

        Args:
            memories: 待巩固的记忆列表
            **kwargs: 可选参数
                - keep_ratio: 覆盖默认保留比例
                - min_importance: 覆盖默认最低重要性

        Returns:
            ConsolidationResult 包含保留和归档的记忆
        """
        if not memories:
            logger.debug("重要性巩固: 输入记忆列表为空，直接返回")
            return ConsolidationResult(
                consolidated=[],
                archived=[],
                stats={"strategy": self.name, "input_count": 0},
            )

        keep_ratio = kwargs.get("keep_ratio", self.keep_ratio)
        min_importance = kwargs.get("min_importance", self.min_importance)
        now = kwargs.get("now", time.time())

        logger.info(
            "重要性巩固开始: %d 条记忆, 保留比例=%.2f, 最低重要性=%.2f",
            len(memories), keep_ratio, min_importance,
        )

        # 计算每条记忆的综合评分
        scored_memories: list[tuple[float, MemoryItem]] = []
        for memory in memories:
            score = self._compute_score(memory, now)
            scored_memories.append((score, memory))

        # 按评分降序排列
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # 确定保留数量
        keep_count = max(1, int(len(memories) * keep_ratio))

        consolidated: list[MemoryItem] = []
        archived: list[MemoryItem] = []

        for rank, (score, memory) in enumerate(scored_memories):
            # 强制归档低于最低重要性的记忆
            if memory.importance < min_importance:
                archived.append(memory)
                logger.debug(
                    "归档低重要性记忆: %s (importance=%.3f < %.3f)",
                    memory.id, memory.importance, min_importance,
                )
            elif rank < keep_count:
                consolidated.append(memory)
            else:
                archived.append(memory)

        # 记录评分统计
        scores = [s for s, _ in scored_memories]
        stats = {
            "strategy": self.name,
            "input_count": len(memories),
            "output_count": len(consolidated),
            "archived_count": len(archived),
            "keep_ratio": keep_ratio,
            "min_importance": min_importance,
            "score_avg": sum(scores) / len(scores) if scores else 0.0,
            "score_max": max(scores) if scores else 0.0,
            "score_min": min(scores) if scores else 0.0,
            "score_threshold": scores[keep_count - 1] if len(scores) >= keep_count else 0.0,
        }

        logger.info(
            "重要性巩固完成: 保留=%d, 归档=%d, 平均分=%.3f",
            len(consolidated), len(archived), stats["score_avg"],
        )

        return ConsolidationResult(
            consolidated=consolidated,
            archived=archived,
            stats=stats,
        )


# ---------------------------------------------------------------------------
# 语义巩固策略
# ---------------------------------------------------------------------------


class SemanticConsolidationStrategy(ConsolidationStrategy):
    """
    语义巩固策略

    使用凝聚式层次聚类算法将语义相关的记忆分组到同一聚类中。
    基于文本相似度（difflib.SequenceMatcher）进行聚类，无需外部依赖。

    工作原理:
        1. 计算所有记忆对之间的相似度矩阵
        2. 使用凝聚聚类逐步合并最相似的记忆对
        3. 当聚类内相似度低于阈值或达到最大聚类大小时停止
        4. 为每个聚类生成摘要

    Args:
        similarity_threshold: 聚类相似度阈值，默认 0.6
        max_cluster_size: 单个聚类最大记忆数，默认 10
        min_cluster_size: 单个聚类最小记忆数（低于此值的聚类不输出），默认 2

    Example:
        strategy = SemanticConsolidationStrategy(
            similarity_threshold=0.5,
            max_cluster_size=15,
        )
        result = strategy.consolidate(memories)
        for cluster in result.clusters:
            print(f"聚类 {cluster.cluster_id}: {cluster.summary}")
    """

    def __init__(
        self,
        similarity_threshold: float = 0.6,
        max_cluster_size: int = 10,
        min_cluster_size: int = 2,
    ) -> None:
        if not (0.0 < similarity_threshold <= 1.0):
            raise ValueError(
                f"similarity_threshold 必须在 (0, 1] 范围内，当前值: {similarity_threshold}"
            )
        if max_cluster_size < 2:
            raise ValueError(
                f"max_cluster_size 必须至少为 2，当前值: {max_cluster_size}"
            )
        if min_cluster_size < 1:
            raise ValueError(
                f"min_cluster_size 必须至少为 1，当前值: {min_cluster_size}"
            )
        self.similarity_threshold = similarity_threshold
        self.max_cluster_size = max_cluster_size
        self.min_cluster_size = min_cluster_size

    @property
    def name(self) -> str:
        return "semantic_consolidation"

    @property
    def description(self) -> str:
        return (
            f"语义巩固策略: 相似度阈值={self.similarity_threshold}, "
            f"最大聚类大小={self.max_cluster_size}"
        )

    def consolidate(
        self, memories: list[MemoryItem], **kwargs: Any
    ) -> ConsolidationResult:
        """
        执行基于语义的记忆巩固

        Args:
            memories: 待巩固的记忆列表
            **kwargs: 可选参数
                - similarity_threshold: 覆盖默认相似度阈值
                - max_cluster_size: 覆盖默认最大聚类大小

        Returns:
            ConsolidationResult 包含聚类信息和合并后的记忆
        """
        if not memories:
            logger.debug("语义巩固: 输入记忆列表为空，直接返回")
            return ConsolidationResult(
                consolidated=[],
                clusters=[],
                stats={"strategy": self.name, "input_count": 0},
            )

        threshold = kwargs.get("similarity_threshold", self.similarity_threshold)
        max_size = kwargs.get("max_cluster_size", self.max_cluster_size)

        logger.info(
            "语义巩固开始: %d 条记忆, 阈值=%.2f, 最大聚类=%d",
            len(memories), threshold, max_size,
        )

        # 执行凝聚聚类
        clusters = self._agglomerative_cluster(memories, threshold, max_size)

        # 过滤过小的聚类
        valid_clusters = [
            c for c in clusters if len(c.memories) >= self.min_cluster_size
        ]

        # 收集已聚类的记忆 ID
        clustered_ids: set[str] = set()
        for cluster in valid_clusters:
            for m in cluster.memories:
                clustered_ids.add(m.id)

        # 未被聚类的记忆作为独立记忆保留
        unclustered = [m for m in memories if m.id not in clustered_ids]

        # 为每个聚类生成摘要
        for cluster in valid_clusters:
            cluster.summary = _generate_cluster_summary(cluster.memories)
            # 选择内容最接近质心的记忆作为代表
            cluster.centroid_content = self._find_centroid(cluster.memories)

        # 构建输出：每个聚类保留最重要的记忆作为代表
        consolidated: list[MemoryItem] = []
        for cluster in valid_clusters:
            representative = max(cluster.memories, key=lambda m: m.importance)
            # 在元数据中标记聚类关系
            rep = copy.deepcopy(representative)
            rep.metadata["cluster_id"] = cluster.cluster_id
            rep.metadata["cluster_size"] = len(cluster.memories)
            rep.metadata["cluster_member_ids"] = [m.id for m in cluster.memories]
            consolidated.append(rep)

        # 添加未聚类的独立记忆
        consolidated.extend(unclustered)

        # 被聚类吸收但未作为代表的记忆
        absorbed: list[MemoryItem] = []
        for cluster in valid_clusters:
            representative_id = max(
                cluster.memories, key=lambda m: m.importance
            ).id
            for m in cluster.memories:
                if m.id != representative_id:
                    absorbed.append(m)

        stats = {
            "strategy": self.name,
            "input_count": len(memories),
            "output_count": len(consolidated),
            "cluster_count": len(valid_clusters),
            "absorbed_count": len(absorbed),
            "unclustered_count": len(unclustered),
            "avg_cluster_size": (
                sum(len(c.memories) for c in valid_clusters) / len(valid_clusters)
                if valid_clusters
                else 0.0
            ),
            "similarity_threshold": threshold,
            "max_cluster_size": max_size,
        }

        logger.info(
            "语义巩固完成: 聚类=%d, 保留=%d, 吸收=%d, 独立=%d",
            stats["cluster_count"],
            stats["output_count"],
            stats["absorbed_count"],
            stats["unclustered_count"],
        )

        return ConsolidationResult(
            consolidated=consolidated,
            merged=absorbed,
            clusters=valid_clusters,
            stats=stats,
        )

    def _agglomerative_cluster(
        self,
        memories: list[MemoryItem],
        threshold: float,
        max_size: int,
    ) -> list[SemanticCluster]:
        """
        凝聚式层次聚类

        从每条记忆作为一个独立聚类开始，迭代合并最相似的两个聚类，
        直到所有聚类对之间的相似度都低于阈值。

        Args:
            memories: 待聚类的记忆列表
            threshold: 合并相似度阈值
            max_size: 单个聚类最大记忆数

        Returns:
            聚类列表
        """
        # 初始化：每条记忆一个聚类
        cluster_map: dict[int, list[MemoryItem]] = {}
        for i, memory in enumerate(memories):
            cluster_map[i] = [memory]

        # 预计算所有记忆对的相似度
        n = len(memories)
        similarity_cache: dict[tuple[int, int], float] = {}
        for i in range(n):
            for j in range(i + 1, n):
                sim = _compute_similarity(memories[i].content, memories[j].content)
                similarity_cache[(i, j)] = sim

        # 凝聚聚类主循环
        merged = True
        while merged:
            merged = False
            best_sim = 0.0
            best_pair: tuple[int, int] | None = None

            # 找到最相似的聚类对
            active_clusters = list(cluster_map.keys())
            for idx_a in range(len(active_clusters)):
                for idx_b in range(idx_a + 1, len(active_clusters)):
                    ca = active_clusters[idx_a]
                    cb = active_clusters[idx_b]

                    # 检查合并后大小是否超限
                    if len(cluster_map[ca]) + len(cluster_map[cb]) > max_size:
                        continue

                    # 计算聚类间相似度（单链接：取最大相似度）
                    cluster_sim = self._cluster_similarity(
                        ca, cb, cluster_map, similarity_cache
                    )

                    if cluster_sim > best_sim:
                        best_sim = cluster_sim
                        best_pair = (ca, cb)

            # 合并最佳聚类对
            if best_pair is not None and best_sim >= threshold:
                ca, cb = best_pair
                cluster_map[ca] = cluster_map[ca] + cluster_map[cb]
                del cluster_map[cb]
                merged = True

        # 转换为 SemanticCluster 对象
        clusters: list[SemanticCluster] = []
        for idx, cluster_id in enumerate(sorted(cluster_map.keys())):
            mems = cluster_map[cluster_id]
            cluster = SemanticCluster(
                cluster_id=f"cluster_{idx:04d}",
                memories=mems,
            )
            # 计算聚类内平均相似度
            if len(mems) > 1:
                total_sim = 0.0
                pair_count = 0
                for i in range(len(mems)):
                    for j in range(i + 1, len(mems)):
                        # 在原始记忆列表中查找索引
                        orig_i = next(
                            k for k, m in enumerate(memories) if m.id == mems[i].id
                        )
                        orig_j = next(
                            k for k, m in enumerate(memories) if m.id == mems[j].id
                        )
                        key = (min(orig_i, orig_j), max(orig_i, orig_j))
                        total_sim += similarity_cache.get(key, 0.0)
                        pair_count += 1
                cluster.avg_similarity = total_sim / pair_count if pair_count > 0 else 0.0
            clusters.append(cluster)

        return clusters

    def _cluster_similarity(
        self,
        cluster_a: int,
        cluster_b: int,
        cluster_map: dict[int, list[MemoryItem]],
        similarity_cache: dict[tuple[int, int], float],
    ) -> float:
        """
        计算两个聚类之间的相似度（单链接方法）

        单链接：取两个聚类中所有记忆对之间的最大相似度。

        Args:
            cluster_a: 聚类 A 的索引
            cluster_b: 聚类 B 的索引
            cluster_map: 聚类索引到记忆列表的映射
            similarity_cache: 预计算的相似度缓存

        Returns:
            聚类间相似度
        """
        max_sim = 0.0
        for ma in cluster_map[cluster_a]:
            for mb in cluster_map[cluster_b]:
                # 使用记忆 ID 查找原始索引
                orig_a = id(ma)  # 使用对象 id 作为代理
                orig_b = id(mb)
                # 直接计算相似度（缓存基于原始索引，此处直接计算更可靠）
                sim = _compute_similarity(ma.content, mb.content)
                if sim > max_sim:
                    max_sim = sim
        return max_sim

    def _find_centroid(self, memories: list[MemoryItem]) -> str:
        """
        找到聚类中与其他记忆平均相似度最高的记忆（质心）

        Args:
            memories: 聚类中的记忆列表

        Returns:
            质心记忆的内容文本
        """
        if not memories:
            return ""
        if len(memories) == 1:
            return memories[0].content

        best_idx = 0
        best_avg_sim = -1.0

        for i, mi in enumerate(memories):
            total_sim = 0.0
            count = 0
            for j, mj in enumerate(memories):
                if i != j:
                    total_sim += _compute_similarity(mi.content, mj.content)
                    count += 1
            avg_sim = total_sim / count if count > 0 else 0.0
            if avg_sim > best_avg_sim:
                best_avg_sim = avg_sim
                best_idx = i

        return memories[best_idx].content


# ---------------------------------------------------------------------------
# 巩固编排器
# ---------------------------------------------------------------------------


class MemoryConsolidator:
    """
    记忆巩固编排器

    协调多个巩固策略按顺序执行，将各策略的结果进行聚合，
    产生最终的巩固输出。

    支持功能:
        - 动态添加/移除巩固策略
        - 按顺序执行所有策略
        - 聚合各策略的统计信息
        - 策略执行日志记录

    Args:
        strategies: 初始策略列表，默认为 None（空列表）

    Example:
        consolidator = MemoryConsolidator()
        consolidator.add_strategy(TemporalConsolidationStrategy())
        consolidator.add_strategy(ImportanceConsolidationStrategy())
        consolidator.add_strategy(SemanticConsolidationStrategy())

        result = consolidator.consolidate(memories)
        print(result.summary_text())

        stats = consolidator.get_consolidation_stats()
    """

    def __init__(
        self, strategies: Optional[list[ConsolidationStrategy]] = None
    ) -> None:
        self._strategies: list[ConsolidationStrategy] = []
        self._history: list[dict[str, Any]] = []
        self._total_consolidations = 0

        if strategies:
            for strategy in strategies:
                self.add_strategy(strategy)

    @property
    def strategy_count(self) -> int:
        """当前已注册的策略数量"""
        return len(self._strategies)

    @property
    def strategy_names(self) -> list[str]:
        """当前已注册的策略名称列表"""
        return [s.name for s in self._strategies]

    def add_strategy(self, strategy: ConsolidationStrategy) -> None:
        """
        添加巩固策略

        Args:
            strategy: 巩固策略实例

        Raises:
            TypeError: 当 strategy 不是 ConsolidationStrategy 子类时
        """
        if not isinstance(strategy, ConsolidationStrategy):
            raise TypeError(
                f"strategy 必须是 ConsolidationStrategy 的子类，"
                f"当前类型: {type(strategy).__name__}"
            )
        self._strategies.append(strategy)
        logger.info("添加巩固策略: %s - %s", strategy.name, strategy.description)

    def remove_strategy(self, strategy_name: str) -> bool:
        """
        按名称移除巩固策略

        Args:
            strategy_name: 要移除的策略名称

        Returns:
            是否成功移除
        """
        for i, strategy in enumerate(self._strategies):
            if strategy.name == strategy_name:
                self._strategies.pop(i)
                logger.info("移除巩固策略: %s", strategy_name)
                return True
        logger.warning("未找到策略: %s，移除失败", strategy_name)
        return False

    def consolidate(
        self, memories: list[MemoryItem], **kwargs: Any
    ) -> ConsolidationResult:
        """
        执行完整的记忆巩固流程

        按注册顺序依次执行所有巩固策略，每个策略的输出作为
        下一个策略的输入。最终聚合所有策略的统计信息。

        Args:
            memories: 待巩固的记忆列表
            **kwargs: 传递给各策略的额外参数

        Returns:
            ConsolidationResult 最终巩固结果
        """
        self._total_consolidations += 1
        start_time = time.time()

        if not self._strategies:
            logger.warning("未注册任何巩固策略，直接返回原始记忆")
            return ConsolidationResult(
                consolidated=list(memories),
                stats={
                    "strategy": "none",
                    "input_count": len(memories),
                    "output_count": len(memories),
                    "elapsed_seconds": 0.0,
                },
            )

        if not memories:
            logger.debug("巩固编排: 输入记忆列表为空，直接返回")
            return ConsolidationResult(
                consolidated=[],
                stats={"strategy": "pipeline", "input_count": 0, "elapsed_seconds": 0.0},
            )

        logger.info(
            "巩固编排开始: %d 条记忆, %d 个策略 [%s]",
            len(memories),
            len(self._strategies),
            ", ".join(s.name for s in self._strategies),
        )

        # 依次执行各策略
        current_memories = list(memories)
        all_merged: list[MemoryItem] = []
        all_archived: list[MemoryItem] = []
        all_clusters: list[SemanticCluster] = []
        strategy_stats: list[dict[str, Any]] = []
        seen_archived_ids: set[str] = set()

        for strategy in self._strategies:
            try:
                result = strategy.consolidate(current_memories, **kwargs)
                strategy_stats.append(result.stats)

                # 收集合并和归档的记忆（去重）
                for m in result.merged:
                    if m.id not in seen_archived_ids:
                        all_merged.append(m)
                        seen_archived_ids.add(m.id)

                for m in result.archived:
                    if m.id not in seen_archived_ids:
                        all_archived.append(m)
                        seen_archived_ids.add(m.id)

                # 收集聚类信息
                all_clusters.extend(result.clusters)

                # 更新当前记忆为策略输出
                current_memories = result.consolidated

                logger.info(
                    "策略 [%s] 完成: 输入=%d, 输出=%d",
                    strategy.name,
                    result.stats.get("input_count", 0),
                    result.stats.get("output_count", 0),
                )

            except (ValueError, TypeError, RuntimeError) as e:
                logger.error(
                    "策略 [%s] 执行失败: %s，跳过该策略",
                    strategy.name, str(e),
                    exc_info=True,
                )
                strategy_stats.append({
                    "strategy": strategy.name,
                    "error": str(e),
                    "input_count": len(current_memories),
                    "output_count": len(current_memories),
                })
                # 出错时保留当前记忆继续执行后续策略
                continue

        elapsed = time.time() - start_time

        # 构建最终结果
        final_result = ConsolidationResult(
            consolidated=current_memories,
            merged=all_merged,
            archived=all_archived,
            clusters=all_clusters,
            stats={
                "strategy": "pipeline",
                "input_count": len(memories),
                "output_count": len(current_memories),
                "total_merged": len(all_merged),
                "total_archived": len(all_archived),
                "total_clusters": len(all_clusters),
                "strategy_count": len(self._strategies),
                "strategy_names": [s.name for s in self._strategies],
                "strategy_details": strategy_stats,
                "elapsed_seconds": round(elapsed, 4),
                "consolidation_id": self._total_consolidations,
            },
        )

        # 记录到历史
        self._history.append({
            "consolidation_id": self._total_consolidations,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_count": len(memories),
            "output_count": len(current_memories),
            "elapsed_seconds": elapsed,
            "strategies": [s.name for s in self._strategies],
        })

        logger.info(
            "巩固编排完成: 输入=%d, 输出=%d, 合并=%d, 归档=%d, "
            "聚类=%d, 耗时=%.4fs",
            len(memories),
            len(current_memories),
            len(all_merged),
            len(all_archived),
            len(all_clusters),
            elapsed,
        )

        return final_result

    def get_consolidation_stats(self) -> dict[str, Any]:
        """
        获取巩固统计信息

        返回编排器自创建以来的累计统计信息，包括执行次数、
        历史记录摘要等。

        Returns:
            统计信息字典
        """
        total_input = sum(h["input_count"] for h in self._history)
        total_output = sum(h["output_count"] for h in self._history)
        total_elapsed = sum(h["elapsed_seconds"] for h in self._history)

        return {
            "total_consolidations": self._total_consolidations,
            "registered_strategies": self.strategy_names,
            "strategy_count": self.strategy_count,
            "total_memories_processed": total_input,
            "total_memories_output": total_output,
            "avg_reduction_ratio": (
                1.0 - (total_output / total_input)
                if total_input > 0
                else 0.0
            ),
            "total_elapsed_seconds": round(total_elapsed, 4),
            "avg_elapsed_seconds": (
                round(total_elapsed / self._total_consolidations, 4)
                if self._total_consolidations > 0
                else 0.0
            ),
            "history_count": len(self._history),
            "last_consolidation": (
                self._history[-1] if self._history else None
            ),
        }

    def clear_history(self) -> None:
        """清除巩固历史记录"""
        self._history.clear()
        logger.info("巩固历史记录已清除")

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        获取最近的巩固历史记录

        Args:
            limit: 返回的最大记录数

        Returns:
            历史记录列表（按时间倒序）
        """
        return list(reversed(self._history[-limit:]))
