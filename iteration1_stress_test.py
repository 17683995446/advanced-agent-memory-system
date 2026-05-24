#!/usr/bin/env python3
"""
Agent Memory System - 多次迭代超级压力测试
第1次迭代：超大规模并发压力测试
"""

import sys
import time
import random
import string
import threading
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Set

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

# 配置超详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d - %(threadName)-12s - %(levelname)-8s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('iteration1')
logger.setLevel(logging.INFO)

class Iteration1StressTest:
    """第1次迭代：超大规模并发压力测试"""

    def __init__(self):
        self.stats = {
            'total_operations': 0,
            'success_operations': 0,
            'failed_operations': 0,
            'errors': []
        }
        self.active_ids: Set[str] = set()
        self._lock = threading.RLock()

    def worker(self, worker_id: int, duration: float, memory):
        """工作线程"""
        thread_name = f"Worker-{worker_id:02d}"
        start = time.time()
        local_ops = 0

        logger.info(f"[{thread_name}] 启动，持续 {duration}s")

        while time.time() - start < duration:
            try:
                # 随机选择操作
                op = random.choice(['remember', 'recall', 'forget', 'entity'])

                if op == 'remember':
                    content = self._gen_content(100, 500)
                    mem_id = memory.remember(
                        content=content,
                        memory_type=random.choice(['fact', 'semantic', 'episodic']),
                        importance=random.uniform(0.0, 1.0)
                    )
                    with self._lock:
                        self.active_ids.add(mem_id)
                    local_ops += 1

                elif op == 'recall':
                    query = self._gen_content(5, 30)
                    results = memory.recall(query, top_k=5)
                    local_ops += 1

                elif op == 'forget':
                    with self._lock:
                        if self.active_ids and random.random() < 0.7:
                            target = random.choice(list(self.active_ids))
                            success = memory.forget_memory(target)
                            if success:
                                self.active_ids.discard(target)
                            local_ops += 1

                elif op == 'entity':
                    name = f"Entity_{worker_id}_{random.randint(1, 9999)}"
                    memory.add_entity(
                        name=name,
                        entity_type=random.choice(['person', 'concept', 'tool']),
                        description=self._gen_content(20, 100)
                    )
                    local_ops += 1

                with self._lock:
                    self.stats['total_operations'] += 1
                    self.stats['success_operations'] += 1

                # 随机延迟
                if random.random() < 0.2:
                    time.sleep(random.uniform(0.001, 0.01))

            except Exception as e:
                with self._lock:
                    self.stats['total_operations'] += 1
                    self.stats['failed_operations'] += 1
                    self.stats['errors'].append({
                        'worker': worker_id,
                        'op': op,
                        'error': str(e),
                        'time': datetime.now().isoformat()
                    })
                logger.error(f"[{thread_name}] 操作失败: {e}")

        logger.info(f"[{thread_name}] 完成 {local_ops} 次操作")
        return local_ops

    def _gen_content(self, min_len: int, max_len: int) -> str:
        """生成内容"""
        length = random.randint(min_len, max_len)
        chars = string.ascii_letters + string.digits + "中文测试日本語"
        return ''.join(random.choice(chars) for _ in range(length))

    def run(self, workers: int = 50, duration: int = 300):
        """运行测试"""
        from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

        logger.info("="*80)
        logger.info("第1次迭代：超大规模并发压力测试")
        logger.info(f"并发线程: {workers}, 持续时间: {duration}s")
        logger.info("="*80)

        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"}
            ),
            knowledge_graph={"enabled": True},
            structured_store={"enabled": True, "db_path": ":memory:"}
        )
        memory = AgentMemory(config)

        # 预填充
        logger.info("预填充 1000 条初始数据...")
        for i in range(1000):
            mem_id = memory.remember(
                content=f"预填充数据 {i}",
                importance=0.5
            )
            self.active_ids.add(mem_id)
        logger.info(f"预填充完成，当前 {len(self.active_ids)} 条记忆")

        # 运行测试
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self.worker, i, duration, memory)
                for i in range(workers)
            ]

            # 监控进度
            last_check = time.time()
            while any(f.running() for f in futures):
                time.sleep(10)
                elapsed = time.time() - start_time

                if time.time() - last_check >= 30:
                    with self._lock:
                        total = self.stats['total_operations']
                        success = self.stats['success_operations']
                        failed = self.stats['failed_operations']

                    throughput = total / elapsed if elapsed > 0 else 0
                    logger.info(f"⏱ {elapsed:.0f}s | 操作: {total:,} | 成功: {success:,} | "
                              f"失败: {failed:,} | 吞吐: {throughput:.1f}/s | 活跃ID: {len(self.active_ids)}")
                    last_check = time.time()

            for f in futures:
                f.result()

        total_time = time.time() - start_time

        # 总结
        logger.info("="*80)
        logger.info("第1次迭代 - 最终报告")
        logger.info("="*80)

        with self._lock:
            total = self.stats['total_operations']
            success = self.stats['success_operations']
            failed = self.stats['failed_operations']

        logger.info(f"总运行时间: {total_time:.2f}s")
        logger.info(f"总操作数: {total:,}")
        logger.info(f"成功操作: {success:,}")
        logger.info(f"失败操作: {failed:,}")
        logger.info(f"成功率: {(success/total*100):.2f}%")
        logger.info(f"平均吞吐: {total/total_time:.1f} ops/s")

        if failed > 0:
            logger.error(f"\n发现 {failed} 个错误！")
            for i, err in enumerate(self.stats['errors'][:5]):
                logger.error(f"  {i+1}. Worker-{err['worker']} [{err['op']}]: {err['error']}")

        memory.close()
        logger.info("测试完成")

        return {
            'success': failed == 0,
            'total_ops': total,
            'success_rate': success/total*100 if total > 0 else 0
        }

if __name__ == "__main__":
    tester = Iteration1StressTest()
    result = tester.run(workers=50, duration=300)  # 50线程，5分钟
    sys.exit(0 if result['success'] else 1)
