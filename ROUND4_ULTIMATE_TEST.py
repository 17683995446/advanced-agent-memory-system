#!/usr/bin/env python3
"""
Agent Memory System - 第四轮超极限迭代测试
300-500线程 × 120秒，终极混乱，每步验证
"""

import sys
import time
import random
import string
import threading
import logging
import gc
import tracemalloc
import psutil
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('ultimate_test')


def generate_ultimate_chaos_content() -> str:
    """生成终极混乱内容：100,000字符，极端数据"""
    length = random.randint(100, 200000)  # 20万字符
    
    charsets = [
        string.ascii_letters * 50,
        string.digits * 30,
        '中文测试内容日本語韓國語Русскийالعربيةहिन्दीPortuguêsDeutschFrançaisEspañol',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'<>[]{}<<<>>>[[[]]]',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃🎄🎅👽🛸🦄' * 100,
        '\n\r\t\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0b\x0c\x0e\x0f',
        '⌚⌛⏰⏳⌛⌚⌛⏰⏳⌛⌚⌛⏰⏳⌛⌚⌛⏰⏳⌛⌚⌛⏰⏳⌛',
        '🏁🚩🎌🏴🏳️🏴󠁧󠁢󠁥󠁮󠁧󠁿🏳️‍🌈🏳️‍⚧️🏴‍☠️',
    ]
    
    content = []
    for _ in range(length):
        charset = random.choice(charsets)
        content.append(random.choice(charset))
    
    return ''.join(content)


class UltimateWorker(threading.Thread):
    """终极压力测试工作线程 - 每步验证"""
    
    def __init__(self, worker_id, duration, result_dict):
        super().__init__(name=f'Ultimate-{worker_id:03d}')
        self.worker_id = worker_id
        self.duration = duration
        self.result_dict = result_dict
        
        self.operations = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'by_type': {},
            'step_logs': [],  # 每步验证日志
        }
        self.errors = []
        self.memory = None
        self.start_memory = 0
        self.end_memory = 0

    def log_step(self, step_name: str, success: bool, details: str = ''):
        """记录每步验证"""
        self.operations['step_logs'].append({
            'timestamp': datetime.now().isoformat(),
            'step': step_name,
            'success': success,
            'details': details
        })

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
        self.log_step("init_memory", True, f"Worker {self.worker_id} initialized")

    def run(self):
        try:
            self.start_memory = get_memory_usage()
            self.init_memory()
        except Exception as e:
            self.log_step("init_memory", False, str(e))
            self.result_dict[f'w_{self.worker_id}'] = {'status': 'init_fail', 'error': str(e)}
            return
        
        start_time = time.time()
        last_log_time = start_time
        ops_list = [
            'remember', 'recall', 'add_entity', 'add_relation', 'store_pref',
            'remember_conversation', 'add_to_working', 'consolidate', 'get_stats',
            'search_entities', 'get_preference', 'get_conversation_history'
        ]
        
        while time.time() - start_time < self.duration:
            try:
                op = random.choice(ops_list)
                self.operations['total'] += 1
                self.operations['by_type'][op] = self.operations['by_type'].get(op, 0) + 1
                
                success = False
                details = ''
                
                if op == 'remember':
                    content = generate_ultimate_chaos_content()[:200000]
                    mem_type = random.choice(['fact', 'semantic', 'episodic', 'procedural', 'conversation'])
                    importance = random.uniform(-10.0, 10.0)
                    
                    try:
                        self.memory.remember(
                            content=content,
                            memory_type=mem_type,
                            importance=max(0.0, min(1.0, importance))
                        )
                        success = True
                        details = f"content_len={len(content)}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'recall':
                    query = generate_ultimate_chaos_content()[:500] if random.random() < 0.8 else ''
                    top_k = random.randint(-100, 500)
                    try:
                        results = self.memory.recall(query, top_k=max(0, top_k))
                        success = True
                        details = f"found={len(results)}, query_len={len(query)}, top_k={top_k}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'add_entity':
                    name = generate_ultimate_chaos_content()[:100]
                    entity_type = random.choice(['person', 'concept', 'tool', 'item', 'unknown', 'place', 'event'])
                    desc = generate_ultimate_chaos_content()[:5000]
                    try:
                        entity_id = self.memory.add_entity(name=name, entity_type=entity_type, description=desc)
                        success = True
                        details = f"entity_id={entity_id}, name_len={len(name)}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'add_relation':
                    source = generate_ultimate_chaos_content()[:50]
                    target = generate_ultimate_chaos_content()[:50]
                    rel_type = random.choice(['related_to', 'uses', 'contains', 'part_of', 'causes', 'similar_to'])
                    try:
                        self.memory.add_entity(name=source[:30], entity_type='concept', description='')
                        self.memory.add_entity(name=target[:30], entity_type='concept', description='')
                        self.memory.add_relation(source=source[:30], target=target[:30], relation_type=rel_type)
                        success = True
                        details = f"source_len={len(source)}, target_len={len(target)}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'store_pref':
                    key = generate_ultimate_chaos_content()[:100]
                    value = generate_ultimate_chaos_content()[:10000]
                    category = random.choice(['ui', 'setting', 'user', 'system', 'custom', 'app', 'config'])
                    try:
                        pref_id = self.memory.store_preference(key=key[:50], value=value[:2000], category=category)
                        success = True
                        details = f"pref_id={pref_id}, key_len={len(key)}, value_len={len(value)}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'remember_conversation':
                    speaker = random.choice(['user', 'assistant', 'system', 'agent', 'bot'])
                    content = generate_ultimate_chaos_content()[:10000]
                    important = random.random() > 0.3
                    try:
                        self.memory.remember_conversation(content=content[:3000], speaker=speaker, important=important)
                        success = True
                        details = f"speaker={speaker}, content_len={len(content)}, important={important}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'add_to_working':
                    key = f"wk_{self.worker_id}_{int(time.time()*1000000)}"
                    content = generate_ultimate_chaos_content()[:5000]
                    try:
                        self.memory.add_to_working_memory(key=key, content=content[:2000], importance=random.random())
                        success = True
                        details = f"key={key}, content_len={len(content)}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'consolidate':
                    try:
                        if hasattr(self.memory, 'consolidate'):
                            self.memory.consolidate()
                        success = True
                    except Exception as e:
                        details = str(e)
                
                elif op == 'get_stats':
                    try:
                        if hasattr(self.memory, 'get_stats'):
                            self.memory.get_stats()
                        success = True
                    except Exception as e:
                        details = str(e)
                
                elif op == 'search_entities':
                    try:
                        if hasattr(self.memory, 'search_entities'):
                            query = generate_ultimate_chaos_content()[:100]
                            results = self.memory.search_entities(query, top_k=random.randint(0, 20))
                            success = True
                            details = f"query_len={len(query)}, results={len(results)}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'get_preference':
                    key = generate_ultimate_chaos_content()[:50]
                    try:
                        pref = self.memory.get_preference(key)
                        success = True
                        details = f"key={key}, found={pref is not None}"
                    except Exception as e:
                        details = str(e)
                
                elif op == 'get_conversation_history':
                    try:
                        history = self.memory.get_conversation_history(limit=random.randint(0, 100))
                        success = True
                        details = f"history_count={len(history)}"
                    except Exception as e:
                        details = str(e)
                
                if success:
                    self.operations['success'] += 1
                    self.log_step(op, True, details)
                else:
                    self.operations['failed'] += 1
                    self.log_step(op, False, details)
                    self.errors.append((op, type(e).__name__ if 'e' in locals() else 'unknown', details))
                
                if random.random() < 0.01:
                    time.sleep(random.uniform(0.0001, 0.01))
                
                if time.time() - last_log_time > 20:
                    logger.info(f"[{self.name}] running - total={self.operations['total']}, "
                               f"success={self.operations['success']}, "
                               f"failed={self.operations['failed']}")
                    last_log_time = time.time()
            
            except Exception as e:
                self.operations['failed'] += 1
                self.log_step("unexpected", False, str(e))
                self.errors.append(('unexpected', type(e).__name__, str(e)[:200]))
        
        self.end_memory = get_memory_usage()
        
        try:
            self.memory.close()
            self.log_step("close_memory", True, "Memory closed successfully")
        except Exception as e:
            self.log_step("close_memory", False, str(e))
        
        rate = self.operations['success'] / self.operations['total'] * 100 if self.operations['total'] > 0 else 0
        mem_change = self.end_memory - self.start_memory
        
        logger.info(f"[{self.name}] COMPLETED - total={self.operations['total']}, "
                   f"success={self.operations['success']}, "
                   f"failed={self.operations['failed']}, "
                   f"rate={rate:.1f}%, "
                   f"mem_change={mem_change:+.2f}MB")
        
        self.result_dict[f'w_{self.worker_id}'] = {
            'status': 'completed',
            'operations': self.operations,
            'errors': self.errors[:100],
            'mem_change': mem_change
        }


def get_memory_usage() -> float:
    """获取内存使用"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def run_phase(workers_count, duration, name):
    """运行单个测试阶段"""
    print(f"\n{'='*160}")
    print(f"🔄 {name}: {workers_count}线程 × {duration}秒")
    print(f"{'='*160}")
    
    result_dict = {}
    workers = []
    overall_start = time.time()
    
    for i in range(workers_count):
        worker = UltimateWorker(i, duration, result_dict)
        workers.append(worker)
    
    for worker in workers:
        worker.start()
    
    for worker in workers:
        worker.join()
    
    elapsed = time.time() - overall_start
    
    total_ops = sum(w['operations']['total'] for w in result_dict.values() if 'operations' in w)
    total_success = sum(w['operations']['success'] for w in result_dict.values() if 'operations' in w)
    total_failed = sum(w['operations']['failed'] for w in result_dict.values() if 'operations' in w)
    total_mem_change = sum(w.get('mem_change', 0) for w in result_dict.values() if 'operations' in w)
    
    success_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print(f"\n📊 {name} 结果:")
    print(f"  总操作: {total_ops:,}")
    print(f"  成功: {total_success:,}")
    print(f"  失败: {total_failed:,}")
    print(f"  成功率: {success_rate:.2f}%")
    print(f"  总耗时: {elapsed:.2f}s")
    print(f"  平均内存变化: {total_mem_change/workers_count:.2f}MB/线程")
    
    return total_ops, total_success, total_failed, success_rate, elapsed


def main():
    print("\n" + "="*160)
    print("🚀 Agent Memory System - 第四轮超极限迭代测试")
    print("="*160)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("测试内容: 300-500线程 × 60-120秒，终极混乱数据，每步验证")
    print("="*160)
    
    overall_start = time.time()
    initial_mem = get_memory_usage()
    
    phases = [
        (300, 60, "阶段1: 300线程 × 60秒"),
        (400, 90, "阶段2: 400线程 × 90秒"),
        (500, 120, "阶段3: 500线程 × 120秒"),
    ]
    
    all_results = []
    total_ops = 0
    total_success = 0
    total_failed = 0
    
    for workers, duration, name in phases:
        ops, success, failed, rate, elapsed = run_phase(workers, duration, name)
        all_results.append((name, ops, success, failed, rate, elapsed))
        total_ops += ops
        total_success += success
        total_failed += failed
    
    overall_time = time.time() - overall_start
    final_mem = get_memory_usage()
    overall_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print("\n" + "="*160)
    print("🏆 第四轮超极限测试总结")
    print("="*160)
    
    print(f"\n总耗时: {overall_time:.2f}s ({overall_time/60:.1f}分钟)")
    print(f"初始内存: {initial_mem:.2f}MB")
    print(f"最终内存: {final_mem:.2f}MB")
    print(f"内存变化: {final_mem - initial_mem:+.2f}MB")
    print(f"\n📈 总体:")
    print(f"  总操作: {total_ops:,}")
    print(f"  总成功: {total_success:,}")
    print(f"  总失败: {total_failed:,}")
    print(f"  总体成功率: {overall_rate:.2f}%")
    
    if overall_rate >= 99:
        print("\n🏆🏆🏆 完美！系统极其稳定！")
        final_status = "excellent"
    elif overall_rate >= 95:
        print("\n✅ 优秀！系统非常稳定！")
        final_status = "great"
    elif overall_rate >= 90:
        print("\n✅ 良好！系统稳定！")
        final_status = "good"
    elif overall_rate >= 80:
        print("\n⚠️ 基本可用，建议优化！")
        final_status = "fair"
    else:
        print("\n❌ 需要修复！")
        final_status = "needs_work"
    
    print(f"\n分阶段结果:")
    for name, ops, success, failed, rate, elapsed in all_results:
        print(f"  {name}: {ops:,} ops, {rate:.2f}% success")
    
    print("\n" + "="*160)
    
    return final_status


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    status = main()
    sys.exit(0 if status in ["excellent", "great", "good"] else 1)
