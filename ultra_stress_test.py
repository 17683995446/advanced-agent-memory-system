#!/usr/bin/env python3
"""
Agent Memory System - 超大规模压力测试
测试系统在极端负载下的表现
"""

import sys
import time
import threading
import random
import string
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

issues_found = []
performance_metrics = defaultdict(list)


def record_issue(severity, category, description, expected, actual):
    """记录发现的问题"""
    issues_found.append({
        "severity": severity,
        "category": category,
        "description": description,
        "expected": expected,
        "actual": actual,
    })
    icon = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
    print(f"  {icon} [{severity.upper()}] {category}: {description}")
    print(f"     期望: {expected}")
    print(f"     实际: {actual}")


def create_test_memory():
    """创建测试用的 AgentMemory 实例"""
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    return AgentMemory(config=config)


# ============================================================
# 测试1: 超大规模数据插入（10000条记忆）
# ============================================================
def test_ultra_large_scale_insert():
    """测试插入10000条记忆的性能和稳定性"""
    print("\n" + "="*70)
    print("🧪 1. 超大规模数据插入测试（10000条记忆）")
    print("="*70)
    
    memory = create_test_memory()
    
    # 生成10000条测试数据
    print(f"  准备生成10000条测试数据...")
    test_data = []
    for i in range(10000):
        content = f"测试记忆{i} - {''.join(random.choices(string.ascii_letters, k=50))}"
        test_data.append({
            "content": content,
            "memory_type": random.choice(["fact", "semantic", "episodic"]),
            "category": random.choice(["tech", "science", "art", "business"]),
            "importance": random.uniform(0.1, 0.9),
            "tags": [f"tag{i%10}", f"category{i%5}"]
        })
    
    # 批量插入测试
    print(f"  开始批量插入...")
    start_time = time.time()
    
    success_count = 0
    error_count = 0
    errors = []
    
    for i, data in enumerate(test_data):
        try:
            memory.remember(**data)
            success_count += 1
            if (i + 1) % 1000 == 0:
                elapsed = time.time() - start_time
                print(f"    已插入 {i+1} 条, 耗时 {elapsed:.2f}s, 速率 {success_count/elapsed:.1f}/s")
        except Exception as e:
            error_count += 1
            errors.append(str(e))
            if error_count <= 3:
                print(f"    ⚠️ 第{i}条记录插入失败: {e}")
    
    total_time = time.time() - start_time
    
    print(f"\n  📊 插入统计:")
    print(f"     总数: {len(test_data)}")
    print(f"     成功: {success_count}")
    print(f"     失败: {error_count}")
    print(f"     总耗时: {total_time:.2f}s")
    print(f"     平均速率: {success_count/total_time:.1f}条/秒")
    
    performance_metrics["insert_speed"].append(success_count/total_time)
    
    if error_count > 0:
        record_issue("medium", "大规模插入", f"10000条插入中有{error_count}条失败", "0失败", f"{error_count}失败")
    
    # 查询测试
    print(f"\n  测试查询性能...")
    query_start = time.time()
    results = memory.recall("测试记忆", top_k=10)
    query_time = time.time() - query_start
    
    print(f"     查询耗时: {query_time:.4f}s")
    print(f"     返回结果: {len(results)}条")
    
    if query_time > 1.0:
        record_issue("medium", "查询性能", f"10000条数据查询耗时{query_time:.2f}s", "<1s", f"{query_time:.2f}s")
    
    performance_metrics["query_speed"].append(query_time)
    
    # 统计验证
    stats = memory.get_stats()
    total_memories = stats["long_term"]["total_memories"]
    print(f"\n  统计验证: 系统报告{total_memories}条记忆")
    
    if abs(total_memories - success_count) > 10:
        record_issue("high", "数据一致性", f"插入成功{success_count}条但统计显示{total_memories}条", f"≈{success_count}", total_memories)
    
    memory.close()
    return True


# ============================================================
# 测试2: 高并发写入（50线程同时写入）
# ============================================================
def test_high_concurrency():
    """测试50个线程同时写入"""
    print("\n" + "="*70)
    print("🧪 2. 高并发写入测试（50线程 × 200条 = 10000条）")
    print("="*70)
    
    memory = create_test_memory()
    
    num_threads = 50
    items_per_thread = 200
    total_items = num_threads * items_per_thread
    
    print(f"  配置: {num_threads}线程 × {items_per_thread}条/线程 = {total_items}条")
    
    errors = []
    success_count = 0
    lock = threading.Lock()
    
    def worker(thread_id):
        nonlocal success_count
        local_success = 0
        local_errors = []
        
        for i in range(items_per_thread):
            try:
                content = f"并发测试[线程{thread_id}][{i}] - 数据内容"
                memory.remember(
                    content=content,
                    memory_type="fact",
                    category="concurrency",
                    importance=0.5,
                    source=f"thread-{thread_id}"
                )
                local_success += 1
            except Exception as e:
                local_errors.append(str(e))
        
        with lock:
            success_count += local_success
            errors.extend(local_errors)
        
        return local_success, len(local_errors)
    
    start_time = time.time()
    
    # 使用线程池执行
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 10 == 0:
                elapsed = time.time() - start_time
                print(f"    已完成 {completed}/{num_threads} 线程, 耗时 {elapsed:.2f}s")
    
    total_time = time.time() - start_time
    
    print(f"\n  📊 并发测试统计:")
    print(f"     总耗时: {total_time:.2f}s")
    print(f"     成功写入: {success_count}")
    print(f"     失败次数: {len(errors)}")
    print(f"     吞吐量: {success_count/total_time:.1f}条/秒")
    
    performance_metrics["concurrent_throughput"].append(success_count/total_time)
    
    if len(errors) > 0:
        unique_errors = list(set(errors[:5]))  # 显示前5个不同错误
        print(f"     错误示例: {unique_errors[0] if unique_errors else 'N/A'}")
        record_issue("high", "并发安全", f"并发写入中有{len(errors)}次失败", "0失败", f"{len(errors)}失败")
    
    # 验证数据一致性
    stats = memory.get_stats()
    actual_count = stats["long_term"]["total_memories"]
    print(f"\n  数据验证: 预期{success_count}条, 实际{actual_count}条")
    
    if abs(actual_count - success_count) > 5:
        record_issue("medium", "并发一致性", f"并发写入{success_count}条但系统记录{actual_count}条", success_count, actual_count)
    
    memory.close()
    return True


# ============================================================
# 测试3: 复杂知识图谱构建
# ============================================================
def test_complex_knowledge_graph():
    """测试构建包含100+实体的复杂知识图谱"""
    print("\n" + "="*70)
    print("🧪 3. 复杂知识图谱测试（100+实体）")
    print("="*70)
    
    memory = create_test_memory()
    
    # 创建实体网络
    tech_stack = [
        "Python", "JavaScript", "TypeScript", "Go", "Rust",
        "React", "Vue", "Angular", "Django", "Flask",
        "FastAPI", "Node.js", "Express", "Spring", "SpringBoot",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Git", "GitHub", "GitLab", "Jenkins", "CircleCI"
    ]
    
    concepts = [
        "面向对象编程", "函数式编程", "响应式编程", "并发编程", "分布式系统",
        "微服务架构", "单体架构", "事件驱动架构", "CQRS", "DDD",
        "REST API", "GraphQL", "WebSocket", "gRPC", "MQTT",
        "单元测试", "集成测试", "端到端测试", "性能测试", "安全测试"
    ]
    
    print(f"  准备创建 {len(tech_stack) + len(concepts)} 个实体...")
    
    # 创建实体间关系
    relations = []
    for i, tech1 in enumerate(tech_stack):
        for tech2 in tech_stack[i+1:i+4]:  # 每个技术与其他2-3个技术建立关系
            relations.append(f"{tech1}经常与{tech2}一起使用")
        
        for concept in concepts[:3]:  # 每个技术与3个概念建立关系
            relations.append(f"{tech1}是实现{concept}的重要工具")
    
    print(f"  创建 {len(relations)} 条关系陈述...")
    
    start_time = time.time()
    
    # 批量添加记忆
    success_count = 0
    for i, relation in enumerate(relations):
        try:
            memory.remember(
                content=relation,
                memory_type="fact",
                category="knowledge-graph",
                importance=0.7,
                source="kg-generator"
            )
            success_count += 1
            
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                print(f"    已处理 {i+1}/{len(relations)} 条, 耗时 {elapsed:.2f}s")
        except Exception as e:
            if success_count < 3:
                print(f"    ⚠️ 第{i}条关系创建失败: {e}")
    
    total_time = time.time() - start_time
    
    print(f"\n  📊 知识图谱构建统计:")
    print(f"     关系陈述: {len(relations)}")
    print(f"     成功处理: {success_count}")
    print(f"     耗时: {total_time:.2f}s")
    
    # 检查知识图谱状态
    stats = memory.get_stats()
    kg = stats.get("knowledge_graph", {})
    
    print(f"\n  📈 知识图谱状态:")
    print(f"     实体数量: {kg.get('entity_count', 0)}")
    print(f"     关系数量: {kg.get('relation_count', 0)}")
    print(f"     密度: {kg.get('density', 0):.4f}")
    print(f"     连接状态: {'是' if kg.get('is_connected', False) else '否'}")
    
    entity_count = kg.get("entity_count", 0)
    relation_count = kg.get("relation_count", 0)
    
    # 实体搜索测试
    print(f"\n  测试实体搜索...")
    search_results = memory.search_entities("Python", top_k=10)
    print(f"     搜索'Python': 返回 {len(search_results)} 条相关实体")
    
    # 查找相关实体
    if search_results:
        # search_entities 返回 [(Entity, score), ...] 元组列表
        top_entity_obj, top_score = search_results[0]
        top_entity = getattr(top_entity_obj, 'name', str(top_entity_obj))
        print(f"     Top实体: {top_entity}, 得分: {top_score}")
        
        related = memory.find_related(top_entity, top_k=5)  # 使用 top_k 而不是 max_results
        print(f"     查找'{top_entity}'的相关实体: 返回 {len(related)} 条")
    
    # 验证知识图谱质量
    if entity_count < 50:
        record_issue("medium", "知识图谱规模", f"创建{success_count}条关系但只提取到{entity_count}个实体", ">50实体", f"{entity_count}实体")
    
    if relation_count == 0:
        record_issue("high", "知识图谱构建", "知识图谱关系数为0，可能未正确构建", ">0", "0")
    
    memory.close()
    return True


# ============================================================
# 测试4: 持续压力测试（模拟长时间运行）
# ============================================================
def test_sustained_pressure():
    """模拟持续运行，测试内存泄漏和资源管理"""
    print("\n" + "="*70)
    print("🧪 4. 持续压力测试（1000次循环操作）")
    print("="*70)
    
    memory = create_test_memory()
    
    print(f"  开始持续压力测试（1000次循环）...")
    
    # 预填充一些数据
    for i in range(100):
        memory.remember(f"预填充数据{i}", memory_type="fact", category="prefill")
    
    print(f"  初始数据: {memory.count_memories()} 条")
    
    start_time = time.time()
    operations = {
        "remember": 0,
        "recall": 0,
        "update": 0,
        "delete": 0,
        "errors": 0
    }
    
    error_examples = []
    
    # 执行1000次随机操作
    for i in range(1000):
        op = random.choice(["remember", "recall", "update", "delete"])
        
        try:
            if op == "remember":
                memory.remember(
                    content=f"循环测试{i}",
                    memory_type="fact",
                    category="stress",
                    importance=0.5
                )
                operations["remember"] += 1
                
            elif op == "recall":
                results = memory.recall("测试", top_k=5)
                operations["recall"] += 1
                
            elif op == "update":
                # 尝试更新一个存在的记忆
                count = memory.count_memories()
                if count > 0:
                    # 获取一个记忆ID并更新
                    all_mem = memory.long_term.get_all(limit=1)
                    if all_mem:
                        old_id = all_mem[0].id
                        memory.long_term.update(old_id, content=f"更新后的内容{i}")
                        operations["update"] += 1
                        
            elif op == "delete":
                # 随机删除
                all_mem = memory.long_term.get_all(limit=10)
                if all_mem:
                    old_id = random.choice(all_mem).id
                    memory.forget_memory(old_id)  # 使用 forget_memory 而不是 forget
                    operations["delete"] += 1
                    
        except Exception as e:
            operations["errors"] += 1
            if len(error_examples) < 3:
                error_examples.append(f"{op}: {str(e)[:50]}")
        
        # 每200次报告一次进度
        if (i + 1) % 200 == 0:
            elapsed = time.time() - start_time
            current_count = memory.count_memories()
            print(f"    循环 {i+1}/1000:")
            print(f"      耗时: {elapsed:.2f}s")
            print(f"      当前记忆数: {current_count}")
            print(f"      操作统计: {operations}")
    
    total_time = time.time() - start_time
    
    print(f"\n  📊 持续压力测试统计:")
    print(f"     总耗时: {total_time:.2f}s")
    print(f"     总操作: {sum(operations.values())}")
    print(f"     操作分布: remember={operations['remember']}, recall={operations['recall']}, update={operations['update']}, delete={operations['delete']}")
    print(f"     错误次数: {operations['errors']}")
    
    if error_examples:
        print(f"     错误示例: {error_examples[0]}")
    
    # 最终状态检查
    final_count = memory.count_memories()
    print(f"\n  📈 最终状态:")
    print(f"     最终记忆数: {final_count}")
    print(f"     初始记忆数: 100")
    print(f"     净变化: {final_count - 100:+d}")
    
    performance_metrics["operations_per_second"].append(sum(operations.values()) / total_time)
    
    if operations["errors"] > 50:
        record_issue("high", "持续稳定性", f"1000次操作中有{operations['errors']}次失败", "<10次失败", f"{operations['errors']}失败")
    
    if final_count < 50:
        record_issue("medium", "数据丢失", f"持续操作后记忆数从100降到{final_count}", ">80", final_count)
    
    memory.close()
    return True


# ============================================================
# 测试5: 边界条件极限测试
# ============================================================
def test_extreme_edge_cases():
    """测试极端边界条件"""
    print("\n" + "="*70)
    print("🧪 5. 极端边界条件测试")
    print("="*70)
    
    memory = create_test_memory()
    
    # 测试1: 超长内容（1MB文本）
    print(f"  测试1: 超长内容（1MB）...")
    try:
        long_content = "测试内容 " * 25000  # ~250KB
        mid = memory.remember(long_content, memory_type="fact", importance=0.5)
        print(f"     ✅ 成功存储超长内容（{len(long_content)}字符）")
        
        # 验证能检索到
        results = memory.recall("测试内容", top_k=1)
        if results:
            print(f"     ✅ 成功检索超长内容")
        else:
            record_issue("medium", "超长内容检索", "存储了超长内容但无法检索", "能检索", "无法检索")
    except Exception as e:
        record_issue("medium", "超长内容", f"无法存储超长内容: {str(e)[:50]}", "正常存储", str(e)[:50])
    
    # 测试2: 大量标签（1000个标签）
    print(f"  测试2: 大量标签（1000个）...")
    try:
        many_tags = [f"tag{i}" for i in range(1000)]
        mid = memory.remember("测试多标签", memory_type="fact", importance=0.5, tags=many_tags)
        print(f"     ✅ 成功存储1000个标签")
        
        # 验证标签数量
        record = memory.long_term.get(mid)
        if record and len(record.tags) > 900:
            print(f"     ✅ 标签数量正确: {len(record.tags)}")
        else:
            print(f"     ⚠️ 标签数量异常: {len(record.tags) if record else 'N/A'}")
    except Exception as e:
        record_issue("low", "大量标签", f"无法存储1000个标签: {str(e)[:50]}", "正常存储", str(e)[:50])
    
    # 测试3: 极端importance值
    print(f"  测试3: 极端importance值...")
    extreme_values = [0.0, 1.0, -0.1, 1.5, float('inf'), -float('inf')]
    for val in extreme_values:
        try:
            mid = memory.remember(f"测试importance={val}", memory_type="fact", importance=val)
            print(f"     ⚠️ importance={val} 被接受（id={mid[:8]}）")
        except (ValueError, TypeError) as e:
            print(f"     ✅ importance={val} 被正确拒绝")
        except Exception as e:
            print(f"     ⚠️ importance={val} 抛出意外异常: {str(e)[:30]}")
    
    # 测试4: 特殊字符和编码
    print(f"  测试4: 特殊字符和编码...")
    special_contents = [
        "中文测试 🎉",
        "emoji 💻 📱 🔧",
        "特殊符号 <>&\'\"\\",
        "控制字符 \t\n\r\0",
        "unicode: 日本語 한국어",
        "阿拉伯语: مرحبا",
        "俄语: Привет",
        "混合: 中文English123🎯"
    ]
    
    for content in special_contents:
        try:
            mid = memory.remember(content, memory_type="fact", importance=0.5)
            results = memory.recall(content[:5], top_k=1)
            if results:
                print(f"     ✅ {content[:20]}... - 存储和检索正常")
            else:
                print(f"     ⚠️ {content[:20]}... - 存储成功但检索失败")
        except Exception as e:
            record_issue("medium", "特殊字符", f"'{content[:20]}...' 处理失败: {str(e)[:30]}", "正常处理", str(e)[:30])
    
    memory.close()
    return True


# ============================================================
# 主函数
# ============================================================
def main():
    print("\n" + "="*70)
    print("🚀 Agent Memory System - 超大规模压力测试")
    print("="*70)
    
    tests = [
        ("超大规模数据插入", test_ultra_large_scale_insert),
        ("高并发写入", test_high_concurrency),
        ("复杂知识图谱", test_complex_knowledge_graph),
        ("持续压力测试", test_sustained_pressure),
        ("极端边界条件", test_extreme_edge_cases),
    ]
    
    passed = 0
    failed = 0
    
    for name, func in tests:
        try:
            func()
            passed += 1
            print(f"\n  ✅ {name} - 通过")
        except Exception as e:
            print(f"\n  ❌ {name} - 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # 汇总报告
    print("\n" + "="*70)
    print("📊 超大规模测试报告")
    print("="*70)
    
    high = [i for i in issues_found if i["severity"] == "high"]
    medium = [i for i in issues_found if i["severity"] == "medium"]
    low = [i for i in issues_found if i["severity"] == "low"]
    
    print(f"\n  测试套件: {passed}/{passed+failed} 通过")
    print(f"\n  发现问题总计: {len(issues_found)}")
    print(f"  🔴 高严重度: {len(high)}")
    print(f"  🟡 中严重度: {len(medium)}")
    print(f"  🟢 低严重度: {len(low)}")
    
    if high:
        print(f"\n  高严重度问题详情:")
        for i, issue in enumerate(high, 1):
            print(f"    {i}. [{issue['category']}] {issue['description']}")
            print(f"       期望: {issue['expected']}")
            print(f"       实际: {issue['actual']}")
    
    if medium:
        print(f"\n  中严重度问题详情:")
        for i, issue in enumerate(medium, 1):
            print(f"    {i}. [{issue['category']}] {issue['description']}")
    
    # 性能指标汇总
    if performance_metrics:
        print(f"\n  性能指标:")
        for metric, values in performance_metrics.items():
            avg = sum(values) / len(values) if values else 0
            print(f"    {metric}: 平均 {avg:.2f}")
    
    return len(issues_found)


if __name__ == "__main__":
    count = main()
    print(f"\n  共发现 {count} 个问题")
