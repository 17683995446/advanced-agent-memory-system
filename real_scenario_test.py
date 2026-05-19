#!/usr/bin/env python3
"""
Agent Memory System - 真实场景深度测试
通过复杂的真实场景，发现系统的问题和潜在 bug
"""

import sys
import os
import time
import json
import random
import string
import threading
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


@dataclass
class TestResult:
    test_name: str
    passed: bool = True
    errors: List[str] = None
    warnings: List[str] = None
    metrics: Dict[str, Any] = None
    execution_time: float = 0.0

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.metrics is None:
            self.metrics = {}

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_metric(self, key: str, value: Any):
        self.metrics[key] = value

    def report(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        print(f"\n{'='*80}")
        print(f"  {status} | {self.test_name}")
        print(f"{'='*80}")
        if self.metrics:
            print("  Metrics:")
            for k, v in self.metrics.items():
                print(f"    - {k}: {v}")
        if self.warnings:
            print(f"\n  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"    ⚠️  {w}")
        if self.errors:
            print(f"\n  Errors ({len(self.errors)}):")
            for e in self.errors:
                print(f"    ❌ {e}")
        print(f"\n  Execution Time: {self.execution_time:.2f}s")


def test_1_basic_operations() -> TestResult:
    """测试1：基础操作 - 记忆存储、检索、更新、删除"""
    result = TestResult("基础操作测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        mem = AgentMemory(config=config)

        # 测试记忆存储
        memory_ids = []
        test_contents = [
            "Python是一种高级编程语言",
            "机器学习是人工智能的一个分支",
            "神经网络可以用于图像识别",
            "数据库系统用于存储和检索数据",
        ]

        for i, content in enumerate(test_contents):
            try:
                mid = mem.remember(
                    content=content,
                    category="tech",
                    importance=0.5 + i * 0.1,
                    tags=["programming", "ai"],
                )
                memory_ids.append(mid)
                result.add_metric(f"memory_{i}_id", mid)
            except Exception as e:
                result.add_error(f"Remember failed for content {i}: {e}")

        result.add_metric("stored_count", len(memory_ids))

        # 测试记忆检索
        try:
            results = mem.recall("Python", top_k=3)
            result.add_metric("recall_results_count", len(results))
            if results:
                result.add_metric("first_result_score", results[0].score if hasattr(results[0], 'score') else "N/A")
        except Exception as e:
            result.add_error(f"Recall failed: {e}")

        # 测试记忆更新
        if memory_ids:
            try:
                mem.update_memory(
                    memory_ids[0],
                    content="Python是一种高级、解释型、通用的编程语言",
                )
                result.add_metric("update_successful", True)
            except Exception as e:
                result.add_error(f"Update failed: {e}")

        # 测试记忆删除
        if len(memory_ids) > 1:
            try:
                deleted = mem.delete_memory(memory_ids[1])
                result.add_metric("delete_successful", deleted)
            except Exception as e:
                result.add_error(f"Delete failed: {e}")

        # 测试统计
        try:
            stats = mem.get_stats()
            result.add_metric("final_count", stats.get("total_memories", "N/A"))
        except Exception as e:
            result.add_error(f"Stats failed: {e}")

        mem.close()

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def test_2_high_volume_operations() -> TestResult:
    """测试2：高容量操作 - 批量插入、批量查询"""
    result = TestResult("高容量操作测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            auto_consolidate=False,
        )
        mem = AgentMemory(config=config)

        # 批量插入测试
        batch_size = 100
        insert_times = []
        memory_ids = []

        for batch in range(5):
            t0 = time.time()
            for i in range(batch_size):
                content = f"Test memory {batch}-{i}: {random_string(50)}"
                mid = mem.remember(
                    content=content,
                    category=f"batch_{batch}",
                    importance=random.uniform(0.1, 0.9),
                )
                memory_ids.append(mid)
            insert_time = time.time() - t0
            insert_times.append(insert_time)
            result.add_metric(f"batch_{batch}_time", f"{insert_time:.3f}s")

        result.add_metric("total_inserted", len(memory_ids))
        result.add_metric("avg_batch_time", f"{sum(insert_times)/len(insert_times):.3f}s")
        result.add_metric("total_insert_time", f"{sum(insert_times):.2f}s")

        # 批量查询测试
        query_times = []
        queries = ["test", "memory", "random", "data", "information"]
        for q in queries:
            t0 = time.time()
            results = mem.recall(q, top_k=10)
            query_time = time.time() - t0
            query_times.append(query_time)
            result.add_metric(f"query_{q}_time", f"{query_time:.3f}s")
            result.add_metric(f"query_{q}_count", len(results))

        result.add_metric("avg_query_time", f"{sum(query_times)/len(query_times):.3f}s")

        mem.close()

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def test_3_knowledge_graph_operations() -> TestResult:
    """测试3：知识图谱操作"""
    result = TestResult("知识图谱操作测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            knowledge_graph={"enabled": True},
        )
        mem = AgentMemory(config=config)

        # 添加实体
        entities = [
            ("Python", "language", "一种高级编程语言"),
            ("TensorFlow", "framework", "机器学习框架"),
            ("Neural Network", "concept", "机器学习模型"),
            ("Image Recognition", "application", "计算机视觉应用"),
        ]

        for name, etype, desc in entities:
            try:
                mem.add_entity(name, entity_type=etype, description=desc)
            except Exception as e:
                result.add_error(f"Add entity {name} failed: {e}")

        # 添加关系
        relations = [
            ("TensorFlow", "Python", "uses"),
            ("Neural Network", "TensorFlow", "implemented_in"),
            ("Image Recognition", "Neural Network", "uses"),
        ]

        for src, target, rtype in relations:
            try:
                mem.add_relation(src, target, relation_type=rtype, weight=1.0)
            except Exception as e:
                result.add_error(f"Add relation {src}->{target} failed: {e}")

        # 搜索实体
        try:
            search_results = mem.search_entities("Python", top_k=3)
            result.add_metric("entity_search_count", len(search_results))
        except Exception as e:
            result.add_error(f"Search entities failed: {e}")

        # 查找相关实体
        try:
            related = mem.find_related("Python", top_k=5)
            result.add_metric("related_entities_count", len(related))
        except Exception as e:
            result.add_error(f"Find related failed: {e}")

        # 从文本构建知识图谱
        try:
            kg = mem.build_knowledge_from_text(
                "JavaScript是一种编程语言，React是使用JavaScript构建的库"
            )
            stats = kg.get_statistics()
            result.add_metric("kg_entities_from_text", stats.get("entity_count", 0))
            result.add_metric("kg_relations_from_text", stats.get("relation_count", 0))
        except Exception as e:
            result.add_error(f"Build knowledge from text failed: {e}")

        # 知识图谱统计
        try:
            stats = mem.get_knowledge_graph_stats()
            result.add_metric("kg_total_entities", stats.get("entity_count", 0))
            result.add_metric("kg_total_relations", stats.get("relation_count", 0))
        except Exception as e:
            result.add_error(f"KG stats failed: {e}")

        mem.close()

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def test_4_concurrent_operations() -> TestResult:
    """测试4：并发操作 - 多线程读写"""
    result = TestResult("并发操作测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            auto_consolidate=False,
        )
        mem = AgentMemory(config=config)

        errors = []
        success_count = [0]
        lock = threading.Lock()

        def writer(thread_id: int, count: int):
            try:
                for i in range(count):
                    mem.remember(
                        f"Thread {thread_id} memory {i}: {random_string(30)}",
                        category="concurrent",
                        importance=random.uniform(0.3, 0.7),
                    )
                    with lock:
                        success_count[0] += 1
            except Exception as e:
                with lock:
                    errors.append(f"Writer {thread_id}: {e}")

        def reader(thread_id: int, count: int):
            try:
                for i in range(count):
                    mem.recall(f"thread {thread_id}", top_k=3)
            except Exception as e:
                with lock:
                    errors.append(f"Reader {thread_id}: {e}")

        # 启动线程
        threads = []
        for i in range(5):
            t = threading.Thread(target=writer, args=(i, 50))
            threads.append(t)
            t.start()

        for i in range(3):
            t = threading.Thread(target=reader, args=(i, 30))
            threads.append(t)
            t.start()

        # 等待完成
        for t in threads:
            t.join(timeout=60)

        result.add_metric("total_success", success_count[0])
        result.add_metric("error_count", len(errors))

        if errors:
            for e in errors[:5]:
                result.add_error(e)
            if len(errors) > 5:
                result.add_warning(f"还有 {len(errors) - 5} 个错误")

        # 验证最终状态
        try:
            stats = mem.get_stats()
            result.add_metric("final_memory_count", stats.get("total_memories", 0))
        except Exception as e:
            result.add_error(f"Final stats check failed: {e}")

        mem.close()

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def test_5_edge_cases() -> TestResult:
    """测试5：边界条件 - 极端输入、异常情况"""
    result = TestResult("边界条件测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        mem = AgentMemory(config=config)

        # 超长内容
        try:
            very_long_content = "x" * 100000  # 10万字符
            mid = mem.remember(very_long_content, category="long")
            result.add_metric("very_long_content", "accepted")
        except Exception as e:
            result.add_error(f"Very long content failed: {e}")

        # 空内容 (应该失败)
        try:
            mem.remember("", category="empty")
            result.add_warning("Empty content should be rejected but was accepted")
        except ValueError:
            result.add_metric("empty_content", "correctly_rejected")
        except Exception as e:
            result.add_error(f"Empty content error type wrong: {type(e).__name__}")

        # 无效重要性
        try:
            mem.remember("Negative importance", importance=-0.5)
            result.add_warning("Negative importance should be rejected")
        except ValueError:
            result.add_metric("negative_importance", "correctly_rejected")
        except Exception as e:
            result.add_error(f"Negative importance error: {e}")

        try:
            mem.remember("Huge importance", importance=2.0)
            result.add_warning("Huge importance should be rejected or clamped")
        except ValueError:
            result.add_metric("huge_importance", "correctly_rejected")
        except Exception as e:
            result.add_error(f"Huge importance error: {e}")

        # 特殊字符
        try:
            special_content = "🎉 测试 Emoji 🚀 中文测试 日本語 العربية"
            mid = mem.remember(special_content, category="special")
            result.add_metric("special_chars", "accepted")
        except Exception as e:
            result.add_error(f"Special chars failed: {e}")

        # 极短内容
        try:
            mid = mem.remember("Hi", category="short")
            result.add_metric("short_content", "accepted")
        except Exception as e:
            result.add_error(f"Short content failed: {e}")

        # 大量标签
        try:
            many_tags = [f"tag_{i}" for i in range(100)]
            mid = mem.remember("Many tags", tags=many_tags)
            result.add_metric("many_tags", "accepted")
        except Exception as e:
            result.add_error(f"Many tags failed: {e}")

        # 不存在的记忆查询
        try:
            result_obj = mem.long_term.get("non_existent_memory_id")
            result.add_metric("non_existent_query", "handled_gracefully")
        except Exception as e:
            result.add_error(f"Non-existent query failed: {e}")

        # 零结果查询
        try:
            results = mem.recall("xyz_this_should_not_exist_123", top_k=5)
            result.add_metric("zero_results", "ok")
        except Exception as e:
            result.add_error(f"Zero results query failed: {e}")

        # 负数 top_k
        try:
            results = mem.recall("test", top_k=-5)
            result.add_warning("Negative top_k should be rejected")
        except (ValueError, TypeError):
            result.add_metric("negative_top_k", "correctly_rejected")
        except Exception as e:
            result.add_error(f"Negative top_k error: {e}")

        # 零 top_k
        try:
            results = mem.recall("test", top_k=0)
            result.add_metric("zero_top_k", f"returned_{len(results)}")
        except Exception as e:
            result.add_error(f"Zero top_k failed: {e}")

        mem.close()

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def test_6_conversation_history() -> TestResult:
    """测试6：对话历史管理"""
    result = TestResult("对话历史测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            short_term={"working_memory_capacity": 10, "history_limit": 100},
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            structured_store={"db_path": ":memory:", "enabled": True},
        )
        mem = AgentMemory(config=config)

        # 模拟对话
        conversation = [
            ("user", "你好，我想了解机器学习"),
            ("assistant", "好的！机器学习是人工智能的一个分支，让我给你详细介绍。"),
            ("user", "什么是神经网络？"),
            ("assistant", "神经网络是一种模拟人脑神经元结构的计算模型。"),
            ("user", "如何学习机器学习？", True),  # Important
            ("assistant", "你可以通过在线课程、书籍和实践项目来学习。"),
            ("user", "推荐一些入门课程吧", True),  # Important
            ("assistant", "Andrew Ng的机器学习课程是很好的入门选择。"),
        ]

        for speaker, content, *important in conversation:
            is_important = important[0] if important else False
            try:
                mem.remember_conversation(
                    content=content,
                    speaker=speaker,
                    important=is_important,
                )
            except Exception as e:
                result.add_error(f"Remember conversation failed: {e}")

        # 获取对话历史
        try:
            history = mem.get_conversation_history(n=10)
            result.add_metric("history_count", len(history))
        except Exception as e:
            result.add_error(f"Get conversation history failed: {e}")

        # 获取相关上下文
        try:
            context = mem.get_relevant_context("机器学习", max_items=3)
            result.add_metric("context_length", len(context) if isinstance(context, list) else "N/A")
        except Exception as e:
            result.add_error(f"Get relevant context failed: {e}")

        # 测试工作记忆
        try:
            mem.add_to_working_memory(
                key="current_topic",
                content="机器学习入门",
                importance=0.8,
                memory_type="topic",
            )
            result.add_metric("working_memory_added", "ok")
        except Exception as e:
            result.add_error(f"Add to working memory failed: {e}")

        mem.close()

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def test_7_export_import() -> TestResult:
    """测试7：导出和导入功能"""
    result = TestResult("导出导入测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )

        # 创建第一个实例并添加数据
        mem1 = AgentMemory(config=config)

        test_data = [
            ("这是第一条测试记忆", "general", 0.6),
            ("这是第二条测试记忆", "general", 0.7),
            ("这是关于Python的记忆", "tech", 0.9),
        ]

        for content, cat, imp in test_data:
            mem1.remember(content, category=cat, importance=imp)

        # 导出
        export_file = "/tmp/memory_export_test.json"
        try:
            exported = mem1.export_memories(export_file, format="json")
            result.add_metric("exported_count", exported.get("exported", 0))
            result.add_metric("export_file_size", f"{os.path.getsize(export_file)} bytes")
        except Exception as e:
            result.add_error(f"Export failed: {e}")
            mem1.close()
            return result

        count_before = mem1.count_memories()
        mem1.close()

        # 导入到新实例
        mem2 = AgentMemory(config=config)
        try:
            imported = mem2.import_memories(export_file)
            result.add_metric("imported_count", imported.get("imported", 0))
            result.add_metric("import_errors", imported.get("errors", 0))
        except Exception as e:
            result.add_error(f"Import failed: {e}")
            mem2.close()
            return result

        # 验证
        count_after = mem2.count_memories()
        result.add_metric("count_before", count_before)
        result.add_metric("count_after", count_after)

        if count_before != count_after:
            result.add_warning(f"Count mismatch: {count_before} vs {count_after}")

        # 清理
        mem2.close()
        if os.path.exists(export_file):
            os.unlink(export_file)

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def test_8_memory_consolidation() -> TestResult:
    """测试8：记忆巩固功能"""
    result = TestResult("记忆巩固测试")
    start_time = time.time()

    try:
        config = AgentMemoryConfig(
            short_term={"working_memory_capacity": 20, "history_limit": 50},
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            consolidation_threshold=0.6,
            auto_consolidate=False,
        )
        mem = AgentMemory(config=config)

        # 添加工作记忆
        work_items = [
            ("key1", "Low importance item", 0.3),
            ("key2", "Medium importance item", 0.5),
            ("key3", "High importance item 1", 0.8),
            ("key4", "High importance item 2", 0.9),
        ]

        for key, content, imp in work_items:
            mem.add_to_working_memory(
                key=key,
                content=content,
                importance=imp,
                memory_type="test",
            )

        # 执行巩固
        try:
            consolidate_result = mem.consolidate()
            result.add_metric("consolidated", consolidate_result.get("consolidated", 0))
            result.add_metric("skipped", consolidate_result.get("skipped", 0))
        except Exception as e:
            result.add_error(f"Consolidate failed: {e}")

        # 验证长期记忆
        try:
            results = mem.recall("High importance", top_k=5)
            result.add_metric("recalled_after_consolidation", len(results))
        except Exception as e:
            result.add_error(f"Recall after consolidation failed: {e}")

        mem.close()

    except Exception as e:
        result.add_error(f"Unexpected error: {e}")
        import traceback
        result.add_error(f"Stack trace: {traceback.format_exc()}")

    result.execution_time = time.time() - start_time
    return result


def random_string(length: int) -> str:
    """生成随机字符串"""
    return ''.join(random.choices(string.ascii_letters + string.digits + ' ', k=length))


def main():
    print("=" * 80)
    print("  AGENT MEMORY SYSTEM - REAL SCENARIO DEPTH TESTING")
    print("=" * 80)

    tests = [
        test_1_basic_operations,
        test_2_high_volume_operations,
        test_3_knowledge_graph_operations,
        test_4_concurrent_operations,
        test_5_edge_cases,
        test_6_conversation_history,
        test_7_export_import,
        test_8_memory_consolidation,
    ]

    all_results = []
    total_start = time.time()

    for i, test_func in enumerate(tests, 1):
        print(f"\n\n{'='*80}")
        print(f"  Running Test {i}/{len(tests)}: {test_func.__name__}")
        print(f"{'='*80}")

        result = test_func()
        result.report()
        all_results.append(result)

    total_time = time.time() - total_start

    # 汇总报告
    print("\n" + "=" * 80)
    print("  SUMMARY REPORT")
    print("=" * 80)

    passed = sum(1 for r in all_results if r.passed)
    total_errors = sum(len(r.errors) for r in all_results)
    total_warnings = sum(len(r.warnings) for r in all_results)

    print(f"\n  Total Tests: {len(all_results)}")
    print(f"  Passed: {passed}/{len(all_results)}")
    print(f"  Total Errors: {total_errors}")
    print(f"  Total Warnings: {total_warnings}")
    print(f"  Total Execution Time: {total_time:.2f}s")

    if total_errors > 0:
        print(f"\n  All Errors ({total_errors}):")
        for r in all_results:
            for e in r.errors:
                print(f"    - [{r.test_name}] {e}")

    if total_warnings > 0:
        print(f"\n  All Warnings ({total_warnings}):")
        for r in all_results:
            for w in r.warnings:
                print(f"    - [{r.test_name}] {w}")

    # 详细统计
    print(f"\n  Individual Test Results:")
    for r in all_results:
        status = "✅" if r.passed else "❌"
        print(f"    {status} {r.test_name} - {r.execution_time:.2f}s")

    print("\n" + "=" * 80)
    return all_results


if __name__ == "__main__":
    main()
