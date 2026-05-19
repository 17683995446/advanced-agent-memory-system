#!/usr/bin/env python3
"""
Agent Memory System - 深度分析与验证测试
慢工出细活：细致验证系统的每个功能
"""

import sys
import time
import random
from datetime import datetime

sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


def test_basic_memory_operations():
    """测试基本记忆操作"""
    print("\n" + "="*80)
    print("1. 基本记忆操作验证")
    print("="*80)
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
        short_term={"working_memory_capacity": 50, "history_limit": 200}
    )
    
    memory = AgentMemory(config=config)
    
    # 写入测试
    print("\n  写入测试记录...")
    test_records = []
    for i in range(10):
        content = f"测试记忆 #{i}: 关于机器学习和AI的内容"
        mem_id = memory.remember(
            content=content,
            memory_type="fact",
            category="test",
            importance=random.uniform(0.3, 0.9)
        )
        test_records.append((mem_id, content))
        print(f"    写入记录 {i}, ID: {mem_id[:12]}...")
    
    # 读取验证
    print("\n  验证读取...")
    read_success = 0
    for mem_id, expected_content in test_records:
        record = memory.long_term.get(mem_id)
        if record:
            print(f"    ✓ 成功读取 {mem_id[:12]}")
            read_success += 1
        else:
            print(f"    ✗ 无法读取 {mem_id[:12]}")
    
    # 搜索测试
    print("\n  搜索测试...")
    search_results = memory.recall("机器学习", top_k=5)
    print(f"    搜索'机器学习': 找到 {len(search_results)} 条结果")
    
    # 统计
    stats = memory.get_stats()
    print(f"\n  系统统计:")
    print(f"    长期记忆: {stats.get('long_term', {}).get('total_memories', 0)}")
    print(f"    短期记忆: {stats.get('short_term', {}).get('history_count', 0)}")
    
    memory.close()
    return read_success == len(test_records)


def test_memory_retrieval_accuracy():
    """测试记忆检索准确性"""
    print("\n" + "="*80)
    print("2. 记忆检索准确性验证")
    print("="*80)
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
    )
    
    memory = AgentMemory(config=config)
    
    # 创建已知主题的记忆
    topics = ["Python编程", "Web开发", "数据库", "AI和机器学习", "系统设计"]
    target_topic = "数据库"
    target_mem_ids = []
    
    print(f"\n  写入包含 '{target_topic}' 的记忆...")
    for i in range(20):
        topic = random.choice(topics)
        content = f"关于 {topic} 的重要信息: {generate_random_text(20)}"
        mem_id = memory.remember(
            content=content,
            importance=0.7 if topic == target_topic else 0.4,
        )
        if topic == target_topic:
            target_mem_ids.append(mem_id)
        if (i+1) % 5 == 0:
            print(f"    已写入 {i+1}/20 条记录")
    
    print(f"\n  共写入 {len(target_mem_ids)} 条 '{target_topic}' 相关记录")
    
    # 检索测试
    print(f"\n  检索测试...")
    results = memory.recall(target_topic, top_k=10)
    print(f"    检索到 {len(results)} 条结果")
    
    # 分析结果
    found_targets = 0
    for result in results:
        content = str(result.get('content', ''))
        if target_topic in content:
            found_targets += 1
            print(f"    ✓ 找到相关内容: {content[:60]}...")
    
    print(f"\n  检索准确率: {found_targets}/{len(results)}")
    
    stats = memory.get_stats()
    print(f"  系统总记忆: {stats.get('long_term', {}).get('total_memories', 0)}")
    
    memory.close()
    return found_targets >= 3  # 至少找到3条相关记录


def test_session_context():
    """测试会话上下文功能"""
    print("\n" + "="*80)
    print("3. 会话上下文功能验证")
    print("="*80)
    
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        ),
    )
    
    memory = AgentMemory(config=config)
    
    # 模拟对话
    print(f"\n  模拟用户对话...")
    dialogues = [
        ("user", "你好，我想了解机器学习"),
        ("assistant", "你好！机器学习是AI的一个分支..."),
        ("user", "有哪些主要算法？"),
        ("assistant", "主要的算法包括：监督学习、非监督学习、强化学习..."),
        ("user", "可以推荐一些学习资源吗？"),
        ("assistant", "当然！推荐你从Python和Scikit-learn开始..."),
    ]
    
    for i, (role, content) in enumerate(dialogues):
        print(f"    {role}: {content[:50]}...")
        memory.add_interaction(role=role, content=content)
    
    # 查看会话历史
    print(f"\n  获取会话历史...")
    history = memory.get_conversation_history()
    print(f"    会话历史长度: {len(history)}")
    
    for i, entry in enumerate(history):
        role = entry.get('role', 'unknown')
        content = entry.get('content', '')[:40]
        print(f"    [{i}] {role}: {content}...")
    
    stats = memory.get_stats()
    print(f"\n  会话统计: {stats.get('short_term', {}).get('history_count', 0)}")
    
    memory.close()
    return len(history) == len(dialogues)


def generate_random_text(length):
    """生成随机测试文本"""
    words = ["测试", "内容", "信息", "数据", "记录", "验证", "系统", "功能", "学习", "开发", 
             "编程", "算法", "模型", "设计", "架构"]
    return "".join([random.choice(words) for _ in range(length)])


def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("Agent Memory System - 慢工出细活：深度分析与验证")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # 测试1：基本操作
    try:
        results["test1"] = test_basic_memory_operations()
        print(f"\n  基本操作测试: {'✅ 通过' if results['test1'] else '❌ 失败'}")
    except Exception as e:
        print(f"\n  基本操作测试异常: {e}")
        results["test1"] = False
    
    # 测试2：检索准确性
    try:
        results["test2"] = test_memory_retrieval_accuracy()
        print(f"\n  检索准确性测试: {'✅ 通过' if results['test2'] else '❌ 失败'}")
    except Exception as e:
        print(f"\n  检索准确性测试异常: {e}")
        results["test2"] = False
    
    # 测试3：会话上下文
    try:
        results["test3"] = test_session_context()
        print(f"\n  会话上下文测试: {'✅ 通过' if results['test3'] else '❌ 失败'}")
    except Exception as e:
        print(f"\n  会话上下文测试异常: {e}")
        results["test3"] = False
    
    # 总结
    print("\n" + "="*80)
    print("深度分析与验证测试总结")
    print("="*80)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\n总测试数: {total}")
    print(f"通过数: {passed}/{total}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    for name, passed in results.items():
        print(f"  {name}: {'✅ 通过' if passed else '❌ 失败'}")
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
