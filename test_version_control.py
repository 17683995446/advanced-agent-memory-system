"""
S3: 记忆版本控制与审计系统 - 专项测试

测试 MemoryVersionControl 的完整功能：
1. 版本记录
2. 版本历史查询
3. 版本回滚
4. 版本对比
5. 审计日志
6. 自动清理
"""

import time

import pytest

from memory_system.core.memory_version_control import (
    ChangeType,
    MemoryVersionControl,
    VersionControlConfig,
)


@pytest.fixture
def vc():
    """创建版本控制器实例"""
    config = VersionControlConfig(
        max_versions_per_memory=5,
        keep_forever_versions=2,
        auto_cleanup=True,
        audit_all_changes=True,
    )
    return MemoryVersionControl(config=config)


class TestRecordChange:
    """版本记录测试"""

    def test_record_create(self, vc):
        """记录创建变更"""
        version = vc.record_change(
            memory_id="mem1",
            change_type=ChangeType.CREATE,
            content_before=None,
            content_after="Initial content",
        )

        assert version.memory_id == "mem1"
        assert version.change_type == ChangeType.CREATE
        assert version.content_after == "Initial content"
        assert version.version_id is not None

    def test_record_update(self, vc):
        """记录更新变更"""
        version = vc.record_change(
            memory_id="mem1",
            change_type=ChangeType.UPDATE,
            content_before="Old content",
            content_after="New content",
            changed_by="user1",
            change_reason="Fixed typo",
        )

        assert version.content_before == "Old content"
        assert version.content_after == "New content"
        assert version.changed_by == "user1"
        assert version.change_reason == "Fixed typo"

    def test_record_delete(self, vc):
        """记录删除变更"""
        version = vc.record_change(
            memory_id="mem1",
            change_type=ChangeType.DELETE,
            content_before="Content to delete",
            content_after=None,
        )

        assert version.change_type == ChangeType.DELETE
        assert version.content_after is None


class TestVersionHistory:
    """版本历史测试"""

    def test_get_version_history(self, vc):
        """获取版本历史"""
        vc.record_change("mem1", ChangeType.CREATE, None, "v1")
        vc.record_change("mem1", ChangeType.UPDATE, "v1", "v2")
        vc.record_change("mem1", ChangeType.UPDATE, "v2", "v3")

        history = vc.get_version_history("mem1")

        assert len(history) == 3
        assert history[0].content_after == "v1"
        assert history[2].content_after == "v3"

    def test_get_version(self, vc):
        """获取特定版本"""
        v1 = vc.record_change("mem1", ChangeType.CREATE, None, "content1")

        found = vc.get_version("mem1", v1.version_id)

        assert found is not None
        assert found.version_id == v1.version_id

    def test_get_version_not_found(self, vc):
        """获取不存在的版本"""
        found = vc.get_version("mem1", "nonexistent")

        assert found is None

    def test_get_latest_version(self, vc):
        """获取最新版本"""
        vc.record_change("mem1", ChangeType.CREATE, None, "v1")
        vc.record_change("mem1", ChangeType.UPDATE, "v1", "v2")

        latest = vc.get_latest_version("mem1")

        assert latest.content_after == "v2"


class TestRollback:
    """版本回滚测试"""

    def test_rollback_to_version(self, vc):
        """回滚到指定版本"""
        v1 = vc.record_change("mem1", ChangeType.CREATE, None, "version1")
        vc.record_change("mem1", ChangeType.UPDATE, "version1", "version2")

        result = vc.rollback_to_version("mem1", v1.version_id)

        assert result == "version1"

        # 验证回滚被记录为新版本
        latest = vc.get_latest_version("mem1")
        assert latest.content_after == "version1"
        assert "Rollback" in latest.change_reason

    def test_rollback_nonexistent_version(self, vc):
        """回滚到不存在的版本"""
        result = vc.rollback_to_version("mem1", "nonexistent")

        assert result is None


class TestCompareVersions:
    """版本对比测试"""

    def test_compare_different_versions(self, vc):
        """对比不同版本"""
        v1 = vc.record_change("mem1", ChangeType.CREATE, None, "line1\nline2")
        v2 = vc.record_change("mem1", ChangeType.UPDATE, "line1\nline2", "line1\nline3")

        comparison = vc.compare_versions("mem1", v1.version_id, v2.version_id)

        assert "error" not in comparison
        assert comparison["version1"]["content"] == "line1\nline2"
        assert comparison["version2"]["content"] == "line1\nline3"
        assert comparison["content_diff"]["type"] == "modified"

    def test_compare_identical_versions(self, vc):
        """对比相同内容"""
        v1 = vc.record_change("mem1", ChangeType.CREATE, None, "same content")

        comparison = vc.compare_versions("mem1", v1.version_id, v1.version_id)

        assert comparison["content_diff"]["type"] == "identical"


class TestAuditLog:
    """审计日志测试"""

    def test_audit_log_recorded(self, vc):
        """审计日志应被记录"""
        vc.record_change("mem1", ChangeType.CREATE, None, "content", changed_by="user1")

        logs = vc.get_audit_log()

        assert len(logs) == 1
        assert logs[0]["memory_id"] == "mem1"
        assert logs[0]["changed_by"] == "user1"

    def test_audit_log_filter_by_memory(self, vc):
        """按记忆筛选审计日志"""
        vc.record_change("mem1", ChangeType.CREATE, None, "content1")
        vc.record_change("mem2", ChangeType.CREATE, None, "content2")

        logs = vc.get_audit_log(memory_id="mem1")

        assert len(logs) == 1
        assert logs[0]["memory_id"] == "mem1"

    def test_audit_log_filter_by_change_type(self, vc):
        """按变更类型筛选审计日志"""
        vc.record_change("mem1", ChangeType.CREATE, None, "content")
        vc.record_change("mem1", ChangeType.UPDATE, "content", "updated")

        logs = vc.get_audit_log(change_type=ChangeType.UPDATE)

        assert len(logs) == 1
        assert logs[0]["change_type"] == "update"


class TestAutoCleanup:
    """自动清理测试"""

    def test_old_versions_cleaned(self, vc):
        """旧版本应被自动清理"""
        # 创建超过 max_versions_per_memory 的版本
        for i in range(7):
            vc.record_change("mem1", ChangeType.UPDATE, f"v{i}", f"v{i+1}")

        history = vc.get_version_history("mem1")

        # 应该只保留 max_versions_per_memory=5 个
        assert len(history) == 5

    def test_keep_forever_versions_preserved(self, vc):
        """keep_forever_versions 应始终保留"""
        # 这个测试验证清理逻辑保留最新的版本
        for i in range(10):
            vc.record_change("mem1", ChangeType.UPDATE, f"v{i}", f"v{i+1}")

        history = vc.get_version_history("mem1")

        # 应该保留最新的5个
        assert len(history) == 5
        assert history[-1].content_after == "v10"


class TestStatistics:
    """统计信息测试"""

    def test_empty_statistics(self, vc):
        """空统计应返回默认值"""
        stats = vc.get_statistics()

        assert stats["total_memories_with_versions"] == 0
        assert stats["total_versions"] == 0
        assert stats["audit_log_entries"] == 0

    def test_statistics_after_changes(self, vc):
        """变更后统计应更新"""
        vc.record_change("mem1", ChangeType.CREATE, None, "content1")
        vc.record_change("mem1", ChangeType.UPDATE, "content1", "content2")
        vc.record_change("mem2", ChangeType.CREATE, None, "content3")

        stats = vc.get_statistics()

        assert stats["total_memories_with_versions"] == 2
        assert stats["total_versions"] == 3
        assert stats["audit_log_entries"] == 3
        assert stats["change_type_distribution"]["create"] == 2
        assert stats["change_type_distribution"]["update"] == 1


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_history(self, vc):
        """空历史"""
        history = vc.get_version_history("nonexistent")

        assert history == []

    def test_no_latest_version(self, vc):
        """没有版本时获取最新"""
        latest = vc.get_latest_version("nonexistent")

        assert latest is None

    def test_metadata_changes(self, vc):
        """元数据变更记录"""
        version = vc.record_change(
            "mem1",
            ChangeType.UPDATE,
            "content",
            "content",
            metadata_changes={"importance": (0.5, 0.8), "tags": (["a"], ["a", "b"])},
        )

        assert version.metadata_changes["importance"] == (0.5, 0.8)
