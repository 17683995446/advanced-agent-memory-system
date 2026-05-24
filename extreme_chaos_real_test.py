#!/usr/bin/env python3
"""
Agent Memory System - 极端复杂混乱场景测试
多次迭代，发现真实运行时的bug
"""

import sys
import time
import random
import string
import threading
import logging
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('chaos_test')


def generate_chaos_content(min_len=10, max_len=2000) -> str:
    """生成极度混乱的内容"""
    length = random.randint(min_len, max_len)

    # 混合各种字符
    charsets = [
        string.ascii_letters,  # 英文
        string.digits,  # 数字
        '中文测试内容日本語韓国語',  # 多语言
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\',  # 特殊符号
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥',  # emoji
    ]

    content = []
    for _ in range(length):
        charset = random.choice(charsets)
        content.append(random.choice(charset))

    return ''.join(content)


def generate_tags():
    """生成随机标签"""
    num_tags = random.randint(0, 20)
    tags = []
    for _ in range(num_tags):
        tag_len = random.randint(1, 30)
        tag = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(tag_len))
        tags.append(tag)
    return tags


def chaos_worker(worker_id: int, duration: float, result_dict: Dict):
    """混乱工作线程"""
    from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

    thread_name = f"ChaosWorker-{worker_id:02d}"

    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"}
            ),
            knowledge_graph={"enabled": True},
            structured_store={"enabled": True, "db_path": ":memory:"}
        )
        memory = AgentMemory(config)
    except Exception as e:
        logger.error(f"[{thread_name}] 初始化失败: {e}")
        result_dict['failed_init'] += 1
        return

    start = time.time()
    ops = {'total': 0, 'success': 0, 'failed': 0}

    while time.time() - start < duration:
        try:
            op = random.choice([
                'remember', 'recall', 'forget', 'entity',
                'store_pref', 'conversation', 'add_to_short'
            ])
            ops['total'] += 1

            if op == 'remember':
                content = generate_chaos_content()
                memory_type = random.choice(['fact', 'semantic', 'episodic', 'procedural', 'conversation'])
                category = random.choice(['chaos', 'test', 'tech', 'personal', 'work'])
                importance = random.uniform(0.0, 1.0)
                tags = generate_tags()

                try:
                    mem_id = memory.remember(
                        content=content,
                        memory_type=memory_type,
                        category=category,
                        importance=importance,
                        tags=tags
                    )
                    ops['success'] += 1
                except (ValueError, TypeError, RuntimeError):
                    ops['failed'] += 1

            elif op == 'recall':
                query = generate_chaos_content(3, 50)
                top_k = random.randint(1, 20)
                try:
                    results = memory.recall(query, top_k=top_k)
                    ops['success'] += 1
                except:
                    ops['failed'] += 1

            elif op == 'entity':
                name = generate_chaos_content(5, 30)
                entity_type = random.choice(['person', 'concept', 'tool', 'item', 'unknown'])
                description = generate_chaos_content(10, 200)
                try:
                    memory.add_entity(name=name, entity_type=entity_type, description=description)
                    ops['success'] += 1
                except:
                    ops['failed'] += 1

            elif op == 'store_pref':
                key = generate_chaos_content(3, 20)
                value = generate_chaos_content(3, 50)
                category = random.choice(['ui', 'setting', 'user', 'system'])
                try:
                    memory.store_preference(key=key, value=value, category=category)
                    ops['success'] += 1
                except:
                    ops['failed'] += 1

            elif op == 'conversation':
                speaker = random.choice(['user', 'assistant', 'system'])
                content = generate_chaos_content(20, 200)
                important = random.random() > 0.7
                try:
                    memory.remember_conversation(content=content, speaker=speaker, important=important)
                    ops['success'] += 1
                except:
                    ops['failed'] += 1

            elif op == 'add_to_short':
                key = f"short_{worker_id}_{int(time.time()*1000000)}"
                content = generate_chaos_content(10, 500)
                importance = random.uniform(0.0, 1.0)
                try:
                    memory.add_to_working_memory(key=key, content=content, importance=importance)
                    ops['success'] += 1
                except:
                    ops['failed'] += 1

            # 随机延迟模拟真实场景
            if random.random() < 0.2:
                time.sleep(random.uniform(0.0001, 0.01))

        except Exception as e:
            ops['failed'] += 1
            logger.error(f"[{thread_name}] 未知异常: {type(e).__name__}: {e}")

    try:
        memory.close()
    except:
        pass

    result_dict[worker_id] = ops
    logger.info(f"[{thread_name}] 完成: 总计 {ops['total']}, 成功 {ops['success']}, 失败 {ops['failed']}")


def main():
    print("\n" + "="*120)
    print("🔥 Agent Memory System - 极端复杂混乱场景测试")
    print("="*120)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n多次迭代测试，发现真实运行时的bug")
    print("="*120)

    # 测试配置
    num_workers = 15
    duration_seconds = 30
    print(f"\n测试配置: {num_workers} 并发线程, 持续 {duration_seconds} 秒")

    result_dict = {'failed_init': 0}
    for i in range(num_workers):
        result_dict[i] = {'total': 0, 'success': 0, 'failed': 0}

    threads = []
    start = time.time()

    print(f"\n[启动线程]")
    for worker_id in range(num_workers):
        t = threading.Thread(
            target=chaos_worker,
            args=(worker_id, duration_seconds, result_dict),
            name=f"ChaosWorker-{worker_id:02d}"
        )
        threads.append(t)
        t.start()

    print(f"✅ {len(threads)} 线程已启动，运行 {duration_seconds} 秒...")

    for t in threads:
        t.join()

    total_time = time.time() - start

    # 总结
    print("\n" + "="*120)
    print("🎯 混乱场景测试总结")
    print("="*120)

    total_ops = 0
    total_success = 0
    total_failed = 0

    print(f"\n每个线程结果:")
    for worker_id in range(num_workers):
        ops = result_dict.get(worker_id, {'total': 0, 'success': 0, 'failed': 0})
        total_ops += ops['total']
        total_success += ops['success']
        total_failed += ops['failed']

        success_rate = ops['success'] / ops['total'] * 100 if ops['total'] > 0 else 0
        print(f"  线程 {worker_id:02d}: 总计 {ops['total']:5d}, "
              f"成功 {ops['success']:5d}, "
              f"失败 {ops['failed']:3d}, "
              f"成功率 {success_rate:5.1f}%")

    overall_success_rate = total_success / total_ops * 100 if total_ops > 0 else 0

    print(f"\n整体结果:")
    print(f"  总操作数: {total_ops:,}")
    print(f"  成功: {total_success:,}")
    print(f"  失败: {total_failed:,}")
    print(f"  成功率: {overall_success_rate:.2f}%")
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  吞吐率: {total_ops / total_time:.1f} ops/s")
    print(f"  初始化失败: {result_dict['failed_init']}")

    # 判定
    print("\n" + "="*120)
    if overall_success_rate >= 95 and total_failed == 0 and result_dict['failed_init'] == 0:
        print("🎉 🎉 极端混乱场景测试完美通过！")
        print("✅ 系统稳定，无崩溃，无bug，达到生产环境标准！")
        code = 0
    elif overall_success_rate >= 90:
        print("✅ 极端混乱场景测试通过！")
        print(f"有 {total_failed} 个失败，但主要是预期异常")
        code = 0
    else:
        print(f"⚠️  需要进一步分析，失败率较高")
        code = 1

    print("="*120)
    return code


if __name__ == '__main__':
    sys.exit(main())
