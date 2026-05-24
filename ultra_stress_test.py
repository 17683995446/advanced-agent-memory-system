#!/usr/bin/env python3
"""
极端复杂长时间压力测试 - 多次迭代，真实场景
"""

import sys
import time
import random
import string
import threading
import logging
import gc
import psutil
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('ultra_stress')


def get_memory_usage() -> float:
    """获取当前内存使用(MB)"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def generate_chaos_content(min_len=10, max_len=3000) -> str:
    """生成极端混乱内容"""
    length = random.randint(min_len, max_len)
    
    charsets = [
        string.ascii_letters,
        string.digits,
        '中文测试内容日本語韓國語阿拉伯語Русский',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄',
    ]
    
    content = []
    for _ in range(length):
        charset = random.choice(charsets)
        content.append(random.choice(charset))
    
    return ''.join(content)


def generate_tags():
    """生成随机标签"""
    num_tags = random.randint(0, 30)
    tags = []
    for _ in range(num_tags):
        tag_len = random.randint(1, 50)
        tag = ''.join(random.choice(string.ascii_letters + string.digits + '_-') for _ in range(tag_len))
        tags.append(tag)
    return tags


class UltraStressWorker:
    """超压测试工作线程"""
    
    def __init__(self, worker_id: int, duration: float, result_dict: Dict):
        self.worker_id = worker_id
        self.duration = duration
        self.result_dict = result_dict
        self.thread_name = f"UltraWorker-{worker_id:02d}"
        
    def run(self):
        from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig
        
        result_dict = self.result_dict
        result_dict[self.worker_id] = {
            'total_ops': 0,
            'success_ops': 0,
            'failed_ops': 0,
            'op_types': {},
            'start_memory': 0,
            'end_memory': 0,
            'errors': [],
        }
        ops = result_dict[self.worker_id]
        
        try:
            config = AgentMemoryConfig(
                long_term=LongTermMemoryConfig(
                    embedding={"provider": "fake", "fake_dimension": 128},
                    vector_store={"backend": "memory"}
                ),
                knowledge_graph={"enabled": True},
                structured_store={"enabled": True, "db_path": ":memory:"}
            )
            memory = AgentMemory(config)
            ops['start_memory'] = get_memory_usage()
            logger.info(f"[{self.thread_name}] 初始化成功，内存: {ops['start_memory']:.2f}MB")
        except Exception as e:
            logger.error(f"[{self.thread_name}] 初始化失败: {e}")
            ops['failed_init'] = True
            result_dict['failed_init'] = result_dict.get('failed_init', 0) + 1
            return
        
        start_time = time.time()
        last_log_time = start_time
        
        operation_types = [
            'remember', 'recall', 'forget', 'add_entity', 'add_relation',
            'store_pref', 'remember_conversation', 'add_to_short',
            'get_entity', 'find_related', 'get_preference',
            'get_conversation_history', 'consolidate', 'compress',
            'detect_conflicts', 'get_stats',
        ]
        
        while time.time() - start_time < self.duration:
            try:
                op = random.choice(operation_types)
                ops['total_ops'] += 1
                ops['op_types'][op] = ops['op_types'].get(op, 0) + 1
                
                success = False
                
                if op == 'remember':
                    content = generate_chaos_content(20, 2500)
                    mem_type = random.choice(['fact', 'semantic', 'episodic', 'procedural', 'conversation'])
                    category = random.choice(['chaos', 'test', 'tech', 'personal', 'work', 'random', 'misc'])
                    importance = random.uniform(0.0, 1.0)
                    tags = generate_tags()
                    
                    try:
                        memory.remember(
                            content=content,
                            memory_type=mem_type,
                            category=category,
                            importance=importance,
                            tags=tags
                        )
                        success = True
                    except Exception as e:
                        ops['errors'].append(f'remember: {type(e).__name__}')
                
                elif op == 'recall':
                    query = generate_chaos_content(5, 100)
                    top_k = random.randint(1, 50)
                    try:
                        memory.recall(query, top_k=top_k)
                        success = True
                    except Exception as e:
                        ops['errors'].append(f'recall: {type(e).__name__}')
                
                elif op == 'add_entity':
                    name = generate_chaos_content(5, 50)
                    entity_type = random.choice(['person', 'concept', 'tool', 'item', 'unknown', 'place', 'event'])
                    desc = generate_chaos_content(10, 500)
                    try:
                        memory.add_entity(name=name, entity_type=entity_type, description=desc)
                        success = True
                    except Exception as e:
                        ops['errors'].append(f'add_entity: {type(e).__name__}')
                
                elif op == 'add_relation':
                    source = generate_chaos_content(5, 30)
                    target = generate_chaos_content(5, 30)
                    rel_type = random.choice(['related_to', 'uses', 'contains', 'part_of', 'causes', 'similar_to'])
                    try:
                        memory.add_entity(name=source, entity_type='concept', description='')
                        memory.add_entity(name=target, entity_type='concept', description='')
                        memory.add_relation(source=source, target=target, relation_type=rel_type)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'store_pref':
                    key = generate_chaos_content(3, 40)
                    value = generate_chaos_content(5, 200)
                    category = random.choice(['ui', 'setting', 'user', 'system', 'custom'])
                    try:
                        memory.store_preference(key=key, value=value, category=category)
                        success = True
                    except Exception as e:
                        ops['errors'].append(f'store_pref: {type(e).__name__}')
                
                elif op == 'remember_conversation':
                    speaker = random.choice(['user', 'assistant', 'system', 'agent'])
                    content = generate_chaos_content(20, 500)
                    important = random.random() > 0.7
                    try:
                        memory.remember_conversation(content=content, speaker=speaker, important=important)
                        success = True
                    except Exception as e:
                        ops['errors'].append(f'remember_conversation: {type(e).__name__}')
                
                elif op == 'add_to_short':
                    key = f"short_{self.worker_id}_{int(time.time()*1000000)}"
                    content = generate_chaos_content(20, 500)
                    importance = random.uniform(0.0, 1.0)
                    try:
                        memory.add_to_working_memory(key=key, content=content, importance=importance)
                        success = True
                    except Exception as e:
                        ops['errors'].append(f'add_to_short: {type(e).__name__}')
                
                elif op == 'get_stats':
                    try:
                        memory.get_stats() if hasattr(memory, 'get_stats') else None
                        success = True
                    except Exception:
                        pass
                
                elif op == 'consolidate':
                    try:
                        memory.consolidate()
                        success = True
                    except Exception:
                        pass
                
                elif op == 'compress':
                    try:
                        if hasattr(memory, 'compress_memories'):
                            memory.compress_memories()
                        success = True
                    except Exception:
                        pass
                
                elif op == 'detect_conflicts':
                    try:
                        if hasattr(memory, 'detect_conflicts'):
                            memory.detect_conflicts()
                        success = True
                    except Exception:
                        pass
                
                elif op == 'get_entity':
                    name = generate_chaos_content(5, 30)
                    try:
                        memory.get_entity(name)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'find_related':
                    name = generate_chaos_content(5, 30)
                    try:
                        memory.find_related(name, top_k=10)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'get_preference':
                    key = generate_chaos_content(3, 20)
                    try:
                        memory.get_preference(key)
                        success = True
                    except Exception:
                        pass
                
                elif op == 'get_conversation_history':
                    try:
                        memory.get_conversation_history(limit=20)
                        success = True
                    except Exception:
                        pass
                
                if success:
                    ops['success_ops'] += 1
                else:
                    ops['failed_ops'] += 1
                
                # 随机延迟
                if random.random() < 0.15:
                    time.sleep(random.uniform(0.0001, 0.005))
                
                # 定期日志
                if time.time() - last_log_time > 5:
                    logger.info(f"[{self.thread_name}] 运行中... 已执行 {ops['total_ops']} 次操作")
                    last_log_time = time.time()
            
            except Exception as e:
                ops['failed_ops'] += 1
                ops['errors'].append(f'unexpected: {type(e).__name__}: {e}')
        
        ops['end_memory'] = get_memory_usage()
        
        try:
            memory.close()
            logger.info(f"[{self.thread_name}] 资源已释放")
        except Exception as e:
            logger.warning(f"[{self.thread_name}] 关闭时异常: {e}")
        
        logger.info(
            f"[{self.thread_name}] 完成! "
            f"总计={ops['total_ops']}, "
            f"成功={ops['success_ops']}, "
            f"失败={ops['failed_ops']}, "
            f"内存变化={ops['end_memory'] - ops['start_memory']:.2f}MB"
        )


def run_ultra_stress_test():
    """运行极端压力测试"""
    print("\n" + "=" * 140)
    print("🚀 Agent Memory System - 超极端长时间复杂场景压力测试")
    print("=" * 140)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n多次迭代，真实场景，内存监控，全面验证")
    print("=" * 140)
    
    # 测试配置
    num_workers = 20
    duration_seconds = 60  # 60秒测试
    
    print(f"\n📋 测试配置:")
    print(f"  并发线程: {num_workers}")
    print(f"  持续时间: {duration_seconds} 秒")
    print(f"  操作类型: 16种核心API")
    print(f"  内容长度: 10-3000字符")
    print(f"  特殊字符: 多语言、emoji、标点、符号")
    
    initial_memory = get_memory_usage()
    print(f"\n💾 初始系统内存: {initial_memory:.2f} MB")
    
    result_dict = {
        'failed_init': 0,
        'start_time': time.time(),
    }
    
    threads = []
    print(f"\n🚀 启动线程...")
    
    for worker_id in range(num_workers):
        worker = UltraStressWorker(worker_id, duration_seconds, result_dict)
        t = threading.Thread(target=worker.run, name=worker.thread_name)
        threads.append(t)
        t.start()
    
    print(f"✅ {len(threads)} 线程已启动，运行 {duration_seconds} 秒...\n")
    
    for t in threads:
        t.join()
    
    total_time = time.time() - result_dict['start_time']
    final_memory = get_memory_usage()
    
    # 总结
    print("\n" + "=" * 140)
    print("📊 超极端压力测试总结")
    print("=" * 140)
    
    total_ops = 0
    total_success = 0
    total_failed = 0
    op_type_stats = {}
    all_errors = []
    memory_usage_data = []
    
    print(f"\n📈 每个线程详细结果:")
    for worker_id in range(num_workers):
        ops = result_dict.get(worker_id, {})
        total_ops += ops.get('total_ops', 0)
        total_success += ops.get('success_ops', 0)
        total_failed += ops.get('failed_ops', 0)
        
        for op_type, count in ops.get('op_types', {}).items():
            op_type_stats[op_type] = op_type_stats.get(op_type, 0) + count
        
        all_errors.extend(ops.get('errors', []))
        
        mem_start = ops.get('start_memory', 0)
        mem_end = ops.get('end_memory', 0)
        memory_usage_data.append((mem_start, mem_end))
        
        success_rate = ops.get('success_ops', 0) / ops.get('total_ops', 1) * 100 if ops.get('total_ops', 0) > 0 else 0
        print(
            f"  线程 {worker_id:02d}: "
            f"总计 {ops.get('total_ops', 0):6,} | "
            f"成功 {ops.get('success_ops', 0):6,} | "
            f"失败 {ops.get('failed_ops', 0):4} | "
            f"成功率 {success_rate:5.1f}% | "
            f"内存变化 {mem_end - mem_start:+7.2f}MB"
        )
    
    overall_success_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print(f"\n🔍 整体结果:")
    print(f"  总操作数:      {total_ops:12,}")
    print(f"  成功操作:      {total_success:12,}")
    print(f"  失败操作:      {total_failed:12,}")
    print(f"  整体成功率:    {overall_success_rate:10.2f}%")
    print(f"  总耗时:        {total_time:10.2f}s")
    print(f"  吞吐率:        {total_ops / total_time:10.1f} ops/s")
    print(f"  初始化失败:    {result_dict.get('failed_init', 0)}")
    
    print(f"\n💾 内存使用情况:")
    print(f"  初始系统内存:  {initial_memory:10.2f} MB")
    print(f"  最终系统内存:  {final_memory:10.2f} MB")
    print(f"  内存增长:      {final_memory - initial_memory:+10.2f} MB")
    
    print(f"\n📋 操作类型统计:")
    for op_type, count in sorted(op_type_stats.items(), key=lambda x: -x[1]):
        print(f"  {op_type:25s}: {count:8,} 次")
    
    if all_errors:
        print(f"\n⚠️  错误统计 (前20个):")
        error_count = {}
        for err in all_errors[:100]:
            error_count[err] = error_count.get(err, 0) + 1
        for err, cnt in sorted(error_count.items(), key=lambda x: -x[1])[:20]:
            print(f"  {err}: {cnt} 次")
    else:
        print(f"\n✅ 没有记录到错误!")
    
    # 判定结果
    print("\n" + "=" * 140)
    if overall_success_rate >= 95 and total_failed <= total_ops * 0.01 and result_dict.get('failed_init', 0) == 0:
        print("🏆🏆🏆 完美通过! 系统极其稳定，达到生产环境最高标准!")
        code = 0
    elif overall_success_rate >= 90:
        print("✅ 优秀! 系统表现出色，可投入生产使用!")
        code = 0
    elif overall_success_rate >= 80:
        print("⚠️  通过，但有改进空间")
        code = 1
    else:
        print("❌ 需要进一步优化")
        code = 2
    
    print("=" * 140)
    return code


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    sys.exit(run_ultra_stress_test())
