"""
第二轮：真实场景深度测试

模拟真实AI Agent使用场景：
1. 多轮对话上下文保持
2. 知识库增量更新
3. 工作流状态持久化
4. 跨会话记忆恢复
5. 智能体协作记忆共享
"""

import sys
import time
import json
import random

sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


class TestResult:
    def __init__(self, name):
        self.name = name
        self.errors = []
        self.warnings = []
        self.metrics = {}
        self.passed = True

    def add_error(self, msg):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg):
        self.warnings.append(msg)

    def report(self):
        status = "✅ 通过" if self.passed else "❌ 失败"
        print(f"\n{'='*60}")
        print(f"  {self.name}: {status}")
        print(f"{'='*60}")
        if self.metrics:
            print("  指标:")
            for k, v in self.metrics.items():
                print(f"    {k}: {v}")
        if self.warnings:
            print(f"  警告 ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"    ⚠ {w}")
        if self.errors:
            print(f"  错误 ({len(self.errors)}):")
            for e in self.errors:
                print(f"    ✗ {e}")
        print()


def make_config():
    return AgentMemoryConfig(
        short_term={"working_memory_capacity": 50, "history_limit": 200},
        long_term={
            "embedding": {"provider": "fake", "fake_dimension": 64},
            "vector_store": {"backend": "memory"},
        },
        knowledge_graph={"enabled": True},
        structured_store={"enabled": True},
        auto_consolidate=False,
    )


# ============================================================
# R1: 多轮对话上下文保持
# ============================================================
def test_conversation_context():
    """模拟AI助手多轮对话，验证上下文保持能力"""
    result = TestResult("R1: 多轮对话上下文保持")
    mem = AgentMemory(config=make_config())
    
    try:
        # 模拟20轮对话
        conversation = [
            ("user", "你好，我想学习Python"),
            ("assistant", "你好！Python是一门优秀的编程语言。你有编程基础吗？"),
            ("user", "有一些Java基础"),
            ("assistant", "那太好了！Java和Python有很多相似之处。你想重点学习哪个方向？"),
            ("user", "想做数据分析"),
            ("assistant", "数据分析是Python的强项。你需要学习pandas、numpy和matplotlib。"),
            ("user", "pandas是什么？"),
            ("assistant", "pandas是Python的数据处理库，类似于Java中的表格数据处理。"),
            ("user", "有推荐的学习资源吗？"),
            ("assistant", "推荐《Python for Data Analysis》和官方文档。"),
            ("user", "学习周期大概多久？"),
            ("assistant", "有Java基础的话，2-3个月可以掌握基础。"),
            ("user", "好的，谢谢！"),
            ("assistant", "不客气！有问题随时问我。"),
        ]
        
        # 记录对话
        for role, content in conversation:
            mem.remember_conversation(content, speaker=role, important=True)
            mem.add_interaction(role, content)
        
        # 测试上下文检索
        context = mem.get_conversation_context(max_turns=5)
        result.metrics["上下文长度"] = len(context)
        
        # 验证关键信息保留
        recall_results = mem.recall("Java基础", top_k=3)
        java_mentions = sum(1 for r in recall_results if "Java" in r.get("content", ""))
        result.metrics["Java提及数"] = java_mentions
        
        if java_mentions == 0:
            result.add_warning("关键信息'Java'未在检索中保留")
        
        # 验证时间范围过滤
        now = time.time()
        recent = mem.recall("学习", time_range=(now - 3600, now), top_k=10)
        result.metrics["最近1小时记录"] = len(recent)
        
    except Exception as e:
        import traceback
        result.add_error(f"异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()
    
    return result


# ============================================================
# R2: 知识库增量更新
# ============================================================
def test_knowledge_incremental_update():
    """模拟知识库的持续学习和更新"""
    result = TestResult("R2: 知识库增量更新")
    mem = AgentMemory(config=make_config())
    
    try:
        # 初始知识库
        initial_facts = [
            ("Python是解释型语言", "programming", 0.9),
            ("Java是编译型语言", "programming", 0.9),
            ("Python 3.9发布于2020年", "version", 0.7),
        ]
        
        for fact, cat, imp in initial_facts:
            mem.remember_fact(fact, category=cat, confidence=imp)
        
        # 更新知识（版本信息过时）
        mem.remember_fact("Python 3.9发布于2020年10月", category="version", confidence=0.95)
        
        # 检测冲突
        conflicts = mem.detect_conflicts()
        result.metrics["检测到的冲突"] = conflicts.get("conflicts_found", 0)
        
        # 知识图谱构建
        mem.build_knowledge_from_text("Python和Java都是流行的编程语言，Python适合数据分析，Java适合企业开发。")
        
        stats = mem.get_knowledge_graph_stats()
        result.metrics["知识图谱实体"] = stats.get("entity_count", 0)
        result.metrics["知识图谱关系"] = stats.get("relation_count", 0)
        
        # 路径查找
        path = mem.find_path("Python", "Java")
        result.metrics["Python到Java路径"] = len(path) if path else 0
        
    except Exception as e:
        import traceback
        result.add_error(f"异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()
    
    return result


# ============================================================
# R3: 工作流状态持久化
# ============================================================
def test_workflow_persistence():
    """模拟复杂工作流的状态保存和恢复"""
    result = TestResult("R3: 工作流状态持久化")
    
    workflow_id = "workflow_001"
    
    try:
        # 第一阶段：创建工作流
        mem1 = AgentMemory(config=make_config())
        
        # 记录工作流步骤（使用remember确保可导出）
        steps = [
            {"step": 1, "action": "数据清洗", "status": "completed", "output": "清洗后数据1000条"},
            {"step": 2, "action": "特征提取", "status": "completed", "output": "提取特征50维"},
            {"step": 3, "action": "模型训练", "status": "running", "output": None},
        ]
        
        for step in steps:
            mem1.remember(
                content=f"工作流步骤: {json.dumps(step)}",
                category="workflow",
                memory_type="procedural",
                metadata={"workflow_id": workflow_id, "step": step["step"], "step_data": step},
                tags=["workflow_state"],
            )
        
        # 导出状态
        mem1.export_memories("/tmp/workflow_state.json", format="json")
        mem1.close()
        
        # 第二阶段：恢复工作流（模拟服务重启）
        mem2 = AgentMemory(config=make_config())
        mem2.import_memories("/tmp/workflow_state.json")
        
        # 验证状态恢复
        recovered = mem2.recall("工作流步骤", category="workflow", tags=["workflow_state"], top_k=10)
        step_3_data = None
        for item in recovered:
            meta = item.get("metadata", {})
            if meta.get("step") == 3:
                step_3_data = meta.get("step_data")
                break
        
        if step_3_data and step_3_data.get("status") == "running":
            result.metrics["状态恢复"] = "成功"
            
            # 继续执行 - 更新步骤状态
            step_3_data["status"] = "completed"
            step_3_data["output"] = "训练准确率0.95"
            mem2.remember(
                content=f"工作流步骤更新: {json.dumps(step_3_data)}",
                category="workflow",
                memory_type="procedural",
                metadata={"workflow_id": workflow_id, "step": 3, "step_data": step_3_data},
                tags=["workflow_state", "completed"],
            )
        else:
            result.add_error("工作流状态恢复失败")
        
        mem2.close()
        
        # 清理
        import os
        if os.path.exists("/tmp/workflow_state.json"):
            os.unlink("/tmp/workflow_state.json")
        
    except Exception as e:
        import traceback
        result.add_error(f"异常: {e}\n{traceback.format_exc()}")
    
    return result


# ============================================================
# R4: 跨会话记忆恢复
# ============================================================
def test_cross_session_recovery():
    """验证用户跨会话的记忆保持"""
    result = TestResult("R4: 跨会话记忆恢复")
    user_id = "user_12345"
    
    try:
        # 会话1：用户初次使用
        session1 = AgentMemory(config=make_config())
        
        # 记录用户偏好（使用remember确保可导出）
        session1.remember("用户姓名: 张三", category="user_profile", memory_type="fact", 
                         metadata={"key": "name", "value": "张三"}, tags=["user_profile"])
        session1.remember("用户兴趣: Python,机器学习,数据分析", category="user_profile", memory_type="fact",
                         metadata={"key": "interests", "value": ["Python", "机器学习", "数据分析"]}, tags=["user_profile"])
        session1.remember("用户技能水平: intermediate", category="user_profile", memory_type="fact",
                         metadata={"key": "skill_level", "value": "intermediate"}, tags=["user_profile"])
        
        # 记录重要事实
        session1.remember_fact("用户正在学习Transformer模型", category="learning", source=user_id)
        session1.remember_fact("用户偏好可视化学习方式", category="preference", source=user_id)
        
        # 导出用户记忆
        session1.export_memories(f"/tmp/user_{user_id}.json", format="json")
        session1.close()
        
        # 会话2：用户再次访问（模拟新会话）
        session2 = AgentMemory(config=make_config())
        session2.import_memories(f"/tmp/user_{user_id}.json")
        
        # 验证记忆恢复
        profile_data = session2.recall("用户", category="user_profile", tags=["user_profile"], top_k=10)
        
        name = None
        interests = None
        for item in profile_data:
            meta = item.get("metadata", {})
            if meta.get("key") == "name":
                name = meta.get("value")
            elif meta.get("key") == "interests":
                interests = meta.get("value")
        
        result.metrics["用户名恢复"] = name if name == "张三" else "失败"
        result.metrics["兴趣恢复"] = f"{len(interests)}项" if interests else "失败"
        
        # 验证个性化检索
        relevant = session2.recall("学习资源", category="learning", top_k=5)
        result.metrics["个性化检索"] = f"{len(relevant)}条"
        
        # 验证时间过滤
        now = time.time()
        recent_facts = session2.recall("用户", time_range=(now - 86400, now), top_k=10)
        result.metrics["24小时内事实"] = len(recent_facts)
        
        session2.close()
        
        # 清理
        import os
        if os.path.exists(f"/tmp/user_{user_id}.json"):
            os.unlink(f"/tmp/user_{user_id}.json")
        
    except Exception as e:
        import traceback
        result.add_error(f"异常: {e}\n{traceback.format_exc()}")
    
    return result


# ============================================================
# R5: 智能体协作记忆共享
# ============================================================
def test_agent_collaboration():
    """模拟多个AI智能体协作并共享记忆"""
    result = TestResult("R5: 智能体协作记忆共享")
    
    try:
        # 创建共享记忆空间（模拟）
        shared_config = make_config()
        
        # Agent A：数据收集
        agent_a = AgentMemory(config=shared_config)
        agent_a.remember_fact("数据集A包含10000条记录", category="data", source="agent_a")
        agent_a.remember_fact("数据质量评分0.85", category="data", source="agent_a")
        agent_a.export_memories("/tmp/shared_memory.json", format="json")
        agent_a.close()
        
        # Agent B：数据分析（读取Agent A的结果）
        agent_b = AgentMemory(config=shared_config)
        agent_b.import_memories("/tmp/shared_memory.json")
        
        # 基于Agent A的发现继续分析
        data_info = agent_b.recall("数据集", category="data", top_k=3)
        if data_info:
            agent_b.remember_fact("基于10000条记录的分析显示正态分布", category="analysis", source="agent_b")
        
        agent_b.export_memories("/tmp/shared_memory.json", format="json")
        agent_b.close()
        
        # Agent C：报告生成（整合所有信息）
        agent_c = AgentMemory(config=shared_config)
        agent_c.import_memories("/tmp/shared_memory.json")
        
        # 验证协作结果
        all_data = agent_c.recall("数据", top_k=10)
        result.metrics["共享记忆条目"] = len(all_data)
        
        sources = set()
        for item in all_data:
            meta = item.get("metadata", {})
            if "source" in meta:
                sources.add(meta["source"])
        
        result.metrics["参与智能体"] = f"{len(sources)}个"
        
        agent_c.close()
        
        # 清理
        import os
        if os.path.exists("/tmp/shared_memory.json"):
            os.unlink("/tmp/shared_memory.json")
        
    except Exception as e:
        import traceback
        result.add_error(f"异常: {e}\n{traceback.format_exc()}")
    
    return result


# ============================================================
# 主执行
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Agent Memory System - 真实场景深度测试")
    print("=" * 60)
    
    all_results = []
    tests = [
        ("R1", test_conversation_context),
        ("R2", test_knowledge_incremental_update),
        ("R3", test_workflow_persistence),
        ("R4", test_cross_session_recovery),
        ("R5", test_agent_collaboration),
    ]
    
    total_start = time.time()
    for name, test_fn in tests:
        print(f"\n▶ 执行 {name}...")
        r = test_fn()
        r.report()
        all_results.append(r)
    total_time = time.time() - total_start
    
    # 汇总
    print("\n" + "=" * 60)
    print("  汇总报告")
    print("=" * 60)
    passed = sum(1 for r in all_results if r.passed)
    total_errors = sum(len(r.errors) for r in all_results)
    total_warnings = sum(len(r.warnings) for r in all_results)
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  通过: {passed}/{len(all_results)}")
    print(f"  错误: {total_errors}")
    print(f"  警告: {total_warnings}")
    
    if total_errors > 0:
        print("\n  需要修复的错误:")
        for r in all_results:
            for e in r.errors:
                print(f"    [{r.name}] {e}")
    
    if total_warnings > 0:
        print(f"\n  警告 ({total_warnings}):")
        for r in all_results:
            for w in r.warnings:
                print(f"    [{r.name}] {w}")
    print()
