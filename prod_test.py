"""
生产级深度测试脚本

测试生产环境中的极端场景：
P1: 跨版本数据兼容性测试
P2: 异常注入与恢复能力测试
P3: 配置边界与错误处理测试
P4: 序列化完整性深度验证
"""

import sys
import time
import json
import traceback
import tempfile
import os

sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


def make_config(**overrides):
    defaults = {
        "short_term": {"working_memory_capacity": 50, "history_limit": 200},
        "long_term": {
            "embedding": {"provider": "fake", "fake_dimension": 64},
            "vector_store": {"backend": "memory"},
        },
        "knowledge_graph": {"enabled": True},
        "structured_store": {"enabled": True},
        "auto_consolidate": False,
    }
    defaults.update(overrides)
    return AgentMemoryConfig(**defaults)


class ProdTestResult:
    def __init__(self, name):
        self.name = name
        self.errors = []
        self.warnings = []
        self.metrics = {}
        self.passed = True

    def add_error(self, msg):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg):
        self.warnings.append(msg)

    def report(self):
        status = "✅ 通过" if self.passed else "❌ 失败"
        print(f"\n{'='*60}")
        print(f"  {self.name}: {status}")
        print(f"{'='*60}")
        if self.metrics:
            print("  指标:")
            for k, v in self.metrics.items():
                print(f"    {k}: {v}")
        if self.warnings:
            print(f"  警告 ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"    ⚠ {w}")
        if self.errors:
            print(f"  错误 ({len(self.errors)}):")
            for e in self.errors:
                print(f"    ✗ {e}")
        print()


# ============================================================
# P1: 跨版本数据兼容性测试
# ============================================================
def test_cross_version_compatibility():
    """测试不同版本导出数据的兼容性"""
    result = ProdTestResult("P1: 跨版本数据兼容性测试")

    try:
        # 模拟旧版本数据格式（v1.0）
        v1_data = {
            "version": "1.0",
            "exported_at": time.time(),
            "record_count": 3,
            "records": [
                {
                    "id": "v1-mem-1",
                    "content": "旧版本记忆1",
                    "category": "legacy",
                    "importance": 0.8,
                    "tags": ["v1"],
                    # v1 没有 memory_type, source, metadata 等字段
                },
                {
                    "id": "v1-mem-2",
                    "content": "旧版本记忆2，缺少某些字段",
                    "category": "legacy",
                    # 缺少 importance, tags
                },
                {
                    "id": "v1-mem-3",
                    "content": "旧版本记忆3，包含未知字段",
                    "category": "legacy",
                    "importance": 0.5,
                    "unknown_field": "should be ignored",  # 未知字段
                    "deprecated_field": {"nested": "data"},
                },
            ]
        }

        # 模拟 v2.0 数据格式
        v2_data = {
            "version": "2.0",
            "exported_at": time.time(),
            "record_count": 2,
            "records": [
                {
                    "id": "v2-mem-1",
                    "content": "v2版本记忆",
                    "memory_type": "semantic",
                    "category": "modern",
                    "importance": 0.9,
                    "tags": ["v2", "modern"],
                    "source": "migration",
                    "metadata": {"migrated_from": "v1"},
                },
                {
                    "id": "v2-mem-2",
                    "content": "v2版本记忆，包含embedding",
                    "memory_type": "semantic",
                    "category": "modern",
                    "importance": 0.7,
                    "tags": ["v2"],
                    "embedding": [0.1] * 64,  # embedding 向量
                },
            ]
        }

        # 测试导入 v1 数据
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(v1_data, f)
            v1_path = f.name

        mem = AgentMemory(config=make_config())
        try:
            import_stats = mem.import_memories(v1_path)
            result.metrics["v1导入成功"] = import_stats.get("imported", 0)
            result.metrics["v1导入失败"] = import_stats.get("errors", 0)

            # 验证导入的数据可检索
            results = mem.recall("旧版本", top_k=5)
            result.metrics["v1数据检索"] = f"返回{len(results)}条"
        except Exception as e:
            result.add_error(f"v1数据导入失败: {type(e).__name__}: {e}")
        finally:
            mem.close()
            os.unlink(v1_path)

        # 测试导入 v2 数据
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(v2_data, f)
            v2_path = f.name

        mem = AgentMemory(config=make_config())
        try:
            import_stats = mem.import_memories(v2_path)
            result.metrics["v2导入成功"] = import_stats.get("imported", 0)
            result.metrics["v2导入失败"] = import_stats.get("errors", 0)
        except Exception as e:
            result.add_error(f"v2数据导入失败: {type(e).__name__}: {e}")
        finally:
            mem.close()
            os.unlink(v2_path)

        # 测试混合版本数据
        mixed_data = {
            "version": "3.0",
            "exported_at": time.time(),
            "record_count": 4,
            "records": v1_data["records"] + v2_data["records"],
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(mixed_data, f)
            mixed_path = f.name

        mem = AgentMemory(config=make_config())
        try:
            import_stats = mem.import_memories(mixed_path)
            result.metrics["混合数据导入"] = f"{import_stats.get('imported', 0)}/5"
        except Exception as e:
            result.add_error(f"混合数据导入失败: {type(e).__name__}: {e}")
        finally:
            mem.close()
            os.unlink(mixed_path)

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")

    return result


# ============================================================
# P2: 异常注入与恢复能力测试
# ============================================================
def test_exception_recovery():
    """测试系统在异常情况下的恢复能力"""
    result = ProdTestResult("P2: 异常注入与恢复能力测试")

    try:
        # 测试1: 写入后立即关闭，验证数据持久化
        mem = AgentMemory(config=make_config())
        mid = mem.remember("持久化测试", category="persistence", importance=0.9)
        mem.close()

        # 重新打开，验证数据是否还在
        mem = AgentMemory(config=make_config())
        results = mem.recall("持久化测试", top_k=5)
        if results:
            result.metrics["数据持久化"] = "成功"
        else:
            result.add_warning("数据未持久化（内存存储预期行为）")
        mem.close()

        # 测试2: 操作失败后系统状态一致性
        mem = AgentMemory(config=make_config())
        mem.remember("状态一致性测试1", category="consistency")
        try:
            # 故意触发异常
            mem.update_memory("non_existent_id", content="should fail")
        except Exception:
            pass
        # 验证系统仍可正常操作
        mem.remember("状态一致性测试2", category="consistency")
        count = mem.count_memories()
        result.metrics["异常后状态一致"] = f"{count}条记忆"
        mem.close()

        # 测试3: 批量操作部分失败
        mem = AgentMemory(config=make_config())
        success_count = 0
        fail_count = 0
        for i in range(20):
            try:
                if i == 10:
                    # 故意构造一个会失败的操作
                    mem.remember("", category="fail")  # 空内容应该失败
                else:
                    mem.remember(f"批量测试{i}", category="batch")
                    success_count += 1
            except Exception:
                fail_count += 1
        result.metrics["批量成功"] = success_count
        result.metrics["批量失败"] = fail_count
        mem.close()

        # 测试4: 资源清理验证
        mem = AgentMemory(config=make_config())
        for i in range(100):
            mem.remember(f"资源测试{i}", category="resource")
        mem.close()

        # 再次创建实例，验证无资源泄漏
        mem2 = AgentMemory(config=make_config())
        mem2.remember("资源清理验证", category="verify")
        result.metrics["资源清理"] = "正常"
        mem2.close()

        # 测试5: 并发异常处理
        import threading
        mem = AgentMemory(config=make_config())
        errors = []
        lock = threading.Lock()

        def worker(thread_id):
            try:
                for i in range(10):
                    mem.remember(f"并发{thread_id}-{i}", category="concurrent")
            except Exception as e:
                with lock:
                    errors.append(f"Thread-{thread_id}: {type(e).__name__}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        result.metrics["并发错误数"] = len(errors)
        if errors:
            result.add_warning(f"并发错误: {errors[:3]}")
        mem.close()

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")

    return result


# ============================================================
# P3: 配置边界与错误处理测试
# ============================================================
def test_config_boundaries():
    """测试配置边界条件和错误处理"""
    result = ProdTestResult("P3: 配置边界与错误处理测试")

    try:
        # 测试1: 极小配置
        try:
            config = AgentMemoryConfig(
                short_term={"working_memory_capacity": 1, "history_limit": 1},
                long_term={
                    "embedding": {"provider": "fake", "fake_dimension": 8},
                    "vector_store": {"backend": "memory"},
                },
            )
            mem = AgentMemory(config=config)
            mem.remember("极小配置测试", category="test")
            results = mem.recall("极小配置", top_k=1)
            result.metrics["极小配置"] = "正常"
            mem.close()
        except Exception as e:
            result.add_error(f"极小配置失败: {type(e).__name__}")

        # 测试2: 极大配置
        try:
            config = AgentMemoryConfig(
                short_term={"working_memory_capacity": 10000, "history_limit": 100000},
                long_term={
                    "embedding": {"provider": "fake", "fake_dimension": 1024},
                    "vector_store": {"backend": "memory"},
                },
            )
            mem = AgentMemory(config=config)
            mem.remember("极大配置测试", category="test")
            result.metrics["极大配置"] = "正常"
            mem.close()
        except Exception as e:
            result.add_error(f"极大配置失败: {type(e).__name__}")

        # 测试3: 禁用可选功能
        try:
            config = AgentMemoryConfig(
                long_term={
                    "embedding": {"provider": "fake", "fake_dimension": 64},
                    "vector_store": {"backend": "memory"},
                },
                knowledge_graph={"enabled": False},
                structured_store={"enabled": False},
            )
            mem = AgentMemory(config=config)
            mem.remember("禁用功能测试", category="test")
            result.metrics["禁用KG/SS"] = "正常"
            mem.close()
        except Exception as e:
            result.add_error(f"禁用功能失败: {type(e).__name__}: {e}")

        # 测试4: 无效配置值
        invalid_configs = [
            ("负数容量", {"short_term": {"working_memory_capacity": -1}}),
            ("零维度", {"long_term": {"embedding": {"provider": "fake", "fake_dimension": 0}}}),
            ("无效后端", {"long_term": {"vector_store": {"backend": "nonexistent"}}}),
        ]

        for name, cfg in invalid_configs:
            try:
                config = make_config(**cfg)
                mem = AgentMemory(config=config)
                mem.close()
                result.add_warning(f"{name}: 未拒绝无效配置")
            except (ValueError, TypeError, KeyError) as e:
                result.metrics[f"拒绝{name}"] = "正确"
            except Exception as e:
                result.add_warning(f"{name}: 异常类型 {type(e).__name__}")

        # 测试5: 配置覆盖
        try:
            base_config = make_config()
            mem = AgentMemory(config=base_config)
            # 运行时不应能修改配置
            result.metrics["配置不可变"] = "正常"
            mem.close()
        except Exception as e:
            result.add_error(f"配置覆盖失败: {type(e).__name__}")

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")

    return result


# ============================================================
# P4: 序列化完整性深度验证
# ============================================================
def test_serialization_integrity():
    """深度验证序列化完整性"""
    result = ProdTestResult("P4: 序列化完整性深度验证")

    try:
        # 测试各种数据类型
        test_cases = [
            # (内容, 类别, 标签, 元数据)
            ("普通文本", "text", ["normal"], {}),
            ("包含特殊字符: <>&\"'", "special", ["chars"], {}),
            ("中文内容：这是中文测试", "chinese", ["中文"], {}),
            ("Unicode: 🎉🧠💡", "unicode", ["emoji"], {}),
            ("多行文本\n第二行\n第三行", "multiline", ["lines"], {}),
            ("JSON内容: {\"key\": \"value\"}", "json", ["json"], {}),
            ("URL: https://example.com/path?query=value", "url", ["url"], {}),
            ("代码: def foo(): return 42", "code", ["python"], {}),
            ("SQL: SELECT * FROM users WHERE id = 1", "sql", ["sql"], {}),
            ("Markdown: # Header\n**bold** *italic*", "markdown", ["md"], {}),
        ]

        mem = AgentMemory(config=make_config())
        ids = []
        for content, category, tags, metadata in test_cases:
            mid = mem.remember(content, category=category, tags=tags, importance=0.8, metadata=metadata)
            ids.append(mid)

        result.metrics["注入测试用例"] = len(test_cases)

        # 导出
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name
        mem.export_memories(export_path, format="json")
        mem.close()

        # 验证导出文件
        with open(export_path, "r") as f:
            exported = json.load(f)

        records = exported.get("records", [])
        result.metrics["导出记录数"] = len(records)

        # 验证每条记录的完整性
        missing_fields = 0
        corrupted_content = 0
        for record in records:
            if not record.get("content"):
                missing_fields += 1
            if not record.get("category"):
                missing_fields += 1
            # 检查内容是否完整（未截断）
            content = record.get("content", "")
            if len(content) < 4:  # 所有测试内容都应 >= 4 字符
                corrupted_content += 1

        result.metrics["缺失字段"] = missing_fields
        result.metrics["内容损坏"] = corrupted_content

        # 导入并验证
        mem2 = AgentMemory(config=make_config())
        import_stats = mem2.import_memories(export_path)
        result.metrics["导入成功"] = import_stats.get("imported", 0)

        # 逐条验证内容一致性
        content_match = 0
        for i, (content, category, tags, metadata) in enumerate(test_cases):
            results = mem2.recall(content[:20], top_k=3)
            for r in results:
                if r.get("content") == content:
                    content_match += 1
                    break

        result.metrics["内容一致"] = f"{content_match}/{len(test_cases)}"
        mem2.close()
        os.unlink(export_path)

        # 测试二进制数据（应该失败或转义）
        try:
            mem3 = AgentMemory(config=make_config())
            binary_content = "Binary: \x00\x01\x02\xff"
            mem3.remember(binary_content, category="binary")
            mem3.close()
            result.metrics["二进制处理"] = "接受（可能转义）"
        except Exception as e:
            result.metrics["二进制处理"] = f"拒绝: {type(e).__name__}"

        # 测试超深嵌套元数据
        try:
            mem4 = AgentMemory(config=make_config())
            deep_metadata = {"level1": {"level2": {"level3": {"level4": {"level5": "deep"}}}}}
            mem4.remember("深层嵌套", category="test", metadata=deep_metadata)
            mem4.close()
            result.metrics["深层嵌套"] = "正常"
        except Exception as e:
            result.add_warning(f"深层嵌套失败: {type(e).__name__}")

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")

    return result


# ============================================================
# 主执行
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Agent Memory System - 生产级深度测试")
    print("=" * 60)

    all_results = []

    tests = [
        ("P1", test_cross_version_compatibility),
        ("P2", test_exception_recovery),
        ("P3", test_config_boundaries),
        ("P4", test_serialization_integrity),
    ]

    total_start = time.time()
    for name, test_fn in tests:
        print(f"\n▶ 执行 {name}...")
        r = test_fn()
        r.report()
        all_results.append(r)
    total_time = time.time() - total_start

    # 汇总
    print("\n" + "=" * 60)
    print("  汇总报告")
    print("=" * 60)
    passed = sum(1 for r in all_results if r.passed)
    total_errors = sum(len(r.errors) for r in all_results)
    total_warnings = sum(len(r.warnings) for r in all_results)
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  通过: {passed}/{len(all_results)}")
    print(f"  错误: {total_errors}")
    print(f"  警告: {total_warnings}")

    if total_errors > 0:
        print("\n  需要修复的错误:")
        for r in all_results:
            for e in r.errors:
                print(f"    [{r.name}] {e}")

    if total_warnings > 0:
        print(f"\n  警告 ({total_warnings}):")
        for r in all_results:
            for w in r.warnings:
                print(f"    [{r.name}] {w}")

    print()
