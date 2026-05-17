"""
S2: 记忆冲突检测与解决机制 - 专项测试

测试 MemoryConflictResolver 的完整功能：
1. 事实矛盾检测
2. 时间冲突检测
3. 来源冲突检测
4. 语义矛盾检测
5. 冲突解决策略
6. 自动解决机制
"""

import time
from dataclasses import dataclass, field
from typing import Any

import pytest

from memory_system.core.memory_conflict_resolver import (
    Conflict,
    ConflictConfig,
    ConflictResult,
    ConflictType,
    MemoryConflictResolver,
    ResolutionStrategy,
)


@dataclass
class MockMemory:
    """模拟记忆记录"""
    id: str
    content: str
    category: str = "general"
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    source: str = "unknown"
    timestamp: float = field(default_factory=time.time)


@pytest.fixture
def resolver():
    """创建冲突解决器实例"""
    config = ConflictConfig(
        similarity_threshold=0.3,
        contradiction_threshold=0.25,  # 降低阈值，使"是"/"不是"能触发冲突
        auto_resolve=False,
    )
    return MemoryConflictResolver(config=config)


@pytest.fixture
def auto_resolver():
    """创建自动解决冲突的解决器"""
    config = ConflictConfig(
        similarity_threshold=0.3,
        contradiction_threshold=0.25,
        auto_resolve=True,
        default_strategy=ResolutionStrategy.KEEP_NEWER,
    )
    return MemoryConflictResolver(config=config)


class TestFactualConflicts:
    """事实矛盾检测测试"""

    def test_detect_contradiction_yes_no(self, resolver):
        """检测是/否矛盾"""
        memories = [
            MockMemory("m1", "这个功能是启用的"),
            MockMemory("m2", "这个功能不是启用的"),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.FACTUAL])
        
        assert len(result.conflicts_found) == 1
        assert result.conflicts_found[0].conflict_type == ConflictType.FACTUAL

    def test_detect_contradiction_support_not(self, resolver):
        """检测支持/不支持矛盾"""
        memories = [
            MockMemory("m1", "Python支持多线程"),
            MockMemory("m2", "Python不支持多线程"),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.FACTUAL])
        
        assert len(result.conflicts_found) == 1

    def test_no_contradiction_same_meaning(self, resolver):
        """相同意思不应检测为矛盾"""
        memories = [
            MockMemory("m1", "这个功能是启用的"),
            MockMemory("m2", "这个功能是启用的"),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.FACTUAL])
        
        assert len(result.conflicts_found) == 0


class TestTemporalConflicts:
    """时间冲突检测测试"""

    def test_detect_temporal_conflict(self, resolver):
        """检测时间冲突 - 需要内容包含时间关键词且时间戳差异大"""
        now = time.time()
        yesterday = now - 86400 * 2  # 2天前
        
        memories = [
            MockMemory("m1", "今天功能启用了", timestamp=yesterday),
            MockMemory("m2", "今天功能禁用了", timestamp=now),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.TEMPORAL])
        
        # 时间冲突检测需要：都包含"今天"且时间戳差异>1天
        assert len(result.conflicts_found) == 1
        assert result.conflicts_found[0].conflict_type == ConflictType.TEMPORAL

    def test_no_temporal_conflict_same_time(self, resolver):
        """相同时间不应检测为冲突"""
        now = time.time()
        
        memories = [
            MockMemory("m1", "今天发生了某事", timestamp=now),
            MockMemory("m2", "今天发生了某事", timestamp=now),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.TEMPORAL])
        
        assert len(result.conflicts_found) == 0


class TestSourceConflicts:
    """来源冲突检测测试"""

    def test_detect_source_conflict(self, resolver):
        """检测来源冲突"""
        memories = [
            MockMemory("m1", "Python是解释型语言", source="doc_a"),
            MockMemory("m2", "Python是解释型语言", source="doc_b"),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.SOURCE])
        
        assert len(result.conflicts_found) == 1
        assert result.conflicts_found[0].conflict_type == ConflictType.SOURCE

    def test_no_source_conflict_same_source(self, resolver):
        """相同来源不应检测为冲突"""
        memories = [
            MockMemory("m1", "Python是解释型语言", source="doc_a"),
            MockMemory("m2", "Python是解释型语言", source="doc_a"),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.SOURCE])
        
        assert len(result.conflicts_found) == 0


class TestSemanticConflicts:
    """语义矛盾检测测试"""

    def test_detect_semantic_conflict_with_negation(self, resolver):
        """检测否定词导致的语义矛盾 - 使用英文内容确保相似度计算正确"""
        memories = [
            MockMemory("m1", "this feature can be used and works well"),
            MockMemory("m2", "this feature cannot be used and not works well"),
        ]

        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.SEMANTIC])

        # 语义冲突需要：内容相似度>=阈值 且 否定状态不同
        assert len(result.conflicts_found) == 1
        assert result.conflicts_found[0].conflict_type == ConflictType.SEMANTIC

    def test_detect_semantic_conflict_not_never(self, resolver):
        """检测英文否定词导致的语义矛盾"""
        memories = [
            MockMemory("m1", "This feature is enabled"),
            MockMemory("m2", "This feature is not enabled"),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.SEMANTIC])
        
        assert len(result.conflicts_found) == 1

    def test_no_semantic_conflict_both_negated(self, resolver):
        """都包含否定词不应检测为矛盾"""
        memories = [
            MockMemory("m1", "这个功能不可以使用"),
            MockMemory("m2", "这个功能不可以使用"),
        ]
        
        result = resolver.detect_conflicts(memories, conflict_types=[ConflictType.SEMANTIC])
        
        assert len(result.conflicts_found) == 0


class TestConflictResolution:
    """冲突解决策略测试"""

    def test_resolve_keep_newer(self, resolver):
        """测试保留较新策略"""
        now = time.time()
        
        memories = [
            MockMemory("m1", "旧记忆", timestamp=now - 100),
            MockMemory("m2", "新记忆", timestamp=now),
        ]
        
        conflict = Conflict(
            conflict_id="test",
            conflict_type=ConflictType.FACTUAL,
            memory_ids=["m1", "m2"],
            description="测试冲突",
            detected_at=now,
        )
        
        result = resolver.resolve_conflict(conflict, ResolutionStrategy.KEEP_NEWER, memories)
        
        assert "m2" in result  # 应保留m2（较新）
        assert conflict.resolved is True

    def test_resolve_keep_older(self, resolver):
        """测试保留较旧策略"""
        now = time.time()
        
        memories = [
            MockMemory("m1", "旧记忆", timestamp=now - 100),
            MockMemory("m2", "新记忆", timestamp=now),
        ]
        
        conflict = Conflict(
            conflict_id="test",
            conflict_type=ConflictType.FACTUAL,
            memory_ids=["m1", "m2"],
            description="测试冲突",
            detected_at=now,
        )
        
        result = resolver.resolve_conflict(conflict, ResolutionStrategy.KEEP_OLDER, memories)
        
        assert "m1" in result  # 应保留m1（较旧）

    def test_resolve_keep_importance(self, resolver):
        """测试保留高重要性策略"""
        now = time.time()
        
        memories = [
            MockMemory("m1", "低重要性", importance=0.3),
            MockMemory("m2", "高重要性", importance=0.9),
        ]
        
        conflict = Conflict(
            conflict_id="test",
            conflict_type=ConflictType.FACTUAL,
            memory_ids=["m1", "m2"],
            description="测试冲突",
            detected_at=now,
        )
        
        result = resolver.resolve_conflict(conflict, ResolutionStrategy.KEEP_HIGHER_IMPORTANCE, memories)
        
        assert "m2" in result  # 应保留m2（高重要性）
        assert "0.9" in result

    def test_resolve_merge(self, resolver):
        """测试合并策略"""
        conflict = Conflict(
            conflict_id="test",
            conflict_type=ConflictType.FACTUAL,
            memory_ids=["m1", "m2"],
            description="测试冲突",
            detected_at=time.time(),
        )
        
        result = resolver.resolve_conflict(conflict, ResolutionStrategy.MERGE)
        
        assert "Merge" in result
        assert conflict.resolved is True

    def test_resolve_delete_both(self, resolver):
        """测试删除两者策略"""
        conflict = Conflict(
            conflict_id="test",
            conflict_type=ConflictType.FACTUAL,
            memory_ids=["m1", "m2"],
            description="测试冲突",
            detected_at=time.time(),
        )
        
        result = resolver.resolve_conflict(conflict, ResolutionStrategy.DELETE_BOTH)
        
        assert "delete" in result.lower() or "delet" in result.lower() or "both" in result.lower()
        assert conflict.resolved is True


class TestAutoResolve:
    """自动解决机制测试"""

    def test_auto_resolve_source_conflict(self, auto_resolver):
        """来源冲突应自动解决"""
        memories = [
            MockMemory("m1", "Python是解释型语言", source="doc_a"),
            MockMemory("m2", "Python是解释型语言", source="doc_b"),
        ]
        
        result = auto_resolver.detect_conflicts(memories)
        
        assert len(result.auto_resolved) == 1
        assert len(result.manual_review) == 0

    def test_no_auto_resolve_factual_conflict(self, auto_resolver):
        """事实矛盾不应自动解决"""
        memories = [
            MockMemory("m1", "这个功能是启用的"),
            MockMemory("m2", "这个功能不是启用的"),
        ]
        
        result = auto_resolver.detect_conflicts(memories, conflict_types=[ConflictType.FACTUAL])
        
        assert len(result.auto_resolved) == 0
        assert len(result.manual_review) == 1


class TestConflictDeduplication:
    """冲突去重测试"""

    def test_deduplicate_same_pair(self, resolver):
        """相同记忆对的冲突应去重"""
        # 创建会触发多种冲突的记忆
        now = time.time()
        yesterday = now - 86400 * 2  # 2天前

        memories = [
            MockMemory("m1", "今天功能启用", source="a", timestamp=yesterday),
            MockMemory("m2", "今天功能不启用", source="b", timestamp=now),
        ]

        result = resolver.detect_conflicts(memories)

        # 应该有冲突（事实矛盾 + 时间冲突 + 来源冲突），但同一对记忆不应重复
        assert len(result.conflicts_found) >= 1

        # 检查没有重复的冲突ID
        conflict_ids = [c.conflict_id for c in result.conflicts_found]
        assert len(conflict_ids) == len(set(conflict_ids))


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_memories(self, resolver):
        """空记忆列表"""
        result = resolver.detect_conflicts([])
        
        assert len(result.conflicts_found) == 0

    def test_single_memory(self, resolver):
        """单条记忆"""
        result = resolver.detect_conflicts([MockMemory("m1", "唯一记忆")])
        
        assert len(result.conflicts_found) == 0

    def test_already_resolved_conflict(self, resolver):
        """已解决的冲突不应重复解决"""
        conflict = Conflict(
            conflict_id="test",
            conflict_type=ConflictType.FACTUAL,
            memory_ids=["m1", "m2"],
            description="测试冲突",
            detected_at=time.time(),
            resolved=True,
            resolution_result="Already resolved",
        )
        
        result = resolver.resolve_conflict(conflict, ResolutionStrategy.KEEP_NEWER)
        
        assert result == "Already resolved"


class TestStatistics:
    """统计信息测试"""

    def test_empty_statistics(self, resolver):
        """空统计应返回默认值"""
        stats = resolver.get_statistics()
        
        assert stats["total_conflicts_detected"] == 0
        assert stats["total_resolved"] == 0

    def test_statistics_after_detection(self, resolver):
        """检测后统计应更新"""
        memories = [
            MockMemory("m1", "this feature is enabled and works well"),
            MockMemory("m2", "this feature is not enabled and not works well"),
        ]

        resolver.detect_conflicts(memories)
        stats = resolver.get_statistics()

        assert stats["total_conflicts_detected"] >= 1

    def test_statistics_after_resolution(self, resolver):
        """解决后统计应更新"""
        memories = [
            MockMemory("m1", "是"),
            MockMemory("m2", "不是"),
        ]
        
        result = resolver.detect_conflicts(memories)
        resolver.resolve_conflict(result.conflicts_found[0], ResolutionStrategy.KEEP_NEWER)
        
        stats = resolver.get_statistics()
        
        assert stats["total_resolved"] == 1
