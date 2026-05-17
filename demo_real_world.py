#!/usr/bin/env python3
"""
Agent Memory System 真实演示 - 智能对话助手

模拟一个真实的 AI 对话助手场景，展示记忆系统的核心功能：
1. 多轮对话记忆
2. 用户偏好学习
3. 语义搜索
4. 知识图谱构建
5. 记忆整合与遗忘
"""

import sys
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system import (
    AgentMemory,
    AgentMemoryConfig,
    HybridSearchEngine,
    KeywordSearchStrategy,
    MemoryConsolidator,
    ImportanceConsolidationStrategy,
)

print("=" * 70)
print("🤖 Agent Memory System v4.2 - 真实场景演示")
print("=" * 70)
print()

# ============================================================
# 场景1: 智能对话助手 - 多轮对话记忆
# ============================================================
print("📌 场景1: 智能对话助手 - 多轮对话记忆")
print("-" * 50)

# 创建记忆系统
print("🔄 正在初始化记忆系统...")
config = AgentMemoryConfig(
    short_term={"working_memory_capacity": 10, "history_limit": 100},
    long_term={
        "embedding": {"provider": "fake", "fake_dimension": 384},
        "vector_store": {"backend": "memory"}
    },
    knowledge_graph={"enabled": True},
    structured_store={"enabled": True, "db_path": ":memory:"},
    auto_consolidate=False,
    default_top_k=5,
)

agent = AgentMemory(config=config)
print(f"✅ 记忆系统初始化完成 (session_id: {agent.session_id[:8]}...)")
print()

# 模拟多轮对话
conversations = [
    ("user", "你好，我叫张三，我是一名Python开发者", "fact"),
    ("assistant", "你好张三！很高兴认识一位Python开发者。有什么我可以帮助你的吗？", "conversation"),
    ("user", "我对机器学习和自然语言处理很感兴趣", "preference"),
    ("assistant", "很棒的兴趣！机器学习和NLP是AI领域最热门的方向。你有什么具体想了解的吗？", "conversation"),
    ("user", "我最近在做一个智能客服项目，需要处理用户意图识别", "conversation"),
    ("assistant", "用户意图识别是NLP的经典应用。你可以考虑使用BERT或者更轻量的FastText模型。", "conversation"),
    ("user", "我的项目使用Django框架，数据库是PostgreSQL", "conversation"),
    ("assistant", "Django + PostgreSQL是很稳定的技术栈。你可以用pgvector扩展来存储向量。", "conversation"),
    ("user", "我住在北京，平时喜欢打篮球", "fact"),
    ("assistant", "北京有很多不错的篮球场地！工作之余运动放松很有必要。", "conversation"),
]

print("💬 对话记录:")
print()
for i, (role, content, mem_type) in enumerate(conversations, 1):
    metadata = {"role": role, "turn": i}
    
    result = agent.remember(
        content=content,
        memory_type=mem_type,
        metadata=metadata,
        importance=0.7 if role == "user" else 0.5,
    )
    
    icon = "👤" if role == "user" else "🤖"
    print(f"  {icon} [{role}] {content[:50]}{'...' if len(content) > 50 else ''}")
    print(f"     → 记忆ID: {result[:8]}... (类型: {mem_type})")

print()
print(f"📊 当前记忆统计: {agent.get_stats()}")
print()

# ============================================================
# 场景2: 语义搜索 - 查找相关记忆
# ============================================================
print("📌 场景2: 语义搜索 - 查找相关记忆")
print("-" * 50)

search_queries = [
    "用户是谁",
    "技术栈是什么",
    "兴趣爱好",
    "项目相关",
]

for query in search_queries:
    print(f"\n🔍 搜索: \"{query}\" (排除结构化数据)")
    # 使用 exclude_sources=["structured"] 排除键值对格式的偏好数据
    results = agent.recall(query, top_k=3, exclude_sources=["structured"])
    
    if results:
        for j, mem in enumerate(results, 1):
            content = mem.get("content", mem.get("record", {}).get("content", ""))
            score = mem.get("score", 0)
            mem_type = mem.get("memory_type", "unknown")
            print(f"  {j}. [{mem_type}] {content[:60]}{'...' if len(content) > 60 else ''}")
            print(f"     相似度: {score:.3f}")
    else:
        print("  (无结果)")

print()

# ============================================================
# 场景3: 知识图谱 - 实体关系
# ============================================================
print("📌 场景3: 知识图谱 - 实体关系")
print("-" * 50)

# 添加更多结构化知识
knowledge_texts = [
    "张三在字节跳动工作，职位是高级工程师",
    "张三的项目使用Django框架和PostgreSQL数据库",
    "张三擅长Python、JavaScript和Go语言",
    "机器学习项目需要训练数据和模型评估",
    "自然语言处理包括分词、命名实体识别、情感分析",
]

print("📚 添加知识:")
for text in knowledge_texts:
    agent.remember(content=text, memory_type="fact", importance=0.8)
    print(f"  ✓ {text}")

print()

# 查看知识图谱
if agent.knowledge_graph:
    stats = agent.get_knowledge_graph_stats()
    print(f"📊 知识图谱统计:")
    print(f"  - 实体数量: {stats.get('entity_count', 0)}")
    print(f"  - 关系数量: {stats.get('relation_count', 0)}")

print()

# ============================================================
# 场景4: 结构化存储 - 用户偏好
# ============================================================
print("📌 场景4: 结构化存储 - 用户偏好")
print("-" * 50)

# 使用 remember_fact 存储用户偏好
preferences = [
    ("name", "张三", "identity"),
    ("location", "北京", "location"),
    ("profession", "Python开发者", "identity"),
    ("company", "字节跳动", "identity"),
]

print("💾 存储用户偏好:")
for key, value, category in preferences:
    agent.remember_fact(f"{key}: {value}", category=category)
    print(f"  ✓ {key}: {value}")

print()

# ============================================================
# 场景5: 记忆整合 - 清理和优化
# ============================================================
print("📌 场景5: 记忆整合 - 清理和优化")
print("-" * 50)

# 获取所有记忆进行整合
all_memories = agent.recall("", top_k=100)
print(f"📊 整合前记忆数量: {len(all_memories)}")

# 创建整合器
consolidator = MemoryConsolidator()
consolidator.add_strategy(ImportanceConsolidationStrategy(keep_ratio=0.8, min_importance=0.3))

# 执行整合
from memory_system.core.memory_consolidation import MemoryItem

# 转换为 MemoryItem 格式
memory_items = []
for i, mem in enumerate(all_memories):
    content = mem.get("content", mem.get("record", {}).get("content", ""))
    if content:
        memory_items.append(MemoryItem(
            id=f"mem-{i}",
            content=content,
            importance=mem.get("importance", 0.5),
            access_count=mem.get("access_count", 0),
        ))

if memory_items:
    result = consolidator.consolidate(memory_items)
    print(f"\n📊 整合结果:")
    print(f"  - 保留: {len(result.consolidated)} 条")
    print(f"  - 合并: {len(result.merged)} 条")
    print(f"  - 归档: {len(result.archived)} 条")
    print(f"\n{result.summary_text()}")

print()

# ============================================================
# 场景6: 混合搜索引擎
# ============================================================
print("📌 场景6: 混合搜索引擎 - 多策略融合")
print("-" * 50)

# 创建混合搜索引擎
engine = HybridSearchEngine(fusion_method="rrf")

# 添加关键词搜索策略
keyword_strategy = KeywordSearchStrategy()
for mem in all_memories[:20]:
    content = mem.get("content", mem.get("record", {}).get("content", ""))
    mem_id = mem.get("id", f"temp-{time.time()}")
    if content:
        keyword_strategy.add_document(mem_id, content)

engine.add_strategy(keyword_strategy, weight=1.0)
print("✅ 混合搜索引擎初始化完成 (RRF融合)")

# 执行搜索
print("\n🔍 混合搜索: 'Python开发'")
results = engine.search("Python开发", top_k=5)
for i, hit in enumerate(results, 1):
    print(f"  {i}. [{hit.source}] {hit.content[:50]}{'...' if len(hit.content) > 50 else ''}")
    print(f"     分数: {hit.score:.4f}")

print()

# ============================================================
# 场景7: 会话管理
# ============================================================
print("📌 场景7: 会话管理")
print("-" * 50)

# 设置会话上下文
agent.set_session_context("user_name", "张三")
agent.set_session_context("current_topic", "智能客服项目")

print("💾 会话上下文:")
print(f"  - user_name: {agent.get_session_context('user_name')}")
print(f"  - current_topic: {agent.get_session_context('current_topic')}")

# 获取对话历史
history = agent.get_conversation_history(n=5)
print(f"\n📜 最近5轮对话:")
for i, turn in enumerate(history, 1):
    role = turn.get("role", "unknown")
    content = turn.get("content", "")
    icon = "👤" if role == "user" else "🤖"
    print(f"  {i}. {icon} {content[:40]}{'...' if len(content) > 40 else ''}")

print()

# ============================================================
# 最终统计
# ============================================================
print("=" * 70)
print("📊 最终统计")
print("=" * 70)

stats = agent.get_stats()
print(f"""
会话ID:        {agent.session_id}
长期记忆:      {stats.get('long_term', {}).get('total_memories', 0)}
知识图谱实体:  {stats.get('knowledge_graph', {}).get('entity_count', 0)}
知识图谱关系:  {stats.get('knowledge_graph', {}).get('relation_count', 0)}
结构化表:      {stats.get('structured_store', {}).get('tables', [])}
""")

# 关闭系统
agent.close()
print("✅ 演示完成！Agent Memory System 运行正常。")
print()
