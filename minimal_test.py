#!/usr/bin/env python3
"""
Agent Memory System - Minimal Test
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# First, let's check what imports are available
print("Checking imports...")

try:
    from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig
    from memory_system.core.long_term_persistent_memory import LongTermMemoryConfig
    print("✅ Core imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("Creating AgentMemory instance...")

try:
    config = AgentMemoryConfig(
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "fake_dimension": 64},
            vector_store={"backend": "memory"},
        )
    )
    
    mem = AgentMemory(config=config)
    print("✅ AgentMemory created successfully")
    
    # Test basic memory operations
    print("\nTesting memory operations...")
    
    mid1 = mem.remember(
        content="Python is a programming language",
        category="tech",
        importance=0.8
    )
    print(f"✅ Remembered memory ID: {mid1}")
    
    mid2 = mem.remember(
        content="Machine learning is fun",
        category="ai",
        importance=0.9
    )
    print(f"✅ Remembered memory ID: {mid2}")
    
    # Test recall
    print("\nTesting recall...")
    results = mem.recall("Python", top_k=3)
    print(f"✅ Recall returned {len(results)} results")
    
    for i, r in enumerate(results):
        print(f"  {i+1}. {r.get('content', 'N/A')} (score: {r.get('score', 0):.2f})")
    
    # Test update
    print("\nTesting update...")
    success = mem.update_memory(
        mid1,
        content="Python is a powerful, interpreted programming language"
    )
    print(f"✅ Update success: {success}")
    
    # Test stats
    print("\nTesting stats...")
    stats = mem.get_stats()
    print(f"✅ Stats: {stats}")
    
    # Test get all memories
    print("\nTesting get_all_memories...")
    all_mem = mem.get_all_memories(limit=10)
    print(f"✅ Got {len(all_mem)} memories")
    
    # Test delete
    print("\nTesting delete...")
    deleted = mem.delete_memory(mid2)
    print(f"✅ Delete success: {deleted}")
    
    # Test count
    print("\nTesting count...")
    count = mem.count_memories()
    print(f"✅ Memory count: {count}")
    
    mem.close()
    print("\n✅ All tests passed!")
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
