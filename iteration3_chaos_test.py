#!/usr/bin/env python3
"""
Agent Memory System - 多次迭代超级压力测试
第3次迭代：极度混乱场景测试
"""

import sys
import time
import random
import string
import threading
import logging
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('iteration3')

class Iteration3ChaosTest:
    """第3次迭代：极度混乱场景测试"""

    def __init__(self):
        self.operations = {'success': 0, 'failed': 0}
        self._lock = threading.Lock()

    def _gen_chaos_content(self) -> str:
        """生成极度混乱的内容"""
        parts = []

        # 中文
        if random.random() < 0.3:
            parts.append("中文测试内容")
        # 日文
        if random.random() < 0.3:
            parts.append("日本語テスト")
        # 韩文
        if random.random() < 0.3:
            parts.append("한국어 테스트")
        # Emoji
        if random.random() < 0.3:
            parts.append("🎉🎊💻🔧🚀⭐")
        # 特殊符号
        if random.random() < 0.3:
            parts.append("!@#$%^&*()_+-=[]{}|;:',.<>?/\\")
        # Unicode
        if random.random() < 0.3:
            parts.append("\u2603\u2604\u2665\u2666\u2660\u2663")
        # 普通字符
        parts.append(''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 100))))

        return ' | '.join(parts)

    def worker(self, worker_id: int, iterations: int, memory):
        """混乱场景工作线程"""
        for i in range(iterations):
            try:
                op = random.choice(['remember', 'recall', 'entity'])

                if op == 'remember':
                    content = self._gen_chaos_content()
                    memory.remember(
                        content=content,
                        memory_type=random.choice(['fact', 'semantic']),
                        importance=random.uniform(0.0, 1.0),
                        tags=[self._gen_chaos_content()[:20] for _ in range(random.randint(0, 5))]
                    )
                    with self._lock:
                        self.operations['success'] += 1

                elif op == 'recall':
                    query = self._gen_chaos_content()[:30]
                    results = memory.recall(query, top_k=5)
                    with self._lock:
                        self.operations['success'] += 1

                elif op == 'entity':
                    memory.add_entity(
                        name=self._gen_chaos_content()[:30],
                        entity_type=random.choice(['concept', 'item']),
                        description=self._gen_chaos_content()
                    )
                    with self._lock:
                        self.operations['success'] += 1

            except Exception as e:
                with self._lock:
                    self.operations['failed'] += 1
                logger.error(f"Worker-{worker_id} 操作失败: {e}")

    def run(self, workers: int = 30, iterations_per_worker: int = 100):
        """运行测试"""
        from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

        logger.info("="*80)
        logger.info("第3次迭代：极度混乱场景测试")
        logger.info(f"并发: {workers} 线程, 每线程 {iterations_per_worker} 次操作")
        logger.info("="*80)

        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"}
            ),
            knowledge_graph={"enabled": True}
        )
        memory = AgentMemory(config)

        start = time.time()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self.worker, i, iterations_per_worker, memory)
                for i in range(workers)
            ]
            for f in futures:
                f.result()

        total_time = time.time() - start
        total_ops = self.operations['success'] + self.operations['failed']

        logger.info("="*80)
        logger.info("第3次迭代 - 最终报告")
        logger.info("="*80)
        logger.info(f"总操作数: {total_ops:,}")
        logger.info(f"成功: {self.operations['success']:,}")
        logger.info(f"失败: {self.operations['failed']:,}")
        logger.info(f"成功率: {self.operations['success']/total_ops*100:.2f}%")
        logger.info(f"总耗时: {total_time:.2f}s")
        logger.info(f"吞吐: {total_ops/total_time:.1f} ops/s")

        memory.close()
        logger.info("测试完成")

        return {
            'success': self.operations['failed'] == 0,
            'success_rate': self.operations['success']/total_ops*100 if total_ops > 0 else 0
        }

if __name__ == "__main__":
    tester = Iteration3ChaosTest()
    result = tester.run(workers=30, iterations_per_worker=100)
    sys.exit(0 if result['success'] else 1)
