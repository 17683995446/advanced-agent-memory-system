#!/usr/bin/env python3
"""
第5轮测试 - 快速验证版本
验证系统在复杂场景下的表现
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
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('round5_quick')


def generate_chaos_content():
    """生成混乱内容"""
    length = random.randint(10, 10000)
    charsets = [
        string.ascii_letters * 10,
        string.digits * 5,
        '中文测试内容日本語韓國語',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃',
        '\n\r\t',
    ]
    content = []
    for _ in range(length):
        charset = random.choice(charsets)
        content.append(random.choice(charset))
    return ''.join(content)


class QuickTestWorker(threading.Thread):
    """快速测试工作线程"""
    
    def __init__(self, worker_id, duration, result_dict):
        super().__init__(name=f'Quick-{worker_id:02d}')
        self.worker_id = worker_id
        self.duration = duration
        self.result_dict = result_dict
        self.ops = {'total': 0, 'success': 0, 'failed': 0, 'errors': []}
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
            self.result_dict[f'worker_{self.worker_id}'] = {'status': 'init_failed', 'error': str(e)}
            return
        
        start = time.time()
        ops_list = ['remember', 'recall', 'add_entity', 'add_relation', 'store_preference']
        
        while time.time() - start < self.duration:
            try:
                op = random.choice(ops_list)
                self.ops['total'] += 1
                success = False
                
                if op == 'remember':
                    content = generate_chaos_content()
                    mem_type = random.choice(['fact', 'semantic', 'episodic', 'conversation'])
                    importance = random.uniform(0.0, 1.0)
                    self.memory.remember(content=content, memory_type=mem_type, importance=importance)
                    success = True
                elif op == 'recall':
                    query = generate_chaos_content() if random.random() < 0.8 else ""
                    self.memory.recall(query, top_k=random.randint(1, 10))
                    success = True
                elif op == 'add_entity':
                    name = generate_chaos_content()[:50]
                    entity_type = random.choice(['person', 'concept', 'tool'])
                    self.memory.add_entity(name=name, entity_type=entity_type, description=generate_chaos_content()[:200])
                    success = True
                elif op == 'add_relation':
                    source = generate_chaos_content()[:30]
                    target = generate_chaos_content()[:30]
                    rel_type = random.choice(['related_to', 'uses', 'contains'])
                    self.memory.add_entity(name=source, entity_type='concept', description='')
                    self.memory.add_entity(name=target, entity_type='concept', description='')
                    self.memory.add_relation(source=source, target=target, relation_type=rel_type)
                    success = True
                elif op == 'store_preference':
                    key = generate_chaos_content()[:30]
                    value = generate_chaos_content()[:500]
                    category = random.choice(['ui', 'setting', 'user', 'system'])
                    self.memory.store_preference(key=key, value=value, category=category)
                    success = True
                
                if success:
                    self.ops['success'] += 1
                else:
                    self.ops['failed'] += 1
                
            except Exception as e:
                self.ops['failed'] += 1
                self.ops['errors'].append(f"{type(e).__name__}: {str(e)[:100]}")
        
        try:
            self.memory.close()
        except Exception:
            pass
        
        self.result_dict[f'worker_{self.worker_id}'] = {
            'status': 'completed',
            'operations': self.ops
        }
        
        rate = self.ops['success'] / self.ops['total'] * 100 if self.ops['total'] > 0 else 0
        logger.info(f"[{self.name}] 完成: total={self.ops['total']}, success={self.ops['success']}, failed={self.ops['failed']}, rate={rate:.2f}%")


def main():
    print("\n" + "=" * 120)
    print("🚀 第5轮超深度测试 - 快速验证")
    print("=" * 120)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    overall_start = time.time()
    
    phases = [
        (10, 5, "阶段1: 10线程预热"),
        (30, 10, "阶段2: 30线程压力"),
        (50, 15, "阶段3: 50线程极限"),
    ]
    
    all_results = []
    total_ops = 0
    total_success = 0
    total_failed = 0
    
    for workers, duration, name in phases:
        print(f"\n{'=' * 120}")
        print(f"🔄 {name}: {workers}线程 x {duration}秒")
        print(f"{'=' * 120}")
        
        result_dict = {}
        threads = []
        for i in range(workers):
            t = QuickTestWorker(i, duration, result_dict)
            threads.append(t)
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        ops = sum(w['operations']['total'] for w in result_dict.values() if 'operations' in w)
        success = sum(w['operations']['success'] for w in result_dict.values() if 'operations' in w)
        failed = sum(w['operations']['failed'] for w in result_dict.values() if 'operations' in w)
        rate = success / ops * 100 if ops > 0 else 0
        
        all_results.append((name, ops, success, failed, rate))
        total_ops += ops
        total_success += success
        total_failed += failed
        
        print(f"\n📊 {name} 结果:")
        print(f"   总操作: {ops:,}")
        print(f"   成功: {success:,}")
        print(f"   失败: {failed:,}")
        print(f"   成功率: {rate:.2f}%")
    
    overall_end = time.time()
    overall_duration = overall_end - overall_start
    overall_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print("\n" + "=" * 120)
    print("🏆 第5轮超深度测试 - 快速验证总结")
    print("=" * 120)
    print(f"\n总耗时: {overall_duration:.2f}s")
    print(f"总操作: {total_ops:,}")
    print(f"总成功: {total_success:,}")
    print(f"总失败: {total_failed:,}")
    print(f"总体成功率: {overall_rate:.2f}%")
    
    if overall_rate >= 95:
        print("\n✅ 优秀！系统非常稳定！")
    elif overall_rate >= 90:
        print("\n✅ 良好！系统稳定！")
    elif overall_rate >= 80:
        print("\n⚠️ 基本可用！")
    else:
        print("\n❌ 需要修复！")
    
    print(f"\n分阶段结果:")
    for name, ops, success, failed, rate in all_results:
        print(f"   {name}: {ops:,} ops, {rate:.2f}% success")
    
    print("\n" + "=" * 120)
    return overall_rate


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    final_rate = main()
    sys.exit(0 if final_rate >= 90 else 1)
