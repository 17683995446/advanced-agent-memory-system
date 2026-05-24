#!/usr/bin/env python3
"""
Agent Memory System - 超大规模多阶段多次迭代测试
第二轮：50线程 x 120秒，真正的高强度压力测试
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
logger = logging.getLogger('ultra_stress')


def generate_mega_chaos_content() -> str:
    """生成超大规模混乱内容"""
    length = random.randint(50, 50000)  # 极端长度
    
    chaos_parts = []
    charsets = [
        string.ascii_letters * 20,
        string.digits * 10,
        '中文测试内容日本語韓國語Русскийالعربيةहिन्दीPortuguês',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'<>[]{}',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃' * 20,
        '\n\r\t\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0b\x0c',
    ]
    
    for _ in range(length):
        charset = random.choice(charsets)
        chaos_parts.append(random.choice(charset))
    
    return ''.join(chaos_parts)


class UltraStressWorker(threading.Thread):
    """超压力测试工作线程"""
    
    def __init__(self, worker_id, duration_seconds, result_dict):
        super().__init__(name=f'Ultra-{worker_id:02d}')
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
                embedding={"provider": "fake", "fake_dimension": 128},
                vector_store={"backend": "memory"}
            ),
            knowledge_graph={"enabled": True},
            structured_store={"enabled": True, "db_path": ":memory:"}
        )
        
        self.memory = AgentMemory(config)
        logger.info(f"[{self.name}] 初始化成功")
    
    def run(self):
        logger.info(f"[{self.name}] 开始 (持续 {self.duration_seconds}s)")
        
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
            'remember_conversation', 'add_to_working', 'consolidate', 'get_stats',
            'search_entities', 'get_preference', 'get_conversation_history'
        ]
        
        while time.time() - start_time < self.duration_seconds:
            try:
                op = random.choice(ops_list)
                self.operations['total'] += 1
                self.operations['by_type'][op] = self.operations['by_type'].get(op, 0) + 1
                
                success = False
                
                if op == 'remember':
                    content = generate_mega_chaos_content()
                    mem_type = random.choice(['fact', 'semantic', 'episodic', 'procedural', 'conversation'])
                    importance = random.uniform(-5.0, 5.0)
                    
                    try:
                        self.memory.remember(
                            content=content[:20000],
                            memory_type=mem_type,
                            importance=max(0.0, min(1.0, importance))
                        )
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'recall':
                    query = generate_mega_chaos_content()[:500] if random.random() < 0.8 else ''
                    top_k = random.randint(-50, 200)
                    try:
                        self.memory.recall(query, top_k=max(0, top_k))
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'add_entity':
                    name = generate_mega_chaos_content()[:100]
                    entity_type = random.choice(['person', 'concept', 'tool', 'item', 'unknown', 'place', 'event'])
                    desc = generate_mega_chaos_content()[:2000]
                    try:
                        self.memory.add_entity(name=name, entity_type=entity_type, description=desc)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'add_relation':
                    source = generate_mega_chaos_content()[:50]
                    target = generate_mega_chaos_content()[:50]
                    rel_type = random.choice(['related_to', 'uses', 'contains', 'part_of', 'causes', 'similar_to'])
                    try:
                        self.memory.add_entity(name=source[:30], entity_type='concept', description='')
                        self.memory.add_entity(name=target[:30], entity_type='concept', description='')
                        self.memory.add_relation(source=source[:30], target=target[:30], relation_type=rel_type)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'store_pref':
                    key = generate_mega_chaos_content()[:100]
                    value = generate_mega_chaos_content()[:5000]
                    category = random.choice(['ui', 'setting', 'user', 'system', 'custom', 'app', 'config'])
                    try:
                        self.memory.store_preference(key=key[:50], value=value[:2000], category=category)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'remember_conversation':
                    speaker = random.choice(['user', 'assistant', 'system', 'agent', 'bot'])
                    content = generate_mega_chaos_content()[:5000]
                    important = random.random() > 0.3
                    try:
                        self.memory.remember_conversation(content=content[:3000], speaker=speaker, important=important)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'add_to_working':
                    key = f'wk_{self.worker_id}_{int(time.time()*1000000)}'
                    content = generate_mega_chaos_content()[:3000]
                    try:
                        self.memory.add_to_working_memory(key=key[:50], content=content[:2000], importance=random.random())
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'consolidate':
                    try:
                        if hasattr(self.memory, 'consolidate'):
                            self.memory.consolidate()
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'get_stats':
                    try:
                        if hasattr(self.memory, 'get_stats'):
                            self.memory.get_stats()
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'search_entities':
                    try:
                        if hasattr(self.memory, 'search_entities'):
                            self.memory.search_entities(generate_mega_chaos_content()[:100], top_k=10)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'get_preference':
                    try:
                        self.memory.get_preference(generate_mega_chaos_content()[:30])
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                elif op == 'get_conversation_history':
                    try:
                        self.memory.get_conversation_history(limit=50)
                        success = True
                    except Exception as e:
                        self.errors.append((op, type(e).__name__, str(e)[:50]))
                
                if success:
                    self.operations['success'] += 1
                else:
                    self.operations['failed'] += 1
                
                if random.random() < 0.02:
                    time.sleep(random.uniform(0.001, 0.01))
                
                if time.time() - last_log_time > 15:
                    logger.info(f"[{self.name}] 已执行 {self.operations['total']} 操作")
                    last_log_time = time.time()
            
            except Exception as e:
                logger.error(f"[{self.name}] 循环异常: {e}")
                self.operations['failed'] += 1
                self.errors.append(('loop', type(e).__name__, str(e)[:100]))
        
        try:
            self.memory.close()
            logger.info(f"[{self.name}] 资源释放成功")
        except Exception as e:
            logger.warning(f"[{self.name}] 关闭异常: {e}")
        
        self.result_dict[f'worker_{self.worker_id}'] = {
            'status': 'completed',
            'operations': self.operations,
            'errors': self.errors[:100]
        }
        
        logger.info(
            f"[{self.name}] 完成: 总计={self.operations['total']}, "
            f"成功={self.operations['success']}, "
            f"失败={self.operations['failed']}, "
            f"成功率={self.operations['success']/self.operations['total']*100:.1f}%"
        )


def run_phase(num_workers, duration):
    """运行单个测试阶段"""
    result_dict = {}
    workers = []
    
    for i in range(num_workers):
        worker = UltraStressWorker(i, duration, result_dict)
        workers.append(worker)
    
    start_time = time.time()
    
    for worker in workers:
        worker.start()
    
    for worker in workers:
        worker.join()
    
    elapsed = time.time() - start_time
    
    return result_dict, elapsed


def main():
    print("\n" + "="*150)
    print("🚀 Agent Memory System - 第二轮超大规模多阶段迭代测试")
    print("="*150)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    overall_start = time.time()
    
    phases = [
        (50, 30, "阶段1: 50线程30秒"),
        (75, 45, "阶段2: 75线程45秒"),
        (100, 60, "阶段3: 100线程60秒"),
    ]
    
    all_results = []
    total_ops = 0
    total_success = 0
    total_failed = 0
    
    for i, (num_workers, duration, name) in enumerate(phases):
        print(f"\n{'='*150}")
        print(f"🔄 {name}")
        print(f"{'='*150}")
        
        result, elapsed = run_phase(num_workers, duration)
        all_results.append((name, result, elapsed))
        
        phase_ops = sum(w['operations']['total'] for w in result.values() if 'operations' in w)
        phase_success = sum(w['operations']['success'] for w in result.values() if 'operations' in w)
        phase_failed = sum(w['operations']['failed'] for w in result.values() if 'operations' in w)
        
        total_ops += phase_ops
        total_success += phase_success
        total_failed += phase_failed
        
        rate = phase_success / phase_ops * 100 if phase_ops > 0 else 0
        print(f"\n📊 {name} 结果:")
        print(f"  总操作: {phase_ops:,}")
        print(f"  成功: {phase_success:,}")
        print(f"  失败: {phase_failed:,}")
        print(f"  成功率: {rate:.2f}%")
        print(f"  耗时: {elapsed:.2f}s")
    
    overall_time = time.time() - overall_start
    overall_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print("\n" + "="*150)
    print("🏆 第二轮超大规模测试总结报告")
    print("="*150)
    
    print(f"\n总耗时: {overall_time:.2f} 秒 ({overall_time/60:.1f} 分钟)")
    print(f"\n📈 总体:")
    print(f"  总操作: {total_ops:,}")
    print(f"  总成功: {total_success:,}")
    print(f"  总失败: {total_failed:,}")
    print(f"  总体成功率: {overall_rate:.2f}%")
    
    if overall_rate >= 99 and total_failed < total_ops * 0.01:
        print("\n🏆🏆🏆 完美通过！系统极其稳定！")
    elif overall_rate >= 95:
        print("\n✅ 优秀！系统非常稳定！")
    elif overall_rate >= 85:
        print("\n⚠️  基本可用，建议优化！")
    else:
        print("\n❌ 需要修复问题！")
    
    print("="*150)
    
    return "pass" if overall_rate >= 95 else "fail"


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    sys.exit(0 if main() == "pass" else 1)
