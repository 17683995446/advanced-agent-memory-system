"""Tests for memory_consolidation module."""

import pytest
import time
from memory_system.core.memory_consolidation import (
    MemoryItem,
    SemanticCluster,
    ConsolidationResult,
    ConsolidationStrategy,
    TemporalConsolidationStrategy,
    ImportanceConsolidationStrategy,
    SemanticConsolidationStrategy,
    MemoryConsolidator,
)


# ============================================================
# Helper Functions
# ============================================================

def make_memory(content, id=None, importance=0.5, access_count=1, hours_ago=0, tags=None):
    """创建测试用 MemoryItem"""
    import time as _time
    now = _time.time()
    return MemoryItem(
        id=id or f"mem-{content[:4]}",
        content=content,
        importance=importance,
        access_count=access_count,
        created_at=now - hours_ago * 3600,
        updated_at=now - max(0, hours_ago - 1) * 3600,
        tags=tags or [],
        metadata={},
    )


# ============================================================
# MemoryItem Tests
# ============================================================

class TestMemoryItem:
    """MemoryItem 数据模型测试"""

    def test_create_memory_item(self):
        item = make_memory("测试内容", id="m1", importance=0.8)
        assert item.id == "m1"
        assert item.content == "测试内容"
        assert item.importance == 0.8
        assert item.access_count == 1

    def test_to_dict_and_from_dict(self):
        item = make_memory("序列化测试", id="m1", importance=0.9, tags=["tag1"])
        d = item.to_dict()
        assert d["id"] == "m1"
        assert d["content"] == "序列化测试"
        assert d["importance"] == 0.9
        assert d["tags"] == ["tag1"]

        restored = MemoryItem.from_dict(d)
        assert restored.id == item.id
        assert restored.content == item.content
        assert restored.importance == item.importance

    def test_from_dict_missing_fields(self):
        d = {"id": "m1", "content": "test"}
        item = MemoryItem.from_dict(d)
        assert item.id == "m1"
        assert item.importance == 0.5  # default
        assert item.access_count == 0  # default


# ============================================================
# TemporalConsolidationStrategy Tests
# ============================================================

class TestTemporalConsolidationStrategy:
    """时间窗口整合策略测试"""

    def test_consolidate_recent_memories(self):
        strategy = TemporalConsolidationStrategy(time_window_hours=24.0, similarity_threshold=0.7)
        memories = [
            make_memory("今天学习了Python基础语法", hours_ago=2),
            make_memory("今天练习了Python列表操作", hours_ago=3),
            make_memory("昨天学习了数据库设计", hours_ago=26),
        ]
        result = strategy.consolidate(memories)
        assert isinstance(result, ConsolidationResult)
        assert len(result.consolidated) > 0

    def test_consolidate_merges_similar(self):
        strategy = TemporalConsolidationStrategy(time_window_hours=24.0, similarity_threshold=0.5)
        memories = [
            make_memory("Python是一种编程语言", hours_ago=1),
            make_memory("Python是流行的编程语言", hours_ago=2),
        ]
        result = strategy.consolidate(memories)
        # 相似记忆应被合并
        assert len(result.merged) >= 1

    def test_consolidate_no_merge_dissimilar(self):
        strategy = TemporalConsolidationStrategy(time_window_hours=24.0, similarity_threshold=0.9)
        memories = [
            make_memory("机器学习是AI的分支", hours_ago=1),
            make_memory("今天天气很好适合散步", hours_ago=2),
        ]
        result = strategy.consolidate(memories)
        # 不相似的记忆不应被合并
        assert len(result.merged) == 0

    def test_consolidate_empty(self):
        strategy = TemporalConsolidationStrategy()
        result = strategy.consolidate([])
        assert len(result.consolidated) == 0

    def test_consolidate_single_memory(self):
        strategy = TemporalConsolidationStrategy()
        memories = [make_memory("单独的记忆")]
        result = strategy.consolidate(memories)
        assert len(result.consolidated) == 1


# ============================================================
# ImportanceConsolidationStrategy Tests
# ============================================================

class TestImportanceConsolidationStrategy:
    """重要性整合策略测试"""

    def test_keep_high_importance(self):
        strategy = ImportanceConsolidationStrategy(keep_ratio=0.5, min_importance=0.3)
        memories = [
            make_memory("重要记忆1", importance=0.9, access_count=10),
            make_memory("重要记忆2", importance=0.8, access_count=8),
            make_memory("普通记忆3", importance=0.5, access_count=2),
            make_memory("低价值记忆4", importance=0.1, access_count=0),
        ]
        result = strategy.consolidate(memories)
        assert len(result.consolidated) >= 2  # 至少保留高重要性的
        assert len(result.archived) >= 1  # 至少归档一个低价值的

    def test_all_high_importance(self):
        strategy = ImportanceConsolidationStrategy(keep_ratio=1.0, min_importance=0.1)
        memories = [
            make_memory(f"高价值{i}", importance=0.9, access_count=10)
            for i in range(5)
        ]
        result = strategy.consolidate(memories)
        # 所有记忆都是高价值的，不应归档
        assert len(result.archived) == 0

    def test_all_low_importance(self):
        strategy = ImportanceConsolidationStrategy(keep_ratio=0.5, min_importance=0.3)
        memories = [
            make_memory(f"低价值{i}", importance=0.05, access_count=0)
            for i in range(10)
        ]
        result = strategy.consolidate(memories)
        # 大部分应被归档
        assert len(result.archived) > 0

    def test_recency_boost(self):
        strategy = ImportanceConsolidationStrategy(keep_ratio=0.5, min_importance=0.1)
        memories = [
            make_memory("最近的记忆", importance=0.3, hours_ago=1),
            make_memory("很久以前的记忆", importance=0.3, hours_ago=1000),
        ]
        result = strategy.consolidate(memories)
        # 最近的记忆应该被保留
        ids = [m.id for m in result.consolidated]
        assert "mem-最近的记" in ids

    def test_empty_memories(self):
        strategy = ImportanceConsolidationStrategy()
        result = strategy.consolidate([])
        assert len(result.consolidated) == 0


# ============================================================
# SemanticConsolidationStrategy Tests
# ============================================================

class TestSemanticConsolidationStrategy:
    """语义整合策略测试"""

    def test_cluster_similar_memories(self):
        strategy = SemanticConsolidationStrategy(similarity_threshold=0.3, max_cluster_size=10)
        memories = [
            make_memory("Python编程语言基础"),
            make_memory("Python高级编程技巧"),
            make_memory("机器学习算法原理"),
            make_memory("深度学习框架使用"),
            make_memory("数据库SQL查询优化"),
        ]
        result = strategy.consolidate(memories)
        assert isinstance(result, ConsolidationResult)
        assert len(result.clusters) > 0

    def test_no_clustering_dissimilar(self):
        strategy = SemanticConsolidationStrategy(similarity_threshold=0.99, max_cluster_size=10)
        memories = [
            make_memory("苹果是水果"),
            make_memory("汽车有四个轮子"),
            make_memory("天空是蓝色的"),
        ]
        result = strategy.consolidate(memories)
        # 相似度阈值很高，不应产生聚类
        assert len(result.clusters) == 0 or all(len(c.memories) <= 1 for c in result.clusters)

    def test_max_cluster_size(self):
        strategy = SemanticConsolidationStrategy(similarity_threshold=0.1, max_cluster_size=3)
        memories = [
            make_memory(f"相似文档{i}") for i in range(10)
        ]
        result = strategy.consolidate(memories)
        # 每个聚类不应超过 max_cluster_size
        for cluster in result.clusters:
            assert len(cluster.memories) <= strategy.max_cluster_size

    def test_empty_memories(self):
        strategy = SemanticConsolidationStrategy()
        result = strategy.consolidate([])
        assert len(result.clusters) == 0

    def test_cluster_has_summary(self):
        strategy = SemanticConsolidationStrategy(similarity_threshold=0.3)
        memories = [
            make_memory("Python基础语法学习"),
            make_memory("Python面向对象编程"),
        ]
        result = strategy.consolidate(memories)
        if result.clusters:
            cluster = result.clusters[0]
            assert cluster.summary is not None or cluster.centroid_content is not None


# ============================================================
# MemoryConsolidator Tests
# ============================================================

class TestMemoryConsolidator:
    """记忆整合编排器测试"""

    def test_single_strategy(self):
        consolidator = MemoryConsolidator()
        consolidator.add_strategy(TemporalConsolidationStrategy(time_window_hours=24.0))
        memories = [
            make_memory("测试记忆1", hours_ago=1),
            make_memory("测试记忆2", hours_ago=2),
        ]
        result = consolidator.consolidate(memories)
        assert isinstance(result, ConsolidationResult)

    def test_multiple_strategies(self):
        consolidator = MemoryConsolidator()
        consolidator.add_strategy(TemporalConsolidationStrategy(time_window_hours=24.0))
        consolidator.add_strategy(ImportanceConsolidationStrategy(keep_ratio=0.8))
        memories = [
            make_memory(f"记忆{i}", importance=0.5, hours_ago=i)
            for i in range(10)
        ]
        result = consolidator.consolidate(memories)
        assert isinstance(result, ConsolidationResult)

    def test_remove_strategy(self):
        consolidator = MemoryConsolidator()
        s = TemporalConsolidationStrategy()
        consolidator.add_strategy(s)
        consolidator.remove_strategy(s.name)
        assert consolidator.strategy_count == 0

    def test_consolidation_stats(self):
        consolidator = MemoryConsolidator()
        consolidator.add_strategy(ImportanceConsolidationStrategy(keep_ratio=0.5))
        memories = [
            make_memory(f"记忆{i}", importance=0.1 * i, access_count=i)
            for i in range(10)
        ]
        consolidator.consolidate(memories)
        stats = consolidator.get_consolidation_stats()
        assert "total_consolidations" in stats
        assert stats["total_consolidations"] == 1

    def test_empty_consolidator(self):
        consolidator = MemoryConsolidator()
        result = consolidator.consolidate([make_memory("测试")])
        # 无策略时应返回原始记忆
        assert len(result.consolidated) == 1

    def test_strategy_failure_does_not_stop_pipeline(self):
        """一个策略失败不应阻止其他策略执行"""
        consolidator = MemoryConsolidator()

        class FailingStrategy(ConsolidationStrategy):
            @property
            def name(self):
                return "failing"
            @property
            def description(self):
                return "Always fails"
            def consolidate(self, memories, **kwargs):
                raise RuntimeError("策略执行失败")

        consolidator.add_strategy(FailingStrategy())
        consolidator.add_strategy(ImportanceConsolidationStrategy(keep_ratio=0.8))

        memories = [make_memory("测试", importance=0.9)]
        result = consolidator.consolidate(memories)
        # 即使第一个策略失败，第二个仍应执行
        assert isinstance(result, ConsolidationResult)

    def test_consolidation_history(self):
        consolidator = MemoryConsolidator()
        consolidator.add_strategy(TemporalConsolidationStrategy())
        consolidator.consolidate([make_memory("第一次")])
        consolidator.consolidate([make_memory("第二次")])
        stats = consolidator.get_consolidation_stats()
        assert stats["total_consolidations"] == 2


# ============================================================
# ConsolidationResult Tests
# ============================================================

class TestConsolidationResult:
    """整合结果测试"""

    def test_to_dict(self):
        result = ConsolidationResult(
            consolidated=[make_memory("保留")],
            merged=[],
            archived=[],
            clusters=[],
            stats={"total_input": 1, "total_output": 1},
        )
        d = result.to_dict()
        assert "consolidated_count" in d
        assert "stats" in d
        assert d["stats"]["total_input"] == 1

    def test_summary_text(self):
        result = ConsolidationResult(
            consolidated=[make_memory("保留")],
            merged=[make_memory("合并")],
            archived=[make_memory("归档")],
            clusters=[],
            stats={},
        )
        text = result.summary_text()
        assert "保留" in text or "1" in text


# ============================================================
# SemanticCluster Tests
# ============================================================

class TestSemanticCluster:
    """语义聚类测试"""

    def test_create_cluster(self):
        cluster = SemanticCluster(
            cluster_id="c1",
            memories=[make_memory("测试")],
            summary="测试聚类",
            centroid_content="测试",
            avg_similarity=0.8,
        )
        assert cluster.cluster_id == "c1"
        assert len(cluster.memories) == 1
        assert cluster.avg_similarity == 0.8
