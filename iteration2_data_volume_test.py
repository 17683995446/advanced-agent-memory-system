#!/usr/bin/env python3
"""
Agent Memory System - 多次迭代超级压力测试
第2次迭代：超大数据量压力测试
"""

import sys
import time
import random
import threading
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('iteration2')

class Iteration2DataVolumeTest:
    """第2次迭代：超大数据量压力测试"""

    def __init__(self):
        self.records_created = 0
        self.errors = []
        self._lock = threading.Lock()

    def run(self, num_records: int = 10000):
        """运行测试"""
        from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

        logger.info("="*80)
        logger.info("第2次迭代：超大数据量压力测试")
        logger.info(f"目标记录数: {num_records:,}")
        logger.info("="*80)

        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"}
            ),
            knowledge_graph={"enabled": True}
        )
        memory = AgentMemory(config)

        # 创建超大数据量
        logger.info("开始创建大量记忆...")
        start = time.time()

        batch_size = 100
        for i in range(0, num_records, batch_size):
            try:
                for j in range(batch_size):
                    if i + j >= num_records:
                        break

                    content = f"记忆 {i+j}: 测试数据内容 " * 5
                    memory.remember(
                        content=content,
                        memory_type=random.choice(['fact', 'semantic', 'episodic']),
                        importance=random.uniform(0.0, 1.0)
                    )

                    with self._lock:
                        self.records_created += 1

                if (i + batch_size) % 1000 == 0:
                    elapsed = time.time() - start
                    rate = (i + batch_size) / elapsed if elapsed > 0 else 0
                    logger.info(f"进度: {i+batch_size:,}/{num_records:,} | "
                              f"速率: {rate:.1f} rec/s | 耗时: {elapsed:.1f}s")

            except Exception as e:
                with self._lock:
                    self.errors.append(str(e))
                logger.error(f"创建失败: {e}")

        create_time = time.time() - start

        # 测试检索性能
        logger.info("测试检索性能...")
        search_start = time.time()
        search_count = 0

        for i in range(100):
            try:
                query = f"记忆 {random.randint(0, num_records-1)}"
                results = memory.recall(query, top_k=10)
                search_count += 1
            except Exception as e:
                logger.error(f"检索失败: {e}")

        search_time = time.time() - search_start

        # 总结
        logger.info("="*80)
        logger.info("第2次迭代 - 最终报告")
        logger.info("="*80)
        logger.info(f"总记录数: {num_records:,}")
        logger.info(f"成功创建: {self.records_created:,}")
        logger.info(f"创建耗时: {create_time:.2f}s")
        logger.info(f"创建速率: {self.records_created/create_time:.1f} rec/s")
        logger.info(f"检索耗时: {search_time:.2f}s")
        logger.info(f"检索速率: {search_count/search_time:.1f} searches/s")
        logger.info(f"错误数: {len(self.errors)}")

        memory.close()
        logger.info("测试完成")

        return {
            'success': len(self.errors) == 0,
            'records_created': self.records_created,
            'create_rate': self.records_created/create_time
        }

if __name__ == "__main__":
    tester = Iteration2DataVolumeTest()
    result = tester.run(num_records=10000)
    sys.exit(0 if result['success'] else 1)
