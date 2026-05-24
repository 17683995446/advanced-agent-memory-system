#!/usr/bin/env python3
"""
全面测试脚本 - 运行核心测试
"""
import sys
import os
sys.path.insert(0, '/workspace/advanced-agent-memory-system')

print("=" * 100)
print("开始全面测试 - Agent Memory System")
print("=" * 100)
print()

# 测试1: 基础系统测试
print("【测试1】运行核心系统测试 (test_system.py)")
print("-" * 80)
try:
    import pytest
    result = pytest.main([
        'tests/test_system.py',
        '-v',
        '--no-header',
        '--tb=short'
    ])
    print()
    print(f"核心系统测试 {'✅ 通过' if result == 0 else '❌ 失败'}")
except Exception as e:
    print(f"运行错误: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 100)
print("【测试2】运行核心模块测试")
print("=" * 100)
print()

# 测试2: 记忆管理器测试
print("【测试2】记忆管理器测试 (test_memory_manager.py)")
print("-" * 80)
try:
    result = pytest.main([
        'tests/test_memory_manager.py',
        '-v',
        '--no-header',
        '--tb=short'
    ])
    print(f"记忆管理器测试 {'✅ 通过' if result == 0 else '❌ 失败'}")
except Exception as e:
    print(f"运行错误: {e}")

print()
print("=" * 100)
print("【测试3】长期记忆测试")
print("=" * 100)
print()

# 测试3: 长期记忆测试
print("【测试3】长期记忆测试 (test_long_term_memory.py)")
print("-" * 80)
try:
    result = pytest.main([
        'tests/test_long_term_memory.py',
        '-v',
        '--no-header',
        '--tb=short'
    ])
    print(f"长期记忆测试 {'✅ 通过' if result == 0 else '❌ 失败'}")
except Exception as e:
    print(f"运行错误: {e}")

print()
print("=" * 100)
print("【测试4】知识图谱测试")
print("=" * 100)
print()

# 测试4: 知识图谱测试
print("【测试4】知识图谱测试 (test_knowledge_graph.py)")
print("-" * 80)
try:
    result = pytest.main([
        'tests/test_knowledge_graph.py',
        '-v',
        '--no-header',
        '--tb=short'
    ])
    print(f"知识图谱测试 {'✅ 通过' if result == 0 else '❌ 失败'}")
except Exception as e:
    print(f"运行错误: {e}")

print()
print("=" * 100)
print("【测试5】混合搜索引擎测试")
print("=" * 100)
print()

# 测试5: 混合搜索测试
print("【测试5】混合搜索测试 (test_hybrid_search_engine.py)")
print("-" * 80)
try:
    result = pytest.main([
        'tests/test_hybrid_search_engine.py',
        '-v',
        '--no-header',
        '--tb=short'
    ])
    print(f"混合搜索测试 {'✅ 通过' if result == 0 else '❌ 失败'}")
except Exception as e:
    print(f"运行错误: {e}")

print()
print("=" * 100)
print("全面测试完成")
print("=" * 100)
