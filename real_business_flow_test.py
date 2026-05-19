#!/usr/bin/env python3
"""
Agent Memory System - 真实业务流程长时测试
模拟真实的智能助手业务场景，长时间运行，发现和验证问题
"""

import sys
import time
import random
import threading
import uuid
import json
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


# =============================================
# 真实业务场景1：用户对话会话
# =============================================

class UserSessionSimulation:
    """模拟单个用户的真实会话"""
    
    def __init__(self, user_id: str, memory: AgentMemory):
        self.user_id = user_id
        self.memory = memory
        self.conversation_history: List[Dict[str, str]] = []
        self.interaction_count = 0
        
    def simulate_interaction(self, round_num: int) -> Dict[str, Any]:
        """模拟一次用户交互"""
        
        user_query = self._generate_user_query(round_num)
        self.conversation_history.append({
            "role": "user",
            "content": user_query
        })
        
        # 记录到短期记忆
        self.memory.add_interaction(
            role="user",
            content=user_query,
            important=True
        )
        
        # 查询相关记忆
        query_results = self.memory.recall(user_query, top_k=3)
        
        # 生成回答（模拟）
        assistant_response = self._generate_response(user_query, query_results)
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        self.memory.add_interaction(
            role="assistant",
            content=assistant_response,
            important=False
        )
        
        self.interaction_count += 1
        
        return {
            "user_id": self.user_id,
            "query": user_query,
            "response": assistant_response,
            "results_count": len(query_results)
        }
        
    def _generate_user_query(self, round_num: int) -> str:
        """生成真实的用户查询"""
        query_templates = [
            "帮我推荐关于{topic}的资料",
            "什么是{topic}？请详细解释一下",
            "{topic}和{other_topic}有什么区别？",
            "如何学习{topic}？",
            "{topic}的最佳实践是什么？",
            "解释一下{topic}的工作原理",
            "给我推荐学习{topic}的资源",
            "{topic}在现实中有什么应用？",
            "对比一下{topic}和{other_topic}",
            "{topic}的未来发展趋势是什么？"
        ]
        
        topics = ["机器学习", "Python编程", "Web开发", "数据库", "系统设计", 
                  "API设计", "数据分析", "人工智能", "深度学习", "自然语言处理"]
        
        template = random.choice(query_templates)
        topic = random.choice(topics)
        other_topic = random.choice([t for t in topics if t != topic])
        
        return template.format(topic=topic, other_topic=other_topic)
        
    def _generate_response(self, query: str, results: List[Dict]) -> str:
        """模拟生成回答"""
        response_parts = []
        
        if results:
            response_parts.append("根据你的问题，我找到了以下相关信息：\n")
            for i, result in enumerate(results[:2], 1):
                response_parts.append(f"{i}. {result.get('content', '')[:100]}...\n")
        else:
            response_parts.append("我没有找到相关的记忆信息。\n")
            
        response_parts.append(f"\n这是我对您关于'{query[:50]}...'的回答。")
        
        return "".join(response_parts)


# =============================================
# 真实业务场景2：多用户并发访问
# =============================================

def simulate_multi_user_scenario(
    num_users: int = 10,
    interactions_per_user: int = 20,
    duration_seconds: int = 30
) -> Dict[str, Any]:
    """模拟多用户并发访问场景"""
    
    print(f"\n{'=' * 80}")
    print("真实业务场景测试：多用户并发访问")
    print(f"{'=' * 80}")
    print(f"用户数量: {num_users}")
    print(f"每个用户交互次数: {interactions_per_user}")
    print(f"目标持续时间: {duration_seconds}秒")
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
        short_term={"working_memory_capacity": 10, "history_limit": 200}
    )
    
    shared_memory = AgentMemory(config=config)
    
    start_time = time.time()
    all_interactions: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    lock = threading.Lock()
    
    def user_worker(user_id: int):
        """单个用户的工作线程"""
        session = UserSessionSimulation(f"user_{user_id}", shared_memory)
        for round_num in range(interactions_per_user):
            try:
                # 随机延迟模拟真实场景
                time.sleep(random.uniform(0.01, 0.1))
                
                result = session.simulate_interaction(round_num)
                
                with lock:
                    all_interactions.append(result)
                    
            except Exception as e:
                with lock:
                    errors.append({
                        "user_id": f"user_{user_id}",
                        "round": round_num,
                        "error": str(e)
                    })
    
    # 启动所有用户线程
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = [
            executor.submit(user_worker, i) 
            for i in range(num_users)
        ]
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            elapsed = time.time() - start_time
            print(f"  进度: {completed}/{num_users} 用户完成, 已运行 {elapsed:.1f}秒")
            
            if elapsed > duration_seconds:
                print(f"  ⚠️ 已超过目标时长，提前结束测试")
                break
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # 收集统计数据
    stats = {
        "duration": total_duration,
        "total_interactions": len(all_interactions),
        "success_rate": (len(all_interactions) - len(errors)) / len(all_interactions) if all_interactions else 0,
        "errors_count": len(errors),
        "interactions_per_second": len(all_interactions) / total_duration if total_duration > 0 else 0
    }
    
    # 结果展示
    print(f"\n{'=' * 50}")
    print("多用户并发测试结果")
    print(f"{'=' * 50}")
    print(f"总交互次数: {len(all_interactions)}")
    print(f"总耗时: {total_duration:.2f}秒")
    print(f"成功率: {stats['success_rate'] * 100:.1f}%")
    print(f"错误数: {len(errors)}")
    print(f"吞吐率: {stats['interactions_per_second']:.1f} 次/秒")
    
    if errors:
        print(f"\n错误示例:")
        for err in errors[:3]:
            print(f"  - {err['user_id']} Round {err['round']}: {err['error']}")
    
    # 验证数据一致性
    memory_stats = shared_memory.get_stats()
    print(f"\n记忆系统统计:")
    print(f"  长期记忆数量: {memory_stats.get('long_term', {}).get('total_memories', 0)}")
    
    shared_memory.close()
    
    return {
        "stats": stats,
        "errors": errors,
        "interactions": all_interactions
    }


# =============================================
# 真实业务场景3：知识图谱构建和推理
# =============================================

def simulate_knowledge_graph_scenario() -> Dict[str, Any]:
    """模拟知识图谱的真实构建和使用场景"""
    
    print(f"\n{'=' * 80}")
    print("真实业务场景测试：知识图谱构建和推理")
    print(f"{'=' * 80}")
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    
    memory = AgentMemory(config=config)
    
    # 模拟构建一个技术知识图谱
    tech_facts = [
        ("Python", "programming_language", "一个易于学习的高级编程语言"),
        ("JavaScript", "programming_language", "主要用于Web开发的脚本语言"),
        ("TypeScript", "programming_language", "JavaScript的超集，增加了类型系统"),
        ("React", "frontend_framework", "用于构建用户界面的前端框架"),
        ("Vue", "frontend_framework", "渐进式JavaScript框架"),
        ("Django", "backend_framework", "Python的Web应用框架"),
        ("FastAPI", "backend_framework", "现代化高性能Python Web框架"),
        ("Node.js", "runtime", "JavaScript运行时环境"),
        ("PostgreSQL", "database", "开源关系型数据库管理系统"),
        ("MongoDB", "database", "NoSQL文档数据库"),
        ("Redis", "database", "内存数据存储和缓存"),
        ("API", "concept", "应用程序编程接口"),
        ("REST", "api_style", "表述性状态传递架构风格"),
        ("GraphQL", "api_style", "一种用于API的查询语言"),
        ("Docker", "tool", "容器化平台"),
        ("Kubernetes", "tool", "容器编排系统"),
        ("Git", "tool", "分布式版本控制系统"),
    ]
    
    relationships = [
        ("Python", "Django", "used_by", 0.95),
        ("Python", "FastAPI", "used_by", 0.9),
        ("JavaScript", "React", "used_by", 0.9),
        ("JavaScript", "Vue", "used_by", 0.85),
        ("TypeScript", "React", "uses", 0.8),
        ("React", "API", "interacts_with", 0.85),
        ("Django", "PostgreSQL", "works_with", 0.9),
        ("FastAPI", "PostgreSQL", "works_with", 0.85),
        ("FastAPI", "Redis", "works_with", 0.8),
        ("Docker", "Kubernetes", "used_with", 0.9),
    ]
    
    print(f"\n阶段1：构建知识图谱（{len(tech_facts)}个实体）")
    entity_count = 0
    for name, entity_type, desc in tech_facts:
        try:
            memory.add_entity(
                name,
                entity_type=entity_type,
                description=desc
            )
            entity_count += 1
        except Exception as e:
            print(f"  ⚠️ 添加实体失败: {name} - {str(e)[:50]}")
    
    print(f"  成功添加 {entity_count}/{len(tech_facts)} 个实体")
    
    print(f"\n阶段2：建立实体关系（{len(relationships)}个关系）")
    relation_count = 0
    for source, target, rel_type, weight in relationships:
        try:
            memory.add_relation(
                source,
                target,
                relationship_type=rel_type,
                weight=weight
            )
            relation_count += 1
        except Exception as e:
            print(f"  ⚠️ 添加关系失败: {source} → {target} - {str(e)[:50]}")
    
    print(f"  成功添加 {relation_count}/{len(relationships)} 个关系")
    
    # 测试查询功能
    print(f"\n阶段3：知识图谱查询测试")
    test_queries = ["Python", "React", "API", "Docker", "数据库"]
    for query in test_queries:
        try:
            results = memory.search_entities(query, top_k=3)
            if results:
                print(f"  搜索'{query}': 找到 {len(results)} 个结果")
                for entity, score in results:
                    print(f"    - {entity.name} (类型: {entity.entity_type}) - 得分: {score:.3f}")
            else:
                print(f"  搜索'{query}': 无结果")
        except Exception as e:
            print(f"  ⚠️ 搜索'{query}'失败: {str(e)[:50]}")
    
    # 测试邻居查询
    print(f"\n阶段4：关系查询测试")
    for source_name in ["Python", "React", "FastAPI"]:
        try:
            related = memory.find_related(source_name, top_k=5)
            if related:
                print(f"  与'{source_name}'相关的实体:")
                for entity in related:
                    print(f"    - {entity.name}")
        except Exception as e:
            print(f"  ⚠️ 查询'{source_name}'的关系失败: {str(e)[:50]}")
    
    stats = memory.get_stats()
    kg_stats = stats.get("knowledge_graph", {})
    
    print(f"\n知识图谱统计:")
    print(f"  实体数: {kg_stats.get('entity_count', 0)}")
    print(f"  关系数: {kg_stats.get('relation_count', 0)}")
    
    memory.close()
    
    return {
        "entities_added": entity_count,
        "relations_added": relation_count,
        "kg_stats": kg_stats
    }


# =============================================
# 真实业务场景4：混合复杂操作（CRUD+搜索）
# =============================================

def simulate_mixed_operations_scenario() -> Dict[str, Any]:
    """模拟混合复杂操作的真实场景"""
    
    print(f"\n{'=' * 80}")
    print("真实业务场景测试：混合复杂操作（CRUD + 搜索）")
    print(f"{'=' * 80}")
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    
    memory = AgentMemory(config=config)
    
    # 阶段1：批量写入数据
    print(f"\n阶段1：批量写入数据")
    num_operations = 200
    written_ids = []
    success_count = 0
    
    for i in range(num_operations):
        try:
            content = f"重要记录 {i}: 关于 {random.choice(['技术', '管理', '科学', '艺术', '生活'])}的内容"
            mem_id = memory.remember(
                content=content,
                memory_type=random.choice(["fact", "semantic", "episodic"]),
                category=random.choice(["work", "personal", "knowledge", "notes"]),
                importance=random.uniform(0.1, 0.9)
            )
            written_ids.append(mem_id)
            success_count += 1
        except Exception as e:
            pass
    
    print(f"  写入完成: {success_count}/{num_operations} 条记录")
    
    # 阶段2：混合CRUD操作
    print(f"\n阶段2：混合CRUD操作")
    operations_count = {"create": 0, "read": 0, "update": 0, "delete": 0}
    errors = []
    
    for i in range(num_operations):
        try:
            op_choice = random.random()
            if op_choice < 0.2:  # 20% 创建
                content = f"新增记录 {i}"
                memory.remember(
                    content=content,
                    memory_type="fact",
                    importance=0.5
                )
                operations_count["create"] += 1
                
            elif op_choice < 0.5:  # 30% 读取
                if written_ids:
                    random_id = random.choice(written_ids)
                    record = memory.long_term.get(random_id)
                    if record:
                        operations_count["read"] += 1
                        
            elif op_choice < 0.7:  # 20% 更新
                if written_ids:
                    random_id = random.choice(written_ids)
                    new_content = f"更新后的内容 - {uuid.uuid4().hex[:10]}"
                    success = memory.long_term.update(random_id, content=new_content)
                    if success:
                        operations_count["update"] += 1
                        
            elif op_choice < 0.85:  # 15% 搜索
                query = random.choice(["记录", "重要", "技术", "内容"])
                results = memory.recall(query, top_k=3)
                if results:
                    operations_count["read"] += 1
                    
            else:  # 15% 删除
                if written_ids:
                    random_id = random.choice(written_ids)
                    memory.forget_memory(random_id)
                    operations_count["delete"] += 1
                    
        except Exception as e:
            errors.append(str(e))
    
    print(f"  混合操作统计:")
    print(f"    创建: {operations_count['create']}")
    print(f"    读取: {operations_count['read']}")
    print(f"    更新: {operations_count['update']}")
    print(f"    删除: {operations_count['delete']}")
    print(f"    错误: {len(errors)}")
    
    # 阶段3：数据验证
    print(f"\n阶段3：最终数据验证")
    stats = memory.get_stats()
    final_count = stats.get("long_term", {}).get("total_memories", 0)
    print(f"  最终记录数量: {final_count}")
    
    memory.close()
    
    return {
        "operations_count": operations_count,
        "final_count": final_count,
        "errors": errors
    }


# =============================================
# 主测试函数
# =============================================

def main():
    """运行所有真实业务场景测试"""
    
    print(f"\n{'=' * 80}")
    print("Agent Memory System - 真实业务流程长时测试")
    print(f"{'=' * 80}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_results = {}
    all_issues = []
    
    # 测试1：多用户并发访问
    try:
        result = simulate_multi_user_scenario(
            num_users=8,
            interactions_per_user=15,
            duration_seconds=40
        )
        all_results["multi_user"] = result
        if result.get("errors"):
            all_issues.append({
                "test": "多用户并发测试",
                "errors": result["errors"]
            })
    except Exception as e:
        print(f"\n❌ 多用户并发测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 测试2：知识图谱构建和推理
    try:
        result = simulate_knowledge_graph_scenario()
        all_results["knowledge_graph"] = result
    except Exception as e:
        print(f"\n❌ 知识图谱测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 测试3：混合复杂操作
    try:
        result = simulate_mixed_operations_scenario()
        all_results["mixed_ops"] = result
        if result.get("errors"):
            all_issues.append({
                "test": "混合操作测试",
                "errors": result["errors"]
            })
    except Exception as e:
        print(f"\n❌ 混合操作测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 最终总结
    print(f"\n{'=' * 80}")
    print("真实业务场景测试 - 最终总结")
    print(f"{'=' * 80}")
    print(f"测试总数: {len(all_results)}")
    print(f"发现问题: {len(all_issues)}")
    
    if all_issues:
        print(f"\n发现的问题:")
        for issue in all_issues:
            print(f"  - {issue['test']}: {len(issue['errors'])} 个错误")
            for err in issue['errors'][:3]:
                print(f"    * {err}")
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return all_results


if __name__ == "__main__":
    main()
