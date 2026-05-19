#!/usr/bin/env python3
"""
Agent Memory System - 超长时间稳定性测试
模拟真实生产环境运行，验证系统在长时间高负载下的稳定性
"""

import sys
import time
import random
import threading
from typing import Dict, List, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


class StabilityTester:
    """稳定性测试器"""
    
    def __init__(self, duration_seconds: int = 120, num_threads: int = 8):
        self.duration_seconds = duration_seconds
        self.num_threads = num_threads
        self.memory = None
        self.stats = {
            "operations": 0,
            "writes": 0,
            "reads": 0,
            "searches": 0,
            "errors": 0,
            "error_list": [],
            "latency_samples": []
        }
        self.start_time = None
        self.lock = threading.Lock()
        self.running = True
    
    def setup(self):
        """初始化系统"""
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
        )
        self.memory = AgentMemory(config=config)
        
        # 预填充一些初始数据
        print(f"\n预填充初始数据...")
        for i in range(200):
            content = f"初始记忆 {i}: 测试数据内容用于稳定性验证"
            self.memory.remember(
                content=content,
                importance=random.uniform(0.1, 0.9)
            )
        print(f"预填充完成: 200条初始记录")
    
    def cleanup(self):
        """清理资源"""
        if self.memory:
            try:
                self.memory.close()
            except:
                pass
    
    def worker(self, worker_id: int):
        """工作线程"""
        print(f"  线程 {worker_id} 启动...")
        
        local_stats = {"ops": 0, "errors": 0}
        
        while self.running and (time.time() - self.start_time < self.duration_seconds):
            try:
                choice = random.random()
                start = time.time()
                
                if choice < 0.35:
                    # 写入
                    content = f"线程{worker_id}操作{local_stats['ops']}: {self.random_text(30)}"
                    self.memory.remember(
                        content=content,
                        memory_type=random.choice(["fact", "semantic", "episodic"]),
                        importance=random.random()
                    )
                    local_stats["ops"] += 1
                    with self.lock:
                        self.stats["writes"] += 1
                    
                elif choice < 0.65:
                    # 搜索
                    query = random.choice(["记忆", "测试", "数据", "内容", "系统", "验证"])
                    results = self.memory.recall(query, top_k=random.randint(2, 6))
                    local_stats["ops"] += 1
                    with self.lock:
                        self.stats["searches"] += 1
                    
                else:
                    # 读取
                    # 这里我们用搜索替代直接读取，简化测试
                    query = random.choice(["初始", "稳定性", "数据"])
                    self.memory.recall(query, top_k=3)
                    local_stats["ops"] += 1
                    with self.lock:
                        self.stats["reads"] += 1
                
                latency = time.time() - start
                with self.lock:
                    self.stats["operations"] += 1
                    self.stats["latency_samples"].append(latency)
                
            except Exception as e:
                local_stats["errors"] += 1
                with self.lock:
                    self.stats["errors"] += 1
                    if len(self.stats["error_list"]) < 10:
                        self.stats["error_list"].append({
                            "thread": worker_id,
                            "time": datetime.now().isoformat(),
                            "error": str(e)[:80]
                        })
            
            # 短暂休息，模拟真实负载
            time.sleep(random.uniform(0.001, 0.01))
        
        print(f"  线程 {worker_id} 完成，执行了 {local_stats['ops']} 操作，{local_stats['errors']} 错误")
    
    def run(self):
        """运行完整的稳定性测试"""
        print(f"\n{'='*80}")
        print(f"Agent Memory System - 超长时间稳定性测试")
        print(f"{'='*80}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试持续时间: {self.duration_seconds}秒 ({self.duration_seconds/60:.1f}分钟)")
        print(f"并发线程数: {self.num_threads}")
        
        self.setup()
        self.start_time = time.time()
        
        # 启动工作线程
        print(f"\n开始执行长时间稳定性测试...")
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = [executor.submit(self.worker, i) for i in range(self.num_threads)]
            
            # 监控进度
            last_report = time.time()
            while any(f.running() for f in futures):
                time.sleep(5)
                elapsed = time.time() - self.start_time
                
                if time.time() - last_report >= 10:
                    with self.lock:
                        ops = self.stats["operations"]
                        errors = self.stats["errors"]
                    print(f"\n[进度] 已运行 {elapsed:.0f}秒, 总操作: {ops}, 错误: {errors}")
                    last_report = time.time()
                
                if elapsed >= self.duration_seconds:
                    self.running = False
                    break
            
            for future in as_completed(futures):
                future.result()
        
        # 最终统计
        self.final_report()
        self.cleanup()
        
        return self.stats
    
    def final_report(self):
        """生成最终报告"""
        elapsed = time.time() - self.start_time
        throughput = self.stats["operations"] / elapsed if elapsed > 0 else 0
        
        avg_latency = 0
        max_latency = 0
        if self.stats["latency_samples"]:
            avg_latency = sum(self.stats["latency_samples"]) / len(self.stats["latency_samples"]) * 1000
            max_latency = max(self.stats["latency_samples"]) * 1000
        
        print(f"\n{'='*80}")
        print(f"超长时间稳定性测试 - 最终报告")
        print(f"{'='*80}")
        print(f"\n总运行时间: {elapsed:.2f}秒")
        print(f"总操作数: {self.stats['operations']}")
        print(f"  写入: {self.stats['writes']}")
        print(f"  读取: {self.stats['reads']}")
        print(f"  搜索: {self.stats['searches']}")
        print(f"总错误数: {self.stats['errors']}")
        print(f"平均延迟: {avg_latency:.2f}ms")
        print(f"最大延迟: {max_latency:.2f}ms")
        print(f"吞吐率: {throughput:.2f} 操作/秒")
        
        if self.stats["error_list"]:
            print(f"\n错误列表 (前10条):")
            for i, err in enumerate(self.stats["error_list"]):
                print(f"  {i+1}. [线程{err['thread']}] {err['time']}: {err['error']}")
        
        # 检查最终状态
        print(f"\n最终系统状态:")
        stats = self.memory.get_stats()
        print(f"  长期记忆: {stats.get('long_term', {}).get('total_memories', 'N/A')} 条")
        
        if self.stats["errors"] == 0 and self.stats["operations"] > 0:
            print(f"\n🎉 稳定性测试成功通过！系统表现完美！")
        else:
            print(f"\n⚠️  稳定性测试完成，发现 {self.stats['errors']} 个错误")
        
        print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    @staticmethod
    def random_text(length: int) -> str:
        """生成随机文本"""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(random.choice(chars) for _ in range(length))


def main():
    """主函数"""
    tester = StabilityTester(duration_seconds=120, num_threads=10)
    stats = tester.run()
    
    if stats["errors"] == 0 and stats["operations"] > 0:
        return 0  # 成功
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
