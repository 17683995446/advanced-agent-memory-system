#!/usr/bin/env python3
"""
Agent Memory System - 超大规模复杂场景压力测试
遵循慢工出细活原则，深度测试系统边界
"""

import sys
import time
import random
import string
import threading
from typing import Dict, List, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig
from memory_system.processing.knowledge_graph_engine import KnowledgeGraph, Entity, Relation


def generate_random_name(length: int = 8) -> str:
    """生成随机实体名称"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def generate_test_content(category: str, idx: int) -> str:
    """生成测试内容"""
    templates = [
        "关于{topic}的深度研究报告",
        "{topic}的历史发展概述",
        "如何学习{topic}的完整指南",
        "{topic}的最佳实践和优化技巧",
        "{topic}与{other}的比较分析",
        "{topic}在{field}领域的应用",
        "{topic}的未来发展趋势预测",
    ]
    topics = ["人工智能", "机器学习", "深度学习", "自然语言处理", "计算机视觉", "数据库", "Web开发"]
    fields = ["企业", "医疗", "教育", "金融", "娱乐"]
    
    template = random.choice(templates)
    topic = random.choice(topics)
    other = random.choice([t for t in topics if t != topic])
    field = random.choice(fields)
    
    return template.format(topic=topic, other=other, field=field)


def test_1_extreme_knowledge_graph():
    """测试1：超大规模知识图谱构建"""
    print("\n" + "="*90)
    print("测试1：超大规模知识图谱构建")
    print("="*90)
    
    kg = KnowledgeGraph()
    num_entities = 500
    num_relations = 1000
    
    print(f"\n目标：构建 {num_entities} 个实体，{num_relations} 个关系")
    start_time = time.time()
    
    entities_created = 0
    entity_names = []
    
    # 批量添加实体
    for i in range(num_entities):
        try:
            name = f"Entity_{i}_{generate_random_name()}"
            entity_types = ["concept", "person", "place", "tool", "project"]
            entity = Entity(
                name=name,
                entity_type=random.choice(entity_types),
                description=f"这是关于 {name} 的描述性信息，包含其基本属性和特点。",
                properties={"created_at": time.time(), "index": i, "importance": random.random()}
            )
            kg.add_entity(entity)
            entity_names.append(name)
            entities_created += 1
            
            if (i+1) % 100 == 0:
                print(f"  已添加 {i+1}/{num_entities} 个实体...")
        except Exception as e:
            print(f"  ❌ 错误添加实体 {i}: {str(e)[:80]}")
    
    relations_created = 0
    
    # 批量添加关系
    relation_types = ["is_a", "part_of", "used_by", "related_to", "created_by", "depends_on", "similar_to"]
    for i in range(num_relations):
        try:
            source = random.choice(entity_names)
            target = random.choice([e for e in entity_names if e != source])
            rel_type = random.choice(relation_types)
            
            relation = Relation(
                source=source,
                target=target,
                relation_type=rel_type,
                weight=random.random(),
                metadata={"created_at": time.time(), "batch": i}
            )
            kg.add_relation(relation)
            relations_created += 1
            
            if (i+1) % 200 == 0:
                print(f"  已添加 {i+1}/{num_relations} 个关系...")
        except Exception as e:
            print(f"  ❌ 错误添加关系 {i}: {str(e)[:80]}")
    
    build_time = time.time() - start_time
    
    # 验证图谱状态
    print(f"\n验证图谱状态...")
    with kg._lock:
        node_count = len(kg.graph.nodes)
        edge_count = len(kg.graph.edges)
    
    print(f"\n知识图谱构建结果:")
    print(f"  实体数: {node_count}")
    print(f"  关系数: {edge_count}")
    print(f"  构建耗时: {build_time:.2f} 秒")
    
    # 测试图谱查询性能
    print(f"\n测试知识图谱查询性能...")
    search_queries = ["Entity", "is_a", "part", "tool", "project"]
    total_search_time = 0
    for query in search_queries:
        start = time.time()
        try:
            results = kg.search_entities(query, top_k=10)
            elapsed = time.time() - start
            total_search_time += elapsed
            print(f"  查询 '{query}': {len(results)} 个结果，耗时 {elapsed*1000:.2f}ms")
        except Exception as e:
            print(f"  ❌ 查询失败 '{query}': {str(e)}")
    
    avg_search_time = total_search_time / len(search_queries) * 1000
    print(f"\n平均查询耗时: {avg_search_time:.2f}ms")
    
    return kg, node_count, edge_count


def test_2_mixed_operations_stress():
    """测试2：混合操作压力测试 - 知识图谱+向量存储同时使用"""
    print("\n" + "="*90)
    print("测试2：混合操作压力测试 - 知识图谱+向量存储并发")
    print("="*90)
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    memory = AgentMemory(config=config)
    
    num_threads = 15
    operations_per_thread = 300
    total_ops = num_threads * operations_per_thread
    
    print(f"\n配置：{num_threads} 线程，{operations_per_thread} 操作/线程，共 {total_ops} 操作")
    
    stats = {
        "writes": 0,
        "reads": 0,
        "kg_entity_adds": 0,
        "kg_relation_adds": 0,
        "searches": 0,
        "errors": 0,
    }
    lock = threading.Lock()
    all_record_ids = []
    
    def worker(worker_id):
        local_writes = 0
        local_reads = 0
        local_kg_entities = 0
        local_kg_relations = 0
        local_searches = 0
        local_errors = 0
        local_ids = []
        
        for i in range(operations_per_thread):
            try:
                choice = random.random()
                
                if choice < 0.35:
                    # 写入记忆
                    content = generate_test_content("mixed", worker_id * 1000 + i)
                    record_id = memory.remember(
                        content=content,
                        memory_type=random.choice(["fact", "semantic", "episodic"]),
                        category=random.choice(["knowledge", "project", "idea", "reference"]),
                        importance=random.random()
                    )
                    local_ids.append(record_id)
                    local_writes += 1
                
                elif choice < 0.55:
                    # 知识图谱添加实体
                    entity_name = f"Worker{worker_id}_Entity{i}"
                    try:
                        entity = Entity(
                            name=entity_name,
                            entity_type=random.choice(["concept", "tool", "project"]),
                            description=f"实体描述信息 - 线程{worker_id}，操作{i}",
                            properties={"worker_id": worker_id, "operation": i}
                        )
                        memory.add_entity(entity)
                        local_kg_entities += 1
                    except Exception:
                        # 尝试直接访问 kg
                        if hasattr(memory, 'knowledge_graph'):
                            memory.knowledge_graph.add_entity(Entity(
                                name=entity_name,
                                entity_type="concept"
                            ))
                            local_kg_entities += 1
                
                elif choice < 0.7:
                    # 搜索
                    query = random.choice(["测试", "数据", "知识", "project", "tool", "混合"])
                    memory.recall(query, top_k=random.randint(2, 8))
                    local_searches += 1
                
                else:
                    # 读取
                    with lock:
                        if all_record_ids:
                            random_id = random.choice(all_record_ids)
                            try:
                                memory.long_term.get(random_id)
                                local_reads += 1
                            except Exception:
                                pass
                
            except Exception as e:
                local_errors += 1
                with lock:
                    if stats["errors"] < 20:
                        print(f"  线程{worker_id} 错误: {str(e)[:60]}")
            
            if (i+1) % 100 == 0 and worker_id == 0:
                with lock:
                    print(f"  进度：线程0已完成 {i+1}/{operations_per_thread} 操作")
        
        # 更新全局统计
        with lock:
            stats["writes"] += local_writes
            stats["reads"] += local_reads
            stats["kg_entity_adds"] += local_kg_entities
            stats["kg_relation_adds"] += local_kg_relations
            stats["searches"] += local_searches
            stats["errors"] += local_errors
            all_record_ids.extend(local_ids)
    
    # 执行测试
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        
        for future in as_completed(futures):
            future.result()
    
    total_time = time.time() - start_time
    
    # 结果汇总
    print(f"\n混合操作测试结果:")
    print(f"  总耗时: {total_time:.2f} 秒")
    print(f"  总操作数: {total_ops}")
    print(f"  写入: {stats['writes']}")
    print(f"  读取: {stats['reads']}")
    print(f"  知识图谱实体添加: {stats['kg_entity_adds']}")
    print(f"  搜索: {stats['searches']}")
    print(f"  错误数: {stats['errors']}")
    print(f"  吞吐率: {total_ops/total_time:.2f} 操作/秒")
    
    return memory, stats


def test_3_extreme_memory_stress():
    """测试3：极端内存压力测试 - 大数量+大内容"""
    print("\n" + "="*90)
    print("测试3：极端内存压力测试 - 大数量+大内容")
    print("="*90)
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    memory = AgentMemory(config=config)
    
    num_large_records = 50
    num_normal_records = 1000
    
    print(f"\n目标：写入 {num_normal_records} 个普通记录 + {num_large_records} 个超大记录")
    
    written_ids = []
    errors = 0
    
    # 写入普通记录
    print(f"\n写入 {num_normal_records} 个普通记录...")
    for i in range(num_normal_records):
        try:
            content = generate_test_content("normal", i)
            record_id = memory.remember(
                content=content,
                memory_type="semantic",
                category="test_batch",
                importance=random.random()
            )
            written_ids.append(record_id)
            
            if (i+1) % 200 == 0:
                print(f"  已完成 {i+1}/{num_normal_records}")
        except Exception as e:
            errors += 1
            if errors < 10:
                print(f"  ❌ 错误{i}: {str(e)}")
    
    # 写入超大记录
    print(f"\n写入 {num_large_records} 个超大记录...")
    for i in range(num_large_records):
        try:
            large_content = "超大数据块：" + "".join([generate_test_content("large", k) * 20 for k in range(5)])
            record_id = memory.remember(
                content=large_content,
                memory_type="document",
                category="large_content",
                importance=0.9,
                tags=["large", "stress", "test"]
            )
            written_ids.append(record_id)
            print(f"  已完成 {i+1}/{num_large_records} 个超大记录")
        except Exception as e:
            errors += 1
            if errors < 20:
                print(f"  ❌ 错误{i}: {str(e)[:80]}")
    
    # 最终验证
    print(f"\n最终验证统计:")
    memory_stats = memory.get_stats()
    lt_count = memory_stats.get('long_term', {}).get('total_memories', 0)
    
    print(f"  系统报告记录数: {lt_count}")
    print(f"  成功写入数: {len(written_ids)}")
    print(f"  错误数: {errors}")
    
    return memory, len(written_ids), errors


def main():
    """主测试函数"""
    print("\n" + "="*90)
    print("Agent Memory System - 超大规模复杂场景压力测试（慢工出细活）")
    print("="*90)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = {}
    
    try:
        # 测试1
        test1_result = test_1_extreme_knowledge_graph()
        test_results['test1'] = {
            'success': True,
            'entities': test1_result[1],
            'relations': test1_result[2],
        }
    except Exception as e:
        print(f"\n❌ 测试1异常: {str(e)}")
        import traceback
        traceback.print_exc()
        test_results['test1'] = {'success': False, 'error': str(e)}
    
    try:
        # 测试2
        test2_result = test_2_mixed_operations_stress()
        test_results['test2'] = {
            'success': True,
            'stats': test2_result[1],
        }
    except Exception as e:
        print(f"\n❌ 测试2异常: {str(e)}")
        import traceback
        traceback.print_exc()
        test_results['test2'] = {'success': False, 'error': str(e)}
    
    try:
        # 测试3
        test3_result = test_3_extreme_memory_stress()
        test_results['test3'] = {
            'success': True,
            'written': test3_result[1],
            'errors': test3_result[2],
        }
    except Exception as e:
        print(f"\n❌ 测试3异常: {str(e)}")
        import traceback
        traceback.print_exc()
        test_results['test3'] = {'success': False, 'error': str(e)}
    
    # 最终总结
    print("\n" + "="*90)
    print("超大规模复杂场景测试 - 最终总结")
    print("="*90)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results.values() if r.get('success', False))
    
    print(f"\n总测试数: {total_tests}")
    print(f"通过数: {passed_tests}/{total_tests}")
    
    for name, result in test_results.items():
        status = "✅ 通过" if result.get('success') else "❌ 失败"
        print(f"\n{name}: {status}")
        if not result.get('success') and 'error' in result:
            print(f"  错误: {result['error']}")
        else:
            for k, v in result.items():
                if k != 'success':
                    print(f"  {k}: {v}")
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*90)
    
    return test_results


if __name__ == "__main__":
    main()
