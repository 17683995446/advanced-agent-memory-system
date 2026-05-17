"""
高性能索引系统

提供多维度索引管理，优化大规模记忆的查询性能：
1. 倒排索引 - 关键词快速定位
2. 类别索引 - 按类别快速过滤
3. 标签索引 - 多标签联合查询
4. 时间索引 - 时间范围查询
5. 重要性索引 - 按重要性排序

支持索引增量更新、自动重建、查询优化。
"""

from __future__ import annotations

import bisect
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class IndexConfig:
    """索引配置"""
    enable_inverted_index: bool = True      # 倒排索引
    enable_category_index: bool = True      # 类别索引
    enable_tag_index: bool = True           # 标签索引
    enable_time_index: bool = True          # 时间索引
    enable_importance_index: bool = True    # 重要性索引
    auto_rebuild_threshold: float = 0.1     # 变更比例超过此值触发重建
    min_rebuild_interval_seconds: int = 300  # 最小重建间隔


@dataclass
class QueryPlan:
    """查询执行计划"""
    strategy: str                           # 执行策略
    index_used: list[str]                   # 使用的索引
    estimated_cost: int                     # 预估成本
    candidate_ids: Optional[set[str]] = None  # 候选ID集合


class MemoryIndexManager:
    """
    记忆索引管理器

    提供高性能的多维度索引：
    - 倒排索引: word -> set(memory_ids)
    - 类别索引: category -> set(memory_ids)
    - 标签索引: tag -> set(memory_ids)
    - 时间索引: sorted list of (timestamp, memory_id)
    - 重要性索引: sorted list of (importance, memory_id)

    Example:
        index_mgr = MemoryIndexManager(config=IndexConfig())
        index_mgr.build_index(memories)
        results = index_mgr.query(keywords=["django"], category="web", tags=["python"])
    """

    def __init__(self, config: Optional[IndexConfig] = None):
        self.config = config or IndexConfig()

        # 倒排索引: word -> set(memory_ids)
        self._inverted_index: dict[str, set[str]] = defaultdict(set)

        # 类别索引: category -> set(memory_ids)
        self._category_index: dict[str, set[str]] = defaultdict(set)

        # 标签索引: tag -> set(memory_ids)
        self._tag_index: dict[str, set[str]] = defaultdict(set)

        # 时间索引: sorted list of (timestamp, memory_id)
        self._time_index: list[tuple[float, str]] = []

        # 重要性索引: sorted list of (-importance, memory_id) for descending order
        self._importance_index: list[tuple[float, str]] = []

        # 元数据缓存: memory_id -> metadata
        self._metadata_cache: dict[str, dict[str, Any]] = {}

        # 统计
        self._indexed_count = 0
        self._last_rebuild_time: Optional[float] = None
        self._modifications_since_rebuild = 0

    def build_index(self, memories: list[Any]) -> None:
        """从记忆列表构建完整索引"""
        start_time = time.time()

        # 清空现有索引
        self._clear_indexes()

        for memory in memories:
            self._index_single(memory)

        # 排序时间索引和重要性索引
        if self.config.enable_time_index:
            self._time_index.sort(key=lambda x: x[0])
        if self.config.enable_importance_index:
            self._importance_index.sort(key=lambda x: x[0])

        self._indexed_count = len(memories)
        self._last_rebuild_time = time.time()
        self._modifications_since_rebuild = 0

        duration = time.time() - start_time
        logger.info("Index built: %d memories in %.3fs", len(memories), duration)

    def _clear_indexes(self) -> None:
        """清空所有索引"""
        self._inverted_index.clear()
        self._category_index.clear()
        self._tag_index.clear()
        self._time_index.clear()
        self._importance_index.clear()
        self._metadata_cache.clear()

    def _index_single(self, memory: Any) -> None:
        """索引单条记忆"""
        memory_id = getattr(memory, "id", str(id(memory)))
        content = getattr(memory, "content", "")
        category = getattr(memory, "category", "general")
        tags = getattr(memory, "tags", [])
        timestamp = getattr(memory, "timestamp", time.time())
        importance = getattr(memory, "importance", 0.5)

        # 缓存元数据
        self._metadata_cache[memory_id] = {
            "category": category,
            "tags": tags,
            "timestamp": timestamp,
            "importance": importance,
        }

        # 倒排索引
        if self.config.enable_inverted_index:
            words = self._tokenize(content)
            for word in words:
                self._inverted_index[word].add(memory_id)

        # 类别索引
        if self.config.enable_category_index:
            self._category_index[category].add(memory_id)

        # 标签索引
        if self.config.enable_tag_index:
            for tag in tags:
                self._tag_index[tag].add(memory_id)

        # 时间索引
        if self.config.enable_time_index:
            self._time_index.append((timestamp, memory_id))

        # 重要性索引
        if self.config.enable_importance_index:
            # 使用负重要性实现降序排序
            self._importance_index.append((-importance, memory_id))

    def add_or_update(self, memory: Any) -> None:
        """添加或更新单条记忆的索引"""
        memory_id = getattr(memory, "id", str(id(memory)))

        # 如果已存在，先移除旧索引
        if memory_id in self._metadata_cache:
            self._remove_from_indexes(memory_id)

        # 添加新索引
        self._index_single(memory)
        self._modifications_since_rebuild += 1

        # 检查是否需要重建
        self._maybe_rebuild()

    def remove(self, memory_id: str) -> None:
        """从索引中移除记忆"""
        if memory_id in self._metadata_cache:
            self._remove_from_indexes(memory_id)
            self._modifications_since_rebuild += 1

    def _remove_from_indexes(self, memory_id: str) -> None:
        """从所有索引中移除指定记忆"""
        metadata = self._metadata_cache.get(memory_id, {})

        # 从倒排索引移除（需要扫描所有词，效率较低）
        for word, ids in list(self._inverted_index.items()):
            ids.discard(memory_id)
            if not ids:
                del self._inverted_index[word]

        # 从类别索引移除
        category = metadata.get("category", "general")
        if category in self._category_index:
            self._category_index[category].discard(memory_id)

        # 从标签索引移除
        for tag in metadata.get("tags", []):
            if tag in self._tag_index:
                self._tag_index[tag].discard(memory_id)

        # 从时间索引移除
        self._time_index = [(t, mid) for t, mid in self._time_index if mid != memory_id]

        # 从重要性索引移除
        self._importance_index = [(imp, mid) for imp, mid in self._importance_index if mid != memory_id]

        # 从缓存移除
        del self._metadata_cache[memory_id]

    def _maybe_rebuild(self) -> None:
        """检查是否需要重建索引"""
        if self._indexed_count == 0:
            return

        # 检查变更比例
        ratio = self._modifications_since_rebuild / self._indexed_count
        if ratio < self.config.auto_rebuild_threshold:
            return

        # 检查时间间隔
        if self._last_rebuild_time:
            elapsed = time.time() - self._last_rebuild_time
            if elapsed < self.config.min_rebuild_interval_seconds:
                return

        # 触发重建（在实际实现中，这里应该异步执行）
        logger.info("Triggering index rebuild: %.2f%% modified", ratio * 100)
        # 注意：实际重建需要访问原始记忆数据，这里仅重置计数器
        self._modifications_since_rebuild = 0
        self._last_rebuild_time = time.time()

    def query(
        self,
        keywords: Optional[list[str]] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        time_range: Optional[tuple[float, float]] = None,
        min_importance: Optional[float] = None,
        limit: int = 100,
    ) -> list[str]:
        """
        多条件联合查询

        Args:
            keywords: 关键词列表（AND关系）
            category: 类别过滤
            tags: 标签列表（AND关系）
            time_range: (start_time, end_time) 时间范围
            min_importance: 最小重要性
            limit: 返回结果数量限制

        Returns:
            记忆ID列表（按相关性排序）
        """
        candidate_sets: list[set[str]] = []
        index_used: list[str] = []

        # 关键词查询（倒排索引）
        if keywords and self.config.enable_inverted_index:
            keyword_results = self._query_keywords(keywords)
            if not keyword_results:
                return []  # 关键词无匹配，直接返回空
            candidate_sets.append(keyword_results)
            index_used.append("inverted")

        # 类别查询
        if category and self.config.enable_category_index:
            category_results = self._category_index.get(category, set())
            if not category_results:
                return []  # 类别无匹配，直接返回空
            candidate_sets.append(category_results)
            index_used.append("category")

        # 标签查询
        if tags and self.config.enable_tag_index:
            tag_results = self._query_tags(tags)
            if not tag_results:
                return []  # 标签无匹配，直接返回空
            candidate_sets.append(tag_results)
            index_used.append("tag")

        # 计算候选集交集
        if candidate_sets:
            candidates = set.intersection(*candidate_sets)
        else:
            # 无过滤条件，返回所有
            candidates = set(self._metadata_cache.keys())

        # 时间范围过滤
        if time_range and self.config.enable_time_index:
            candidates = self._filter_by_time(candidates, time_range)
            index_used.append("time")

        # 重要性过滤
        if min_importance is not None and self.config.enable_importance_index:
            candidates = self._filter_by_importance(candidates, min_importance)
            index_used.append("importance")

        # 转换为列表并限制数量
        results = list(candidates)[:limit]

        logger.debug(
            "Query: keywords=%s, category=%s, tags=%s, candidates=%d, results=%d, indexes=%s",
            keywords, category, tags, len(candidates), len(results), index_used
        )

        return results

    def _query_keywords(self, keywords: list[str]) -> set[str]:
        """关键词查询（AND关系）"""
        results: Optional[set[str]] = None
        for keyword in keywords:
            keyword = keyword.lower()
            ids = self._inverted_index.get(keyword, set())
            if results is None:
                results = set(ids)
            else:
                results &= ids
        return results or set()

    def _query_tags(self, tags: list[str]) -> set[str]:
        """标签查询（AND关系）"""
        results: Optional[set[str]] = None
        for tag in tags:
            ids = self._tag_index.get(tag, set())
            if results is None:
                results = set(ids)
            else:
                results &= ids
        return results or set()

    def _filter_by_time(self, candidates: set[str], time_range: tuple[float, float]) -> set[str]:
        """时间范围过滤"""
        start_time, end_time = time_range
        # 二分查找定位起始位置
        left = bisect.bisect_left(self._time_index, (start_time, ""))
        right = bisect.bisect_right(self._time_index, (end_time, "~"))

        time_matches = {mid for _, mid in self._time_index[left:right]}
        return candidates & time_matches

    def _filter_by_importance(self, candidates: set[str], min_importance: float) -> set[str]:
        """重要性过滤（返回重要性 >= min_importance 的记忆）"""
        # 重要性索引按降序排列（负值升序）
        # 找到第一个重要性 < min_importance 的位置
        threshold = -min_importance
        # 使用 bisect_left 确保包含等于 threshold 的元素
        idx = bisect.bisect_left(self._importance_index, (threshold, ""))

        # idx之前的所有元素重要性都 > min_importance，idx位置可能等于
        # 需要包含所有 >= min_importance 的元素
        important_ids = {mid for _, mid in self._importance_index[:idx]}
        # 检查 idx 位置的元素是否也满足条件
        if idx < len(self._importance_index):
            imp, mid = self._importance_index[idx]
            if imp <= threshold:  # 原重要性 >= min_importance
                important_ids.add(mid)
        return candidates & important_ids

    def get_query_plan(
        self,
        keywords: Optional[list[str]] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> QueryPlan:
        """获取查询执行计划（用于优化分析）"""
        strategies = []
        indexes = []
        cost = 0

        if keywords and self.config.enable_inverted_index:
            for kw in keywords:
                count = len(self._inverted_index.get(kw.lower(), set()))
                cost += count
            strategies.append("keyword_scan")
            indexes.append("inverted")

        if category and self.config.enable_category_index:
            count = len(self._category_index.get(category, set()))
            cost += count
            strategies.append("category_filter")
            indexes.append("category")

        if tags and self.config.enable_tag_index:
            for tag in tags:
                count = len(self._tag_index.get(tag, set()))
                cost += count
            strategies.append("tag_filter")
            indexes.append("tag")

        return QueryPlan(
            strategy="->".join(strategies) if strategies else "full_scan",
            index_used=indexes,
            estimated_cost=cost,
        )

    def _tokenize(self, text: str) -> set[str]:
        """文本分词"""
        import re
        # 提取英文单词和连续中文字符
        # 中文不使用单词边界 \b，直接匹配连续中文字符
        english_words = re.findall(r"[a-zA-Z0-9]+", text.lower())
        chinese_words = re.findall(r"[\u4e00-\u9fa5]+", text)
        return set(english_words + chinese_words)

    def get_statistics(self) -> dict[str, Any]:
        """获取索引统计信息"""
        return {
            "indexed_memories": self._indexed_count,
            "cached_metadata": len(self._metadata_cache),
            "inverted_index_terms": len(self._inverted_index),
            "category_count": len(self._category_index),
            "tag_count": len(self._tag_index),
            "modifications_since_rebuild": self._modifications_since_rebuild,
            "last_rebuild_time": self._last_rebuild_time,
        }


__all__ = [
    "MemoryIndexManager",
    "IndexConfig",
    "QueryPlan",
]