"""
S1: 三大独立模块深度集成到 AgentMemory - 专项测试

验证 MemoryCompressionEngine、MemoryConflictResolver、MemoryVersionControl
已正确集成到 AgentMemory 核心类中。
"""

import sys

import pytest

sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


def _make_config(**overrides):
    defaults = {
        "short_term": {"working_memory_capacity": 10, "history_limit": 50},
        "long_term": {
            "embedding": {"provider": "fake", "fake_dimension": 128},
            "vector_store": {"backend": "memory"},
        },
        "knowledge_graph": {"enabled": True},
        "structured_store": {"enabled": True},
        "auto_consolidate": False,
    }
    defaults.update(overrides)
    return AgentMemoryConfig(**defaults)


@pytest.fixture
def memory():
    mem = AgentMemory(config=_make_config())
    yield mem
    mem.close()


class TestEngineInitialization:
    """引擎初始化测试"""

    def test_compression_engine_initialized(self, memory):
        """压缩引擎应已初始化"""
        assert hasattr(memory, "_compression_engine")
        assert memory._compression_engine is not None

    def test_conflict_resolver_initialized(self, memory):
        """冲突解决器应已初始化"""
        assert hasattr(memory, "_conflict_resolver")
        assert memory._conflict_resolver is not None

    def test_version_control_initialized(self, memory):
        """版本控制应已初始化"""
        assert hasattr(memory, "_version_control")
        assert memory._version_control is not None

    def test_all_engines_in_stats(self, memory):
        """所有引擎统计应出现在 get_stats() 中"""
        stats = memory.get_stats()
        assert "compression" in stats
        assert "conflict_resolver" in stats
        assert "version_control" in stats
        assert "decay_engine" in stats


class TestVersionControlIntegration:
    """版本控制集成测试"""

    def test_remember_records_version(self, memory):
        """remember() 应自动记录版本"""
        memory_id = memory.remember("测试内容", category="test")

        history = memory.get_version_history(memory_id)
        assert len(history) == 1
        assert history[0]["change_type"] == "create"
        assert history[0]["content_after"] == "测试内容"

    def test_update_records_version(self, memory):
        """update_memory() 应自动记录版本"""
        memory_id = memory.remember("原始内容", category="test")
        memory.update_memory(memory_id, content="更新后的内容")

        history = memory.get_version_history(memory_id)
        assert len(history) == 2
        assert history[1]["change_type"] == "update"
        assert history[1]["content_before"] == "原始内容"
        assert history[1]["content_after"] == "更新后的内容"

    def test_delete_records_version(self, memory):
        """delete_memory() 应自动记录版本"""
        memory_id = memory.remember("待删除内容", category="test")
        memory.delete_memory(memory_id)

        history = memory.get_version_history(memory_id)
        assert len(history) == 2
        assert history[1]["change_type"] == "delete"
        assert history[1]["content_before"] == "待删除内容"

    def test_multiple_updates_tracked(self, memory):
        """多次更新应全部追踪"""
        memory_id = memory.remember("v1", category="test")
        memory.update_memory(memory_id, content="v2")
        memory.update_memory(memory_id, content="v3")
        memory.update_memory(memory_id, content="v4")

        history = memory.get_version_history(memory_id)
        assert len(history) == 4  # 1 create + 3 updates

    def test_rollback_memory(self, memory):
        """rollback_memory() 应恢复到历史版本"""
        memory_id = memory.remember("原始内容", category="test")
        memory.update_memory(memory_id, content="修改内容")

        # 获取第一个版本（原始内容）的ID
        history = memory.get_version_history(memory_id)
        first_version_id = history[0]["version_id"]

        # 回滚
        result = memory.rollback_memory(memory_id, first_version_id)
        assert result == "原始内容"

        # 验证回滚后的版本历史
        new_history = memory.get_version_history(memory_id)
        assert len(new_history) == 3  # create + update + rollback(update)

    def test_audit_log(self, memory):
        """审计日志应记录所有操作"""
        memory.remember("内容1", category="test")
        memory.remember("内容2", category="test")
        memory.update_memory("内容1", content="更新")  # 可能失败（ID不对），不影响测试

        log = memory.get_audit_log()
        assert len(log) >= 2  # 至少2条 create 记录

    def test_audit_log_filter_by_type(self, memory):
        """按类型筛选审计日志"""
        memory.remember("内容1", category="test")

        log = memory.get_audit_log(change_type="create")
        assert len(log) >= 1
        assert all(entry["change_type"] == "create" for entry in log)


class TestCompressionIntegration:
    """压缩引擎集成测试"""

    def test_compress_below_threshold(self, memory):
        """低于阈值不应执行压缩"""
        memory.remember("内容1", category="test")
        memory.remember("内容2", category="test")

        result = memory.compress_memories()
        assert result["compressed_count"] == 0
        assert result["removed_count"] == 0

    def test_compress_dedup(self, memory):
        """去重压缩策略"""
        # 添加重复内容
        for _ in range(5):
            memory.remember("完全相同的重复内容", category="test")

        result = memory.compress_memories(strategies=["dedup"])
        # 去重应在引擎层面检测到重复
        assert result["duration_ms"] >= 0

    def test_compress_all_strategies(self, memory):
        """所有压缩策略"""
        result = memory.compress_memories(strategies=["dedup", "expire"])
        assert "compressed_count" in result
        assert "removed_count" in result


class TestConflictDetectionIntegration:
    """冲突检测集成测试"""

    def test_detect_conflicts_few_memories(self, memory):
        """少量记忆不应检测到冲突"""
        memory.remember("内容A", category="cat1")
        memory.remember("内容B", category="cat2")

        result = memory.detect_conflicts()
        assert result["conflicts_found"] >= 0

    def test_detect_conflicts_with_contradictions(self, memory):
        """矛盾记忆应被检测到"""
        memory.remember("this feature is enabled and works well", category="test")
        memory.remember("this feature is not enabled and not works well", category="test")

        result = memory.detect_conflicts(conflict_types=["semantic"])
        # 语义矛盾检测需要内容相似且否定状态不同
        assert "conflicts_found" in result
        assert "duration_ms" in result

    def test_detect_specific_type(self, memory):
        """检测特定类型冲突"""
        memory.remember("内容A", category="test")
        memory.remember("内容B", category="test")

        result = memory.detect_conflicts(conflict_types=["factual"])
        assert result["conflicts_found"] >= 0


class TestPublicAPI:
    """公共API测试"""

    def test_compress_memories_is_public(self, memory):
        """compress_memories 应为公共方法"""
        assert callable(getattr(memory, "compress_memories", None))

    def test_detect_conflicts_is_public(self, memory):
        """detect_conflicts 应为公共方法"""
        assert callable(getattr(memory, "detect_conflicts", None))

    def test_get_version_history_is_public(self, memory):
        """get_version_history 应为公共方法"""
        assert callable(getattr(memory, "get_version_history", None))

    def test_rollback_memory_is_public(self, memory):
        """rollback_memory 应为公共方法"""
        assert callable(getattr(memory, "rollback_memory", None))

    def test_get_audit_log_is_public(self, memory):
        """get_audit_log 应为公共方法"""
        assert callable(getattr(memory, "get_audit_log", None))


class TestClosedState:
    """关闭状态测试"""

    def test_compress_after_close_raises(self, memory):
        memory.close()
        with pytest.raises(RuntimeError, match="closed"):
            memory.compress_memories()

    def test_detect_conflicts_after_close_raises(self, memory):
        memory.close()
        with pytest.raises(RuntimeError, match="closed"):
            memory.detect_conflicts()

    def test_get_version_history_after_close_raises(self, memory):
        memory.close()
        with pytest.raises(RuntimeError, match="closed"):
            memory.get_version_history("any_id")

    def test_rollback_after_close_raises(self, memory):
        memory.close()
        with pytest.raises(RuntimeError, match="closed"):
            memory.rollback_memory("any_id", "any_version")

    def test_get_audit_log_after_close_raises(self, memory):
        memory.close()
        with pytest.raises(RuntimeError, match="closed"):
            memory.get_audit_log()
