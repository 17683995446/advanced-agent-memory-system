"""
S1: 高性能索引系统 - 专项测试

测试 MemoryIndexManager 的完整功能：
1. 索引构建
2. 倒排索引查询
3. 类别/标签索引查询
4. 时间范围查询
5. 重要性过滤
6. 多条件联合查询
7. 增量更新
8. 查询执行计划
"""

import time
from dataclasses import dataclass, field
from typing import Any

import pytest

from memory_system.core.memory_index_manager import (
    IndexConfig,
    MemoryIndexManager,
    QueryPlan,
)


@dataclass
class MockMemory:
    """模拟记忆记录"""
    id: str
    content: str
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5


@pytest.fixture
def index_mgr():
    """创建索引管理器实例"""
    config = IndexConfig(
        enable_inverted_index=True,
        enable_category_index=True,
        enable_tag_index=True,
        enable_time_index=True,
        enable_importance_index=True,
    )
    return MemoryIndexManager(config=config)


@pytest.fixture
def sample_memories():
    """创建样本记忆"""
    return [
        MockMemory("m1", "Django is a Python web framework", "web", ["python", "django"], time.time() - 1000, 0.9),
        MockMemory("m2", "Flask is a lightweight Python framework", "web", ["python", "flask"], time.time() - 2000, 0.8),
        MockMemory("m3", "React is a JavaScript library", "frontend", ["javascript", "react"], time.time() - 3000, 0.7),
        MockMemory("m4", "Vue is a progressive JavaScript framework", "frontend", ["javascript", "vue"], time.time() - 4000, 0.6),
        MockMemory("m5", "FastAPI is a modern Python web framework", "web", ["python", "fastapi"], time.time() - 5000, 0.95),
    ]


class TestIndexBuilding:
    """索引构建测试"""

    def test_build_index(self, index_mgr, sample_memories):
        """构建索引"""
        index_mgr.build_index(sample_memories)
        
        stats = index_mgr.get_statistics()
        assert stats["indexed_memories"] == 5
        assert stats["cached_metadata"] == 5
        assert stats["inverted_index_terms"] > 0

    def test_build_empty_index(self, index_mgr):
        """构建空索引"""
        index_mgr.build_index([])
        
        stats = index_mgr.get_statistics()
        assert stats["indexed_memories"] == 0
        assert stats["inverted_index_terms"] == 0


class TestInvertedIndexQuery:
    """倒排索引查询测试"""

    def test_query_single_keyword(self, index_mgr, sample_memories):
        """单关键词查询"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(keywords=["python"])
        assert len(results) == 3  # m1, m2, m5

    def test_query_multiple_keywords(self, index_mgr, sample_memories):
        """多关键词AND查询"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(keywords=["python", "framework"])
        assert len(results) == 3  # m1, m2, m5 (all have both words)

    def test_query_nonexistent_keyword(self, index_mgr, sample_memories):
        """查询不存在的关键词"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(keywords=["nonexistent"])
        assert len(results) == 0


class TestCategoryIndexQuery:
    """类别索引查询测试"""

    def test_query_by_category(self, index_mgr, sample_memories):
        """按类别查询"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(category="web")
        assert len(results) == 3  # m1, m2, m5

    def test_query_by_nonexistent_category(self, index_mgr, sample_memories):
        """查询不存在的类别"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(category="mobile")
        assert len(results) == 0


class TestTagIndexQuery:
    """标签索引查询测试"""

    def test_query_by_single_tag(self, index_mgr, sample_memories):
        """单标签查询"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(tags=["python"])
        assert len(results) == 3  # m1, m2, m5

    def test_query_by_multiple_tags(self, index_mgr, sample_memories):
        """多标签AND查询"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(tags=["python", "django"])
        assert len(results) == 1  # m1


class TestTimeRangeQuery:
    """时间范围查询测试"""

    def test_query_by_time_range(self, index_mgr, sample_memories):
        """时间范围查询"""
        index_mgr.build_index(sample_memories)
        
        now = time.time()
        results = index_mgr.query(time_range=(now - 2500, now))
        assert len(results) == 2  # m1, m2 (within last 2500 seconds)


class TestImportanceFilter:
    """重要性过滤测试"""

    def test_query_by_min_importance(self, index_mgr, sample_memories):
        """最小重要性过滤"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(min_importance=0.8)
        assert len(results) == 3  # m1 (0.9), m2 (0.8), m5 (0.95)


class TestCombinedQuery:
    """多条件联合查询测试"""

    def test_query_multiple_conditions(self, index_mgr, sample_memories):
        """多条件联合查询"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(
            keywords=["python"],
            category="web",
            tags=["django"],
        )
        # Only m1 has all: python keyword, web category, django tag
        assert len(results) == 1  # m1

    def test_query_with_limit(self, index_mgr, sample_memories):
        """限制返回数量"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(keywords=["python"], limit=2)
        assert len(results) <= 2


class TestIncrementalUpdate:
    """增量更新测试"""

    def test_add_new_memory(self, index_mgr, sample_memories):
        """添加新记忆"""
        index_mgr.build_index(sample_memories)
        
        new_memory = MockMemory("m6", "New Python framework", "web", ["python"], time.time(), 0.7)
        index_mgr.add_or_update(new_memory)
        
        results = index_mgr.query(keywords=["python"])
        assert len(results) == 4  # Now includes m6

    def test_update_existing_memory(self, index_mgr, sample_memories):
        """更新现有记忆"""
        index_mgr.build_index(sample_memories)
        
        # Update m1 with new content
        updated = MockMemory("m1", "Updated Django content", "web", ["python", "django"], time.time(), 0.9)
        index_mgr.add_or_update(updated)
        
        # Should still find it
        results = index_mgr.query(keywords=["updated"])
        assert "m1" in results

    def test_remove_memory(self, index_mgr, sample_memories):
        """移除记忆"""
        index_mgr.build_index(sample_memories)
        
        index_mgr.remove("m1")
        
        results = index_mgr.query(keywords=["python"])
        assert "m1" not in results
        assert len(results) == 2  # m2, m5


class TestQueryPlan:
    """查询执行计划测试"""

    def test_query_plan_with_keywords(self, index_mgr, sample_memories):
        """关键词查询计划"""
        index_mgr.build_index(sample_memories)
        
        plan = index_mgr.get_query_plan(keywords=["python"])
        assert "keyword_scan" in plan.strategy
        assert "inverted" in plan.index_used
        assert plan.estimated_cost > 0

    def test_query_plan_with_category(self, index_mgr, sample_memories):
        """类别查询计划"""
        index_mgr.build_index(sample_memories)
        
        plan = index_mgr.get_query_plan(category="web")
        assert "category_filter" in plan.strategy
        assert "category" in plan.index_used


class TestStatistics:
    """统计信息测试"""

    def test_empty_statistics(self, index_mgr):
        """空统计"""
        stats = index_mgr.get_statistics()
        assert stats["indexed_memories"] == 0
        assert stats["inverted_index_terms"] == 0

    def test_statistics_after_build(self, index_mgr, sample_memories):
        """构建后统计"""
        index_mgr.build_index(sample_memories)
        
        stats = index_mgr.get_statistics()
        assert stats["indexed_memories"] == 5
        assert stats["category_count"] == 2  # web, frontend
        assert stats["tag_count"] == 7  # python, django, flask, javascript, react, vue, fastapi


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_keywords(self, index_mgr, sample_memories):
        """空关键词列表"""
        index_mgr.build_index(sample_memories)
        
        results = index_mgr.query(keywords=[])
        assert len(results) == 5  # Returns all

    def test_case_insensitive(self, index_mgr, sample_memories):
        """大小写不敏感"""
        index_mgr.build_index(sample_memories)
        
        results_lower = index_mgr.query(keywords=["python"])
        results_upper = index_mgr.query(keywords=["PYTHON"])
        assert results_lower == results_upper

    def test_chinese_tokenization(self, index_mgr):
        """中文分词 - 当前实现将连续中文作为整体，查询需匹配完整片段"""
        memories = [
            MockMemory("m1", "这是一个中文测试内容", "test", ["中文"]),
        ]
        index_mgr.build_index(memories)

        # 查询完整中文句子（当前分词策略将连续中文作为整体）
        results = index_mgr.query(keywords=["这是一个中文测试内容"])
        assert len(results) == 1
