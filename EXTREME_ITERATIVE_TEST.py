#!/usr/bin/env python3
"""
极端复杂场景 - 多阶段多次迭代测试
真正的压力测试，长时间、大规模、混乱数据
"""

import sys
import time
import random
import string
import threading
import logging
import gc
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('extreme_test')


def generate_extreme_content() -> str:
    """生成极端混乱的内容"""
    length = random.randint(10, 10000)  # 超长内容
    
    chaos_parts = []
    charsets = [
        string.ascii_letters * 10,
        string.digits * 5,
        '中文测试内容日本語韓國語Русскийالعربية',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯' * 5,
        '\n\r\t\x00\x01\x02\x03'  # 特殊字符
    ]
    
    for _ in range(length):
        charset = random.choice(charsets)
        chaos_parts.append(random.choice(charset))
    
    return ''.join(chaos_parts)


class IterativeStressWorker(threading.Thread):
    """迭代压力测试工作线程"""
    
    def __init__(self, worker_id, duration_seconds, result_dict):
        super().__init__(name=f'Worker-{worker_id}')
        self.worker_id = worker_id
        self.duration_seconds = duration_seconds
        self.result_dict = result_dict
        
        self.operations = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'by_type': {}
        }
        self.errors = []
        
        self.memory = None
    
    def init_memory(self):
        from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig
        
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"}
            ),
            knowledge_graph={"enabled": True},
            structured_store={"enabled": True, "db_path": ":memory:"}
        )
        
        self.memory = AgentMemory(config)
    
    def run(self):
        logger.info(f"[{self.name}] 开始极端压力测试 (持续 {self.duration_seconds}s)")
        
        try:
            self.init_memory()
        except Exception as e:
            logger.error(f"[{self.name}] 初始化失败: {e}")
            self.result_dict[f'worker_{self.worker_id}'] = {'status': 'init_failed', 'error': str(e)}
            return
        
        start_time = time.time()
        last_log_time = start_time
        ops_list = [
            'remember', 'recall', 'add_entity', 'add_relation', 'store_pref',
            'remember_conversation', 'add_to_working', 'consolidate', 'get_stats'
        ]
        
        while time.time() - start_time < self.duration_seconds:
            try:
                op = random.choice(ops_list)
                self.operations['total'] += 1
                self.operations['by_type'][op] = self.operations['by_type'].get(op, 0) + 1
                
                success = False
                
                if op == 'remember':
                    content = generate_extreme_content()
                    mem_type = random.choice(['fact', 'semantic', 'episodic', 'procedural', 'conversation'])
                    importance = random.uniform(-2.0, 3.0)  # 故意让值越界
                    
                    try:
                        self.memory.remember(
                            content=content,
                            memory_type=mem_type,
                            importance=max(0.0, min(1.0, importance))
                        )
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'recall':
                    query = generate_extreme_content() if random.random() < 0.7 else ''
                    top_k = random.randint(-10, 100)
                    try:
                        self.memory.recall(query, top_k=max(0, top_k))
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'add_entity':
                    name = generate_extreme_content()
                    entity_type = random.choice(['person', 'concept', 'tool', 'item', 'unknown'])
                    desc = generate_extreme_content()
                    try:
                        self.memory.add_entity(name=name, entity_type=entity_type, description=desc)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'add_relation':
                    source = generate_extreme_content()
                    target = generate_extreme_content()
                    rel_type = random.choice(['related_to', 'uses', 'contains', 'part_of', 'causes'])
                    try:
                        self.memory.add_relation(source=source, target=target, relation_type=rel_type)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'store_pref':
                    key = generate_extreme_content()[:50]
                    value = generate_extreme_content()
                    category = random.choice(['ui', 'setting', 'user', 'system', 'custom'])
                    try:
                        self.memory.store_preference(key=key, value=value, category=category)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'remember_conversation':
                    speaker = random.choice(['user', 'assistant', 'system'])
                    content = generate_extreme_content()
                    important = random.random() > 0.5
                    try:
                        self.memory.remember_conversation(content=content, speaker=speaker, important=important)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'add_to_working':
                    key = f'wk_{self.worker_id}_{int(time.time()*1000000)}'
                    content = generate_extreme_content()
                    try:
                        self.memory.add_to_working_memory(key=key, content=content, importance=random.random())
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'consolidate':
                    try:
                        if hasattr(self.memory, 'consolidate'):
                            self.memory.consolidate()
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                elif op == 'get_stats':
                    try:
                        if hasattr(self.memory, 'get_stats'):
                            self.memory.get_stats()
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__))
                
                if success:
                    self.operations['success'] += 1
                else:
                    self.operations['failed'] += 1
                
                # 随机延迟
                if random.random() < 0.05:
                    time.sleep(random.uniform(0.001, 0.01))
                
                if time.time() - last_log_time > 10:
                    logger.info(f"[{self.name}] 已执行 {self.operations['total']} 操作")
                    last_log_time = time.time()
            
            except Exception as e:
                logger.error(f"[{self.name}] 循环异常: {e}")
                self.operations['failed'] += 1
        
        try:
            self.memory.close()
        except Exception as e:
            logger.warning(f"[{self.name}] 关闭异常: {e}")
        
        self.result_dict[f'worker_{self.worker_id}'] = {
            'status': 'completed',
            'operations': self.operations,
            'errors': self.errors[:50]
        }
        
        logger.info(
            f"[{self.name}] 完成: 总计={self.operations['total']}, "
            f"成功={self.operations['success']}, "
            f"失败={self.operations['failed']}, "
            f"成功率={self.operations['success']/self.operations['total']*100:.1f}%"
        )


def run_iterative_test():
    """运行多阶段迭代测试"""
    
    print("\n" + "="*140)
    print("🚀 Agent Memory System - 超极端复杂场景多次迭代测试")
    print("="*140)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    overall_start = time.time()
    
    # 阶段1: 10个线程，持续10秒
    print("\n" + "="*140)
    print("🔄 迭代阶段 1/3: 10线程，持续10秒")
    print("="*140)
    
    result1 = run_single_test_phase(num_workers=10, duration=10, phase_name="Phase1")
    
    # 阶段2: 20个线程，持续15秒
    print("\n" + "="*140)
    print("🔄 迭代阶段 2/3: 20线程，持续15秒")
    print("="*140)
    
    result2 = run_single_test_phase(num_workers=20, duration=15, phase_name="Phase2")
    
    # 阶段3: 30个线程，持续20秒
    print("\n" + "="*140)
    print("🔄 迭代阶段 3/3: 30线程，持续20秒")
    print("="*140)
    
    result3 = run_single_test_phase(num_workers=30, duration=20, phase_name="Phase3")
    
    overall_time = time.time() - overall_start
    
    # 汇总报告
    print("\n" + "="*140)
    print("🏆 多次迭代测试总结报告")
    print("="*140)
    
    print(f"\n总耗时: {overall_time:.2f} 秒")
    
    all_results = [result1, result2, result3]
    total_ops = 0
    total_success = 0
    total_failed = 0
    
    for i, res in enumerate(all_results):
        phase_ops = sum(w['operations']['total'] for w in res.values() if 'operations' in w)
        phase_success = sum(w['operations']['success'] for w in res.values() if 'operations' in w)
        phase_failed = sum(w['operations']['failed'] for w in res.values() if 'operations' in w)
        
        total_ops += phase_ops
        total_success += phase_success
        total_failed += phase_failed
        
        success_rate = phase_success / phase_ops * 100 if phase_ops > 0 else 0
        print(f"\n📊 阶段{i+1}:")
        print(f"  总操作: {phase_ops:,}")
        print(f"  成功: {phase_success:,}")
        print(f"  失败: {phase_failed:,}")
        print(f"  成功率: {success_rate:.2f}%")
    
    overall_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print("\n" + "="*140)
    print(f"\n📈 总体:")
    print(f"  总操作: {total_ops:,}")
    print(f"  总成功: {total_success:,}")
    print(f"  总失败: {total_failed:,}")
    print(f"  总体成功率: {overall_rate:.2f}%")
    
    if overall_rate >= 99 and total_failed < total_ops * 0.01:
        print("\n🏆🏆🏆 完美通过！系统极其稳定，适合最苛刻的生产环境！")
        final_status = "pass"
    elif overall_rate >= 90:
        print("\n✅ 优秀！系统非常稳定，可投入生产使用！")
        final_status = "pass"
    elif overall_rate >= 75:
        print("\n⚠️ 基本可用，但建议进一步优化！")
        final_status = "pass"
    else:
        print("\n❌ 存在较多问题，需要修复！")
        final_status = "fail"
    
    print("="*140)
    
    return final_status


def run_single_test_phase(num_workers, duration, phase_name):
    """运行单个测试阶段"""
    
    result_dict = {}
    workers = []
    
    for i in range(num_workers):
        worker = IterativeStressWorker(i, duration, result_dict)
        workers.append(worker)
    
    start_time = time.time()
    
    for worker in workers:
        worker.start()
    
    for worker in workers:
        worker.join()
    
    elapsed = time.time() - start_time
    
    return result_dict


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    sys.exit(0 if run_iterative_test() == "pass" else 1)
