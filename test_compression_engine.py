"""
S1: 智能记忆压缩与摘要系统 - 专项测试

测试 MemoryCompressionEngine 的完整功能：
1. 过期记忆清理
2. 重复记忆去重
3. 相似记忆合并
4. 长记忆摘要生成
5. 压缩统计
6. 自动压缩触发
"""

import time
from dataclasses import dataclass, field
from typing import Any

import pytest

from memory_system.core.memory_compression_engine import (
    CompressionConfig,
    CompressionResult,
    CompressionStrategy,
    MemoryCompressionEngine,
)


@dataclass
class MockMemory:
    """模拟记忆记录"""
    id: str
    content: str
    category: str = "general"
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@pytest.fixture
def engine():
    """创建压缩引擎实例"""
    config = CompressionConfig(
        min_memories_to_compress=5,
        similarity_threshold=0.6,
        max_summary_length=100,
        min_content_length_to_summarize=100,
        max_age_days=30,
        low_importance_decay_days=7,
    )
    return MemoryCompressionEngine(config=config)


@pytest.fixture
def many_memories():
    """创建大量测试记忆"""
    return [
        MockMemory(f"m{i}", f"测试记忆内容{i}", category="test", tags=["tag1", "tag2"])
        for i in range(50)
    ]


class TestExpireOld:
    """过期记忆清理测试"""

    def test_remove_old_memories(self, engine):
        """应移除过期记忆"""
        now = time.time()
        old_time = now - 40 * 24 * 3600  # 40天前
        
        memories = [
            MockMemory("old1", "很旧的记忆", timestamp=old_time, importance=0.1),
            MockMemory("old2", "另一个旧记忆", timestamp=old_time, importance=0.2),
            MockMemory("new1", "新记忆", timestamp=now, importance=0.8),
            MockMemory("new2", "另一个新记忆", timestamp=now, importance=0.9),
            MockMemory("new3", "第三个新记忆", timestamp=now, importance=0.7),
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.EXPIRE_OLD])
        
        assert result.removed_count == 2  # 移除了2个旧记忆
        assert result.compressed_count == 0

    def test_keep_high_importance_old(self, engine):
        """高重要性旧记忆应保留"""
        now = time.time()
        old_time = now - 40 * 24 * 3600  # 40天前
        
        memories = [
            MockMemory("old_high", "重要旧记忆", timestamp=old_time, importance=0.9),
            MockMemory("old_low", "不重要旧记忆", timestamp=old_time, importance=0.1),
            MockMemory("m1", "普通记忆1", timestamp=now, importance=0.5),
            MockMemory("m2", "普通记忆2", timestamp=now, importance=0.5),
            MockMemory("m3", "普通记忆3", timestamp=now, importance=0.5),
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.EXPIRE_OLD])
        
        # 只有低重要性旧记忆被移除（importance < 0.3）
        # importance=0.9 的高重要性记忆保留，importance=0.1 的低重要性记忆移除
        assert result.removed_count == 1


class TestRemoveDuplicates:
    """重复记忆去重测试"""

    def test_remove_exact_duplicates(self, engine):
        """应移除完全重复的记忆"""
        memories = [
            MockMemory("m1", "完全相同的记忆内容"),
            MockMemory("m2", "完全相同的记忆内容"),  # 重复
            MockMemory("m3", "不同的记忆内容"),
            MockMemory("m4", "另一个不同内容"),
            MockMemory("m5", "完全相同的记忆内容"),  # 又一个重复
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.REMOVE_DUPLICATES])
        
        assert result.removed_count == 2  # 移除了2个重复

    def test_keep_unique_memories(self, engine):
        """唯一记忆应保留"""
        memories = [
            MockMemory("m1", "记忆内容1"),
            MockMemory("m2", "记忆内容2"),
            MockMemory("m3", "记忆内容3"),
            MockMemory("m4", "记忆内容4"),
            MockMemory("m5", "记忆内容5"),
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.REMOVE_DUPLICATES])
        
        assert result.removed_count == 0


class TestMergeSimilar:
    """相似记忆合并测试"""

    def test_merge_same_category_and_tags(self, engine):
        """相同类别和标签的记忆应被识别为相似"""
        memories = [
            MockMemory("m1", "内容A", category="api", tags=["http", "get"]),
            MockMemory("m2", "内容B", category="api", tags=["http", "get"]),
            MockMemory("m3", "内容C", category="api", tags=["http", "post"]),
            MockMemory("m4", "内容D", category="session", tags=["cookie"]),
            MockMemory("m5", "内容E", category="session", tags=["cookie"]),
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.MERGE_SIMILAR])
        
        # m1,m2 相似度 = 0.5(类别) + 0.5(标签) = 1.0 >= 0.6
        # m4,m5 相似度 = 0.5(类别) + 0(标签交集) = 0.5 < 0.6
        assert len(result.merged_groups) >= 1

    def test_no_merge_different_category(self, engine):
        """不同类别的记忆不应合并"""
        memories = [
            MockMemory("m1", "内容A", category="api", tags=["http"]),
            MockMemory("m2", "内容B", category="session", tags=["http"]),
            MockMemory("m3", "内容C", category="model", tags=["http"]),
            MockMemory("m4", "内容D", category="adapter", tags=["http"]),
            MockMemory("m5", "内容E", category="auth", tags=["http"]),
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.MERGE_SIMILAR])
        
        # 类别都不同，相似度只有标签部分 = 0.5 * 1 = 0.5 < 0.6
        assert len(result.merged_groups) == 0


class TestSummarize:
    """摘要生成测试"""

    def test_summarize_long_content(self, engine):
        """长内容应生成摘要"""
        long_content = "这是一个很长的记忆内容。" * 20  # 超过100字符
        
        memories = [
            MockMemory("m1", long_content),
            MockMemory("m2", long_content),
            MockMemory("m3", long_content),
            MockMemory("m4", long_content),
            MockMemory("m5", long_content),
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.SUMMARIZE])
        
        assert len(result.summaries_generated) == 5
        # 摘要应比原文短
        for mem_id, summary in result.summaries_generated:
            assert len(summary) < len(long_content)
            assert len(summary) <= engine.config.max_summary_length + 3  # +3 for "..."

    def test_skip_short_content(self, engine):
        """短内容不应生成摘要"""
        memories = [
            MockMemory("m1", "短内容1"),
            MockMemory("m2", "短内容2"),
            MockMemory("m3", "短内容3"),
            MockMemory("m4", "短内容4"),
            MockMemory("m5", "短内容5"),
        ]
        
        result = engine.compress_memories(memories, strategies=[CompressionStrategy.SUMMARIZE])
        
        assert len(result.summaries_generated) == 0


class TestFullCompression:
    """完整压缩流程测试"""

    def test_all_strategies_together(self, engine):
        """所有策略一起应用"""
        now = time.time()
        old_time = now - 40 * 24 * 3600
        long_content = "这是一个很长的记忆内容，需要生成摘要。" * 10
        
        memories = [
            MockMemory("old_dup", "重复内容", timestamp=old_time, importance=0.1),
            MockMemory("dup1", "重复内容"),  # 重复
            MockMemory("dup2", "重复内容"),  # 重复
            MockMemory("sim1", "相似A", category="api", tags=["http"]),
            MockMemory("sim2", "相似B", category="api", tags=["http"]),
            MockMemory("long1", long_content),
            MockMemory("long2", long_content),
            MockMemory("keep", "保留的记忆", category="unique", tags=["special"]),
            MockMemory("keep2", "另一个保留的", category="unique2", tags=["special2"]),
            MockMemory("keep3", "再一个保留的", category="unique3", tags=["special3"]),
        ]
        
        result = engine.compress_memories(memories)
        
        # 应有一些压缩发生
        assert result.removed_count > 0 or result.compressed_count > 0
        assert result.duration_ms > 0
        assert result.saved_bytes_estimate >= 0

    def test_below_threshold_no_compress(self, engine):
        """低于阈值不应压缩"""
        memories = [
            MockMemory("m1", "内容1"),
            MockMemory("m2", "内容2"),
            MockMemory("m3", "内容3"),
        ]
        
        result = engine.compress_memories(memories)
        
        assert result.removed_count == 0
        assert result.compressed_count == 0
        assert result.duration_ms == 0


class TestStatistics:
    """统计信息测试"""

    def test_empty_statistics(self, engine):
        """空统计应返回默认值"""
        stats = engine.get_statistics()
        
        assert stats["total_compressions"] == 0
        assert stats["total_removed"] == 0
        assert stats["total_saved_bytes"] == 0

    def test_statistics_after_compression(self, engine):
        """压缩后统计应更新"""
        memories = [
            MockMemory(f"m{i}", f"重复内容")  # 制造重复
            for i in range(10)
        ]
        
        engine.compress_memories(memories)
        
        stats = engine.get_statistics()
        
        assert stats["total_compressions"] == 1
        assert stats["total_removed"] == 9  # 9个重复被移除
        assert stats["last_compress_time"] is not None


class TestAutoCompress:
    """自动压缩测试"""

    def test_should_compress_above_threshold(self, engine):
        """超过阈值应触发压缩"""
        engine.config.auto_compress = True
        engine.config.compress_interval_hours = 1
        
        assert engine.should_compress(200) is True

    def test_should_not_compress_below_threshold(self, engine):
        """低于阈值不应触发"""
        engine.config.auto_compress = True
        
        assert engine.should_compress(3) is False

    def test_should_not_compress_if_disabled(self, engine):
        """禁用自动压缩时不触发"""
        engine.config.auto_compress = False
        
        assert engine.should_compress(1000) is False

    def test_respect_interval(self, engine):
        """应尊重压缩间隔"""
        engine.config.auto_compress = True
        engine.config.compress_interval_hours = 24
        engine._last_compress_time = time.time()  # 刚刚压缩过
        
        assert engine.should_compress(200) is False


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_memories(self, engine):
        """空记忆列表"""
        result = engine.compress_memories([])
        
        assert result.removed_count == 0
        assert result.compressed_count == 0

    def test_single_memory(self, engine):
        """单条记忆"""
        result = engine.compress_memories([MockMemory("m1", "唯一记忆")])
        
        assert result.removed_count == 0
        assert result.compressed_count == 0

    def test_callback_invoked(self, engine):
        """回调函数应被调用"""
        callback_called = False
        callback_ids = []
        
        def callback(ids):
            nonlocal callback_called, callback_ids
            callback_called = True
            callback_ids = ids
        
        engine.config.on_compress_callback = callback
        
        memories = [MockMemory(f"m{i}", f"内容{i}") for i in range(10)]
        engine.compress_memories(memories)
        
        assert callback_called is True
        assert len(callback_ids) > 0
