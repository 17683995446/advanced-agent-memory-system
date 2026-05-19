"""
极端场景深度测试脚本

测试系统在极端条件下的表现：
1. 并发压力测试 - 多线程同时读写
2. 内存极限测试 - 大量数据注入
3. 死锁探测 - 复杂锁竞争场景
4. 深度边界探测 - 负数、None、循环引用等
5. 长时间运行稳定性
6. 跨模块复杂交互
"""

import sys
import time
import threading
import traceback
import gc
import weakref

sys.path.insert(0, "/workspace/agent-memory-system")

from memory_system import AgentMemory, AgentMemoryConfig


def make_config():
    return AgentMemoryConfig(
        short_term={"working_memory_capacity": 50, "history_limit": 200},
        long_term={
            "embedding": {"provider": "fake", "fake_dimension": 32},
            "vector_store": {"backend": "memory"},
        },
        knowledge_graph={"enabled": True},
        structured_store={"enabled": True},
        auto_consolidate=False,
    )


class DeepTestResult:
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
# R1: 并发压力测试
# ============================================================
def test_concurrent_access():
    """多线程并发读写测试"""
    result = DeepTestResult("R1: 并发压力测试")
    mem = AgentMemory(config=make_config())

    try:
        errors = []
        success_count = [0]
        lock = threading.Lock()

        def writer_thread(thread_id, count):
            try:
                for i in range(count):
                    mem.remember(
                        f"线程{thread_id}记忆{i}",
                        category=f"thread_{thread_id}",
                        importance=0.5,
                    )
                with lock:
                    success_count[0] += count
            except Exception as e:
                with lock:
                    errors.append(f"Writer-{thread_id}: {type(e).__name__}: {e}")

        def reader_thread(thread_id, count):
            try:
                for i in range(count):
                    mem.recall(f"线程{thread_id}", top_k=5)
            except Exception as e:
                with lock:
                    errors.append(f"Reader-{thread_id}: {type(e).__name__}: {e}")

        # 启动多个写线程
        start = time.time()
        threads = []
        for i in range(10):  # 10个写线程
            t = threading.Thread(target=writer_thread, args=(i, 100))
            threads.append(t)
            t.start()

        # 同时启动读线程
        for i in range(5):  # 5个读线程
            t = threading.Thread(target=reader_thread, args=(i, 50))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join(timeout=30)

        duration = time.time() - start
        result.metrics["写入成功数"] = f"{success_count[0]}/1000"
        result.metrics["并发耗时"] = f"{duration:.2f}s"
        result.metrics["线程数"] = len(threads)

        if errors:
            for e in errors[:5]:  # 只显示前5个错误
                result.add_error(e)
            if len(errors) > 5:
                result.add_warning(f"还有{len(errors)-5}个错误未显示")

        if success_count[0] < 900:
            result.add_warning(f"写入成功率低于90%: {success_count[0]/1000*100:.1f}%")

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# R2: 深度边界探测
# ============================================================
def test_deep_boundaries():
    """深度边界条件测试"""
    result = DeepTestResult("R2: 深度边界探测")
    mem = AgentMemory(config=make_config())

    try:
        # 测试1: 负数重要性
        try:
            mid = mem.remember("负数重要性测试", importance=-0.5)
            if mid:
                result.add_warning("负数重要性被接受，可能需要验证")
            else:
                result.metrics["负数重要性"] = "被拒绝或返回空"
        except (ValueError, TypeError):
            result.metrics["负数重要性"] = "正确抛出异常"
        except Exception as e:
            result.add_error(f"负数重要性异常: {type(e).__name__}")

        # 测试2: 超大重要性
        try:
            mid = mem.remember("超大重要性测试", importance=999.0)
            if mid:
                result.metrics["超大重要性"] = "被接受(可能需要clamp)"
            else:
                result.metrics["超大重要性"] = "被拒绝"
        except Exception as e:
            result.metrics["超大重要性"] = f"抛出{type(e).__name__}"

        # 测试3: None值字段
        try:
            mid = mem.remember("None值测试", category=None, tags=None)
            result.metrics["None值字段"] = "被接受"
        except (ValueError, TypeError):
            result.metrics["None值字段"] = "正确拒绝"
        except Exception as e:
            result.add_error(f"None值异常: {type(e).__name__}")

        # 测试4: 空标签列表
        try:
            mid = mem.remember("空标签测试", tags=[])
            result.metrics["空标签列表"] = "被接受"
        except Exception as e:
            result.add_error(f"空标签异常: {type(e).__name__}")

        # 测试5: 特殊字符标签
        try:
            special_tags = ["<script>", "'; DROP", "\x00null", "🎉emoji"]
            mid = mem.remember("特殊字符标签测试", tags=special_tags)
            result.metrics["特殊字符标签"] = "被接受"
        except Exception as e:
            result.metrics["特殊字符标签"] = f"抛出{type(e).__name__}"

        # 测试6: 循环引用检测（通过metadata）
        try:
            circular = {}
            circular["self"] = circular
            mid = mem.remember("循环引用测试", metadata=circular)
            result.add_warning("循环引用被接受，可能导致序列化问题")
        except (ValueError, TypeError, RecursionError):
            result.metrics["循环引用"] = "正确拒绝"
        except Exception as e:
            result.metrics["循环引用"] = f"抛出{type(e).__name__}"

        # 测试7: 极长ID查询
        try:
            very_long_id = "x" * 10000
            found = mem.long_term.get(very_long_id)
            result.metrics["极长ID查询"] = f"返回{found}"
        except Exception as e:
            result.metrics["极长ID查询"] = f"抛出{type(e).__name__}"

        # 测试8: 负数top_k
        try:
            results = mem.recall("测试", top_k=-10)
            result.add_warning("负数top_k被接受，返回{len(results)}条")
        except (ValueError, TypeError):
            result.metrics["负数top_k"] = "正确拒绝"
        except Exception as e:
            result.metrics["负数top_k"] = f"抛出{type(e).__name__}"

        # 测试9: 零top_k
        try:
            results = mem.recall("测试", top_k=0)
            result.metrics["零top_k"] = f"返回{len(results)}条"
        except Exception as e:
            result.metrics["零top_k"] = f"抛出{type(e).__name__}"

        # 测试10: 浮点数top_k
        try:
            results = mem.recall("测试", top_k=5.5)
            result.metrics["浮点top_k"] = f"返回{len(results)}条"
        except (ValueError, TypeError):
            result.metrics["浮点top_k"] = "正确拒绝"
        except Exception as e:
            result.metrics["浮点top_k"] = f"抛出{type(e).__name__}"

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# R3: 内存极限测试
# ============================================================
def test_memory_limits():
    """内存极限测试"""
    result = DeepTestResult("R3: 内存极限测试")
    mem = AgentMemory(config=make_config())

    try:
        # 测试1: 大量小记忆
        start = time.time()
        count = 10000
        try:
            for i in range(count):
                mem.remember(f"小记忆{i}", category="small", importance=0.5)
            duration = time.time() - start
            result.metrics[f"{count}条小记忆"] = f"{duration:.2f}s"
        except MemoryError:
            result.add_warning(f"内存不足，在{i}条时失败")
        except Exception as e:
            result.add_error(f"大量小记忆失败: {type(e).__name__}")

        # 测试2: 少量大记忆
        try:
            large_content = "A" * 100000  # 100KB
            start = time.time()
            for i in range(10):
                mem.remember(large_content, category="large")
            duration = time.time() - start
            result.metrics["10条100KB记忆"] = f"{duration:.2f}s"
        except MemoryError:
            result.add_warning("大记忆内存不足")
        except Exception as e:
            result.add_error(f"大记忆失败: {type(e).__name__}")

        # 测试3: 统计内存使用
        try:
            stats = mem.get_stats()
            memory_count = mem.count_memories()
            result.metrics["最终记忆数"] = memory_count
        except Exception as e:
            result.add_error(f"统计失败: {type(e).__name__}")

        # 测试4: 批量删除后内存
        try:
            all_mems = list(mem.get_all_memories())[:1000]
            start = time.time()
            for m in all_mems:
                mem.delete_memory(m.id)
            duration = time.time() - start
            result.metrics["删除1000条耗时"] = f"{duration:.2f}s"
        except Exception as e:
            result.add_error(f"批量删除失败: {type(e).__name__}")

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# R4: 长时间运行稳定性
# ============================================================
def test_long_running():
    """长时间运行稳定性测试"""
    result = DeepTestResult("R4: 长时间运行稳定性")
    mem = AgentMemory(config=make_config())

    try:
        iterations = 500
        errors_during_run = []

        start = time.time()
        for i in range(iterations):
            try:
                # 写入
                mid = mem.remember(f"稳定性测试{i}", category="stability")

                # 读取
                results = mem.recall(f"稳定性测试", top_k=10)

                # 更新（每10次）
                if i % 10 == 0 and mid:
                    mem.update_memory(mid, content=f"更新后的稳定性测试{i}")

                # 删除（每20次）
                if i % 20 == 0 and mid:
                    mem.delete_memory(mid)

            except Exception as e:
                errors_during_run.append(f"Iteration {i}: {type(e).__name__}")

        duration = time.time() - start
        result.metrics["迭代次数"] = iterations
        result.metrics["总耗时"] = f"{duration:.2f}s"
        result.metrics["平均每次"] = f"{duration/iterations*1000:.1f}ms"

        if errors_during_run:
            result.add_error(f"运行中{len(errors_during_run)}次错误")
            for e in errors_during_run[:3]:
                result.add_warning(e)

        # 检查最终状态
        try:
            final_count = mem.count_memories()
            result.metrics["最终记忆数"] = final_count

            health = mem.health_check()
            result.metrics["健康状态"] = health.get("status", "unknown")
        except Exception as e:
            result.add_error(f"最终状态检查失败: {type(e).__name__}")

    except Exception as e:
        result.add_error(f"未预期的异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()

    return result


# ============================================================
# R5: 跨模块复杂交互
# ============================================================
def test_cross_module_complex():
    """跨模块复杂交互测试"""
    result = DeepTestResult("R5: 跨模块复杂交互")
    mem = AgentMemory(config=make_config())

    try:
        # 测试1: 记忆 + 知识图谱 + 版本控制联动
        try:
            # 创建记忆
            mid1 = mem.remember("Python是一种编程语言", category="tech", importance=0.9)
            mid2 = mem.remember("Django是Python框架", category="tech", importance=0.8)

            # 添加知识图谱实体
            if mem.knowledge_graph:
                from memory_system.processing.knowledge_graph_engine import Entity, Relation
                mem.knowledge_graph.add_entity(Entity(name="Python", entity_type="language"))
                mem.knowledge_graph.add_entity(Entity(name="Django", entity_type="framework"))
                mem.knowledge_graph.add_relation(Relation(source="Django", target="Python", relation_type="uses"))

                # 查询路径
                path = mem.find_path("Django", "Python")
                result.metrics["知识图谱路径"] = str(path) if path else "None"

            # 版本控制
            mem.update_memory(mid1, content="Python是一种高级编程语言")
            history = mem.get_version_history(mid1)
            result.metrics["版本历史数"] = len(history)

            # 冲突检测
            conflicts = mem.detect_conflicts()
            result.metrics["冲突检测"] = f"发现{conflicts.get('conflicts_found', 0)}个"

        except Exception as e:
            result.add_error(f"跨模块联动失败: {type(e).__name__}: {e}")

        # 测试2: 压缩 + 衰减联动
        try:
            # 添加大量低重要性记忆
            for i in range(100):
                mem.remember(f"低重要性记忆{i}", category="low", importance=0.1)

            # 执行压缩
            compress_result = mem.compress_memories()
            result.metrics["压缩移除数"] = compress_result.get("removed_count", 0)

        except Exception as e:
            result.add_error(f"压缩联动失败: {type(e).__name__}")

        # 测试3: 导出 + 导入 + 验证
        try:
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                export_path = f.name

            # 导出
            mem.export_memories(export_path, format="json")

            # 导入到新实例
            new_mem = AgentMemory(config=make_config())
            import_stats = new_mem.import_memories(export_path)

            # 验证
            original_count = mem.count_memories()
            imported_count = new_mem.count_memories()

            result.metrics["导出/导入"] = f"{original_count}→{imported_count}"

            new_mem.close()
            os.unlink(export_path)

        except Exception as e:
            result.add_error(f"导出导入失败: {type(e).__name__}")

        # 测试4: 索引 + 搜索联动
        try:
            from memory_system.core.memory_index_manager import MemoryIndexManager, IndexConfig

            idx_mgr = MemoryIndexManager(config=IndexConfig())
            all_mems = list(mem.get_all_memories())
            idx_mgr.build_index(all_mems)

            # 索引查询
            idx_results = idx_mgr.query(keywords=["Python"], limit=10)
            result.metrics["索引查询结果"] = f"{len(idx_results)}条"

        except Exception as e:
            result.add_error(f"索引联动失败: {type(e).__name__}")

        # 测试5: 推理引擎联动
        try:
            from memory_system.core.memory_inference_engine import MemoryInferenceEngine

            engine = MemoryInferenceEngine()
            infer_result = engine.infer("Python和Django的关系是什么？", mem)

            result.metrics["推理置信度"] = f"{infer_result.confidence:.2f}"
            result.metrics["推理步骤数"] = len(infer_result.steps)

        except Exception as e:
            result.add_error(f"推理联动失败: {type(e).__name__}")

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
    print("  Agent Memory System - 极端场景深度测试")
    print("=" * 60)

    all_results = []

    tests = [
        ("R1", test_concurrent_access),
        ("R2", test_deep_boundaries),
        ("R3", test_memory_limits),
        ("R4", test_long_running),
        ("R5", test_cross_module_complex),
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
