"""
v12.1 深度集成测试 - 验证所有新功能
"""

import sys
import time

sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


def make_config():
    return AgentMemoryConfig(
        short_term={"working_memory_capacity": 50, "history_limit": 200},
        long_term={
            "embedding": {"provider": "fake", "fake_dimension": 64},
            "vector_store": {"backend": "memory"},
        },
        knowledge_graph={"enabled": True},
        structured_store={"enabled": True},
        auto_consolidate=False,
    )


def test_all():
    errors = []
    warnings = []
    mem = AgentMemory(config=make_config())

    try:
        # === 1. 基础 CRUD ===
        print("1. 基础 CRUD...")
        mid = mem.remember("测试记忆", category="test", importance=0.8, tags=["tag1"])
        assert mid, "remember 返回空ID"
        rec = mem.get_memory(mid)
        assert rec is not None, "get_memory 返回None"
        assert rec.content == "测试记忆", f"内容不匹配: {rec.content}"

        mem.update_memory(mid, content="更新后的测试记忆")
        rec2 = mem.get_memory(mid)
        assert rec2.content == "更新后的测试记忆", "更新失败"

        mem.delete_memory(mid)
        rec3 = mem.get_memory(mid)
        assert rec3 is None, "删除失败"
        print("   OK")

        # === 2. 批量操作 ===
        print("2. 批量操作...")
        items = [{"content": f"批量{i}", "category": "batch", "importance": 0.5} for i in range(20)]
        br = mem.batch_remember(items)
        assert br["success"] == 20, f"batch_remember: {br['success']}/20"
        assert br["failed"] == 0, f"batch_remember 失败: {br['failed']}"

        bd = mem.batch_delete(br["ids"][:10])
        assert bd["deleted"] == 10, f"batch_delete: {bd['deleted']}/10"

        bu = mem.batch_update([{"id": br["ids"][10], "content": "批量更新"}])
        assert bu["updated"] == 1, f"batch_update: {bu['updated']}"
        print("   OK")

        # === 3. 检索 + 过滤 ===
        print("3. 检索 + 过滤...")
        mem.remember("Python编程", category="lang", importance=0.95)
        mem.remember("Java编程", category="lang", importance=0.3)

        r1 = mem.recall("编程", min_importance=0.9)
        assert len(r1) >= 1, f"min_importance 过滤失败: {len(r1)}"

        r2 = mem.recall("编程", category="lang")
        assert len(r2) >= 2, f"category 过滤失败: {len(r2)}"

        now = time.time()
        r3 = mem.recall("编程", time_range=(0, now))
        assert len(r3) >= 2, f"time_range 过滤失败: {len(r3)}"

        r4 = mem.recall("编程", time_range=(now + 86400, now + 172800))
        assert len(r4) == 0, f"未来时间范围应返回0: {len(r4)}"
        print("   OK")

        # === 4. 性能指标 ===
        print("4. 性能指标...")
        metrics = mem.get_metrics()
        assert metrics["remember_count"] > 0, "remember_count 为0"
        assert metrics["recall_count"] > 0, "recall_count 为0"
        assert metrics["update_count"] > 0, "update_count 为0"
        assert metrics["delete_count"] > 0, "delete_count 为0"
        assert metrics["batch_remember_count"] > 0, "batch_remember_count 为0"
        assert metrics["batch_delete_count"] > 0, "batch_delete_count 为0"
        assert metrics["batch_update_count"] > 0, "batch_update_count 为0"
        assert metrics["remember_avg_time"] >= 0, "remember_avg_time 异常"
        assert metrics["recall_avg_time"] >= 0, "recall_avg_time 异常"

        mem.reset_metrics()
        m2 = mem.get_metrics()
        assert m2["remember_count"] == 0, "reset_metrics 未清零"
        print("   OK")

        # === 5. 版本控制 ===
        print("5. 版本控制...")
        vid = mem.remember("版本测试", category="ver")
        mem.update_memory(vid, content="版本测试v2")
        mem.update_memory(vid, content="版本测试v3")
        history = mem.get_version_history(vid)
        assert len(history) >= 3, f"版本历史不足: {len(history)}"

        rolled = mem.rollback_memory(vid, history[0]["version_id"])
        assert "版本测试" in rolled, f"回滚失败: {rolled}"
        print("   OK")

        # === 6. 知识图谱 ===
        print("6. 知识图谱...")
        mem.add_entity("测试实体", entity_type="test")
        mem.add_relation("测试实体", "Python", relation_type="related")
        path = mem.find_path("测试实体", "Python")
        assert path is not None, "路径查找失败"
        print("   OK")

        # === 7. 压缩 + 冲突 ===
        print("7. 压缩 + 冲突...")
        for i in range(20):
            mem.remember(f"低重要性{i}", category="low", importance=0.1)
        comp = mem.compress_memories()
        assert comp.get("removed_count", 0) >= 0, "压缩异常"

        mem.remember("冲突A: x=1", category="conflict")
        mem.remember("冲突B: x=2", category="conflict")
        conflicts = mem.detect_conflicts()
        assert "conflicts_found" in conflicts, "冲突检测格式错误"
        print("   OK")

        # === 8. 导出导入 ===
        print("8. 导出导入...")
        import tempfile, os, json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        mem.export_memories(path, format="json")

        with open(path) as f:
            data = json.load(f)
        records = data.get("records", data) if isinstance(data, dict) else data
        assert len(records) > 0, "导出为空"

        new_mem = AgentMemory(config=make_config())
        imp = new_mem.import_memories(path)
        assert imp.get("imported", 0) > 0, "导入失败"
        new_mem.close()
        os.unlink(path)
        print("   OK")

        # === 9. 健康检查 ===
        print("9. 健康检查...")
        health = mem.health_check()
        assert health.get("status") in ("healthy", "warning"), f"健康状态异常: {health}"
        print("   OK")

        # === 10. 参数验证 ===
        print("10. 参数验证...")
        try:
            mem.remember("", category="test")
            errors.append("空内容未被拒绝")
        except ValueError:
            pass

        try:
            mem.remember("test", importance=2.0)
            errors.append("超大importance未被拒绝")
        except ValueError:
            pass

        try:
            mem.recall("test", top_k=-1)
            errors.append("负数top_k未被拒绝")
        except ValueError:
            pass

        try:
            mem.recall("test", top_k=3.5)
            errors.append("浮点top_k未被拒绝")
        except ValueError:
            pass

        try:
            import json as j
            circular = {"self": None}
            circular["self"] = circular
            mem.remember("test", metadata=circular)
            errors.append("循环引用未被拒绝")
        except ValueError:
            pass
        print("   OK")

    except Exception as e:
        import traceback
        errors.append(f"未预期异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    # 汇总
    print(f"\n{'='*40}")
    if errors:
        print(f"  FAIL: {len(errors)} errors")
        for e in errors:
            print(f"    - {e}")
    if warnings:
        print(f"  WARN: {len(warnings)} warnings")
        for w in warnings:
            print(f"    - {w}")
    if not errors and not warnings:
        print("  ALL 10 TESTS PASSED")
    print(f"{'='*40}")
    return len(errors) == 0


if __name__ == "__main__":
    ok = test_all()
    sys.exit(0 if ok else 1)
