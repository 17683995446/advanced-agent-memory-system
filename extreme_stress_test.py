#!/usr/bin/env python3
"""
Agent Memory System - 极端压力测试
测试系统在极端条件下的行为
"""

import sys
import time
import random
import string
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


def run_extreme_stress_test():
    print("=" * 80)
    print("🧪 Agent Memory System - 极端压力测试")
    print("=" * 80)

    results = {
        'passed': 0,
        'failed': 0,
        'issues_found': []
    }
    
    # 测试1: 大容量测试 - 大量短时间内密集写入
    print("\n" + "=" * 80)
    print("测试1: 超密集写入 - 大容量短时间内大量写入")
    print("=" * 80)
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        num_records = 5000
        print(f"准备写入 {num_records} 条记录...")
        
        start_time = time.time()
        
        written = 0
        for i in range(num_records):
            content = f"Record {i}: " + "".join(random.choices(string.ascii_letters + string.digits, k=100))
            try:
                memory_id = memory.remember(
                    content=content,
                    memory_type="semantic",
                    category="stress_test",
                    importance=random.uniform(0.1, 0.9)
                )
                written += 1
            except Exception as e:
                pass
        
        elapsed = time.time() - start_time
        print(f"✓ 写入完成: {written} 条记录, 耗时 {elapsed:.2f}s")
        print(f"✓ 平均速度: {written/elapsed:.1f} 条/秒")
        
        # 验证数据完整性
        stats = memory.get_stats()
        total = stats.get("long_term", {}).get("total_memories", 0)
        
        if total == written:
            print(f"✓ 数据一致性: 统计一致, {total} == {written}")
            results['passed'] += 1
        else:
            print(f"✗ 数据一致性问题: 统计 {total} != 实际 {written}")
            results['failed'] += 1
            results['issues_found'].append({
                "type": "inconsistent_count",
                "expected": written,
                "actual": total
            })
        
        memory.close()
        
    except Exception as e:
        results['failed'] += 1
        print(f"✗ 异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试2: 混合搜索性能测试
    print("\n" + "=" * 80)
    print("测试2: 混合搜索性能")
    print("=" * 80)
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 先写入测试数据
        for i in range(1000):
            memory.remember(
                content=f"测试数据 {i}: 关于人工智能、机器学习、深度学习的内容",
                memory_type="semantic",
                category="tech",
                importance=0.5 + random.random() * 0.5
            )
        
        # 测试搜索性能
        search_queries = ["人工智能", "机器学习", "深度学习", "神经网络", "数据科学"]
        
        search_times = []
        for _ in range(100):
            query = random.choice(search_queries)
            start = time.time()
            results = memory.recall(query, top_k=10)
            search_times.append(time.time() - start)
        
        avg_search_time = sum(search_times) / len(search_times)
        max_search_time = max(search_times)
        
        print(f"✓ 平均搜索时间: {avg_search_time*1000:.2f}ms")
        print(f"✓ 最大搜索时间: {max_search_time*1000:.2f}ms")
        
        if avg_search_time < 0.1:
            print("✓ 搜索性能良好")
            results['passed'] += 1
        else:
            print("⚠️ 搜索性能略慢")
            results['issues_found'].append({
                "type": "slow_search",
                "avg_ms": avg_search_time * 1000
            })
        
        memory.close()
        
    except Exception as e:
        results['failed'] += 1
        print(f"✗ 异常: {e}")
    
    # 测试3: 知识图谱构建大规模实体关系
    print("\n" + "=" * 80)
    print("测试3: 知识图谱大规模测试")
    print("=" * 80)
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 创建100个实体和关系
        entity_names = [f"Entity_{i}" for i in range(100)]
        
        for name in entity_names:
            try:
                memory.add_entity(name, entity_type="test_entity", description=f"Test entity {name}")
            except Exception:
                pass
        
        # 关系类型
        relation_types = ["relates_to", "is_a", "part_of", "uses"]
        
        for i in range(200):
            src = random.choice(entity_names)
            tgt = random.choice(entity_names)
            rel = random.choice(relation_types)
            try:
                memory.add_relation(src, tgt, rel, weight=random.random())
            except Exception:
                pass
        
        # 测试图谱查询
        try:
            results = memory.search_entities("Entity_5", top_k=5)
            if results:
                print(f"✓ 实体搜索成功: 找到 {len(results)} 条相关实体")
                results['passed'] += 1
            else:
                print("⚠️ 未找到相关实体")
        except Exception as e:
            print(f"⚠️ 实体搜索问题: {e}")
        
        stats = memory.get_stats()
        kg_stats = stats.get("knowledge_graph", {})
        print(f"✓ 知识图谱统计: {kg_stats}")
        
        memory.close()
        
    except Exception as e:
        results['failed'] += 1
        print(f"✗ 异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试4: 数据边界值
    print("\n" + "=" * 80)
    print("测试4: 数据边界值")
    print("=" * 80)
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 特殊字符内容
        special_content = (
            "Special chars: 中文 日本語 العربية 한국어 "
            "!@#$%^&*()_+{}[]|\\:;\"'<>?,./"
            "🤖🎯🎉✨"
        )
        memory_id = memory.remember(
            content=special_content,
            memory_type="test",
            importance=0.5
        )
        print("✓ 特殊字符内容存储成功")
        
        # 验证读取
        record = memory.long_term.get(memory_id)
        if record and record.content == special_content:
            print("✓ 特殊字符内容完整读取")
            results['passed'] += 1
        
        memory.close()
        
    except Exception as e:
        results['failed'] += 1
        print(f"✗ 异常: {e}")
    
    # 测试5: 并发混合操作
    print("\n" + "=" * 80)
    print("测试5: 并发混合操作")
    print("=" * 80)
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        memory = AgentMemory(config=config)
        
        # 初始数据
        for i in range(500):
            memory.remember(
                f"初始数据 {i}",
                memory_type="semantic",
                importance=0.5
            )
        
        num_threads = 20
        ops_per_thread = 50
        
        print(f"使用 {num_threads} 个线程，每个线程 {ops_per_thread} 次操作...")
        
        errors = []
        
        def worker(worker_id):
            for _ in range(ops_per_thread):
                try:
                    if random.random() < 0.6:
                        memory.remember(
                            content=f"线程{worker_id}写入",
                            memory_type="semantic",
                            importance=random.random()
                        )
                    else:
                        memory.recall(f"数据", top_k=5)
                except Exception as e:
                    errors.append(str(e))
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(worker, i) for i in range(num_threads)
            ]
            for future in as_completed(futures):
                future.result()
        
        elapsed = time.time() - start_time
        
        total_ops = num_threads * ops_per_thread
        print(f"✓ {total_ops} 次并发操作完成, 耗时 {elapsed:.2f}s")
        print(f"✓ 吞吐量: {total_ops/elapsed:.1f} 操作/秒")
        
        if not errors:
            print("✓ 无并发错误")
            results['passed'] += 1
        else:
            print(f"⚠️ 发生 {len(errors)} 个并发错误")
        
        memory.close()
        
    except Exception as e:
        results['failed'] += 1
        print(f"✗ 异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 总结
    print("\n" + "=" * 80)
    print("极端压力测试总结")
    print("=" * 80)
    print(f"通过: {results['passed']}, 失败: {results['failed']}")
    if results['issues_found']:
        print("\n发现问题:")
        for issue in results['issues_found']:
            print(f"  - {issue}")
    
    return results


if __name__ == "__main__":
    run_extreme_stress_test()
