"""
第四轮深度测试脚本

聚焦系统深层模块的极端场景：
Q1: 生命周期深度探测 - 巩固/衰减/驱逐/清理
Q2: 知识图谱复杂操作 - 环路/断连/大规模遍历
Q3: 搜索策略交互 - 空索引/权重/策略冲突
Q4: 压缩引擎边界 - 重复压缩/恢复/边界
"""

import sys
import time
import traceback

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


class QResult:
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
# Q1: 生命周期深度探测
# ============================================================
def test_lifecycle_deep():
    """生命周期深度探测：巩固、衰减、驱逐、清理"""
    result = QResult("Q1: 生命周期深度探测")
    mem = AgentMemory(config=make_config())

    try:
        # 测试1: 巩固机制 - 短期→长期
        mem.add_to_working_memory(key="wm1", content="工作记忆内容1", importance=0.9)
        mem.add_to_working_memory(key="wm2", content="工作记忆内容2", importance=0.3)
        mem.add_to_working_memory(key="wm3", content="工作记忆内容3", importance=0.7)

        snapshot = mem.get_working_memory_snapshot()
        wm_items = snapshot.get("working_memory", "")
        result.metrics["工作记忆项数"] = wm_items.count("[") if wm_items else 0

        # 测试巩固
        try:
            consolidated = mem.consolidate()
            result.metrics["巩固结果"] = f"{consolidated.get('consolidated', 0)}条"
        except Exception as e:
            result.add_error(f"巩固失败: {type(e).__name__}: {e}")

        # 测试2: 生命周期维护
        for i in range(50):
            mem.remember(f"生命周期测试{i}", category="lifecycle", importance=0.1 + (i % 10) * 0.09)

        try:
            report = mem.lifecycle_maintenance(auto_compress=False)
            result.metrics["维护报告"] = f"记忆数={report.get('memory_count', 0)}"
        except Exception as e:
            result.add_error(f"维护失败: {type(e).__name__}: {e}")

        # 测试3: 删除后状态一致性
        all_memories = list(mem.get_all_memories())
        if all_memories:
            # 删除一半
            to_delete = all_memories[:len(all_memories)//2]
            for m in to_delete:
                mem.delete_memory(m.id)

            remaining = mem.count_memories()
            expected = len(all_memories) - len(to_delete)
            result.metrics["删除一致性"] = f"期望{expected}，实际{remaining}"
            if remaining != expected:
                result.add_warning(f"删除后数量不一致: {remaining} vs {expected}")

        # 测试4: 重复删除同一记忆
        if all_memories:
            did = all_memories[0].id
            mem.delete_memory(did)
            # 第二次删除不应报错
            try:
                mem.delete_memory(did)
                result.metrics["重复删除"] = "安全（无异常）"
            except Exception as e:
                result.add_error(f"重复删除异常: {type(e).__name__}")

        # 测试5: 健康检查在大量操作后
        health = mem.health_check()
        result.metrics["健康状态"] = health.get("status", "unknown")

        # 测试6: 审计日志完整性
        audit = mem.get_audit_log()
        result.metrics["审计日志数"] = len(audit)

        # 验证审计日志格式
        if audit:
            first = audit[0]
            required_keys = {"action", "timestamp"}
            if not required_keys.issubset(first.keys()):
                result.add_warning(f"审计日志格式不完整: 缺少{required_keys - first.keys()}")
            else:
                result.metrics["审计日志格式"] = "完整"

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# Q2: 知识图谱复杂操作
# ============================================================
def test_knowledge_graph_complex():
    """知识图谱复杂操作：环路、断连、大规模遍历"""
    result = QResult("Q2: 知识图谱复杂操作")
    mem = AgentMemory(config=make_config())

    try:
        if not mem.knowledge_graph:
            result.add_warning("知识图谱未启用，跳过测试")
            return result

        from memory_system.processing.knowledge_graph_engine import Entity, Relation

        # 测试1: 构建复杂图结构
        entities = []
        for i in range(30):
            e = Entity(name=f"Node{i}", entity_type=f"type{i % 5}")
            mem.knowledge_graph.add_entity(e)
            entities.append(e)

        # 构建链式关系
        for i in range(29):
            r = Relation(source=f"Node{i}", target=f"Node{i+1}", relation_type="chain")
            mem.knowledge_graph.add_relation(r)

        # 构建环路
        mem.knowledge_graph.add_relation(Relation(source="Node29", target="Node0", relation_type="loop"))

        # 构建星形关系
        for i in range(1, 10):
            mem.knowledge_graph.add_relation(Relation(source=f"Node0", target=f"Node{i}", relation_type="star"))

        stats = mem.knowledge_graph.get_statistics()
        result.metrics["实体数"] = stats.get("entity_count", 0)
        result.metrics["关系数"] = stats.get("relation_count", 0)

        # 测试2: 路径查找（含环路）
        try:
            path = mem.find_path("Node0", "Node29")
            if path:
                result.metrics["环路路径长度"] = len(path)
            else:
                result.add_warning("环路路径查找返回None")
        except Exception as e:
            result.add_error(f"环路路径查找失败: {type(e).__name__}: {e}")

        # 测试3: 路径查找（断连节点）
        orphan = Entity(name="Orphan", entity_type="isolated")
        mem.knowledge_graph.add_entity(orphan)
        path = mem.find_path("Node0", "Orphan")
        if path is None:
            result.metrics["断连路径"] = "正确返回None"
        else:
            result.add_warning(f"断连节点不应有路径: {path}")

        # 测试4: 自环
        try:
            mem.knowledge_graph.add_relation(Relation(source="Node0", target="Node0", relation_type="self"))
            result.metrics["自环"] = "被接受"
        except Exception as e:
            result.metrics["自环"] = f"拒绝: {type(e).__name__}"

        # 测试5: 重复关系
        try:
            mem.knowledge_graph.add_relation(Relation(source="Node0", target="Node1", relation_type="chain"))
            result.metrics["重复关系"] = "被接受（多重图）"
        except Exception as e:
            result.metrics["重复关系"] = f"拒绝: {type(e).__name__}"

        # 测试6: 大规模邻居查询
        try:
            neighbors = mem.knowledge_graph.get_neighbors("Node0")
            result.metrics["Node0邻居数"] = len(neighbors)
        except Exception as e:
            result.add_error(f"邻居查询失败: {type(e).__name__}")

        # 测试7: 删除实体后的关系一致性
        try:
            mem.knowledge_graph.remove_entity("Node15")
            # 查询经过Node15的路径应该失败或绕过
            path_after = mem.find_path("Node14", "Node16")
            result.metrics["删除后路径"] = f"{'存在' if path_after else '断裂'}"
        except Exception as e:
            result.add_error(f"删除实体后查询失败: {type(e).__name__}: {e}")

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# Q3: 搜索策略交互
# ============================================================
def test_search_strategy_interaction():
    """搜索策略交互：空索引、权重、策略冲突"""
    result = QResult("Q3: 搜索策略交互")
    mem = AgentMemory(config=make_config())

    try:
        # 测试1: 空系统搜索
        empty_results = mem.recall("不存在的查询", top_k=10)
        result.metrics["空系统搜索"] = f"返回{len(empty_results)}条"

        # 注入数据
        for i in range(50):
            mem.remember(f"搜索测试{i}: 关于Python编程的第{i}条内容", category="search", importance=0.5)

        # 测试2: top_k=1
        single = mem.recall("Python", top_k=1)
        result.metrics["top_k=1"] = f"返回{len(single)}条"

        # 测试3: top_k超过总量
        large_k = mem.recall("测试", top_k=10000)
        result.metrics["top_k=10000"] = f"返回{len(large_k)}条"

        # 测试4: 按类别过滤（不存在的类别）
        no_cat = mem.recall("测试", category="nonexistent_category_xyz")
        result.metrics["不存在类别"] = f"返回{len(no_cat)}条"

        # 测试5: 按标签过滤（不存在的标签）
        no_tag = mem.recall("测试", tags=["nonexistent_tag_xyz"])
        result.metrics["不存在标签"] = f"返回{len(no_tag)}条"

        # 测试6: 多标签AND过滤
        mem.remember("多标签测试", category="test", tags=["tag_a", "tag_b", "tag_c"])
        multi_tag = mem.recall("多标签", tags=["tag_a", "tag_b"])
        result.metrics["多标签AND"] = f"返回{len(multi_tag)}条"

        # 测试7: 时间范围过滤（当前未实现，验证参数不被静默忽略）
        try:
            time_results = mem.recall("测试", time_range=(0, 1))
            if len(time_results) > 0:
                result.add_warning("time_range 参数被静默忽略（功能未实现）")
            result.metrics["时间范围"] = f"参数被忽略，返回{len(time_results)}条"
        except TypeError as e:
            result.metrics["时间范围"] = f"正确拒绝: {type(e).__name__}"

        # 测试8: 最小重要性过滤（当前未实现，验证参数不被静默忽略）
        try:
            high_importance = mem.recall("测试", min_importance=0.99)
            if len(high_importance) > 0:
                result.add_warning("min_importance 参数被静默忽略（功能未实现）")
            result.metrics["min_importance=0.99"] = f"参数被忽略，返回{len(high_importance)}条"
        except TypeError as e:
            result.metrics["min_importance"] = f"正确拒绝: {type(e).__name__}"

        # 测试9: 组合过滤（类别+不存在的参数）
        combined = mem.recall("测试", category="search")
        result.metrics["类别过滤"] = f"返回{len(combined)}条"

        # 测试10: 空字符串查询
        empty_query = mem.recall("", top_k=5)
        result.metrics["空字符串查询"] = f"返回{len(empty_query)}条"

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# Q4: 压缩引擎边界
# ============================================================
def test_compression_boundaries():
    """压缩引擎边界：重复压缩、恢复、边界"""
    result = QResult("Q4: 压缩引擎边界")
    mem = AgentMemory(config=make_config())

    try:
        # 注入可压缩数据（大量低重要性相似记忆）
        for i in range(100):
            mem.remember(
                f"重复内容测试{i}: 这是一条关于Python编程的重复性内容，用于测试压缩引擎的边界条件。",
                category="compressible",
                importance=0.2,
                tags=["python", "repeated"],
            )

        # 注入不可压缩数据（高重要性独特记忆）
        for i in range(10):
            mem.remember(
                f"重要独特记忆{i}: 这是第{i}条独特的重要记忆内容，包含独特的标识符{i}。",
                category="important",
                importance=0.95,
                tags=["unique", f"special_{i}"],
            )

        pre_count = mem.count_memories()

        # 测试1: 第一次压缩
        try:
            comp1 = mem.compress_memories()
            result.metrics["第一次压缩"] = f"移除{comp1.get('removed_count', 0)}条"
        except Exception as e:
            result.add_error(f"第一次压缩失败: {type(e).__name__}: {e}")

        after_comp1 = mem.count_memories()

        # 测试2: 重复压缩（应该无效果或极少效果）
        try:
            comp2 = mem.compress_memories()
            result.metrics["重复压缩"] = f"移除{comp2.get('removed_count', 0)}条"
        except Exception as e:
            result.add_error(f"重复压缩失败: {type(e).__name__}: {e}")

        after_comp2 = mem.count_memories()

        # 验证重要记忆未被压缩
        important_results = mem.recall("重要独特记忆", top_k=20)
        important_found = sum(1 for r in important_results if "独特" in r.get("content", ""))
        result.metrics["重要记忆保留"] = f"{important_found}/10"

        if important_found < 8:
            result.add_warning(f"重要记忆被误压缩: {important_found}/10")

        # 测试3: 压缩后检索能力
        search_results = mem.recall("Python编程", top_k=10)
        result.metrics["压缩后检索"] = f"返回{len(search_results)}条"

        # 测试4: 冲突检测在压缩后
        try:
            conflicts = mem.detect_conflicts()
            result.metrics["压缩后冲突"] = f"发现{conflicts.get('conflicts_found', 0)}个"
        except Exception as e:
            result.add_error(f"压缩后冲突检测失败: {type(e).__name__}: {e}")

        # 测试5: 导出压缩后的数据
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name
        try:
            mem.export_memories(export_path, format="json")
            file_size = os.path.getsize(export_path)
            result.metrics["导出文件大小"] = f"{file_size/1024:.1f}KB"
        except Exception as e:
            result.add_error(f"导出失败: {type(e).__name__}: {e}")
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

        # 测试6: 压缩空系统
        empty_mem = AgentMemory(config=make_config())
        try:
            empty_comp = empty_mem.compress_memories()
            result.metrics["空系统压缩"] = f"移除{empty_comp.get('removed_count', 0)}条"
        except Exception as e:
            result.add_error(f"空系统压缩失败: {type(e).__name__}: {e}")
        finally:
            empty_mem.close()

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# 主执行
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Agent Memory System - 第四轮深度测试")
    print("=" * 60)

    all_results = []
    tests = [
        ("Q1", test_lifecycle_deep),
        ("Q2", test_knowledge_graph_complex),
        ("Q3", test_search_strategy_interaction),
        ("Q4", test_compression_boundaries),
    ]

    total_start = time.time()
    for name, test_fn in tests:
        print(f"\n▶ 执行 {name}...")
        r = test_fn()
        r.report()
        all_results.append(r)
    total_time = time.time() - total_start

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
