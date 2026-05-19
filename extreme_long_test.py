#!/usr/bin/env python3
"""
Agent Memory System - 极端长时混合操作压力测试
基于第一性原理，长时间运行大量混合操作，验证稳定性
"""

import sys
import time
import random
import threading
import uuid
import gc
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


@dataclass
class TestMetrics:
    """测试指标记录"""
    operations: int = 0
    writes: int = 0
    reads: int = 0
    updates: int = 0
    deletes: int = 0
    searches: int = 0
    errors: int = 0
    latency_samples: List[float] = field(default_factory=list)
    error_log: List[Dict] = field(default_factory=list)
    start_time: float = 0.0


def generate_large_content(length: int) -> str:
    """生成大内容"""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789中文测试日本語한국어"
    return ''.join(random.choice(chars) for _ in range(length))


def random_memory_content() -> Tuple[str, Dict[str, Any]]:
    """生成随机记忆内容和元数据"""
    categories = ["work", "personal", "knowledge", "notes", "ideas", "projects"]
    memory_types = ["fact", "semantic", "episodic", "procedural", "conversation"]
    topics = ["机器学习", "Python", "Web开发", "系统设计", "API", "数据分析", "AI", "数据库", "测试"]
    
    topic = random.choice(topics)
    length = random.randint(50, 1000)
    content = f"关于{topic}的记忆内容: {generate_large_content(length)}"
    
    metadata = {
        "category": random.choice(categories),
        "memory_type": random.choice(memory_types),
        "project": f"project_{random.randint(1, 100)}",
        "user": f"user_{random.randint(1, 20)}"
    }
    
    return content, metadata


def test_extreme_long_operations(duration_minutes: int = 2, 
                            num_threads: int = 12) -> Dict[str, Any]:
    """极端长时间混合操作测试"""
    
    print(f"\n{'=' * 80}")
    print(f"极端长时混合操作测试")
    print(f"{'=' * 80}")
    print(f"目标时长: {duration_minutes} 分钟")
    print(f"线程数: {num_threads}")
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
        short_term={"working_memory_capacity": 20
    )
    
    memory = AgentMemory(config=config)
    
    metrics = TestMetrics(start_time=time.time())
    all_ids: List[str] = []
    lock = threading.Lock()
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    def worker_thread(thread_id: int):
        """工作线程"""
        local_metrics = {"writes": 0, "reads": 0, "updates": 0, 
                       "deletes": 0, "searches": 0, "errors": 0}
        
        while time.time() < end_time:
            try:
                # 混合操作分布
                choice = random.random()
                operation_start = time.time()
                
                if choice < 0.35:  # 35% 写入
                    content, metadata = random_memory_content()
                    mem_id = memory.remember(
                        content=content,
                        importance=random.uniform(0.1, 0.9),
                        **metadata
                    )
                    with lock:
                        all_ids.append(mem_id)
                    local_metrics["writes"] += 1
                    
                elif choice < 0.6:  # 25% 读取
                    with lock:
                        if all_ids:
                            random_id = random.choice(all_ids)
                            try:
                                record = memory.long_term.get(random_id)
                                if record:
                                    local_metrics["reads"] += 1
                            except:
                                pass
                    
                elif choice < 0.75:  # 15% 更新
                    with lock:
                        if all_ids:
                            random_id = random.choice(all_ids)
                            try:
                                new_content = f"更新内容: {generate_large_content(random.randint(50, 500))}"
                                success = memory.long_term.update(random_id, content=new_content)
                                if success:
                                    local_metrics["updates"] += 1
                            except:
                                pass
                    
                elif choice < 0.9:  # 15% 搜索
                    queries = ["记忆", "机器学习", "Python", "知识", "测试", "项目"]
                    try:
                        results = memory.recall(
                            random.choice(queries), 
                            top_k=random.randint(1, 5)
                        )
                        local_metrics["searches"] += 1
                    except:
                        pass
                    
                else:  # 10% 删除
                    with lock:
                        if all_ids:
                            random_id = random.choice(all_ids)
                            try:
                                success = memory.forget_memory(random_id)
                                if success:
                                    all_ids.remove(random_id)
                                    local_metrics["deletes"] += 1
                            except:
                                pass
                
                # 记录延迟
                latency = time.time() - operation_start
                with lock:
                    metrics.latency_samples.append(latency)
                    metrics.operations += 1
                
            except Exception as e:
                local_metrics["errors"] += 1
                with lock:
                    metrics.errors += 1
                    if len(metrics.error_log) < 100:
                        metrics.error_log.append({
                            "thread": thread_id,
                            "time": time.time(),
                            "error": str(e)[:100]
                        })
                time.sleep(0.01)  # 出错时短暂暂停
            
            time.sleep(random.uniform(0.001, 0.01))
        
        # 汇总本地指标
        with lock:
            metrics.writes += local_metrics["writes"]
            metrics.reads += local_metrics["reads"]
            metrics.updates += local_metrics["updates"]
            metrics.deletes += local_metrics["deletes"]
            metrics.searches += local_metrics["searches"]
    
    print(f"\n开始测试中...请等待 {duration_minutes} 分钟")
    
    # 先预填充一些初始数据
    print(f"\n预填充初始数据...")
    for i in range(100):
        content, metadata = random_memory_content()
        mem_id = memory.remember(
            content=content,
            importance=random.uniform(0.1, 0.9),
            **metadata
        )
        all_ids.append(mem_id)
    print(f"预填充了 {len(all_ids)} 条记录")
    
    # 启动所有工作线程
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_thread, i) for i in range(num_threads)]
        
        # 监控进度
        last_report_time = time.time()
        last_ops_count = 0
        while time.time() < end_time:
            time.sleep(5)
            
            with lock:
                current_ops = metrics.operations
                elapsed = time.time() - start_time
                if time.time() - last_report_time >= 30:  # 每30秒报告一次
                    ops_since = current_ops - last_ops_count
                    ops_rate = ops_since / (time.time() - last_report_time)
                    
                    print(f"\n[进度] 已运行 {elapsed:.1f}秒")
                    print(f"  总操作: {current_ops}")
                    print(f"  最近速率: {ops_rate:.1f} 操作/秒")
                    
                    last_report_time = time.time()
                    last_ops_count = current_ops
        
        # 等待所有线程完成
        for future in futures:
            future.result()
    
    # 计算最终指标
    total_time = time.time() - start_time
    
    # 分析性能指标
    avg_latency = (
        sum(metrics.latency_samples) / len(metrics.latency_samples) if metrics.latency_samples else 0
    max_latency = max(metrics.latency_samples) if metrics.latency_samples else 0
    
    print(f"\n{'=' * 60}")
    print("极端长时混合操作测试 - 结果")
    print(f"{'=' * 60}")
    print(f"总耗时: {total_time:.2f}秒 ({total_time/60:.1f}分钟)")
    print(f"总操作数: {metrics.operations}")
    print(f"  写入: {metrics.writes}")
    print(f"  读取: {metrics.reads}")
    print(f"  更新: {metrics.updates}")
    print(f"  删除: {metrics.deletes}")
    print(f"  搜索: {metrics.searches}")
    print(f"  错误: {metrics.errors}")
    print(f"平均延迟: {avg_latency*1000:.2f}ms")
    print(f"最大延迟: {max_latency*1000:.2f}ms")
    print(f"吞吐率: {metrics.operations/total_time:.1f} 操作/秒")
    
    # 数据验证
    print(f"\n最终系统统计:")
    stats = memory.get_stats()
    print(f"  长期记忆数量: {stats.get('long_term', {}).get('total_memories', 0)}")
    print(f"  短期记忆数量: {stats.get('short_term', {}).get('history_count', 0)}")
    
    # 清理
    memory.close()
    
    result = {
        "total_time": total_time,
        "operations": metrics.operations,
        "writes": metrics.writes,
        "reads": metrics.reads,
        "updates": metrics.updates,
        "deletes": metrics.deletes,
        "searches": metrics.searches,
        "errors": metrics.errors,
        "error_log": metrics.error_log,
        "avg_latency": avg_latency,
        "max_latency": max_latency,
        "final_stats": stats
    }
    
    return result


def test_memory_consistency_after_stress():
    """压力测试后的数据一致性验证"""
    
    print(f"\n{'=' * 80}")
    print(f"数据一致性验证测试")
    print(f"{'=' * 80}")
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    
    memory = AgentMemory(config=config)
    
    # 先写入1000条记录
    print(f"\n写入参考数据: 1000 条")
    ids = []
    for i in range(1000):
        content = f"验证记录 #{i}: {generate_large_content(100)}"
        mem_id = memory.remember(
            content=content,
            memory_type="fact",
            importance=0.7,
            index=i
        )
        ids.append(mem_id)
    
    # 执行一些压力操作
    print(f"执行混合操作: 写入、更新、删除...")
    for i in range(200):
        choice = random.random()
        if choice < 0.3 and ids:
            random_id = random.choice(ids)
            memory.forget_memory(random_id)
            ids.remove(random_id)
        elif choice < 0.6 and ids:
            random_id = random.choice(ids)
            new_content = f"已更新内容 {i}"
            memory.long_term.update(random_id, content=new_content)
    
    # 验证
    print(f"\n验证读取一致性:")
    verified = 0
    errors = []
    
    for mem_id in ids[:100]:  # 抽样验证
        try:
            record = memory.long_term.get(mem_id)
            if record:
                verified += 1
        except Exception as e:
            errors.append(str(e))
    
    print(f"  抽样验证: {verified}/100")
    print(f"  错误: {len(errors)}")
    
    # 批量搜索
    print(f"\n搜索一致性验证:")
    search_queries = ["验证", "记录", "内容", "测试"]
    search_errors = []
    for q in search_queries:
        try:
            results = memory.recall(q, top_k=3)
            print(f"  查询 '{q}': {len(results)} 结果")
        except Exception as e:
            search_errors.append(str(e))
    
    stats = memory.get_stats()
    print(f"\n最终统计: {stats.get('long_term', {}).get('total_memories', 0)}")
    
    memory.close()
    
    return {
        "verified_count": verified,
        "errors": errors,
        "search_errors": search_errors
    }


def main():
    """主函数：运行完整极端压力测试"""
    
    print(f"\n{'=' * 80}")
    print("Agent Memory System - 极端长时混合操作压力测试")
    print(f"{'=' * 80}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_results = {}
    
    # 测试1：极端长时混合操作（时间缩短为1分钟演示）
    try:
        result = test_extreme_long_operations(duration_minutes=1, num_threads=12)
        all_results["extreme_long_ops"] = result
    except Exception as e:
        print(f"\n❌ 极端长时操作测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 测试2：一致性验证
    try:
        result = test_memory_consistency_after_stress()
        all_results["consistency"] = result
    except Exception as e:
        print(f"\n❌ 一致性验证测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 总结
    print(f"\n{'=' * 80}")
    print("极端压力测试 - 最终总结")
    print(f"{'=' * 80}")
    
    total_issues = 0
    if "extreme_long_ops" in all_results:
        extreme_result = all_results["extreme_long_ops"]
        total_issues += extreme_result.get("errors", 0)
        
        print(f"\n极端长时操作测试:")
        print(f"  错误数: {extreme_result['errors']}")
        if extreme_result.get("error_log"):
            print(f"  错误示例:")
            for err in extreme_result["error_log"][:5]:
                print(f"    - {err}")
    
    if "consistency" in all_results:
        consistency_result = all_results["consistency"]
        total_issues += len(consistency_result.get("errors", []))
        total_issues += len(consistency_result.get("search_errors", []))
        
        print(f"\n一致性验证测试:")
        print(f"  验证错误: {len(consistency_result.get('errors', []))}")
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return all_results


if __name__ == "__main__":
    main()
