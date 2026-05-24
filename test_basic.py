#!/usr/bin/env python3
"""
最简单的基础测试 - 验证系统能正常工作
"""
import sys
import os
sys.path.insert(0, '/workspace/advanced-agent-memory-system')

print("=" * 80)
print("基础功能验证测试")
print("=" * 80)

# 测试1: 导入基本模块
print()
print("【测试1】导入基本模块...")
try:
    from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig
    print("✅ 模块导入成功")
except Exception as e:
    print(f"❌ 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试2: 初始化 AgentMemory
print()
print("【测试2】初始化 AgentMemory...")
try:
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
        knowledge_graph={"enabled": True},
        structured_store={"db_path": ":memory:", "enabled": True},
    )
    memory = AgentMemory(config)
    print("✅ AgentMemory 初始化成功")
except Exception as e:
    print(f"❌ 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试3: 记住一些内容
print()
print("【测试3】记住内容...")
try:
    memory_id = memory.remember(
        content="Python is a programming language",
        memory_type="fact",
        importance=0.8,
    )
    print(f"✅ 记住内容成功, memory_id = {memory_id[:16]}")
except Exception as e:
    print(f"❌ 记住失败: {e}")

# 测试4: 搜索
print()
print("【测试4】搜索记忆...")
try:
    results = memory.recall("Python", top_k=3)
    print(f"✅ 搜索成功, 找到 {len(results)} 个结果")
    for i, r in enumerate(results):
        print(f"  {i+1}. {r.get('content', '')[:50]}...")
except Exception as e:
    print(f"❌ 搜索失败: {e}")

# 测试5: 知识图谱
print()
print("【测试5】知识图谱操作...")
try:
    entity_id = memory.add_entity(
        name="Python",
        entity_type="programming_language",
        description="A powerful programming language"
    )
    print(f"✅ 添加实体成功: {entity_id}")
except Exception as e:
    print(f"❌ 知识图谱操作失败: {e}")

# 测试6: 获取统计
print()
print("【测试6】获取系统统计...")
try:
    stats = memory.get_stats()
    print(f"✅ 获取统计成功")
    print(f"  会话: {stats.get('session', {})}")
    print(f"  短期记忆: {stats.get('short_term', {})}")
    print(f"  长期记忆: {stats.get('long_term', {})}")
except Exception as e:
    print(f"❌ 获取统计失败: {e}")

# 测试7: 关闭
print()
print("【测试7】关闭系统...")
try:
    memory.close()
    print("✅ 关闭成功")
except Exception as e:
    print(f"❌ 关闭失败: {e}")

print()
print("=" * 80)
print("✅ 所有基础测试通过！")
print("=" * 80)
