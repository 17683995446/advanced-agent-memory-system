#!/usr/bin/env python3
"""
Agent Memory System - Comprehensive Real-World Test
Discovering bugs through practical usage scenarios
"""

import sys
import os
import time
import json
import random
import threading
from typing import List, Dict, Any, Optional, Tuple

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


def test_basic_memory_operations() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Test 1: Basic memory operations (store, retrieve, update, delete)"""
    errors = []
    warnings = []
    metrics = {}
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        mem = AgentMemory(config=config)
        
        # Store memories
        memory_ids = []
        test_data = [
            ("Python is a programming language", "tech", 0.8),
            ("Machine learning is a subset of AI", "ai", 0.9),
            ("Neural networks are used for pattern recognition", "tech", 0.7),
            ("SQL databases store structured data", "tech", 0.6),
        ]
        
        start_time = time.time()
        for content, category, importance in test_data:
            try:
                mid = mem.remember(
                    content=content,
                    category=category,
                    importance=importance
                )
                memory_ids.append(mid)
            except Exception as e:
                errors.append(f"remember failed: {e}")
        
        metrics["store_time"] = time.time() - start_time
        metrics["stored_count"] = len(memory_ids)
        
        # Retrieve memories
        try:
            results = mem.recall("Python", top_k=3)
            metrics["retrieval_results_count"] = len(results)
        except Exception as e:
            errors.append(f"recall failed: {e}")
        
        # Update a memory
        if memory_ids:
            try:
                success = mem.update_memory(
                    memory_ids[0],
                    content="Python is a powerful, interpreted programming language"
                )
                metrics["update_success"] = success
            except Exception as e:
                errors.append(f"update failed: {e}")
        
        # Delete a memory
        if len(memory_ids) > 1:
            try:
                deleted = mem.delete_memory(memory_ids[1])
                metrics["delete_success"] = deleted
            except Exception as e:
                errors.append(f"delete failed: {e}")
        
        # Get statistics
        try:
            stats = mem.get_stats()
            metrics["final_memory_count"] = stats.get("long_term", {}).get("total_count", 0)
        except Exception as e:
            warnings.append(f"get_stats failed: {e}")
        
        mem.close()
        
    except Exception as e:
        errors.append(f"Unexpected error in basic ops: {e}")
        import traceback
        errors.append(f"Stack trace: {traceback.format_exc()}")
    
    return len(errors) == 0, errors + warnings, metrics


def test_knowledge_graph() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Test 2: Knowledge graph operations"""
    errors = []
    warnings = []
    metrics = {}
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            knowledge_graph={"enabled": True},
        )
        mem = AgentMemory(config=config)
        
        # Add entities
        entities = [
            ("Python", "language", "A programming language"),
            ("TensorFlow", "framework", "ML framework"),
            ("Neural Network", "concept", "Computational model"),
        ]
        
        for name, etype, desc in entities:
            try:
                mem.add_entity(name, entity_type=etype, description=desc)
            except Exception as e:
                errors.append(f"add_entity failed for {name}: {e}")
        
        # Add relations
        relations = [
            ("TensorFlow", "Python", "uses"),
            ("Neural Network", "TensorFlow", "implemented_in"),
        ]
        
        for src, target, rtype in relations:
            try:
                mem.add_relation(src, target, relation_type=rtype, weight=1.0)
            except Exception as e:
                errors.append(f"add_relation failed: {e}")
        
        # Search entities
        try:
            results = mem.search_entities("Python", top_k=3)
            metrics["entity_search_count"] = len(results)
        except Exception as e:
            errors.append(f"search_entities failed: {e}")
        
        # Find related entities
        try:
            related = mem.find_related("Python", top_k=5)
            metrics["related_entities_count"] = len(related)
        except Exception as e:
            errors.append(f"find_related failed: {e}")
        
        # Get knowledge graph stats
        try:
            kg_stats = mem.get_knowledge_graph_stats()
            metrics["kg_entities"] = kg_stats.get("entity_count", 0)
            metrics["kg_relations"] = kg_stats.get("relation_count", 0)
        except Exception as e:
            warnings.append(f"get_knowledge_graph_stats failed: {e}")
        
        mem.close()
        
    except Exception as e:
        errors.append(f"Unexpected error in knowledge graph: {e}")
        import traceback
        errors.append(f"Stack trace: {traceback.format_exc()}")
    
    return len(errors) == 0, errors + warnings, metrics


def test_concurrent_operations() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Test 3: Concurrent memory operations"""
    errors = []
    warnings = []
    metrics = {}
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            auto_consolidate=False,
        )
        mem = AgentMemory(config=config)
        
        thread_errors = []
        success_count = [0]
        lock = threading.Lock()
        
        def writer_thread(thread_id: int, count: int):
            try:
                for i in range(count):
                    mem.remember(
                        f"Thread {thread_id} memory {i}: {random.randint(1, 100000)}",
                        category="concurrent",
                        importance=0.5
                    )
                    with lock:
                        success_count[0] += 1
            except Exception as e:
                with lock:
                    thread_errors.append(f"Writer {thread_id}: {e}")
        
        def reader_thread(thread_id: int, count: int):
            try:
                for i in range(count):
                    mem.recall(f"thread {thread_id}", top_k=3)
            except Exception as e:
                with lock:
                    thread_errors.append(f"Reader {thread_id}: {e}")
        
        # Start threads
        start_time = time.time()
        threads = []
        
        # 5 writer threads, 3 reader threads
        for i in range(5):
            t = threading.Thread(target=writer_thread, args=(i, 20))
            threads.append(t)
            t.start()
        
        for i in range(3):
            t = threading.Thread(target=reader_thread, args=(i, 10))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=30)
        
        metrics["concurrent_time"] = time.time() - start_time
        metrics["success_count"] = success_count[0]
        metrics["thread_errors"] = len(thread_errors)
        
        if thread_errors:
            for e in thread_errors[:5]:
                errors.append(e)
        
        # Check final state
        try:
            stats = mem.get_stats()
            metrics["final_count"] = stats.get("long_term", {}).get("total_count", 0)
        except Exception as e:
            warnings.append(f"Final stats check failed: {e}")
        
        mem.close()
        
    except Exception as e:
        errors.append(f"Unexpected error in concurrent ops: {e}")
        import traceback
        errors.append(f"Stack trace: {traceback.format_exc()}")
    
    return len(errors) == 0, errors + warnings, metrics


def test_edge_cases() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Test 4: Edge cases and boundary conditions"""
    errors = []
    warnings = []
    metrics = {}
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        mem = AgentMemory(config=config)
        
        # Very long content
        try:
            long_content = "A" * 10000  # 10k chars
            mid = mem.remember(long_content, category="long")
            metrics["long_content"] = "accepted"
        except Exception as e:
            errors.append(f"Long content failed: {e}")
        
        # Empty content (should fail)
        try:
            mem.remember("", category="empty")
            warnings.append("Empty content should be rejected but was accepted")
        except ValueError:
            metrics["empty_content"] = "correctly_rejected"
        except Exception as e:
            errors.append(f"Empty content wrong error: {type(e).__name__}")
        
        # Invalid importance
        try:
            mem.remember("Negative importance test", importance=-0.5)
            warnings.append("Negative importance should be rejected")
        except ValueError:
            metrics["negative_importance"] = "correctly_rejected"
        except Exception as e:
            errors.append(f"Negative importance error: {e}")
        
        try:
            mem.remember("Huge importance test", importance=2.0)
            warnings.append("Huge importance should be rejected or clamped")
        except ValueError:
            metrics["huge_importance"] = "correctly_rejected"
        except Exception as e:
            errors.append(f"Huge importance error: {e}")
        
        # Special characters
        try:
            special_content = "🎉 Emoji test, 中文测试, 日本語"
            mem.remember(special_content, category="special")
            metrics["special_chars"] = "accepted"
        except Exception as e:
            errors.append(f"Special chars failed: {e}")
        
        # Non-existent memory operations
        try:
            found = mem.get_memory("non_existent_memory_id_12345")
            metrics["non_existent_get"] = "handled_ok" if found is None else "returned_something"
        except Exception as e:
            errors.append(f"Non-existent get failed: {e}")
        
        try:
            deleted = mem.delete_memory("non_existent_memory_id_12345")
            metrics["non_existent_delete"] = "handled_ok"
        except Exception as e:
            errors.append(f"Non-existent delete failed: {e}")
        
        # Invalid top_k
        try:
            mem.recall("test", top_k=-1)
            warnings.append("Negative top_k should be rejected")
        except ValueError:
            metrics["negative_top_k"] = "correctly_rejected"
        except Exception as e:
            errors.append(f"Negative top_k error: {e}")
        
        mem.close()
        
    except Exception as e:
        errors.append(f"Unexpected error in edge cases: {e}")
        import traceback
        errors.append(f"Stack trace: {traceback.format_exc()}")
    
    return len(errors) == 0, errors + warnings, metrics


def test_conversation_history() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Test 5: Conversation history and working memory"""
    errors = []
    warnings = []
    metrics = {}
    
    try:
        config = AgentMemoryConfig(
            short_term={"working_memory_capacity": 10, "history_limit": 100},
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            structured_store={"db_path": ":memory:", "enabled": True},
        )
        mem = AgentMemory(config=config)
        
        # Simulate a conversation
        conversation = [
            ("user", "Hello, I want to learn about AI"),
            ("assistant", "Great! I can help you with that. What do you want to know?"),
            ("user", "What is machine learning?", True),  # Important
            ("assistant", "Machine learning is a subset of AI that enables systems to learn"),
            ("user", "Tell me about neural networks", True),  # Important
            ("assistant", "Neural networks are computational models inspired by the brain"),
        ]
        
        for speaker, content, *important in conversation:
            is_important = important[0] if important else False
            try:
                mem.remember_conversation(
                    content=content,
                    speaker=speaker,
                    important=is_important
                )
            except Exception as e:
                errors.append(f"remember_conversation failed: {e}")
        
        # Get conversation history
        try:
            history = mem.get_conversation_history(n=10)
            metrics["history_count"] = len(history)
        except Exception as e:
            errors.append(f"get_conversation_history failed: {e}")
        
        # Add to working memory
        try:
            mem.add_to_working_memory(
                key="current_topic",
                content="Neural networks and machine learning",
                importance=0.8,
                memory_type="topic"
            )
            metrics["working_memory_added"] = True
        except Exception as e:
            errors.append(f"add_to_working_memory failed: {e}")
        
        # Get relevant context
        try:
            context = mem.get_relevant_context("AI", max_items=5)
            metrics["context_generated"] = len(context) > 0
        except Exception as e:
            errors.append(f"get_relevant_context failed: {e}")
        
        mem.close()
        
    except Exception as e:
        errors.append(f"Unexpected error in conversation: {e}")
        import traceback
        errors.append(f"Stack trace: {traceback.format_exc()}")
    
    return len(errors) == 0, errors + warnings, metrics


def test_batch_operations() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Test 6: Batch operations"""
    errors = []
    warnings = []
    metrics = {}
    
    try:
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            )
        )
        mem = AgentMemory(config=config)
        
        # Batch remember
        batch_items = []
        for i in range(50):
            batch_items.append({
                "content": f"Batch memory {i}: {random.randint(1, 100000)}",
                "category": "batch_test",
                "importance": 0.3 + (i % 5) * 0.1
            })
        
        start_time = time.time()
        try:
            result = mem.batch_remember(batch_items)
            metrics["batch_remember_success"] = result.get("success", 0)
            metrics["batch_remember_failed"] = result.get("failed", 0)
            metrics["batch_remember_time"] = time.time() - start_time
            
            if result.get("errors"):
                for e in result.get("errors", [])[:3]:
                    warnings.append(f"Batch error: {e}")
        except Exception as e:
            errors.append(f"batch_remember failed: {e}")
        
        # Get all memories
        try:
            all_memories = mem.get_all_memories(limit=200)
            metrics["total_after_batch"] = len(all_memories)
        except Exception as e:
            warnings.append(f"get_all_memories failed: {e}")
        
        mem.close()
        
    except Exception as e:
        errors.append(f"Unexpected error in batch ops: {e}")
        import traceback
        errors.append(f"Stack trace: {traceback.format_exc()}")
    
    return len(errors) == 0, errors + warnings, metrics


def test_memory_consolidation() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Test 7: Memory consolidation"""
    errors = []
    warnings = []
    metrics = {}
    
    try:
        config = AgentMemoryConfig(
            short_term={"working_memory_capacity": 20, "history_limit": 50},
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            consolidation_threshold=0.6,
            auto_consolidate=False,
        )
        mem = AgentMemory(config=config)
        
        # Add working memories with varying importance
        working_items = [
            ("item1", "Low importance item", 0.3),
            ("item2", "Medium importance item", 0.5),
            ("item3", "High importance item 1", 0.8),
            ("item4", "High importance item 2", 0.9),
        ]
        
        for key, content, imp in working_items:
            try:
                mem.add_to_working_memory(
                    key=key,
                    content=content,
                    importance=imp,
                    memory_type="test"
                )
            except Exception as e:
                errors.append(f"add_to_working_memory failed: {e}")
        
        # Execute consolidation
        try:
            consolidate_result = mem.consolidate()
            metrics["consolidated"] = consolidate_result.get("consolidated", 0)
            metrics["skipped"] = consolidate_result.get("skipped", 0)
        except Exception as e:
            errors.append(f"consolidate failed: {e}")
        
        mem.close()
        
    except Exception as e:
        errors.append(f"Unexpected error in consolidation: {e}")
        import traceback
        errors.append(f"Stack trace: {traceback.format_exc()}")
    
    return len(errors) == 0, errors + warnings, metrics


def main():
    print("=" * 80)
    print("AGENT MEMORY SYSTEM - REAL-WORLD COMPREHENSIVE TEST")
    print("=" * 80)
    
    tests = [
        ("Basic Memory Operations", test_basic_memory_operations),
        ("Knowledge Graph", test_knowledge_graph),
        ("Concurrent Operations", test_concurrent_operations),
        ("Edge Cases", test_edge_cases),
        ("Conversation History", test_conversation_history),
        ("Batch Operations", test_batch_operations),
        ("Memory Consolidation", test_memory_consolidation),
    ]
    
    all_results = []
    total_start = time.time()
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 80}")
        print(f"TEST: {test_name}")
        print(f"{'=' * 80}")
        
        passed, messages, metrics = test_func()
        all_results.append((test_name, passed, messages, metrics))
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status}")
        
        if metrics:
            print("\nMetrics:")
            for k, v in metrics.items():
                print(f"  - {k}: {v}")
        
        if messages:
            print(f"\nMessages ({len(messages)}):")
            for msg in messages:
                print(f"  - {msg}")
    
    total_time = time.time() - start_time if 'start_time' in locals() else 0
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    
    passed_count = sum(1 for _, p, _, _ in all_results if p)
    total_count = len(all_results)
    
    print(f"\nTotal Tests: {total_count}")
    print(f"Passed: {passed_count}/{total_count}")
    print(f"Total Time: {total_time:.2f}s")
    
    print("\nDetailed Results:")
    for name, passed, messages, _ in all_results:
        status = "✅" if passed else "❌"
        msg_count = len(messages)
        print(f"  {status} {name} - {msg_count} messages")
    
    # All errors and warnings
    all_messages = []
    for name, _, messages, _ in all_results:
        for msg in messages:
            all_messages.append(f"[{name}] {msg}")
    
    if all_messages:
        print(f"\nAll Messages ({len(all_messages)}):")
        for msg in all_messages:
            print(f"  - {msg}")
    
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
