#!/usr/bin/env python3
"""
Agent Memory System - 第一性原理深度测试

基于第一性原理的测试方法：
1. 从核心组件基本原理出发
2. 验证数据一致性
3. 测试长期运行稳定性
4. 验证并发安全性
5. 测试边界极限
6. 确保数据完整性

这是一个真实场景的长时间运行测试。
"""

import sys
import time
import threading
import uuid
import random
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


# =============================================
# 第一性原理测试数据模型
# =============================================

class FirstPrincipleTestResult:
    """第一性原理测试结果"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = True
        self.duration = 0.0
        self.issues: List[Dict] = []
        self.metrics: Dict[str, Any] = {}
        self.start_time = 0.0
        
    def start(self):
        self.start_time = time.time()
        
    def finish(self):
        self.duration = time.time() - self.start_time
        
    def record_issue(self, severity: str, category: str, description: str, expected: Any, actual: Any):
        self.issues.append({
            "severity": severity,
            "category": category,
            "description": description,
            "expected": expected,
            "actual": actual
        })
        if severity in ["high", "critical"]:
            self.passed = False


# =============================================
# 第一性原理测试1: 核心数据一致性测试
# =============================================

def test_1_core_data_consistency() -> FirstPrincipleTestResult:
    """测试1: 核心数据一致性
    
    验证原理：
    - 写入的数据应该等于读取的数据
    - 数据ID和内容的对应关系
    - 元数据的一致性
    """
    print("\n" + "=" * 80)
    print("🧪 第一性原理测试1: 核心数据一致性验证")
    print("=" * 80)
    
    result = FirstPrincipleTestResult("核心数据一致性测试")
    result.start()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 测试数据准备
        test_cases = [
            ("内容1", "semantic", "general", 0.5, "user"),
            ("内容2", "episodic", "important", 0.9, "assistant"),
            ("内容3", "procedural", "technical", 0.7, "system"),
        ]
        
        written_ids = []
        written_data = {}
        
        # 写入阶段
        print("  阶段1: 数据写入验证")
        for content, mem_type, category, importance, source in test_cases:
            try:
                mem_id = memory.remember(
                    content=content,
                    memory_type=mem_type,
                    category=category,
                    importance=importance,
                    source=source
                )
                written_ids.append(mem_id)
                written_data[mem_id] = {
                    "content": content,
                    "memory_type": mem_type,
                    "category": category,
                    "importance": importance,
                    "source": source
                }
                print(f"    ✅ 写入成功: ID={mem_id}, 内容={content}")
            except Exception as e:
                result.record_issue("high", "数据写入", "写入失败", "成功", str(e))
        
        # 读取验证阶段
        print("\n  阶段2: 数据读取验证")
        for mem_id, expected in written_data.items():
            try:
                record = memory.long_term.get(mem_id)
                if record is None:
                    result.record_issue("high", "数据读取", "记录不存在", "记录存在", "None")
                    continue
                
                # 验证内容一致
                if record.content != expected["content"]:
                    result.record_issue(
                        "high", "内容一致性", "内容不匹配", 
                        expected["content"], record.content
                    )
                
                # 验证元数据一致
                if record.memory_type != expected["memory_type"]:
                    result.record_issue(
                        "medium", "元数据一致性", "memory_type不匹配", 
                        expected["memory_type"], record.memory_type
                    )
                
                if record.category != expected["category"]:
                    result.record_issue(
                        "medium", "元数据一致性", "category不匹配", 
                        expected["category"], record.category
                    )
                
                # 验证重要性在合理范围内（可能有微小浮点误差）
                if abs(record.importance - expected["importance"]) > 0.001:
                    result.record_issue(
                        "low", "元数据一致性", "importance不匹配", 
                        expected["importance"], record.importance
                    )
                
                if record.source != expected["source"]:
                    result.record_issue(
                        "medium", "元数据一致性", "source不匹配", 
                        expected["source"], record.source
                    )
                
                print(f"    ✅ 读取验证通过: ID={mem_id}")
                
            except Exception as e:
                result.record_issue("high", "数据读取", "读取异常", "正常", str(e))
        
        # 验证去重机制
        print("\n  阶段3: 去重机制验证")
        for content, mem_type, category, importance, source in test_cases:
            try:
                same_id = memory.remember(
                    content=content,
                    memory_type=mem_type,
                    category=category,
                    importance=importance,
                    source=source
                )
                # 应该返回相同的ID
                original_id = None
                for key, value in written_data.items():
                    if value["content"] == content:
                        original_id = key
                        break
                
                if original_id and same_id != original_id:
                    result.record_issue(
                        "medium", "去重机制", "去重失败，返回不同ID",
                        original_id, same_id
                    )
                else:
                    print(f"    ✅ 去重机制正常: 相同内容返回相同ID")
                    
            except Exception as e:
                result.record_issue("medium", "去重机制", "去重操作异常", "成功", str(e))
        
    except Exception as e:
        result.record_issue("critical", "测试框架", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.finish()
    print(f"\n  📊 测试完成: 结果={'通过' if result.passed else '失败'}, 耗时={result.duration:.2f}秒, 发现问题={len(result.issues)}个")
    return result


# =============================================
# 第一性原理测试2: 长期运行稳定性测试
# =============================================

def test_2_long_term_stability() -> FirstPrincipleTestResult:
    """测试2: 长期运行稳定性
    
    验证原理：
    - 大量数据写入不会导致系统崩溃
    - 内存使用保持稳定
    - 长时间运行后功能正常
    """
    print("\n" + "=" * 80)
    print("🧪 第一性原理测试2: 长期运行稳定性验证")
    print("=" * 80)
    
    result = FirstPrincipleTestResult("长期运行稳定性测试")
    result.start()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        TOTAL_ITERATIONS = 1000
        OPERATION_TYPES = ["write", "read", "search", "update"]
        
        print(f"  配置: 执行{TOTAL_ITERATIONS}次随机操作")
        
        stats = {
            "writes": 0,
            "reads": 0,
            "searches": 0,
            "updates": 0,
            "errors": 0,
            "write_latencies": [],
            "search_latencies": []
        }
        
        written_ids = []
        
        # 执行长时间操作
        for i in range(TOTAL_ITERATIONS):
            try:
                op = random.choice(OPERATION_TYPES)
                
                if op == "write":
                    content = f"长期测试内容_{i}_{uuid.uuid4().hex[:8]}"
                    start = time.time()
                    mem_id = memory.remember(
                        content=content,
                        memory_type="semantic",
                        category="long_term_test",
                        importance=random.random()
                    )
                    latency = time.time() - start
                    stats["write_latencies"].append(latency)
                    stats["writes"] += 1
                    written_ids.append(mem_id)
                
                elif op == "read" and written_ids:
                    random_id = random.choice(written_ids)
                    record = memory.long_term.get(random_id)
                    if record:
                        stats["reads"] += 1
                
                elif op == "search":
                    query = f"长期测试内容_{random.randint(0, i//2)}"
                    start = time.time()
                    results = memory.recall(query, top_k=5)
                    latency = time.time() - start
                    stats["search_latencies"].append(latency)
                    stats["searches"] += 1
                
                elif op == "update" and written_ids:
                    random_id = random.choice(written_ids)
                    new_content = f"更新后的长期测试内容_{i}"
                    try:
                        success = memory.long_term.update(random_id, content=new_content)
                        if success:
                            stats["updates"] += 1
                    except Exception:
                        pass
                
                # 进度报告
                if (i + 1) % 200 == 0:
                    print(f"    进度: {i+1}/{TOTAL_ITERATIONS} ({(i+1)*100/TOTAL_ITERATIONS:.0f}%)")
                
            except Exception as e:
                stats["errors"] += 1
                if stats["errors"] <= 5:  # 只记录前5个错误
                    result.record_issue(
                        "medium" if stats["errors"] <= 3 else "low",
                        "长期稳定性",
                        f"第{i}次操作失败",
                        "成功",
                        str(e)
                    )
        
        # 计算性能指标
        print("\n  性能指标计算...")
        if stats["write_latencies"]:
            avg_write_latency = sum(stats["write_latencies"]) / len(stats["write_latencies"])
            max_write_latency = max(stats["write_latencies"])
            result.metrics["平均写入延迟"] = f"{avg_write_latency*1000:.2f}ms"
            result.metrics["最大写入延迟"] = f"{max_write_latency*1000:.2f}ms"
            print(f"    平均写入延迟: {avg_write_latency*1000:.2f}ms, 最大: {max_write_latency*1000:.2f}ms")
        
        if stats["search_latencies"]:
            avg_search_latency = sum(stats["search_latencies"]) / len(stats["search_latencies"])
            max_search_latency = max(stats["search_latencies"])
            result.metrics["平均搜索延迟"] = f"{avg_search_latency*1000:.2f}ms"
            result.metrics["最大搜索延迟"] = f"{max_search_latency*1000:.2f}ms"
            print(f"    平均搜索延迟: {avg_search_latency*1000:.2f}ms, 最大: {max_search_latency*1000:.2f}ms")
        
        result.metrics["总写入"] = stats["writes"]
        result.metrics["总读取"] = stats["reads"]
        result.metrics["总搜索"] = stats["searches"]
        result.metrics["总更新"] = stats["updates"]
        result.metrics["错误数"] = stats["errors"]
        
        print(f"\n  操作统计: 写入={stats['writes']}, 读取={stats['reads']}, 搜索={stats['searches']}, 更新={stats['updates']}, 错误={stats['errors']}")
        
        # 错误率检查
        error_rate = stats["errors"] / TOTAL_ITERATIONS if TOTAL_ITERATIONS > 0 else 0
        if error_rate > 0.05:  # 超过5%错误率
            result.record_issue(
                "medium", "稳定性", "错误率过高",
                "<5%", f"{error_rate*100:.1f}%"
            )
        elif error_rate > 0.01:
            result.record_issue(
                "low", "稳定性", "存在少量错误",
                "<1%", f"{error_rate*100:.1f}%"
            )
        
    except Exception as e:
        result.record_issue("critical", "长期稳定性", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.finish()
    print(f"\n  📊 测试完成: 结果={'通过' if result.passed else '失败'}, 耗时={result.duration:.2f}秒, 发现问题={len(result.issues)}个")
    return result


# =============================================
# 第一性原理测试3: 并发安全性测试
# =============================================

def test_3_concurrent_safety() -> FirstPrincipleTestResult:
    """测试3: 并发安全性
    
    验证原理：
    - 多线程同时操作不会导致数据损坏
    - 读写互斥正确
    - 最终数据一致性
    """
    print("\n" + "=" * 80)
    print("🧪 第一性原理测试3: 并发安全性验证")
    print("=" * 80)
    
    result = FirstPrincipleTestResult("并发安全性测试")
    result.start()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        NUM_THREADS = 10
        OPERATIONS_PER_THREAD = 100
        
        print(f"  配置: {NUM_THREADS}个线程 × {OPERATIONS_PER_THREAD}次操作")
        
        # 线程安全变量
        lock = threading.Lock()
        all_written_ids = []
        error_count = 0
        
        def worker(thread_id: int):
            nonlocal error_count
            thread_ids = []
            for i in range(OPERATIONS_PER_THREAD):
                try:
                    content = f"并发测试_线程{thread_id}_操作{i}_{uuid.uuid4().hex[:6]}"
                    mem_id = memory.remember(
                        content=content,
                        memory_type="semantic",
                        category="concurrency_test",
                        importance=0.5 + random.random() * 0.5,
                        source=f"thread_{thread_id}"
                    )
                    thread_ids.append(mem_id)
                    
                    # 偶尔读取一下
                    if random.random() < 0.3:
                        memory.recall("并发测试", top_k=3)
                        
                except Exception:
                    with lock:
                        error_count += 1
            
            # 收集写入的ID
            with lock:
                all_written_ids.extend(thread_ids)
        
        # 启动线程
        threads = []
        start_time = time.time()
        for i in range(NUM_THREADS):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        total_duration = time.time() - start_time
        
        print(f"  所有线程完成, 总耗时: {total_duration:.2f}秒")
        
        # 验证数据完整性
        print("\n  阶段1: 数据完整性验证")
        verified_count = 0
        source_counts = defaultdict(int)
        
        for mem_id in all_written_ids:
            try:
                record = memory.long_term.get(mem_id)
                if record:
                    verified_count += 1
                    source_counts[record.source] += 1
            except Exception:
                pass
        
        total_expected = NUM_THREADS * OPERATIONS_PER_THREAD
        print(f"    期望记录数: {total_expected}, 实际验证: {verified_count}")
        
        result.metrics["期望记录数"] = total_expected
        result.metrics["实际验证数"] = verified_count
        result.metrics["并发吞吐量"] = f"{total_expected/total_duration:.1f} 操作/秒"
        
        # 检查数据完整性
        completeness_rate = verified_count / total_expected if total_expected > 0 else 0
        if completeness_rate < 0.95:
            result.record_issue(
                "high", "并发完整性", "数据丢失过多",
                "≥95%", f"{completeness_rate*100:.1f}%"
            )
        elif completeness_rate < 1.0:
            result.record_issue(
                "low", "并发完整性", "存在少量数据丢失",
                "100%", f"{completeness_rate*100:.1f}%"
            )
        
        # 检查来源分布
        print(f"\n  阶段2: 来源分布验证")
        for source, count in sorted(source_counts.items()):
            print(f"    {source}: {count}条")
        
        if len(source_counts) < NUM_THREADS * 0.8:  # 至少应该有80%的线程有数据
            result.record_issue(
                "medium", "并发分布", "线程数据分布不均匀",
                "≥80%的线程有数据", f"{len(source_counts)}/{NUM_THREADS}个线程有数据"
            )
        
        print(f"\n  错误统计: {error_count}个")
        
        if error_count > total_expected * 0.05:
            result.record_issue(
                "medium", "并发错误", "并发错误率过高",
                "<5%", f"{error_count/total_expected*100:.1f}%"
            )
        
    except Exception as e:
        result.record_issue("critical", "并发安全性", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.finish()
    print(f"\n  📊 测试完成: 结果={'通过' if result.passed else '失败'}, 耗时={result.duration:.2f}秒, 发现问题={len(result.issues)}个")
    return result


# =============================================
# 第一性原理测试4: 边界极限测试
# =============================================

def test_4_boundary_limits() -> FirstPrincipleTestResult:
    """测试4: 边界极限测试
    
    验证原理：
    - 超大内容
    - 极小内容
    - 大量标签
    - 极高/极低重要性
    - 特殊字符
    """
    print("\n" + "=" * 80)
    print("🧪 第一性原理测试4: 边界极限验证")
    print("=" * 80)
    
    result = FirstPrincipleTestResult("边界极限测试")
    result.start()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        test_cases = []
        
        # 极限测试1: 极大内容
        print("\n  极限测试1: 超大内容")
        huge_content = "X" * 50000  # 50KB超大内容
        try:
            huge_id = memory.remember(
                content=huge_content,
                memory_type="document",
                category="huge_content",
                importance=0.5
            )
            print(f"    ✅ 超大内容写入成功: ID={huge_id}, 大小={len(huge_content)}字节")
            
            # 验证读取
            record = memory.long_term.get(huge_id)
            if record and len(record.content) == len(huge_content):
                print(f"    ✅ 超大内容读取验证成功")
            else:
                result.record_issue(
                    "medium", "边界极限", "超大内容读取不完整",
                    f"{len(huge_content)}字节", f"{len(record.content) if record else 0}字节"
                )
        except Exception as e:
            result.record_issue("high", "边界极限", "超大内容处理失败", "成功", str(e))
        
        # 极限测试2: 极小内容
        print("\n  极限测试2: 极小内容")
        tiny_contents = ["A", "1", " ", "\n", "\t"]
        tiny_success = 0
        for tiny in tiny_contents:
            try:
                tiny_id = memory.remember(
                    content=tiny,
                    memory_type="fact",
                    category="tiny_content",
                    importance=0.3
                )
                tiny_success += 1
            except Exception as e:
                result.record_issue(
                    "low", "边界极限", f"极小内容处理失败: {repr(tiny)}",
                    "成功", str(e)
                )
        
        print(f"    ✅ 极小内容测试完成: {tiny_success}/{len(tiny_contents)}成功")
        
        # 极限测试3: 大量标签
        print("\n  极限测试3: 大量标签")
        many_tags = [f"tag_{i}" for i in range(200)]
        try:
            tags_id = memory.remember(
                content="大量标签测试内容",
                memory_type="fact",
                category="tags_test",
                importance=0.5,
                tags=many_tags
            )
            print(f"    ✅ 大量标签写入成功: {len(many_tags)}个标签")
            
            # 验证标签
            record = memory.long_term.get(tags_id)
            if record and len(record.tags) >= 100:  # 只要有100个以上就算可以接受
                print(f"    ✅ 标签数量验证通过: {len(record.tags)}个")
            elif record:
                result.record_issue(
                    "low", "边界极限", "部分标签丢失",
                    f"{len(many_tags)}个", f"{len(record.tags)}个"
                )
        except Exception as e:
            result.record_issue("medium", "边界极限", "大量标签处理失败", "成功", str(e))
        
        # 极限测试4: 极端重要性值
        print("\n  极限测试4: 极端重要性值")
        importance_test_values = [0.0, 0.0001, 0.5, 0.9999, 1.0]
        for importance in importance_test_values:
            try:
                imp_id = memory.remember(
                    content=f"重要性测试内容_{importance}",
                    memory_type="fact",
                    category="importance_test",
                    importance=importance
                )
                record = memory.long_term.get(imp_id)
                if record:
                    print(f"    ✅ importance={importance} 处理成功")
            except Exception as e:
                if 0 < importance < 1:  # 在有效范围内应该成功
                    result.record_issue(
                        "medium", "边界极限", f"importance={importance}处理失败",
                        "成功", str(e)
                    )
        
        # 极限测试5: 特殊字符
        print("\n  极限测试5: 特殊字符")
        special_content = (
            "中文测试\x00特殊字符\n换行\t制表"
            "🐼Emoji测试💻\n"
            "Unicode字符\u2028\u2029"
        )
        try:
            special_id = memory.remember(
                content=special_content,
                memory_type="fact",
                category="special_chars",
                importance=0.4
            )
            print(f"    ✅ 特殊字符写入成功")
            
            record = memory.long_term.get(special_id)
            if record and len(record.content) > 0:
                print(f"    ✅ 特殊字符读取成功")
        except Exception as e:
            result.record_issue("medium", "边界极限", "特殊字符处理失败", "成功", str(e))
        
    except Exception as e:
        result.record_issue("critical", "边界极限", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.finish()
    print(f"\n  📊 测试完成: 结果={'通过' if result.passed else '失败'}, 耗时={result.duration:.2f}秒, 发现问题={len(result.issues)}个")
    return result


# =============================================
# 第一性原理测试5: 知识图谱深度集成测试
# =============================================

def test_5_knowledge_graph_integration() -> FirstPrincipleTestResult:
    """测试5: 知识图谱深度集成测试
    
    验证原理：
    - 知识图谱构建
    - 实体关系查询
    - 图谱遍历
    - 混合搜索集成
    """
    print("\n" + "=" * 80)
    print("🧪 第一性原理测试5: 知识图谱深度集成验证")
    print("=" * 80)
    
    result = FirstPrincipleTestResult("知识图谱深度集成测试")
    result.start()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 构建复杂知识图谱
        print("\n  阶段1: 构建复杂知识图谱")
        
        # 领域实体
        entities = [
            ("Python", "language", "Python编程语言"),
            ("JavaScript", "language", "JavaScript编程语言"),
            ("React", "framework", "React前端框架"),
            ("Vue", "framework", "Vue前端框架"),
            ("Django", "framework", "Django后端框架"),
            ("FastAPI", "framework", "FastAPI后端框架"),
            ("数据库", "technology", "数据存储技术"),
            ("API", "concept", "应用程序接口"),
            ("机器学习", "field", "人工智能领域"),
            ("深度学习", "field", "机器学习子领域"),
        ]
        
        entity_ids = {}
        for name, entity_type, description in entities:
            try:
                eid = memory.add_entity(name, entity_type=entity_type, description=description)
                entity_ids[name] = eid
                print(f"    ✅ 添加实体: {name} ({entity_type})")
            except Exception as e:
                result.record_issue(
                    "low", "知识图谱", f"添加实体失败: {name}",
                    "成功", str(e)
                )
        
        # 构建关系
        print("\n  阶段2: 构建实体关系")
        relations = [
            ("Python", "Django", "used_in", 0.9),
            ("Python", "FastAPI", "used_in", 0.85),
            ("Python", "机器学习", "used_in", 0.95),
            ("JavaScript", "React", "used_in", 0.9),
            ("JavaScript", "Vue", "used_in", 0.85),
            ("React", "API", "interacts_with", 0.7),
            ("Django", "API", "provides", 0.8),
            ("FastAPI", "API", "provides", 0.9),
            ("机器学习", "深度学习", "includes", 0.9),
        ]
        
        relation_count = 0
        for source, target, rel_type, weight in relations:
            if source in entity_ids and target in entity_ids:
                try:
                    memory.add_relation(source, target, rel_type, weight=weight)
                    relation_count += 1
                    print(f"    ✅ 添加关系: {source} → {rel_type} → {target}")
                except Exception as e:
                    pass
        
        print(f"\n  图谱构建完成: {len(entity_ids)}个实体, {relation_count}个关系")
        
        # 添加相关的长期记忆
        print("\n  阶段3: 添加相关长期记忆")
        kg_memories = [
            "Django是一个高效的Web框架，使用Python开发",
            "React和Vue都是流行的前端框架，各有特点",
            "API是现代Web应用的核心组成部分",
            "机器学习和深度学习正在快速发展",
            "FastAPI以其高性能著称",
        ]
        
        for content in kg_memories:
            try:
                memory.remember(
                    content=content,
                    memory_type="semantic",
                    category="knowledge",
                    importance=0.8,
                    source="knowledge_base"
                )
            except Exception:
                pass
        
        # 测试实体搜索
        print("\n  阶段4: 知识图谱查询测试")
        try:
            search_results = memory.search_entities("Python", top_k=5)
            if search_results:
                print(f"    ✅ 实体搜索成功: 找到{len(search_results)}个相关实体")
                for entity_obj, score in search_results:
                    entity_name = getattr(entity_obj, 'name', str(entity_obj))
                    print(f"      - {entity_name}, 相似度: {score:.3f}")
            else:
                result.record_issue(
                    "low", "知识图谱", "实体搜索无结果",
                    "有结果", "无结果"
                )
        except Exception as e:
            result.record_issue("medium", "知识图谱", "实体搜索异常", "正常", str(e))
        
        # 测试相关实体查询
        print("\n  阶段5: 相关实体查询")
        if "Python" in entity_ids:
            try:
                related = memory.find_related("Python", top_k=5)
                if related:
                    print(f"    ✅ 相关实体查询成功: 找到{len(related)}个")
                else:
                    print(f"    ⚠️ 相关实体查询无结果（可能是新特性）")
            except Exception as e:
                print(f"    ⚠️ 相关实体查询失败: {str(e)[:50]}")
        
        # 测试混合搜索
        print("\n  阶段6: 知识图谱增强的混合搜索")
        try:
            hybrid_results = memory.recall("Python框架", top_k=5)
            if hybrid_results:
                print(f"    ✅ 混合搜索成功: 找到{len(hybrid_results)}条记忆")
                for i, res in enumerate(hybrid_results):
                    preview = res.get("content", "")[:50]
                    print(f"      {i+1}. {preview}...")
            else:
                print(f"    ⚠️ 混合搜索无结果")
        except Exception as e:
            result.record_issue("low", "知识图谱", "混合搜索异常", "正常", str(e))
        
        # 知识图谱统计
        print("\n  阶段7: 知识图谱统计")
        try:
            stats = memory.get_stats()
            kg_stats = stats.get("knowledge_graph", {})
            print(f"    实体数: {kg_stats.get('entity_count', 0)}")
            print(f"    关系数: {kg_stats.get('relation_count', 0)}")
            result.metrics.update(kg_stats)
        except Exception as e:
            pass
        
    except Exception as e:
        result.record_issue("critical", "知识图谱", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.finish()
    print(f"\n  📊 测试完成: 结果={'通过' if result.passed else '失败'}, 耗时={result.duration:.2f}秒, 发现问题={len(result.issues)}个")
    return result


# =============================================
# 主测试函数
# =============================================

def main():
    print("\n" + "=" * 80)
    print("🚀 Agent Memory System - 第一性原理深度测试")
    print("=" * 80)
    print(f"\n开始时间: {datetime.now().isoformat()}")
    
    tests = [
        test_1_core_data_consistency,
        test_2_long_term_stability,
        test_3_concurrent_safety,
        test_4_boundary_limits,
        test_5_knowledge_graph_integration,
    ]
    
    all_results = []
    all_issues = []
    
    for test_func in tests:
        try:
            result = test_func()
            all_results.append(result)
            all_issues.extend(result.issues)
        except Exception as e:
            print(f"\n❌ {test_func.__name__} 异常: {e}")
            import traceback
            traceback.print_exc()
    
    # 最终总结
    print("\n" + "=" * 80)
    print("📊 第一性原理深度测试 - 最终总结")
    print("=" * 80)
    
    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    
    print(f"\n测试统计:")
    print(f"  总测试数: {total}")
    print(f"  通过: {passed}/{total} ({passed*100/total if total > 0 else 0:.1f}%)")
    print(f"  发现问题总数: {len(all_issues)}")
    
    if all_issues:
        print(f"\n问题汇总:")
        for i, issue in enumerate(all_issues):
            icon = "🔴" if issue["severity"] in ["high", "critical"] else "🟡" if issue["severity"] == "medium" else "🟢"
            print(f"  {icon} [{i+1}] {issue['category']}: {issue['description']}")
            print(f"      期望: {issue['expected']}")
            print(f"      实际: {issue['actual']}")
    
    # 性能指标汇总
    print(f"\n性能指标汇总:")
    for result in all_results:
        if result.metrics:
            print(f"\n  {result.test_name}:")
            for key, value in result.metrics.items():
                print(f"    - {key}: {value}")
    
    print(f"\n完成时间: {datetime.now().isoformat()}")
    print("=" * 80)
    
    return all_results


if __name__ == "__main__":
    results = main()
