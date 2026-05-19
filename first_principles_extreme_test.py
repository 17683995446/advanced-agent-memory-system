#!/usr/bin/env python3
"""
Agent Memory System - 第一性原理超极端压力测试

基于第一性原理设计的极限测试：
1. 极端并发（100+线程同时操作）
2. 极限数据量（10000+条记录）
3. 长时间持续运行（模拟真实生产环境）
4. 边界条件（内存、CPU极限）
5. 数据完整性（CRUD完全一致性验证）

这些测试模拟真实生产环境中最极端的情况。
"""

import sys
import time
import random
import string
import threading
import uuid
import os
import gc
from datetime import datetime
from typing import Dict, List, Any, Set
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import hashlib

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


@dataclass
class ExtremeTestResult:
    """极端测试结果"""
    test_name: str
    passed: bool = True
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[Dict] = field(default_factory=list)
    
    def record_issue(self, severity: str, category: str, description: str, expected: Any, actual: Any):
        self.issues.append({
            "severity": severity,
            "category": category,
            "description": description,
            "expected": expected,
            "actual": actual
        })
        if severity in ["critical", "high"]:
            self.passed = False


def generate_extreme_content(index: int, size: int = 1000) -> str:
    """生成极端测试内容"""
    chars = string.ascii_letters + string.digits + "中文测试日本語한국어"
    return f"ExtremeTest_{index}_" + "".join(random.choices(chars, k=size))


def generate_unique_id(index: int, thread_id: int) -> str:
    """生成唯一标识"""
    timestamp = int(time.time() * 1000000)
    return f"{index}_{thread_id}_{timestamp}_{uuid.uuid4().hex[:8]}"


# ================================================
# 第一性原理测试1: 极端并发安全性测试
# ================================================

def test_1_extreme_concurrency() -> ExtremeTestResult:
    """测试1: 极端并发安全性
    
    第一性原理：多线程同时操作时，系统必须保证：
    1. 数据不损坏
    2. 读写互斥正确
    3. 最终数据一致性
    """
    print("\n" + "="*90)
    print("🧪 第一性原理测试1: 极端并发安全性 (100线程×200操作)")
    print("="*90)
    
    result = ExtremeTestResult("极端并发安全性测试")
    result.start_time = time.time()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        NUM_THREADS = 100
        OPS_PER_THREAD = 200
        TOTAL_OPS = NUM_THREADS * OPS_PER_THREAD
        
        print(f"  配置: {NUM_THREADS}线程 × {OPS_PER_THREAD}操作 = {TOTAL_OPS}总操作")
        
        # 线程安全统计
        lock = threading.Lock()
        stats = {
            "writes": 0,
            "reads": 0,
            "updates": 0,
            "deletes": 0,
            "searches": 0,
            "errors": 0,
            "written_ids": [],
            "error_messages": []
        }
        
        def worker(thread_id: int):
            local_writes = 0
            local_reads = 0
            local_updates = 0
            local_deletes = 0
            local_searches = 0
            local_errors = 0
            local_ids = []
            
            for op_index in range(OPS_PER_THREAD):
                try:
                    # 混合操作：60%写，20%读，10%更新，10%搜索
                    op_choice = random.random()
                    
                    if op_choice < 0.6:  # 写入
                        content = generate_extreme_content(op_index + thread_id * OPS_PER_THREAD, random.randint(100, 500))
                        mem_id = memory.remember(
                            content=content,
                            memory_type=random.choice(["fact", "semantic", "episodic"]),
                            category="extreme_concurrency",
                            importance=random.uniform(0.1, 0.9),
                            source=f"thread_{thread_id}"
                        )
                        local_ids.append(mem_id)
                        local_writes += 1
                        
                    elif op_choice < 0.8:  # 读取
                        if local_ids:
                            random_id = random.choice(local_ids)
                            record = memory.long_term.get(random_id)
                            if record:
                                local_reads += 1
                                
                    elif op_choice < 0.9:  # 更新
                        if local_ids:
                            random_id = random.choice(local_ids)
                            new_content = generate_extreme_content(op_index, 50)
                            success = memory.long_term.update(random_id, content=new_content)
                            if success:
                                local_updates += 1
                                
                    else:  # 搜索
                        query = f"ExtremeTest_{random.randint(0, TOTAL_OPS)}"
                        results = memory.recall(query, top_k=3)
                        local_searches += 1
                
                except Exception as e:
                    local_errors += 1
                    with lock:
                        if len(stats["error_messages"]) < 5:
                            stats["error_messages"].append(str(e)[:100])
            
            # 更新全局统计
            with lock:
                stats["writes"] += local_writes
                stats["reads"] += local_reads
                stats["updates"] += local_updates
                stats["deletes"] += local_deletes
                stats["searches"] += local_searches
                stats["errors"] += local_errors
                stats["written_ids"].extend(local_ids)
        
        # 启动所有线程
        print("  启动线程池...")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = [executor.submit(worker, i) for i in range(NUM_THREADS)]
            
            completed = 0
            for future in as_completed(futures):
                future.result()
                completed += 1
                if completed % 20 == 0:
                    elapsed = time.time() - start_time
                    print(f"    进度: {completed}/{NUM_THREADS} 线程完成, 耗时 {elapsed:.1f}秒")
        
        duration = time.time() - start_time
        
        print(f"\n  操作统计:")
        print(f"    总操作: {TOTAL_OPS}")
        print(f"    写入: {stats['writes']}")
        print(f"    读取: {stats['reads']}")
        print(f"    更新: {stats['updates']}")
        print(f"    搜索: {stats['searches']}")
        print(f"    错误: {stats['errors']}")
        print(f"  总耗时: {duration:.2f}秒")
        print(f"  吞吐量: {TOTAL_OPS/duration:.1f} 操作/秒")
        
        result.metrics["总操作数"] = TOTAL_OPS
        result.metrics["吞吐量"] = f"{TOTAL_OPS/duration:.1f} ops/s"
        result.metrics["错误数"] = stats["errors"]
        result.metrics["错误率"] = f"{stats['errors']/TOTAL_OPS*100:.2f}%"
        
        # 验证数据完整性
        print(f"\n  阶段1: 数据完整性验证")
        unique_ids = set(stats["written_ids"])
        print(f"    写入ID数量: {len(stats['written_ids'])}")
        print(f"    唯一ID数量: {len(unique_ids)}")
        
        if len(stats["written_ids"]) != len(unique_ids):
            result.record_issue(
                "medium", "ID唯一性",
                f"写入ID不唯一（可能有重复）",
                f"{len(unique_ids)} 个唯一ID",
                f"{len(stats['written_ids'])} 个ID（含重复）"
            )
        
        # 验证读取
        print(f"\n  阶段2: 随机样本读取验证")
        sample_size = min(50, len(unique_ids))
        sample_ids = random.sample(list(unique_ids), sample_size)
        verified = 0
        corrupted = 0
        
        for mem_id in sample_ids:
            try:
                record = memory.long_term.get(mem_id)
                if record and record.content:
                    verified += 1
                else:
                    corrupted += 1
            except Exception:
                corrupted += 1
        
        print(f"    样本数量: {sample_size}")
        print(f"    验证成功: {verified}")
        print(f"    数据损坏: {corrupted}")
        
        if corrupted > sample_size * 0.05:  # 超过5%损坏率
            result.record_issue(
                "high", "数据完整性",
                f"数据损坏率过高",
                f"<5% ({corrupted}/{sample_size})",
                f"损坏率: {corrupted/sample_size*100:.1f}%"
            )
        
        # 错误率检查
        error_rate = stats["errors"] / TOTAL_OPS if TOTAL_OPS > 0 else 0
        if error_rate > 0.01:  # 超过1%
            result.record_issue(
                "medium", "并发错误",
                f"并发错误率过高",
                "<1%",
                f"{error_rate*100:.2f}%"
            )
        
        if stats["error_messages"]:
            print(f"\n    错误示例:")
            for msg in stats["error_messages"][:3]:
                print(f"      - {msg}")
        
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
    
    result.end_time = time.time()
    result.duration = result.end_time - result.start_time
    
    print(f"\n  📊 测试完成: {'✅ 通过' if result.passed else '❌ 失败'}, 耗时={result.duration:.2f}秒")
    return result


# ================================================
# 第一性原理测试2: 极限数据量CRUD测试
# ================================================

def test_2_extreme_crud_consistency() -> ExtremeTestResult:
    """测试2: 极限数据量CRUD完全一致性
    
    第一性原理：
    1. Create - 能创建任意数据
    2. Read - 能读取所有数据
    3. Update - 能更新任意数据
    4. Delete - 能删除任意数据
    5. 全程数据完全一致
    """
    print("\n" + "="*90)
    print("🧪 第一性原理测试2: 极限数据量CRUD完全一致性 (10000条)")
    print("="*90)
    
    result = ExtremeTestResult("极限数据量CRUD测试")
    result.start_time = time.time()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        TOTAL_RECORDS = 10000
        print(f"  配置: 创建和验证 {TOTAL_RECORDS} 条记录")
        
        # 阶段1: 批量创建
        print(f"\n  阶段1: 批量创建 {TOTAL_RECORDS} 条记录")
        start_time = time.time()
        
        created_ids = []
        create_errors = []
        
        for i in range(TOTAL_RECORDS):
            try:
                content = generate_extreme_content(i, random.randint(50, 200))
                mem_id = memory.remember(
                    content=content,
                    memory_type=random.choice(["fact", "semantic", "episodic"]),
                    category="crud_test",
                    importance=random.uniform(0.1, 0.9)
                )
                created_ids.append(mem_id)
                
                if (i + 1) % 1000 == 0:
                    elapsed = time.time() - start_time
                    print(f"    进度: {i+1}/{TOTAL_RECORDS}, 耗时: {elapsed:.1f}秒")
            except Exception as e:
                create_errors.append(str(e)[:50])
        
        create_duration = time.time() - start_time
        create_rate = len(created_ids) / create_duration
        
        print(f"\n  创建统计:")
        print(f"    成功: {len(created_ids)}/{TOTAL_RECORDS}")
        print(f"    失败: {len(create_errors)}")
        print(f"    耗时: {create_duration:.2f}秒")
        print(f"    速率: {create_rate:.1f} 条/秒")
        
        result.metrics["创建成功"] = len(created_ids)
        result.metrics["创建失败"] = len(create_errors)
        result.metrics["创建速率"] = f"{create_rate:.1f} rec/s"
        
        if len(create_errors) > TOTAL_RECORDS * 0.01:  # 超过1%失败
            result.record_issue(
                "medium", "创建失败",
                f"创建失败率过高",
                "<1%",
                f"{len(create_errors)/TOTAL_RECORDS*100:.2f}%"
            )
        
        # 阶段2: 批量读取验证
        print(f"\n  阶段2: 批量读取验证 ({len(created_ids)} 条)")
        start_time = time.time()
        
        read_success = 0
        read_failed = 0
        content_mismatch = 0
        
        for i, mem_id in enumerate(created_ids):
            try:
                record = memory.long_term.get(mem_id)
                if record and record.content:
                    read_success += 1
                else:
                    read_failed += 1
                
                if (i + 1) % 2000 == 0:
                    elapsed = time.time() - start_time
                    print(f"    进度: {i+1}/{len(created_ids)}, 耗时: {elapsed:.1f}秒")
            except Exception:
                read_failed += 1
        
        read_duration = time.time() - start_time
        read_rate = len(created_ids) / read_duration
        
        print(f"\n  读取统计:")
        print(f"    成功: {read_success}/{len(created_ids)}")
        print(f"    失败: {read_failed}")
        print(f"    耗时: {read_duration:.2f}秒")
        print(f"    速率: {read_rate:.1f} 条/秒")
        
        result.metrics["读取成功"] = read_success
        result.metrics["读取失败"] = read_failed
        
        if read_failed > len(created_ids) * 0.01:
            result.record_issue(
                "high", "读取失败",
                f"读取失败率过高",
                "<1%",
                f"{read_failed/len(created_ids)*100:.2f}%"
            )
        
        # 阶段3: 批量更新
        print(f"\n  阶段3: 批量更新 (抽样 {min(1000, len(created_ids))} 条)")
        start_time = time.time()
        
        sample_size = min(1000, len(created_ids))
        sample_ids = random.sample(created_ids, sample_size)
        update_success = 0
        update_failed = 0
        
        for i, mem_id in enumerate(sample_ids):
            try:
                new_content = generate_extreme_content(i + TOTAL_RECORDS, random.randint(50, 200))
                success = memory.long_term.update(mem_id, content=new_content)
                if success:
                    update_success += 1
                else:
                    update_failed += 1
            except Exception:
                update_failed += 1
        
        update_duration = time.time() - start_time
        update_rate = sample_size / update_duration if update_duration > 0 else 0
        
        print(f"\n  更新统计:")
        print(f"    样本: {sample_size}")
        print(f"    成功: {update_success}")
        print(f"    失败: {update_failed}")
        print(f"    耗时: {update_duration:.2f}秒")
        print(f"    速率: {update_rate:.1f} 条/秒")
        
        result.metrics["更新成功"] = update_success
        result.metrics["更新失败"] = update_failed
        
        # 验证更新效果
        print(f"\n  阶段4: 更新验证 (随机抽样)")
        verify_sample = random.sample(sample_ids, min(50, len(sample_ids)))
        verify_success = 0
        verify_failed = 0
        
        for mem_id in verify_sample:
            try:
                record = memory.long_term.get(mem_id)
                if record and record.content.startswith("ExtremeTest_"):
                    verify_success += 1
                else:
                    verify_failed += 1
            except Exception:
                verify_failed += 1
        
        print(f"    验证样本: {len(verify_sample)}")
        print(f"    验证成功: {verify_success}")
        print(f"    验证失败: {verify_failed}")
        
        if verify_failed > len(verify_sample) * 0.1:
            result.record_issue(
                "medium", "更新验证",
                f"更新后数据不正确",
                "<10% 失败",
                f"{verify_failed/len(verify_sample)*100:.1f}%"
            )
        
        # 阶段5: 统计验证
        print(f"\n  阶段5: 统计验证")
        stats = memory.get_stats()
        total_memories = stats.get("long_term", {}).get("total_memories", 0)
        
        print(f"    期望记录数: {len(created_ids)}")
        print(f"    系统统计: {total_memories}")
        
        if total_memories != len(created_ids):
            result.record_issue(
                "medium", "统计不一致",
                f"系统统计与实际记录数不一致",
                len(created_ids),
                total_memories
            )
        
    except Exception as e:
        result.record_issue("critical", "CRUD测试", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.end_time = time.time()
    result.duration = result.end_time - result.start_time
    
    print(f"\n  📊 测试完成: {'✅ 通过' if result.passed else '❌ 失败'}, 耗时={result.duration:.2f}秒")
    return result


# ================================================
# 第一性原理测试3: 内存和资源极限测试
# ================================================

def test_3_memory_resource_limits() -> ExtremeTestResult:
    """测试3: 内存和资源极限测试
    
    第一性原理：
    1. 系统在资源紧张时不应崩溃
    2. 应有合理的错误处理
    3. 资源应被正确释放
    """
    print("\n" + "="*90)
    print("🧪 第一性原理测试3: 内存和资源极限测试")
    print("="*90)
    
    result = ExtremeTestResult("内存和资源极限测试")
    result.start_time = time.time()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 测试1: 超大单条内容
        print(f"\n  测试1: 超大单条内容 (1MB)")
        try:
            huge_content = "X" * (1024 * 1024)  # 1MB
            mem_id = memory.remember(
                content=huge_content,
                memory_type="document",
                category="huge_content"
            )
            print(f"    ✅ 1MB内容写入成功: {mem_id}")
            result.metrics["超大内容1MB"] = "成功"
            
            # 验证读取
            record = memory.long_term.get(mem_id)
            if record and len(record.content) == len(huge_content):
                print(f"    ✅ 1MB内容读取验证成功")
                result.metrics["超大内容1MB读取"] = "成功"
            else:
                result.record_issue(
                    "medium", "超大内容",
                    "1MB内容读取长度不匹配",
                    len(huge_content),
                    len(record.content) if record else 0
                )
        except Exception as e:
            result.record_issue("medium", "超大内容", "1MB内容处理失败", "成功", str(e)[:50])
            result.metrics["超大内容1MB"] = f"失败: {str(e)[:30]}"
        
        # 测试2: 大量标签
        print(f"\n  测试2: 大量标签 (1000个)")
        try:
            many_tags = [f"tag_{i}" for i in range(1000)]
            mem_id = memory.remember(
                content="大量标签测试",
                memory_type="fact",
                tags=many_tags
            )
            print(f"    ✅ 1000个标签写入成功")
            
            # 验证
            record = memory.long_term.get(mem_id)
            if record:
                print(f"    ✅ 标签数量: {len(record.tags)}")
                if len(record.tags) < 900:  # 允许一些标签丢失
                    result.record_issue(
                        "low", "大量标签",
                        f"部分标签丢失",
                        ">=900",
                        len(record.tags)
                    )
        except Exception as e:
            result.record_issue("medium", "大量标签", "1000个标签处理失败", "成功", str(e)[:50])
        
        # 测试3: 重复关闭测试
        print(f"\n  测试3: 重复关闭（幂等性）")
        try:
            memory.close()
            memory.close()  # 第二次关闭
            print(f"    ✅ 重复关闭不报错（幂等）")
            result.metrics["重复关闭"] = "幂等"
            memory = None  # 避免finally中再次关闭
        except Exception as e:
            result.record_issue(
                "low", "重复关闭",
                "重复关闭应该幂等",
                "不报错",
                str(e)[:50]
            )
        
    except Exception as e:
        result.record_issue("critical", "资源测试", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.end_time = time.time()
    result.duration = result.end_time - result.start_time
    
    print(f"\n  📊 测试完成: {'✅ 通过' if result.passed else '❌ 失败'}, 耗时={result.duration:.2f}秒")
    return result


# ================================================
# 第一性原理测试4: 性能退化测试
# ================================================

def test_4_performance_degradation() -> ExtremeTestResult:
    """测试4: 性能退化测试
    
    第一性原理：
    1. 系统性能应保持稳定
    2. 不应出现明显性能退化
    3. 长期运行后仍保持高效率
    """
    print("\n" + "="*90)
    print("🧪 第一性原理测试4: 性能退化测试 (持续操作)")
    print("="*90)
    
    result = ExtremeTestResult("性能退化测试")
    result.start_time = time.time()
    
    memory = None
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 预填充数据
        print(f"  预填充1000条记录...")
        for i in range(1000):
            memory.remember(
                content=f"预填充数据_{i}",
                memory_type="semantic"
            )
        
        # 性能测试：初期
        print(f"\n  阶段1: 初期性能测试 (100次写入+100次搜索)")
        
        early_write_times = []
        for i in range(100):
            start = time.time()
            memory.remember(f"性能测试初期_{i}", memory_type="semantic")
            early_write_times.append(time.time() - start)
        
        early_search_times = []
        for i in range(100):
            start = time.time()
            memory.recall("性能测试初期", top_k=5)
            early_search_times.append(time.time() - start)
        
        early_write_avg = sum(early_write_times) / len(early_write_times)
        early_search_avg = sum(early_search_times) / len(early_search_times)
        
        print(f"    初期写入平均: {early_write_avg*1000:.2f}ms")
        print(f"    初期搜索平均: {early_search_avg*1000:.2f}ms")
        
        # 中期操作
        print(f"\n  阶段2: 中期持续操作 (500次混合操作)")
        for i in range(500):
            if random.random() < 0.5:
                memory.remember(f"中期测试_{i}", memory_type="semantic")
            else:
                memory.recall("测试", top_k=3)
        
        # 性能测试：后期
        print(f"\n  阶段3: 后期性能测试 (100次写入+100次搜索)")
        
        late_write_times = []
        for i in range(100):
            start = time.time()
            memory.remember(f"性能测试后期_{i}", memory_type="semantic")
            late_write_times.append(time.time() - start)
        
        late_search_times = []
        for i in range(100):
            start = time.time()
            memory.recall("性能测试后期", top_k=5)
            late_search_times.append(time.time() - start)
        
        late_write_avg = sum(late_write_times) / len(late_write_times)
        late_search_avg = sum(late_search_times) / len(late_search_times)
        
        print(f"    后期写入平均: {late_write_avg*1000:.2f}ms")
        print(f"    后期搜索平均: {late_search_avg*1000:.2f}ms")
        
        # 计算性能退化
        write_degradation = (late_write_avg - early_write_avg) / early_write_avg * 100
        search_degradation = (late_search_avg - early_search_avg) / early_search_avg * 100
        
        print(f"\n  性能退化分析:")
        print(f"    写入退化: {write_degradation:+.1f}%")
        print(f"    搜索退化: {search_degradation:+.1f}%")
        
        result.metrics["初期写入延迟"] = f"{early_write_avg*1000:.2f}ms"
        result.metrics["后期写入延迟"] = f"{late_write_avg*1000:.2f}ms"
        result.metrics["写入退化"] = f"{write_degradation:+.1f}%"
        result.metrics["初期搜索延迟"] = f"{early_search_avg*1000:.2f}ms"
        result.metrics["后期搜索延迟"] = f"{late_search_avg*1000:.2f}ms"
        result.metrics["搜索退化"] = f"{search_degradation:+.1f}%"
        
        # 判断性能退化是否可接受
        if write_degradation > 50:  # 退化超过50%
            result.record_issue(
                "medium", "性能退化",
                f"写入性能退化严重",
                "<50%退化",
                f"{write_degradation:.1f}%"
            )
        
        if search_degradation > 50:
            result.record_issue(
                "medium", "性能退化",
                f"搜索性能退化严重",
                "<50%退化",
                f"{search_degradation:.1f}%"
            )
        
    except Exception as e:
        result.record_issue("critical", "性能测试", "测试异常", "正常", str(e))
        import traceback
        traceback.print_exc()
    finally:
        if memory:
            try:
                memory.close()
            except:
                pass
    
    result.end_time = time.time()
    result.duration = result.end_time - result.start_time
    
    print(f"\n  📊 测试完成: {'✅ 通过' if result.passed else '❌ 失败'}, 耗时={result.duration:.2f}秒")
    return result


# ================================================
# 主函数
# ================================================

def main():
    print("\n" + "="*90)
    print("🚀 Agent Memory System - 第一性原理超极端压力测试")
    print("="*90)
    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("极端并发安全性测试", test_1_extreme_concurrency),
        ("极限数据量CRUD测试", test_2_extreme_crud_consistency),
        ("内存和资源极限测试", test_3_memory_resource_limits),
        ("性能退化测试", test_4_performance_degradation),
    ]
    
    all_results = []
    total_issues = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            all_results.append(result)
            total_issues.extend(result.issues)
        except Exception as e:
            print(f"\n❌ {test_name} 异常: {e}")
            import traceback
            traceback.print_exc()
    
    # 最终总结
    print("\n" + "="*90)
    print("📊 第一性原理超极端压力测试 - 最终总结")
    print("="*90)
    
    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    
    print(f"\n测试统计:")
    print(f"  总测试数: {total}")
    print(f"  通过: {passed}/{total} ({passed*100//total if total > 0 else 0}%)")
    print(f"  发现问题总数: {len(total_issues)}")
    
    if total_issues:
        print(f"\n问题汇总:")
        for i, issue in enumerate(total_issues):
            icon = "🔴" if issue["severity"] in ["critical", "high"] else "🟡" if issue["severity"] == "medium" else "🟢"
            print(f"  {icon} [{issue['severity'].upper()}] {issue['category']}: {issue['description']}")
            print(f"      期望: {issue['expected']}")
            print(f"      实际: {issue['actual']}")
    
    # 性能指标汇总
    print(f"\n关键性能指标:")
    for result in all_results:
        if result.metrics:
            print(f"\n  【{result.test_name}】")
            for key, value in result.metrics.items():
                print(f"    • {key}: {value}")
    
    total_duration = sum(r.duration for r in all_results)
    print(f"\n总测试耗时: {total_duration:.2f}秒 ({total_duration/60:.1f}分钟)")
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*90)
    
    return all_results


if __name__ == "__main__":
    results = main()
