#!/usr/bin/env python3
"""
详细分析测试，找出为什么有些操作没有统计到成功
"""

import sys
import time
import random
import string
import logging
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('debug_analysis')


def generate_chaos_content(min_len=10, max_len=2000) -> str:
    """生成混乱内容"""
    length = random.randint(min_len, max_len)
    charsets = [
        string.ascii_letters,
        string.digits,
        '中文测试内容日本語韓國語',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥',
    ]
    content = []
    for _ in range(length):
        charset = random.choice(charsets)
        content.append(random.choice(charset))
    return ''.join(content)


def single_thread_debug_test():
    """单线程调试测试"""
    from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig
    
    print("=" * 100)
    print("🔍 单线程调试测试 - 分析每个操作")
    print("=" * 100)
    
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
        print("✅ 初始化成功")
    except Exception as e:
        print(f"❌ 初始化失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return
    
    test_cases = [
        ('remember', 5),
        ('recall', 5),
        ('entity', 3),
        ('store_pref', 3),
        ('conversation', 3),
        ('add_to_short', 3),
    ]
    
    results = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'details': []
    }
    
    for op_type, count in test_cases:
        for i in range(count):
            results['total'] += 1
            print(f"\n--- 测试 {results['total']}: {op_type} ---")
            
            try:
                if op_type == 'remember':
                    content = generate_chaos_content(20, 200)
                    mem_type = random.choice(['fact', 'semantic', 'episodic', 'procedural', 'conversation'])
                    category = random.choice(['chaos', 'test', 'tech', 'personal', 'work'])
                    importance = random.uniform(0.0, 1.0)
                    
                    print(f"  参数: content长度={len(content)}, type={mem_type}, category={category}")
                    
                    try:
                        mem_id = memory.remember(
                            content=content,
                            memory_type=mem_type,
                            category=category,
                            importance=importance
                        )
                        print(f"  ✅ 成功, memory_id={mem_id}")
                        results['success'] += 1
                        results['details'].append((op_type, 'success', mem_id))
                    except Exception as e:
                        print(f"  ❌ remember失败: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        results['failed'] += 1
                        results['details'].append((op_type, 'failed', str(e)))
                
                elif op_type == 'recall':
                    query = generate_chaos_content(5, 50)
                    top_k = random.randint(1, 10)
                    
                    print(f"  参数: query长度={len(query)}, top_k={top_k}")
                    
                    try:
                        res = memory.recall(query, top_k=top_k)
                        print(f"  ✅ 成功, 找到 {len(res)} 条结果")
                        results['success'] += 1
                        results['details'].append((op_type, 'success', len(res)))
                    except Exception as e:
                        print(f"  ❌ recall失败: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        results['failed'] += 1
                        results['details'].append((op_type, 'failed', str(e)))
                
                elif op_type == 'entity':
                    name = generate_chaos_content(10, 30)
                    entity_type = random.choice(['person', 'concept', 'tool', 'item', 'unknown'])
                    desc = generate_chaos_content(20, 100)
                    
                    print(f"  参数: name={name[:20]}..., type={entity_type}")
                    
                    try:
                        entity_id = memory.add_entity(name=name, entity_type=entity_type, description=desc)
                        print(f"  ✅ 成功, entity_id={entity_id}")
                        results['success'] += 1
                        results['details'].append((op_type, 'success', entity_id))
                    except Exception as e:
                        print(f"  ❌ add_entity失败: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        results['failed'] += 1
                        results['details'].append((op_type, 'failed', str(e)))
                
                elif op_type == 'store_pref':
                    key = generate_chaos_content(5, 20)
                    value = generate_chaos_content(10, 50)
                    category = random.choice(['ui', 'setting', 'user', 'system'])
                    
                    print(f"  参数: key={key}, category={category}")
                    
                    try:
                        pref_id = memory.store_preference(key=key, value=value, category=category)
                        print(f"  ✅ 成功, pref_id={pref_id}")
                        results['success'] += 1
                        results['details'].append((op_type, 'success', pref_id))
                    except Exception as e:
                        print(f"  ❌ store_preference失败: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        results['failed'] += 1
                        results['details'].append((op_type, 'failed', str(e)))
                
                elif op_type == 'conversation':
                    speaker = random.choice(['user', 'assistant', 'system'])
                    content = generate_chaos_content(30, 100)
                    important = random.random() > 0.5
                    
                    print(f"  参数: speaker={speaker}, important={important}")
                    
                    try:
                        res = memory.remember_conversation(content=content, speaker=speaker, important=important)
                        print(f"  ✅ 成功, 返回={res}")
                        results['success'] += 1
                        results['details'].append((op_type, 'success', res))
                    except Exception as e:
                        print(f"  ❌ remember_conversation失败: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        results['failed'] += 1
                        results['details'].append((op_type, 'failed', str(e)))
                
                elif op_type == 'add_to_short':
                    key = f"debug_key_{int(time.time())}_{i}"
                    content = generate_chaos_content(20, 100)
                    importance = random.uniform(0.0, 1.0)
                    
                    print(f"  参数: key={key}, importance={importance:.2f}")
                    
                    try:
                        res = memory.add_to_working_memory(key=key, content=content, importance=importance)
                        print(f"  ✅ 成功, 返回={res}")
                        results['success'] += 1
                        results['details'].append((op_type, 'success', res))
                    except Exception as e:
                        print(f"  ❌ add_to_working_memory失败: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        results['failed'] += 1
                        results['details'].append((op_type, 'failed', str(e)))
            
            except Exception as e:
                print(f"❌ 外层异常: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                results['failed'] += 1
                results['details'].append(('outer', 'failed', str(e)))
    
    print("\n" + "=" * 100)
    print("📊 调试测试总结")
    print("=" * 100)
    print(f"总操作: {results['total']}")
    print(f"成功: {results['success']}")
    print(f"失败: {results['failed']}")
    print(f"成功率: {results['success']/results['total']*100:.1f}%")
    
    print("\n详细结果:")
    for i, (op_type, status, detail) in enumerate(results['details']):
        print(f"  {i+1}. {op_type:15s} - {status:8s} - {detail}")
    
    try:
        memory.close()
        print("\n✅ 资源释放成功")
    except Exception as e:
        print(f"\n⚠️  关闭时异常: {e}")
    
    return results


if __name__ == '__main__':
    single_thread_debug_test()
