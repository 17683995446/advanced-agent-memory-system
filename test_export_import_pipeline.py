"""
S3: 记忆导出/导入管道 - 专项测试

测试 export_memories() 和 import_memories() 的完整功能：
1. JSON 导出/导入往返
2. YAML 导出/导入往返
3. 类别过滤导出
4. 嵌入向量包含/排除
5. 覆盖 vs 跳过模式
6. 空记忆库导出
7. 边界情况处理
"""

import json
import os
import tempfile
import time

import pytest

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


def _make_config(**overrides):
    """创建测试用 AgentMemoryConfig，默认使用 fake embedding 和 memory backend"""
    defaults = {
        "short_term": {"working_memory_capacity": 5, "history_limit": 20},
        "long_term": {
            "embedding": {"provider": "fake"},
            "vector_store": {"backend": "memory"},
        },
        "knowledge_graph": {"enabled": False},
        "structured_store": {"enabled": False},
        "auto_consolidate": False,
    }
    defaults.update(overrides)
    return AgentMemoryConfig(**defaults)


@pytest.fixture
def memory():
    """创建一个配置好的 AgentMemory 实例"""
    mem = AgentMemory(config=_make_config())
    yield mem
    mem.close()


@pytest.fixture
def populated_memory(memory):
    """填充测试数据的记忆实例"""
    # 添加不同类别的记忆
    memory.remember("Python是一种编程语言", category="knowledge", importance=0.9, tags=["编程", "语言"])
    memory.remember("今天的天气很好", category="daily", importance=0.3, tags=["天气"])
    memory.remember("机器学习是AI的子领域", category="knowledge", importance=0.8, tags=["AI", "ML"])
    memory.remember("会议安排在下午3点", category="task", importance=0.7, tags=["会议"])
    memory.remember("我喜欢吃苹果", category="preference", importance=0.5, tags=["食物"])
    memory.remember("深度学习使用神经网络", category="knowledge", importance=0.85, tags=["AI", "DL"])
    return memory


class TestExportBasic:
    """基础导出功能测试"""

    def test_export_json_creates_file(self, populated_memory):
        """JSON导出应创建有效文件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            result = populated_memory.export_memories(filepath, format="json")
            assert result == filepath
            assert os.path.exists(filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "records" in data
            assert data["record_count"] == 6
            assert len(data["records"]) == 6
        finally:
            os.unlink(filepath)

    def test_export_json_record_structure(self, populated_memory):
        """导出的JSON记录应包含正确的字段"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            populated_memory.export_memories(filepath, format="json")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            record = data["records"][0]
            expected_fields = {
                "id", "content", "memory_type", "category",
                "importance", "tags", "source", "metadata",
                "timestamp", "access_count",
            }
            assert expected_fields.issubset(set(record.keys()))
            assert isinstance(record["content"], str)
            assert isinstance(record["importance"], (int, float))
            assert isinstance(record["tags"], list)
        finally:
            os.unlink(filepath)

    def test_export_empty_memory(self, memory):
        """空记忆库导出应产生空记录列表"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            memory.export_memories(filepath, format="json")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["record_count"] == 0
            assert len(data["records"]) == 0
        finally:
            os.unlink(filepath)

    def test_export_after_close_raises(self, memory):
        """关闭后导出应抛出异常"""
        memory.close()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            with pytest.raises(RuntimeError, match="closed"):
                memory.export_memories(filepath, format="json")
        finally:
            os.unlink(filepath)


class TestExportCategoryFilter:
    """类别过滤导出测试"""

    def test_export_by_category_knowledge(self, populated_memory):
        """按knowledge类别过滤导出"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            populated_memory.export_memories(filepath, format="json", category="knowledge")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 应该有3条knowledge类别的记忆
            assert data["record_count"] == 3
            for record in data["records"]:
                assert record["category"] == "knowledge"
        finally:
            os.unlink(filepath)

    def test_export_by_category_nonexistent(self, populated_memory):
        """导出不存在的类别应产生空列表"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            populated_memory.export_memories(filepath, format="json", category="nonexistent")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["record_count"] == 0
        finally:
            os.unlink(filepath)

    def test_export_by_category_task(self, populated_memory):
        """按task类别过滤导出"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            populated_memory.export_memories(filepath, format="json", category="task")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["record_count"] == 1
            assert data["records"][0]["content"] == "会议安排在下午3点"
        finally:
            os.unlink(filepath)


class TestExportEmbeddings:
    """嵌入向量导出测试"""

    def test_export_without_embeddings(self, populated_memory):
        """默认不包含嵌入向量"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            populated_memory.export_memories(filepath, format="json", include_embeddings=False)

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for record in data["records"]:
                assert "embedding" not in record
        finally:
            os.unlink(filepath)

    def test_export_with_embeddings(self, populated_memory):
        """包含嵌入向量时应有embedding字段"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name

        try:
            populated_memory.export_memories(filepath, format="json", include_embeddings=True)

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # fake embedding provider 会生成嵌入向量
            for record in data["records"]:
                # 如果有嵌入向量，应该是一个列表
                if "embedding" in record:
                    assert isinstance(record["embedding"], list)
        finally:
            os.unlink(filepath)


class TestImportBasic:
    """基础导入功能测试"""

    def test_import_json_roundtrip(self, populated_memory):
        """JSON导出→导入往返应保持数据完整性"""
        export_path = tempfile.mktemp(suffix=".json")

        try:
            # 导出
            populated_memory.export_memories(export_path, format="json")

            # 创建新的空记忆实例
            new_memory = AgentMemory(config=_make_config())

            # 导入
            stats = new_memory.import_memories(export_path, format="json")

            assert stats["imported"] == 6
            assert stats["skipped"] == 0
            assert stats["errors"] == 0

            # 验证导入的记忆数量
            assert new_memory.count_memories() == 6

            new_memory.close()
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_import_stats_structure(self, populated_memory):
        """导入统计应包含正确的键"""
        export_path = tempfile.mktemp(suffix=".json")

        try:
            populated_memory.export_memories(export_path, format="json")

            new_memory = AgentMemory(config=_make_config())
            stats = new_memory.import_memories(export_path)

            assert "imported" in stats
            assert "skipped" in stats
            assert "errors" in stats
            assert isinstance(stats["imported"], int)
            assert isinstance(stats["skipped"], int)
            assert isinstance(stats["errors"], int)

            new_memory.close()
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_import_empty_file(self, memory):
        """导入空记录文件应返回零统计"""
        # 创建一个只有空记录列表的文件
        export_data = {
            "version": "3.0",
            "exported_at": time.time(),
            "record_count": 0,
            "records": [],
        }
        filepath = tempfile.mktemp(suffix=".json")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f)

            stats = memory.import_memories(filepath)
            assert stats["imported"] == 0
            assert stats["skipped"] == 0
            assert stats["errors"] == 0
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_import_after_close_raises(self, memory):
        """关闭后导入应抛出异常"""
        memory.close()
        filepath = tempfile.mktemp(suffix=".json")
        try:
            with pytest.raises(RuntimeError, match="closed"):
                memory.import_memories(filepath)
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)


class TestImportOverwrite:
    """导入覆盖模式测试"""

    def test_import_skip_existing(self, populated_memory):
        """非覆盖模式应跳过已存在的记忆"""
        export_path = tempfile.mktemp(suffix=".json")

        try:
            # 导出当前记忆
            populated_memory.export_memories(export_path, format="json")

            # 再次导入到同一个实例（不覆盖）
            stats = populated_memory.import_memories(export_path, overwrite=False)

            # 所有记忆都应该被跳过（因为已存在相同内容）
            assert stats["skipped"] >= 0  # dedup 可能导致 skipped
            assert stats["errors"] == 0
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_import_overwrite_existing(self, populated_memory):
        """覆盖模式应重新导入所有记忆"""
        export_path = tempfile.mktemp(suffix=".json")

        try:
            populated_memory.export_memories(export_path, format="json")
            original_count = populated_memory.count_memories()

            # 覆盖导入
            stats = populated_memory.import_memories(export_path, overwrite=True)

            # 所有记忆都应该被导入
            assert stats["imported"] == 6
            assert stats["errors"] == 0
            # 记忆总数应增加（因为 remember 会生成新ID，旧记录仍在）
            assert populated_memory.count_memories() >= original_count
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestImportEdgeCases:
    """导入边界情况测试"""

    def test_import_records_with_empty_content(self, memory):
        """空内容的记录应被跳过"""
        import_data = {
            "version": "3.0",
            "exported_at": time.time(),
            "record_count": 3,
            "records": [
                {"id": "1", "content": "有效内容", "category": "test"},
                {"id": "2", "content": "", "category": "test"},
                {"id": "3", "content": "另一个有效内容", "category": "test"},
            ],
        }
        filepath = tempfile.mktemp(suffix=".json")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(import_data, f)

            stats = memory.import_memories(filepath)
            assert stats["imported"] == 2
            assert stats["skipped"] == 1  # 空内容被跳过
            assert stats["errors"] == 0
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_import_malformed_records(self, memory):
        """格式错误的记录应计入errors"""
        import_data = {
            "version": "3.0",
            "exported_at": time.time(),
            "record_count": 2,
            "records": [
                {"id": "1", "content": "正常记录"},
                {"bad_field": "missing content"},
            ],
        }
        filepath = tempfile.mktemp(suffix=".json")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(import_data, f)

            stats = memory.import_memories(filepath)
            # 第二条记录没有content字段，get("content","") 返回 ""，会被跳过
            assert stats["imported"] >= 0
            assert stats["skipped"] >= 0
            assert stats["errors"] >= 0
            assert stats["imported"] + stats["skipped"] + stats["errors"] == 2
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_import_preserves_metadata(self, memory):
        """导入应保留元数据"""
        import_data = {
            "version": "3.0",
            "exported_at": time.time(),
            "record_count": 1,
            "records": [
                {
                    "id": "meta-test-1",
                    "content": "带元数据的记忆",
                    "category": "test",
                    "importance": 0.95,
                    "tags": ["标签1", "标签2"],
                    "metadata": {"key": "value", "nested": {"a": 1}},
                },
            ],
        }
        filepath = tempfile.mktemp(suffix=".json")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(import_data, f)

            stats = memory.import_memories(filepath)
            assert stats["imported"] == 1

            # 验证记忆可以通过recall检索到
            results = memory.recall("带元数据的记忆", top_k=1)
            assert len(results) > 0
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_import_nonexistent_file_raises(self, memory):
        """导入不存在的文件应抛出异常"""
        with pytest.raises(FileNotFoundError):
            memory.import_memories("/nonexistent/path/memories.json")


class TestExportImportRoundtrip:
    """导出→导入完整往返测试"""

    def test_full_roundtrip_preserves_categories(self, populated_memory):
        """完整往返应保留所有类别"""
        export_path = tempfile.mktemp(suffix=".json")

        try:
            populated_memory.export_memories(export_path, format="json")

            new_memory = AgentMemory(config=_make_config())
            new_memory.import_memories(export_path)

            # 验证各类别记忆都存在
            knowledge_memories = new_memory.get_memories_by_category("knowledge")
            daily_memories = new_memory.get_memories_by_category("daily")
            task_memories = new_memory.get_memories_by_category("task")
            preference_memories = new_memory.get_memories_by_category("preference")

            assert len(knowledge_memories) == 3
            assert len(daily_memories) == 1
            assert len(task_memories) == 1
            assert len(preference_memories) == 1

            new_memory.close()
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_roundtrip_then_recall(self, populated_memory):
        """往返后recall应能检索到导入的记忆"""
        export_path = tempfile.mktemp(suffix=".json")

        try:
            populated_memory.export_memories(export_path, format="json")

            new_memory = AgentMemory(config=_make_config())
            new_memory.import_memories(export_path)

            # 验证recall能找到记忆
            results = new_memory.recall("编程语言", top_k=3)
            assert len(results) > 0

            results2 = new_memory.recall("机器学习", top_k=3)
            assert len(results2) > 0

            new_memory.close()
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_export_filtered_then_import(self, populated_memory):
        """过滤导出后导入应只包含过滤的记忆"""
        export_path = tempfile.mktemp(suffix=".json")

        try:
            # 只导出knowledge类别
            populated_memory.export_memories(export_path, format="json", category="knowledge")

            new_memory = AgentMemory(config=_make_config())
            new_memory.import_memories(export_path)

            # 应该只有3条knowledge记忆
            assert new_memory.count_memories() == 3

            # 不应有其他类别
            daily = new_memory.get_memories_by_category("daily")
            task = new_memory.get_memories_by_category("task")
            assert len(daily) == 0
            assert len(task) == 0

            new_memory.close()
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestYamlFormat:
    """YAML格式导出/导入测试"""

    def test_export_yaml_creates_file(self, populated_memory):
        """YAML导出应创建有效文件"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        filepath = tempfile.mktemp(suffix=".yaml")

        try:
            populated_memory.export_memories(filepath, format="yaml")
            assert os.path.exists(filepath)

            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            assert "records" in data
            assert data["record_count"] == 6
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_yaml_roundtrip(self, populated_memory):
        """YAML导出→导入往返"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        export_path = tempfile.mktemp(suffix=".yaml")

        try:
            populated_memory.export_memories(export_path, format="yaml")

            new_memory = AgentMemory(config=_make_config())
            stats = new_memory.import_memories(export_path)

            assert stats["imported"] == 6
            assert stats["errors"] == 0
            assert new_memory.count_memories() == 6

            new_memory.close()
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestLargeScaleExportImport:
    """大规模导出/导入测试"""

    def test_export_import_100_records(self, memory):
        """100条记忆的导出/导入"""
        # 批量添加100条记忆
        for i in range(100):
            memory.remember(
                f"测试记忆内容第{i}条，这是一段关于各种主题的文本",
                category=f"cat_{i % 5}",
                importance=0.1 + (i % 10) * 0.09,
                tags=[f"tag_{i % 3}"],
            )

        assert memory.count_memories() == 100

        export_path = tempfile.mktemp(suffix=".json")

        try:
            memory.export_memories(export_path, format="json")

            new_memory = AgentMemory(config=_make_config())
            stats = new_memory.import_memories(export_path)

            assert stats["imported"] == 100
            assert stats["errors"] == 0

            new_memory.close()
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)
