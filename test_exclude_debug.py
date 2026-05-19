#!/usr/bin/env python3
"""
深入调试 exclude_sources 问题
"""

import sys
sys.path.insert(0, '/workspace/agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

def test_exclude_sources():
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    mem = AgentMemory(config=config)
    
    # 记住两条不同 source 的记忆
    id1 = mem.remember("测试内容A", memory_type="fact", category="test", importance=0.8, source="source-A")
    id2 = mem.remember("测试内容B", memory_type="fact", category="test", importance=0.8, source="source-B")
    
    print(f"记忆 ID1 (source-A): {id1}")
    print(f"记忆 ID2 (source-B): {id2}")
    
    # 检查直接获取的记录
    print("\n直接获取记录检查所有字段:")
    record1 = mem.long_term.get(id1)
    record2 = mem.long_term.get(id2)
    if record1:
        print(f"  record1: {record1}")
        print(f"    type: {type(record1)}")
        print(f"    source attr: {getattr(record1, 'source', 'NOT_FOUND')}")
    if record2:
        print(f"  record2: {record2}")
        print(f"    type: {type(record2)}")
        print(f"    source attr: {getattr(record2, 'source', 'NOT_FOUND')}")
    
    # 测试 long_term.recall 返回的记录
    print("\n测试 long_term.recall 返回的记录:")
    lt_results = mem.long_term.recall("测试内容", top_k=10)
    for record, score in lt_results:
        print(f"  record.id={record.id}, source={getattr(record, 'source', 'NOT_FOUND')}, score={score}")
    
    # 测试 agent_memory.recall 返回的结果
    print("\n测试 agent_memory.recall 返回的结果:")
    results_all = mem.recall("测试内容", top_k=10)
    for r in results_all:
        print(f"  id={r['id']}, source={r.get('source', 'NOT_FOUND')}")
    
    # 测试 exclude_sources 过滤
    print("\n测试 exclude_sources=['source-A'] 过滤:")
    results_filtered = mem.recall("测试内容", top_k=10, exclude_sources=["source-A"])
    for r in results_filtered:
        print(f"  id={r['id']}, source={r.get('source', 'NOT_FOUND')}")
    
    mem.close()

if __name__ == "__main__":
    test_exclude_sources()
