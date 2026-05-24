#!/usr/bin/env python3
"""
Agent Memory System - 第四轮小版本验证测试
100线程 × 30秒，快速验证
"""

import sys
import time
import random
import string
import threading
import logging
import gc
import psutil
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('validation_test')


def generate_chaos_content() -> str:
    length = random.randint(100, 50000)
    
    charsets = [
        string.ascii_letters * 20,
        string.digits * 10,
        '中文测试内容日本語韓國語Русскийالعربية',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯' * 30,
        '\n\r\t\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0b\x0c',
    ]
    
    content = []
    for _ in range(length):
        charset = random.choice(charsets)
        content.append(random.choice(charset))
    
    return ''.join(content)


class SmallWorker(threading.Thread):
    """验证测试工作线程"""
    
    def __init__(self, worker_id, duration, result_dict):
        super().__init__(name=f'Small-{worker_id:03d')
        self.worker_id = worker_id
        self.duration = duration
        self.result_dict = result_dict
        
        self.operations = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'by_type': {},
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
        try:
            self.init_memory()
        except Exception as e:
            self.result_dict[f'w_{self.worker_id}'] = {'status': 'init_fail', 'error': str(e)}
            return
        
        start_time = time.time()
        ops_list = [
            'remember', 'recall', 'add_entity', 'add_relation', 'store_pref',
            'remember_conversation', 'add_to_working', 'get_stats',
        ]
        
        while time.time() - start_time < self.duration:
            try:
                op = random.choice(ops_list)
                self.operations['total'] += 1
                self.operations['by_type'][op] = self.operations['by_type'].get(op, 0) + 1
                
                success = False
                
                if op == 'remember':
                    content = generate_chaos_content()[:20000
                    mem_type = random.choice(['fact', 'semantic', 'episodic', 'conversation'])
                    importance = random.uniform(0.0, 1.0)
                    
                    try:
                        self.memory.remember(
                            content=content,
                            memory_type=mem_type,
                            importance=importance
                        )
                        success = True
                    except Exception:
                        pass
                
                elif op == 'recall':
                    query = generate_chaos_content()[:200] if random.random() < 0.8 else ''
                    try:
                        self.memory.recall(query, top_k=random.randint(0, 20))
                        success = True
                    except Exception:
                        pass
                
                elif op == 'add_entity':
                    name = generate_chaos_content()[:50]
                    entity_type = random.choice(['person', 'concept', 'tool'])
                    desc = generate_chaos_content()[:500
                    try:
                        self.memory.add_entity(name=name, entity_type=entity_type, description=desc)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'add_relation':
                    source = generate_chaos_content()[:30]
                    target = generate_chaos_content()[:30]
                    rel_type = random.choice(['related_to', 'uses'])
                    try:
                        self.memory.add_entity(name=source, entity_type='concept', description='')
                        self.memory.add_entity(name=target, entity_type='concept', description='')
                        self.memory.add_relation(source=source, target=target, relation_type=rel_type)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'store_pref':
                    key = generate_chaos_content()[:50]
                    value = generate_chaos_content()[:1000
                    category = random.choice(['ui', 'setting', 'user', 'system'])
                    try:
                        self.memory.store_preference(key=key, value=value, category=category)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'remember_conversation':
                    speaker = random.choice(['user', 'assistant', 'system'])
                    content = generate_chaos_content()[:2000
                    important = random.random() > 0.5
                    try:
                        self.memory.remember_conversation(content=content, speaker=speaker, important=important)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'add_to_working':
                    key = f'wk_{self.worker_id}_{int(time.time()*1000000)}
                    content = generate_chaos_content()[:1000
                    try:
                        self.memory.add_to_working_memory(key=key, content=content, importance=random.random())
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
                
                if success:
                    self.operations['success'] += 1
                else:
                    self.operations['failed'] += 1
                
                if random.random() < 0.02:
                    time.sleep(0.001)
            
            except Exception:
                self.operations['failed'] += 1
        
        try:
            self.memory.close()
        except Exception:
            pass
        
        rate = self.operations['success'] / self.operations['total'] * 100 if self.operations['total'] > 0 else 0
        
        logger.info(f"[{self.name}] COMPLETED - total={self.operations['total']}, success={self.operations['success']}, "
                 f"failed={self.operations['failed']}, rate={rate:.1f}%")
        
        self.result_dict[f'w_{self.worker_id}'] = {
            'status': 'completed',
            'operations': self.operations,
            'errors': self.errors[:50]
        }


def main():
    print("\n" + "="*120)
    print("🔍 Agent Memory System - 第四轮小版本验证测试")
    print("="*120)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')")
    print("测试: 100线程 × 30秒")
    print("="*120)
    
    workers_count = 100
    duration = 30
    
    result_dict = {}
    workers = []
    overall_start = time.time()
    
    for i in range(workers_count):
        worker = SmallWorker(i, duration, result_dict)
        workers.append(worker)
    
    for worker in workers:
        worker.start()
    
    for worker in workers:
        worker.join()
    
    elapsed = time.time() - overall_start
    
    total_ops = sum(w['operations']['total'] for w in result_dict.values() if 'operations' in w)
    total_success = sum(w['operations']['success'] for w in result_dict.values() if 'operations' in w)
    total_failed = sum(w['operations']['failed'] for w in result_dict.values() if 'operations' in w)
    
    success_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print("\n" + "="*120)
    print("📊 小版本验证结果")
    print("="*120)
    print(f"总操作: {total_ops:,}")
    print(f"成功: {total_success:,}")
    print(f"失败: {total_failed:,}")
    print(f"成功率: {success_rate:.2f}%")
    print(f"总耗时: {elapsed:.2f}s")
    print("="*120)
    
    if success_rate >= 95:
        print("\n✅ 优秀！系统运行正常！可以进行超大规模测试！")
        final_status = "success"
    elif success_rate >= 90:
        print("\n✅ 良好！可以进行超大规模测试！")
        final_status = "good"
    else:
        print("\n⚠️ 基本可用，但建议先检查问题！")
        final_status = "needs_check"
    
    return final_status


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    status = main()
    sys.exit(0 if status in ["success", "good"] else 1)
