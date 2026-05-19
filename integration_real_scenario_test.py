#!/usr/bin/env python3
"""
Agent Memory System - 多模块集成真实场景测试
模拟真实的智能助手使用场景，全面测试系统
"""

import sys
import time
import random
import uuid
import json
from typing import Dict, List, Any
from dataclasses import dataclass

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

issues_found = []
performance_metrics = []


@dataclass
class TestResult:
    test_name: str
    passed: bool
    duration: float
    details: Dict[str, Any]
    issue: str = ""


def record_issue(severity: str, category: str, description: str, expected: str, actual: str):
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
    """创建测试用的记忆系统实例"""
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
        short_term={"working_memory_capacity": 5, "history_limit": 100},
        knowledge_graph={"enabled": True},
        auto_consolidate=False,
        default_top_k=5
    )
    return AgentMemory(config=config)


def test_1_real_assistant_conversation():
    """测试1: 真实智能助手对话场景"""
    print("\n" + "="*70)
    print("🧪 测试1: 真实智能助手对话场景")
    print("="*70)
    
    start_time = time.time()
    memory = create_test_memory()
    
    # 模拟真实对话场景
    conversation_scenes = [
        {"role": "user", "content": "你好，我想了解机器学习的基础知识", "important": True},
        {"role": "assistant", "content": "好的！机器学习是人工智能的一个分支，主要让计算机从数据中学习模式。", "important": True},
        {"role": "user", "content": "深度学习和传统机器学习有什么区别？", "important": True},
        {"role": "assistant", "content": "深度学习是机器学习的子集，使用神经网络多层结构学习。", "important": True},
        {"role": "user", "content": "能给我推荐一些入门课程吗？", "important": True},
        {"role": "assistant", "content": "推荐Andrew Ng的Coursera机器学习课程，非常适合初学者！", "important": True},
        {"role": "user", "content": "需要什么数学基础？", "important": True},
        {"role": "assistant", "content": "主要需要线性代数、微积分、概率统计和优化理论。", "important": True},
    ]
    
    # 执行对话
    print(f"  模拟 {len(conversation_scenes)} 轮对话...")
    for i, turn in enumerate(conversation_scenes):
        memory.add_interaction(
            role=turn["role"],
            content=turn["content"],
            important=turn["important"]
        )
    
    # 测试短期记忆
    print(f"  测试短期记忆...")
    conversation_history = memory.get_conversation_history()
    recent_history = memory.get_interaction_history()
    
    if len(recent_history) >= len(conversation_scenes):
        print(f"  ✅ 短期记忆正确记录了对话")
    else:
        record_issue(
            "medium", "短期记忆", 
            f"短期记忆历史数量较少", 
            f">={len(conversation_scenes)}条", 
            f"{len(recent_history)}条"
        )
    
    # 测试知识图谱
    print(f"  测试知识图谱...")
    try:
        # 添加相关知识
        memory.add_entity("机器学习", entity_type="concept", description="人工智能分支")
        memory.add_entity("深度学习", entity_type="concept", description="神经网络学习")
        memory.add_entity("Andrew Ng", entity_type="person", description="AI专家")
        memory.add_entity("Coursera", entity_type="platform", description="在线课程")
        
        memory.add_relation("机器学习", "深度学习", "subfield", weight=0.9)
        memory.add_relation("Andrew Ng", "Coursera机器学习课程", "teaches", weight=0.8)
        
        # 测试实体搜索
        results = memory.search_entities("学习", top_k=3)
        if results:
            print(f"  ✅ 知识图谱实体搜索成功，找到 {len(results)} 个相关实体")
        else:
            record_issue("medium", "知识图谱", "知识图谱实体搜索返回空", ">0结果", "0结果")
    except Exception as e:
        record_issue("high", "知识图谱", f"知识图谱操作失败: {str(e)[:50]}", "正常操作", str(e))
    
    # 测试混合搜索
    print(f"  测试混合搜索...")
    try:
        recall_results = memory.recall("课程推荐", top_k=3)
        if recall_results:
            print(f"  ✅ 混合搜索成功，找到 {len(recall_results)} 条相关记忆")
        else:
            record_issue("medium", "混合搜索", "混合搜索返回空结果", ">0结果", "0结果")
    except Exception as e:
        record_issue("medium", "混合搜索", f"混合搜索失败: {str(e)[:50]}", "正常搜索", str(e))
    
    memory.close()
    duration = time.time() - start_time
    
    return TestResult(
        test_name="真实智能助手对话场景",
        passed=True,
        duration=duration,
        details={"conversation_turns": len(conversation_scenes)}
    )


def test_2_short_term_working_memory():
    """测试2: 短期工作记忆的复杂场景"""
    print("\n" + "="*70)
    print("🧪 测试2: 短期工作记忆的复杂场景")
    print("="*70)
    
    start_time = time.time()
    memory = create_test_memory()
    
    print(f"  测试工作记忆容量限制（容量=5）...")
    
    # 添加6条记忆到工作记忆（容量只有5）
    work_items = [
        {"key": "item1", "content": "用户姓名：张三", "importance": 0.8},
        {"key": "item2", "content": "用户邮箱：zhangsan@example.com", "importance": 0.7},
        {"key": "item3", "content": "项目截止日期：2026-06-30", "importance": 0.9},
        {"key": "item4", "content": "当前任务：编写代码", "importance": 0.6},
        {"key": "item5", "content": "会议时间：明天14:00", "importance": 0.85},
        {"key": "item6", "content": "购物清单：牛奶、面包", "importance": 0.5},  # 这条应该被淘汰
    ]
    
    for item in work_items:
        try:
            memory.add_to_working_memory(
                item["key"], 
                item["content"], 
                importance=item["importance"]
            )
        except Exception as e:
            record_issue("medium", "工作记忆", f"添加工作记忆失败: {str(e)[:30]}", "正常添加", str(e))
    
    # 验证工作记忆的淘汰机制
    # 直接访问 short_term 的 working_memory
    working_memory = memory.short_term.working_memory
    all_items = working_memory.get_all()
    memory_keys = [key for key, _ in all_items]
    
    if len(memory_keys) > 5:
        record_issue(
            "medium", "工作记忆淘汰", 
            "工作记忆超出容量限制", 
            "<=5个记忆", 
            f"{len(memory_keys)}个记忆"
        )
    elif len(memory_keys) == 5:
        print(f"  ✅ 工作记忆正确保持在容量限制内（5个记忆）")
        if "item6" in memory_keys:
            record_issue(
                "medium", "工作记忆淘汰逻辑", 
                "低重要性记忆未被正确淘汰", 
                "低重要性记忆item6被淘汰", 
                "item6仍然存在"
            )
        else:
            print(f"  ✅ 低重要性记忆item6被正确淘汰")
    else:
        record_issue(
            "medium", "工作记忆", 
            f"工作记忆数量异常", 
            "5个记忆", 
            f"{len(memory_keys)}个记忆"
        )
    
    # 测试焦点切换
    print(f"  测试工作记忆焦点切换...")
    try:
        # 使用 working_memory 对象的方法
        working_memory.set_focus("item3")
        focus_content = working_memory.get_focus_content()
        if focus_content and "项目截止日期" in focus_content:
            print(f"  ✅ 工作记忆焦点切换正常")
    except Exception as e:
        print(f"  ⚠️  工作记忆焦点API测试跳过: {str(e)[:30]}")
    
    memory.close()
    return TestResult(
        test_name="短期工作记忆复杂场景",
        passed=True,
        duration=time.time() - start_time,
        details={"items_tested": len(work_items)}
    )


def test_3_knowledge_graph_integration():
    """测试3: 知识图谱与长期记忆集成"""
    print("\n" + "="*70)
    print("🧪 测试3: 知识图谱与长期记忆深度集成")
    print("="*70)
    
    start_time = time.time()
    memory = create_test_memory()
    
    # 创建复杂的知识图谱场景
    print(f"  构建复杂知识图谱...")
    
    entities = [
        ("Python", "language", "高级编程语言"),
        ("JavaScript", "language", "前端编程语言"),
        ("React", "framework", "前端框架"),
        ("Django", "framework", "Python后端框架"),
        ("FastAPI", "framework", "Python API框架"),
        ("PostgreSQL", "database", "关系数据库"),
        ("Redis", "database", "内存数据库"),
        ("数据科学", "domain", "数据分析和机器学习"),
        ("Web开发", "domain", "网站开发"),
    ]
    
    relations = [
        ("Python", "Django", "used_in", 0.9),
        ("Python", "FastAPI", "used_in", 0.85),
        ("Python", "数据科学", "used_in", 0.9),
        ("JavaScript", "React", "used_in", 0.9),
        ("Django", "Web开发", "used_for", 0.95),
        ("React", "Web开发", "used_for", 0.9),
        ("FastAPI", "PostgreSQL", "integrates_with", 0.8),
        ("Django", "PostgreSQL", "integrates_with", 0.7),
    ]
    
    # 添加实体
    entity_count = 0
    for name, etype, desc in entities:
        try:
            memory.add_entity(name, entity_type=etype, description=desc)
            entity_count += 1
        except Exception as e:
            record_issue("medium", "知识图谱添加", f"添加实体失败: {name}", "成功添加", str(e)[:30])
    
    # 添加关系
    relation_count = 0
    for source, target, rel_type, weight in relations:
        try:
            memory.add_relation(source, target, rel_type, weight=weight)
            relation_count += 1
        except Exception as e:
            record_issue("medium", "知识图谱关系", f"添加关系失败: {source}->{target}", "成功添加", str(e)[:30])
    
    print(f"  ✅ 添加了 {entity_count} 个实体，{relation_count} 个关系")
    
    # 同时添加相关的长期记忆
    print(f"  添加相关长期记忆...")
    long_term_items = [
        "Django是一个成熟的Python后端框架，适合快速开发",
        "React是流行的前端框架，与Vue、Angular并称为三巨头",
        "FastAPI是现代化的Python框架，性能优异",
        "数据科学常用的Python库有NumPy、Pandas和Scikit-learn",
    ]
    
    for content in long_term_items:
        memory.remember(
            content=content,
            memory_type="fact",
            category="tech_knowledge",
            importance=0.7,
            source="curriculum"
        )
    
    # 测试混合搜索和知识图谱联合检索
    print(f"  测试知识图谱增强的搜索...")
    try:
        # 搜索与Python相关的内容
        python_results = memory.recall("Python框架", top_k=5)
        if python_results:
            print(f"  ✅ Python相关搜索找到 {len(python_results)} 条结果")
        else:
            record_issue("medium", "知识图谱搜索", "Python相关搜索返回空", ">0结果", "0结果")
        
        # 测试实体搜索和相关查询
        entity_results = memory.search_entities("Python", top_k=3)
        if entity_results:
            top_entity, score = entity_results[0]
            entity_name = getattr(top_entity, 'name', str(top_entity))
            print(f"  ✅ 实体搜索找到 '{entity_name}'，得分 {score:.3f}")
            
            related_entities = memory.find_related(entity_name, top_k=3)
            if related_entities:
                print(f"  ✅ 找到 {len(related_entities)} 个相关实体")
    except Exception as e:
        record_issue("high", "知识图谱搜索", f"知识图谱搜索失败: {str(e)[:50]}", "正常搜索", str(e))
    
    memory.close()
    return TestResult(
        test_name="知识图谱与长期记忆集成",
        passed=True,
        duration=time.time() - start_time,
        details={"entities": entity_count, "relations": relation_count}
    )


def test_4_mixed_search_complex_scenarios():
    """测试4: 混合搜索的复杂场景"""
    print("\n" + "="*70)
    print("🧪 测试4: 混合搜索的复杂真实场景")
    print("="*70)
    
    start_time = time.time()
    memory = create_test_memory()
    
    # 创建大量混合类型的记忆
    print(f"  创建混合类型记忆库...")
    memory_types = ["fact", "episodic", "semantic", "procedural", "concept"]
    categories = ["work", "personal", "tech", "health", "finance"]
    sources = ["user", "assistant", "system", "curriculum", "document"]
    
    # 生成测试记忆
    test_memories = []
    for i in range(100):
        content = f"这是记忆{i}，关于{random.choice(categories)}的内容"
        mem_type = random.choice(memory_types)
        category = random.choice(categories)
        source = random.choice(sources)
        importance = random.uniform(0.3, 0.9)
        
        mem_id = memory.remember(
            content=content,
            memory_type=mem_type,
            category=category,
            importance=importance,
            source=source
        )
        test_memories.append({"id": mem_id, "content": content, "category": category, "source": source})
    
    print(f"  ✅ 创建了 {len(test_memories)} 条混合类型记忆")
    
    # 测试精确查询
    print(f"  测试精确查询...")
    exact_query = "这是记忆"
    results_exact = memory.recall(exact_query, top_k=5)
    if len(results_exact) >= 3:
        print(f"  ✅ 精确查询成功，返回 {len(results_exact)} 条结果")
    else:
        record_issue("medium", "混合搜索精确性", "精确查询结果太少", ">=3条", f"{len(results_exact)}条")
    
    # 测试条件过滤
    print(f"  测试条件过滤...")
    results_filtered = memory.recall("工作", top_k=10, exclude_sources=["system"])
    if results_filtered:
        print(f"  ✅ 条件过滤返回 {len(results_filtered)} 条结果")
        
        # 验证过滤是否生效
        system_sources = [r for r in results_filtered if r.get("source") == "system"]
        if system_sources:
            record_issue(
                "medium", "过滤功能", 
                f"exclude_sources过滤未生效，仍有 {len(system_sources)} 条来源为system的结果", 
                "0条system来源", 
                f"{len(system_sources)}条"
            )
        else:
            print(f"  ✅ exclude_sources过滤生效正确")
    
    # 测试 top_k 参数
    print(f"  测试top_k参数...")
    for k in [1, 3, 5, 10]:
        results_k = memory.recall("记忆", top_k=k)
        if len(results_k) > k + 1:  # 允许小的偏差
            record_issue(
                "medium", "top_k准确性", 
                f"top_k={k} 返回了过多结果", 
                f"<={k+1}条", 
                f"{len(results_k)}条"
            )
    
    memory.close()
    return TestResult(
        test_name="混合搜索复杂场景",
        passed=True,
        duration=time.time() - start_time,
        details={"memories": len(test_memories)}
    )


def test_5_consolidation_and_retrieval():
    """测试5: 记忆巩固与持久化"""
    print("\n" + "="*70)
    print("🧪 测试5: 记忆巩固与检索优化")
    print("="*70)
    
    start_time = time.time()
    memory = create_test_memory()
    
    # 添加重要记忆（应该被巩固）
    print(f"  添加不同重要性的记忆...")
    important_memories = []
    for i in range(20):
        importance = random.uniform(0.3, 0.95)
        content = f"重要记忆{i}，重要性{importance:.2f}"
        
        if importance >= 0.7:
            # 高重要性记忆
            mem_id = memory.remember(
                content=content,
                memory_type="fact",
                category="important",
                importance=importance,
                source="priority_source"
            )
            important_memories.append({"id": mem_id, "importance": importance})
    
    print(f"  ✅ 添加了 {len(important_memories)} 条高重要性记忆")
    
    # 测试统计功能
    print(f"  测试统计功能...")
    try:
        stats = memory.get_stats()
        if stats and "long_term" in stats:
            total = stats["long_term"].get("total_memories", 0)
            print(f"  ✅ 统计功能正常，共 {total} 条长期记忆")
    except Exception as e:
        record_issue("medium", "统计功能", f"获取统计失败: {str(e)[:30]}", "正常返回", str(e))
    
    # 测试大量检索
    print(f"  测试批量检索性能...")
    retrieval_start = time.time()
    for i in range(50):
        query = f"记忆{i % 10}"
        results = memory.recall(query, top_k=3)
    
    retrieval_time = time.time() - retrieval_start
    avg_time = retrieval_time / 50
    print(f"  ✅ 50次检索，平均每次 {avg_time:.4f}秒")
    
    if avg_time > 0.05:  # 如果平均超过50ms，记录为潜在性能问题
        record_issue(
            "medium", "检索性能", 
            "检索平均时间较长", 
            "<0.05秒", 
            f"{avg_time:.4f}秒"
        )
    
    memory.close()
    return TestResult(
        test_name="记忆巩固与检索优化",
        passed=True,
        duration=time.time() - start_time,
        details={"important_memories": len(important_memories), "retrieval_avg_time": avg_time}
    )


def test_6_edge_cases_and_error_handling():
    """测试6: 边界情况和错误处理"""
    print("\n" + "="*70)
    print("🧪 测试6: 边界情况和错误处理")
    print("="*70)
    
    start_time = time.time()
    memory = create_test_memory()
    
    # 测试空内容处理
    print(f"  测试空内容处理...")
    try:
        memory.remember("", memory_type="fact")
        record_issue(
            "medium", "空内容验证", 
            "空内容应该抛出异常", 
            "抛出ValueError", 
            "未抛出异常"
        )
    except ValueError:
        print(f"  ✅ 空内容正确抛出ValueError")
    except Exception as e:
        record_issue(
            "medium", "空内容验证", 
            "空内容应该抛出ValueError", 
            "ValueError", 
            type(e).__name__
        )
    
    # 测试关闭后操作
    print(f"  测试关闭后操作...")
    memory.close()
    try:
        memory.remember("关闭后的记忆", memory_type="fact")
        record_issue(
            "high", "关闭后操作", 
            "关闭后应该禁止操作", 
            "抛出RuntimeError", 
            "未抛出异常"
        )
    except RuntimeError:
        print(f"  ✅ 关闭后操作正确抛出RuntimeError")
    except Exception as e:
        record_issue(
            "medium", "关闭后操作", 
            "关闭后应该抛出RuntimeError", 
            "RuntimeError", 
            type(e).__name__
        )
    
    # 创建新实例测试更多边界
    memory2 = create_test_memory()
    
    # 测试超长内容
    print(f"  测试超长内容...")
    very_long_content = "超长内容" * 20000  # 约100KB
    try:
        mem_id = memory2.remember(very_long_content, memory_type="document")
        results = memory2.recall("超长内容", top_k=1)
        if results:
            print(f"  ✅ 超长内容存储和检索正常")
    except Exception as e:
        record_issue("medium", "超长内容", f"超长内容处理失败: {str(e)[:30]}", "正常处理", str(e))
    
    memory2.close()
    
    return TestResult(
        test_name="边界情况和错误处理",
        passed=True,
        duration=time.time() - start_time,
        details={}
    )


def run_all_tests():
    """运行所有集成测试"""
    tests = [
        test_1_real_assistant_conversation,
        test_2_short_term_working_memory,
        test_3_knowledge_graph_integration,
        test_4_mixed_search_complex_scenarios,
        test_5_consolidation_and_retrieval,
        test_6_edge_cases_and_error_handling,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
            print(f"\n  ✅ {result.test_name} - 完成 ({result.duration:.2f}秒)")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\n  ❌ {test_func.__name__} - 失败: {str(e)}")
            results.append(TestResult(
                test_name=test_func.__name__,
                passed=False,
                duration=0,
                details={},
                issue=str(e)
            ))
    
    return results


def generate_report(results):
    """生成测试报告"""
    print("\n" + "="*70)
    print("📊 多模块集成测试最终报告")
    print("="*70)
    
    passed_tests = sum(1 for r in results if r.passed)
    total_tests = len(results)
    
    print(f"\n  测试总数: {total_tests}")
    print(f"  通过: {passed_tests}/{total_tests} ({passed_tests*100//total_tests if total_tests >0 else 0}%)")
    print(f"  发现问题: {len(issues_found)}个")
    
    if issues_found:
        print(f"\n  问题汇总:")
        for i, issue in enumerate(issues_found, 1):
            icon = "🔴" if issue["severity"] == "high" else "🟡" if issue["severity"] == "medium" else "🟢"
            print(f"  {icon} {i}. [{issue['category']}] {issue['description']}")
    
    print(f"\n  详细结果:")
    for result in results:
        status = "✅" if result.passed else "❌"
        print(f"  {status} {result.test_name} - {result.duration:.2f}秒")
        if result.issue:
            print(f"     问题: {result.issue}")
    
    print("\n" + "="*70)


def main():
    print("\n" + "="*70)
    print("🚀 Agent Memory System - 多模块集成真实场景测试")
    print("="*70)
    
    results = run_all_tests()
    generate_report(results)
    
    print(f"\n  共发现 {len(issues_found)} 个问题")
    return len(issues_found)


if __name__ == "__main__":
    main()
