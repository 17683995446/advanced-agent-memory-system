#!/usr/bin/env python3
"""
Agent Memory System - 简化的极端长时压力测试
"""

import sys
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


def main():
    """主函数"""
    
    print(f"\n{'=' * 80}")
    print("Agent Memory System - 简化极端长时压力测试")
    print(f"{'=' * 80}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 配置
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
        short_term={"working_memory_capacity": 50}
    )
    
    memory = AgentMemory(config=config)
    
    # 全局统计
    lock = threading.Lock()
    stats = {"writes": 0, "reads": 0, "updates": 0, "searches": 0, "deletes": 0, "errors": 0}
    all_ids = []
    
    # 工作线程函数
    def worker(worker_id, duration_seconds):
        start = time.time()
        local_ids = []
        while time.time() - start < duration_seconds:
            try:
                choice = random.random()
                
                if choice < 0.4:
                    # 写入
                    content = f"测试内容 {worker_id}_{random.randint(1, 100000)}"
                    mem_id = memory.remember(
                        content=content,
                        importance=random.uniform(0.1, 0.9)
                    )
                    with lock:
                        all_ids.append(mem_id)
                        local_ids.append(mem_id)
                        stats["writes"] += 1
                        
                elif choice < 0.7:
                    # 读取
                    with lock:
                        if all_ids:
                            random_id = random.choice(all_ids)
                            record = memory.long_term.get(random_id)
                            if record:
                                stats["reads"] += 1
                
                elif choice < 0.85:
                    # 搜索
                    queries = ["测试", "内容", "系统", "验证"]
                    results = memory.recall(random.choice(queries), top_k=3)
                    with lock:
                        stats["searches"] += 1
                
                else:
                    # 更新
                    with lock:
                        if all_ids:
                            random_id = random.choice(all_ids)
                            new_content = f"更新后 {random.randint(1, 100000)}"
                            success = memory.long_term.update(random_id, content=new_content)
                            if success:
                                stats["updates"] += 1
                
                time.sleep(random.uniform(0.001, 0.01))
                
            except Exception as e:
                with lock:
                    stats["errors"] += 1
                    if stats["errors"] <= 10:
                        print(f"⚠️ 错误 #{stats['errors']}: {str(e)[:80]}")
    
    # 预填充一些数据
    print(f"\n预填充初始数据...")
    for i in range(200):
        content = f"初始数据 #{i}: 一些测试内容"
        mem_id = memory.remember(content=content, importance=0.5)
        all_ids.append(mem_id)
    print(f"预填充完成: {len(all_ids)} 条记录")
    
    # 运行测试
    NUM_THREADS = 10
    DURATION = 45  # 秒
    
    print(f"\n开始极端测试: {NUM_THREADS} 线程, {DURATION} 秒")
    print("-" * 80)
    
    start_time = time.time()
    last_report_time = time.time()
    
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = [executor.submit(worker, i, DURATION) for i in range(NUM_THREADS)]
        
        # 进度报告
        while time.time() - start_time < DURATION:
            time.sleep(5)
            elapsed = time.time() - start_time
            with lock:
                total_ops = sum(stats.values()) - stats["errors"]
            print(f"  已运行 {elapsed:.0f}s, 总操作: {total_ops}")
    
    # 等待所有线程完成
    for future in futures:
        future.result()
    
    # 最终统计
    elapsed = time.time() - start_time
    total_ops = sum(stats.values()) - stats["errors"]
    
    print(f"\n{'=' * 60}")
    print("最终测试结果")
    print(f"{'=' * 60}")
    print(f"总耗时: {elapsed:.2f}秒")
    print(f"总操作: {total_ops}")
    print(f"  写入: {stats['writes']}")
    print(f"  读取: {stats['reads']}")
    print(f"  更新: {stats['updates']}")
    print(f"  搜索: {stats['searches']}")
    print(f"  错误: {stats['errors']}")
    print(f"吞吐率: {total_ops/elapsed:.1f} 操作/秒")
    
    # 验证系统状态
    print(f"\n系统状态验证:")
    final_stats = memory.get_stats()
    print(f"  长期记忆: {final_stats.get('long_term', {}).get('total_memories', 0)}")
    
    memory.close()
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    main()
