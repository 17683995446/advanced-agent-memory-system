#!/usr/bin/env python3
"""
Agent Memory System - 快速极度混乱场景测试
慢工出细活：快速发现真实运行时的bug（1分钟版本）
"""

import sys
import time
import random
import string
import threading
import traceback
from typing import Dict, List, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from collections import defaultdict

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


@dataclass
class ChaosMetrics:
    """混乱度量和监控"""
    operations: int = 0
    writes: int = 0
    reads: int = 0
    updates: int = 0
    deletes: int = 0
    searches: int = 0
    kg_operations: int = 0
    errors: int = 0
    warnings: int = 0
    error_log: List[Dict] = field(default_factory=list)
    warning_log: List[Dict] = field(default_factory=list)
    latencies: List[float] = field(default_factory=list)
    start_time: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


def generate_chaos_content(size: int) -> str:
    """生成混乱的内容"""
    chars = string.ascii_letters + string.digits + "中文测试日本語한국어🎉🎊💻🔧"
    return ''.join(random.choice(chars) for _ in range(size))


def generate_chaos_metadata() -> Dict[str, Any]:
    """生成混乱的元数据"""
    categories = ["chaos", "test", "extreme", "混乱", "Chaos", "极端", "疯狂"]
    memory_types = ["fact", "semantic", "episodic", "procedural", "flashbulb", "未知类型"]
    sources = ["user_input", "system", "api", "web", "unknown", "未知来源"]
    
    num_tags = random.randint(0, 20)
    tags = [generate_chaos_content(random.randint(3, 15)) for _ in range(num_tags)]
    
    return {
        "category": random.choice(categories),
        "memory_type": random.choice(memory_types),
        "source": random.choice(sources),
        "importance": random.uniform(0.0, 1.0),  # 确保在有效范围内
        "tags": tags,
    }


def chaos_worker(
    worker_id: int,
    duration_seconds: int,
    metrics: ChaosMetrics,
    all_ids: List[str],
    all_ids_lock: threading.Lock
) -> Dict[str, Any]:
    """极度混乱的工作线程"""
    
    local_stats = {
        "ops": 0, "writes": 0, "reads": 0, "updates": 0,
        "deletes": 0, "searches": 0, "kg_ops": 0, "errors": 0
    }
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
        )
        memory = AgentMemory(config=config)
    except Exception as e:
        with metrics.lock:
            metrics.errors += 1
            metrics.error_log.append({
                "worker": worker_id,
                "time": datetime.now().isoformat(),
                "phase": "init",
                "error": str(e)
            })
        return local_stats
    
    start_time = time.time()
    end_time = start_time + duration_seconds
    
    operation_patterns = [
        ("write", 0.30),
        ("read", 0.25),
        ("update", 0.15),
        ("delete", 0.10),
        ("search", 0.15),
        ("kg", 0.05),
    ]
    
    while time.time() < end_time:
        try:
            choice = random.random()
            operation = None
            cumulative = 0
            for op_name, prob in operation_patterns:
                cumulative += prob
                if choice < cumulative:
                    operation = op_name
                    break
            
            if operation is None:
                operation = "write"
            
            op_start = time.time()
            
            if operation == "write":
                content_size = random.randint(10, 5000)
                content = generate_chaos_content(content_size)
                metadata = generate_chaos_metadata()
                
                mem_id = memory.remember(content=content, **metadata)
                
                with all_ids_lock:
                    all_ids.append(mem_id)
                
                local_stats["writes"] += 1
                
            elif operation == "read":
                with all_ids_lock:
                    if all_ids:
                        target_id = random.choice(all_ids)
                        if random.random() < 0.1:
                            target_id = f"non_existent_{random.randint(1, 999999)}"
                
                try:
                    record = memory.long_term.get(target_id)
                    local_stats["reads"] += 1
                except Exception:
                    pass
                    
            elif operation == "update":
                with all_ids_lock:
                    if all_ids:
                        target_id = random.choice(all_ids)
                
                try:
                    new_content = generate_chaos_content(random.randint(10, 1000))
                    memory.long_term.update(target_id, content=new_content)
                    local_stats["updates"] += 1
                except Exception:
                    pass
                    
            elif operation == "delete":
                with all_ids_lock:
                    if all_ids:
                        target_id = random.choice(all_ids)
                        if random.random() < 0.3:
                            target_id = f"fake_id_{random.randint(1, 999999)}"
                
                try:
                    success = memory.forget_memory(target_id)
                    if success:
                        with all_ids_lock:
                            if target_id in all_ids:
                                all_ids.remove(target_id)
                    local_stats["deletes"] += 1
                except Exception:
                    pass
                    
            elif operation == "search":
                query_size = random.randint(1, 50)
                query = generate_chaos_content(query_size)
                top_k = random.randint(1, 20)
                
                try:
                    results = memory.recall(query, top_k=top_k)
                    local_stats["searches"] += 1
                except Exception as e:
                    with metrics.lock:
                        metrics.warnings += 1
                        if len(metrics.warning_log) < 50:
                            metrics.warning_log.append({
                                "worker": worker_id,
                                "time": datetime.now().isoformat(),
                                "phase": "search",
                                "warning": str(e)[:100]
                            })
                    
            elif operation == "kg":
                try:
                    entity_name = f"ChaosEntity_{worker_id}_{random.randint(1, 10000)}"
                    from memory_system.processing.knowledge_graph_engine import Entity
                    entity = Entity(
                        name=entity_name,
                        entity_type="chaos",
                        description=generate_chaos_content(100)
                    )
                    memory.add_entity(entity)
                    local_stats["kg_ops"] += 1
                except Exception:
                    pass
            
            op_latency = time.time() - op_start
            
            with metrics.lock:
                metrics.operations += 1
                metrics.latencies.append(op_latency)
            
            local_stats["ops"] += 1
            
            if random.random() < 0.1:
                time.sleep(random.uniform(0.01, 0.1))
            else:
                time.sleep(random.uniform(0.0001, 0.01))
                
        except Exception as e:
            local_stats["errors"] += 1
            with metrics.lock:
                metrics.errors += 1
                if len(metrics.error_log) < 100:
                    metrics.error_log.append({
                        "worker": worker_id,
                        "time": datetime.now().isoformat(),
                        "phase": "operation",
                        "error": str(e),
                        "trace": traceback.format_exc()[:200]
                    })
    
    try:
        memory.close()
    except:
        pass
    
    return local_stats


def run_chaos_test(
    duration_seconds: int = 60,
    num_workers: int = 20,
    initial_records: int = 500
) -> Dict[str, Any]:
    """运行极度混乱的测试"""
    
    print(f"\n{'='*100}")
    print(f"🔥 极度混乱场景测试 - 慢工出细活 (快速版)")
    print(f"{'='*100}")
    print(f"测试时长: {duration_seconds}秒")
    print(f"并发工作线程: {num_workers}")
    print(f"初始记录数: {initial_records}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
    )
    shared_memory = AgentMemory(config=config)
    
    print(f"\n预填充初始数据...")
    all_ids = []
    for i in range(initial_records):
        content = f"初始数据 {i}: " + generate_chaos_content(200)
        mem_id = shared_memory.remember(
            content=content,
            category="initial",
            importance=0.5
        )
        all_ids.append(mem_id)
        if (i+1) % 100 == 0:
            print(f"  已预填充 {i+1}/{initial_records} 条记录")
    
    print(f"预填充完成！开始极度混乱测试...")
    
    metrics = ChaosMetrics()
    metrics.start_time = time.time()
    
    print(f"\n启动 {num_workers} 个极度混乱的工作线程...")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(
                chaos_worker,
                i,
                duration_seconds,
                metrics,
                all_ids,
                threading.Lock()
            )
            for i in range(num_workers)
        ]
        
        last_report = time.time()
        while any(f.running() for f in futures):
            time.sleep(5)
            
            elapsed = time.time() - start_time
            if time.time() - last_report >= 15:
                with metrics.lock:
                    ops = metrics.operations
                    errors = metrics.errors
                    throughput = ops / elapsed if elapsed > 0 else 0
                
                print(f"\n[进度] 已运行 {elapsed:.0f}秒")
                print(f"  总操作: {ops:,}")
                print(f"  错误数: {errors}")
                print(f"  吞吐率: {throughput:.1f} 操作/秒")
                
                last_report = time.time()
        
        worker_results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                worker_results.append(result)
            except Exception as e:
                with metrics.lock:
                    metrics.errors += 1
                    metrics.error_log.append({
                        "worker": "executor",
                        "error": str(e)
                    })
    
    total_duration = time.time() - start_time
    
    try:
        shared_memory.close()
    except:
        pass
    
    return generate_chaos_report(total_duration, metrics, worker_results)


def generate_chaos_report(
    duration: float,
    metrics: ChaosMetrics,
    worker_results: List[Dict]
) -> Dict[str, Any]:
    """生成混乱测试报告"""
    
    print(f"\n{'='*100}")
    print(f"🔥 极度混乱场景测试 - 最终报告")
    print(f"{'='*100}")
    
    total_ops = sum(wr.get("ops", 0) for wr in worker_results)
    total_writes = sum(wr.get("writes", 0) for wr in worker_results)
    total_reads = sum(wr.get("reads", 0) for wr in worker_results)
    total_updates = sum(wr.get("updates", 0) for wr in worker_results)
    total_deletes = sum(wr.get("deletes", 0) for wr in worker_results)
    total_searches = sum(wr.get("searches", 0) for wr in worker_results)
    total_kg_ops = sum(wr.get("kg_ops", 0) for wr in worker_results)
    total_errors = sum(wr.get("errors", 0) for wr in worker_results)
    
    avg_latency = sum(metrics.latencies) / len(metrics.latencies) if metrics.latencies else 0
    max_latency = max(metrics.latencies) if metrics.latencies else 0
    p95_latency = sorted(metrics.latencies)[int(len(metrics.latencies) * 0.95)] if metrics.latencies else 0
    
    print(f"\n总运行时间: {duration:.2f}秒")
    print(f"\n操作统计:")
    print(f"  总操作数: {total_ops:,}")
    print(f"  写入: {total_writes:,}")
    print(f"  读取: {total_reads:,}")
    print(f"  更新: {total_updates:,}")
    print(f"  删除: {total_deletes:,}")
    print(f"  搜索: {total_searches:,}")
    print(f"  知识图谱: {total_kg_ops:,}")
    print(f"  错误数: {total_errors:,}")
    
    print(f"\n性能统计:")
    print(f"  平均延迟: {avg_latency*1000:.2f}ms")
    print(f"  最大延迟: {max_latency*1000:.2f}ms")
    print(f"  P95延迟: {p95_latency*1000:.2f}ms")
    print(f"  吞吐率: {total_ops/duration:.2f} 操作/秒")
    
    if metrics.error_log:
        print(f"\n错误详情:")
        error_counts = defaultdict(int)
        for err in metrics.error_log:
            error_type = err.get("error", "Unknown")[:80]
            error_counts[error_type] += 1
        
        for error_type, count in sorted(error_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  [{count}x] {error_type}")
    
    if metrics.warning_log:
        print(f"\n警告详情:")
        for warn in metrics.warning_log[:10]:
            print(f"  [Worker {warn['worker']}] {warn.get('warning', 'N/A')[:80]}")
    
    error_rate = total_errors / total_ops if total_ops > 0 else 0
    success_rate = (1 - error_rate) * 100
    
    print(f"\n{'='*60}")
    print(f"测试结果评估:")
    print(f"{'='*60}")
    print(f"  成功率: {success_rate:.2f}%")
    print(f"  错误率: {error_rate*100:.2f}%")
    
    if error_rate < 0.01:
        print(f"\n🎉 完美！极度混乱测试成功通过！")
        status = "PASS"
    elif error_rate < 0.05:
        print(f"\n✅ 良好！系统表现稳定。")
        status = "GOOD"
    elif error_rate < 0.1:
        print(f"\n⚠️  警告！系统存在一些问题。")
        status = "WARNING"
    else:
        print(f"\n❌ 失败！系统出现严重问题。")
        status = "FAIL"
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*100}")
    
    return {
        "status": status,
        "duration": duration,
        "total_ops": total_ops,
        "success_rate": success_rate,
        "error_rate": error_rate,
        "errors": total_errors,
        "error_log": metrics.error_log,
        "warnings": len(metrics.warning_log)
    }


def main():
    """主函数"""
    result = run_chaos_test(
        duration_seconds=60,
        num_workers=20,
        initial_records=500
    )
    
    return 0 if result["status"] in ["PASS", "GOOD"] else 1


if __name__ == "__main__":
    sys.exit(main())
