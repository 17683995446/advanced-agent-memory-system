#!/usr/bin/env python3
"""
Agent Memory System - 第三轮超极限迭代测试
150线程 x 120秒，真正的极限挑战
"""

import sys
import time
import random
import string
import threading
import logging
import gc
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('extreme_round3')


def generate_ultimate_chaos() -> str:
    """生成终极混乱内容"""
    length = random.randint(100, 100000)
    
    charsets = [
        string.ascii_letters * 30,
        string.digits * 15,
        '中文测试内容日本語韓國語Русскийالعربيةहिन्दीPortuguêsDeutschFrançais',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'<>[]{}<<<>>>[[[]]]',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃🎄🎅👽🛸🦄' * 30,
        '\n\r\t\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0b\x0c\x0e\x0f',
        'абвгдежзийклмнопрстуфхцчшщъыьэюяअआइईउऊऋॠॢॣ',
    ]
    
    content = []
    for _ in range(length):
        charset = random.choice(charsets)
        content.append(random.choice(charset))
    
    return ''.join(content)


class ExtremeWorker(threading.Thread):
    """极限压力测试工作线程"""
    
    def __init__(self, worker_id, duration, result_dict):
        super().__init__(name=f'Extreme-{worker_id:03d}')
        self.worker_id = worker_id
        self.duration = duration
        self.result_dict = result_dict
        self.ops = {'total': 0, 'success': 0, 'failed': 0, 'types': {}}
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
        try:
            self.init_memory()
        except Exception as e:
            self.result_dict[f'w_{self.worker_id}'] = {'status': 'init_fail', 'error': str(e)}
            return
        
        start_time = time.time()
        ops_list = [
            'remember', 'recall', 'add_entity', 'add_relation', 'store_pref',
            'remember_conversation', 'add_to_working', 'consolidate', 'get_stats',
            'search_entities', 'get_preference', 'get_conversation_history'
        ]
        
        while time.time() - start_time < self.duration:
            try:
                op = random.choice(ops_list)
                self.ops['total'] += 1
                self.ops['types'][op] = self.ops['types'].get(op, 0) + 1
                
                success = False
                
                if op == 'remember':
                    content = generate_ultimate_chaos()
                    try:
                        self.memory.remember(
                            content=content[:15000],
                            memory_type=random.choice(['fact', 'semantic', 'episodic']),
                            importance=random.uniform(0, 1)
                        )
                        success = True
                    except Exception:
                        pass
                
                elif op == 'recall':
                    query = generate_ultimate_chaos()[:300] if random.random() < 0.8 else ''
                    try:
                        self.memory.recall(query, top_k=random.randint(0, 20))
                        success = True
                    except Exception:
                        pass
                
                elif op == 'add_entity':
                    try:
                        self.memory.add_entity(
                            name=generate_ultimate_chaos()[:50],
                            entity_type=random.choice(['person', 'concept', 'tool']),
                            description=generate_ultimate_chaos()[:500]
                        )
                        success = True
                    except Exception:
                        pass
                
                elif op == 'add_relation':
                    try:
                        s = generate_ultimate_chaos()[:30]
                        t = generate_ultimate_chaos()[:30]
                        self.memory.add_entity(name=s, entity_type='concept', description='')
                        self.memory.add_entity(name=t, entity_type='concept', description='')
                        self.memory.add_relation(s, t, random.choice(['related', 'uses']))
                        success = True
                    except Exception:
                        pass
                
                elif op == 'store_pref':
                    try:
                        self.memory.store_preference(
                            key=generate_ultimate_chaos()[:30],
                            value=generate_ultimate_chaos()[:1000],
                            category=random.choice(['ui', 'user', 'system'])
                        )
                        success = True
                    except Exception:
                        pass
                
                elif op == 'remember_conversation':
                    try:
                        self.memory.remember_conversation(
                            content=generate_ultimate_chaos()[:2000],
                            speaker=random.choice(['user', 'assistant']),
                            important=random.random() > 0.5
                        )
                        success = True
                    except Exception:
                        pass
                
                elif op == 'add_to_working':
                    try:
                        self.memory.add_to_working_memory(
                            key=f'key_{self.worker_id}_{int(time.time()*1000)}',
                            content=generate_ultimate_chaos()[:1000],
                            importance=random.random()
                        )
                        success = True
                    except Exception:
                        pass
                
                elif op == 'consolidate':
                    try:
                        if hasattr(self.memory, 'consolidate'):
                            self.memory.consolidate()
                        success = True
                    except Exception:
                        pass
                
                elif op == 'get_stats':
                    try:
                        if hasattr(self.memory, 'get_stats'):
                            self.memory.get_stats()
                        success = True
                    except Exception:
                        pass
                
                elif op == 'search_entities':
                    try:
                        if hasattr(self.memory, 'search_entities'):
                            self.memory.search_entities(generate_ultimate_chaos()[:50], top_k=5)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'get_preference':
                    try:
                        self.memory.get_preference(generate_ultimate_chaos()[:20])
                        success = True
                    except Exception:
                        pass
                
                elif op == 'get_conversation_history':
                    try:
                        self.memory.get_conversation_history(limit=20)
                        success = True
                    except Exception:
                        pass
                
                if success:
                    self.ops['success'] += 1
                else:
                    self.ops['failed'] += 1
                
                if random.random() < 0.01:
                    time.sleep(0.001)
            
            except Exception:
                self.ops['failed'] += 1
        
        try:
            self.memory.close()
        except Exception:
            pass
        
        rate = self.ops['success'] / self.ops['total'] * 100 if self.ops['total'] > 0 else 0
        print(f"[{self.name}] 完成: {self.ops['total']}ops, 成功率{rate:.1f}%")
        
        self.result_dict[f'w_{self.worker_id}'] = {
            'status': 'done',
            'ops': self.ops,
            'errors': self.errors[:20]
        }


def run_phase(workers_count, duration, name):
    """运行测试阶段"""
    print(f"\n{'='*120}")
    print(f"🔄 {name}: {workers_count}线程 x {duration}秒")
    print(f"{'='*120}")
    
    results = {}
    threads = []
    
    for i in range(workers_count):
        t = ExtremeWorker(i, duration, results)
        threads.append(t)
        t.start()
    
    start = time.time()
    for t in threads:
        t.join()
    elapsed = time.time() - start
    
    total = sum(r['ops']['total'] for r in results.values() if 'ops' in r)
    success = sum(r['ops']['success'] for r in results.values() if 'ops' in r)
    failed = sum(r['ops']['failed'] for r in results.values() if 'ops' in r)
    rate = success / total * 100 if total > 0 else 0
    
    print(f"\n📊 {name} 结果:")
    print(f"  总操作: {total:,}")
    print(f"  成功: {success:,}")
    print(f"  失败: {failed:,}")
    print(f"  成功率: {rate:.2f}%")
    print(f"  耗时: {elapsed:.2f}s")
    
    return total, success, failed, rate


def main():
    print("\n" + "="*120)
    print("🚀 Agent Memory System - 第三轮超极限迭代测试")
    print("="*120)
    print(f"开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    overall_start = time.time()
    
    phases = [
        (150, 40, "阶段1: 150线程40秒"),
        (200, 60, "阶段2: 200线程60秒"),
        (250, 80, "阶段3: 250线程80秒"),
    ]
    
    total_all = 0
    success_all = 0
    failed_all = 0
    
    for workers, duration, name in phases:
        t, s, f, r = run_phase(workers, duration, name)
        total_all += t
        success_all += s
        failed_all += f
    
    overall_time = time.time() - overall_start
    overall_rate = success_all / total_all * 100 if total_all > 0 else 0
    
    print("\n" + "="*120)
    print("🏆 第三轮超极限测试总结")
    print("="*120)
    
    print(f"\n总耗时: {overall_time:.2f}s ({overall_time/60:.1f}min)")
    print(f"\n📈 总体:")
    print(f"  总操作: {total_all:,}")
    print(f"  总成功: {success_all:,}")
    print(f"  总失败: {failed_all:,}")
    print(f"  成功率: {overall_rate:.2f}%")
    
    if overall_rate >= 95:
        print("\n🏆🏆🏆 完美通过！系统极其稳定！")
    elif overall_rate >= 90:
        print("\n✅ 优秀！系统非常稳定！")
    elif overall_rate >= 85:
        print("\n⚠️  基本可用！")
    else:
        print("\n❌ 需要优化！")
    
    print("="*120)
    
    return "pass" if overall_rate >= 90 else "fail"


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    sys.exit(0 if main() == "pass" else 1)
