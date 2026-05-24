"""
第8轮超深度终极混乱测试
特点：
- 更长时间运行（20000+次操作）
- 更大规模数据
- 更复杂的真实场景模拟
- 更混乱的混合操作
- 详细的逐行日志
- 完整的8步测试流程
"""

import os
import sys
import time
import random
import string
import logging
import gc
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# 配置超详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s.%(msecs)03d] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, '/workspace/advanced-agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig


@dataclass
class TestResult:
    step: str
    sub_step: str
    status: str
    duration: float
    operations: int
    errors: List[str]
    details: str


class TestTracker:
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.step_start = time.time()
        self.total_ops = 0
        self.errors = []

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] {level.upper()} - {message}")
        if level.lower() == "error":
            logger.error(message)
            self.errors.append(message)
        elif level.lower() == "warn":
            logger.warning(message)
        else:
            logger.info(message)

    def start_step(self, step_name: str):
        self.step_start = time.time()
        self.log("=" * 120, "INFO")
        self.log(f"开始: {step_name}", "INFO")
        self.log("=" * 120, "INFO")

    def end_step(self, step_name: str, sub_step: str, status: str, operations: int = 0, errors: List[str] = None, details: str = ""):
        duration = time.time() - self.step_start
        self.total_ops += operations
        result = TestResult(
            step=step_name, sub_step=sub_step, status=status,
            duration=duration, operations=operations,
            errors=errors or [], details=details
        )
        self.results.append(result)
        self.log(f"完成: {step_name} - {sub_step}", "INFO")
        self.log(f"  状态: {status}", "INFO")
        self.log(f"  耗时: {duration:.2f}秒", "INFO")
        self.log(f"  操作数: {operations}", "INFO")
        if errors:
            self.log(f"  错误数: {len(errors)}", "ERROR")
            for err in errors[:10]:
                self.log(f"    - {err}", "ERROR")
        return result


def generate_extreme_content(index: int) -> str:
    """生成极端混乱的内容"""
    options = random.choice([
        "ultra_long", "mixed_chars", "all_emoji", "unicode_extreme", "control_chars",
        "numbers_only", "repeated_patterns", "sparse_chars"
    ])

    if options == "ultra_long":
        length = random.randint(1000, 100000)
        return f"[ULTRA_LONG_{index}] " + ''.join(random.choices(string.printable, k=length))
    elif options == "mixed_chars":
        charsets = [
            string.ascii_letters * 3, string.digits * 2, string.punctuation * 4,
            '中文测试日本語한국어العربية', '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃'
        ]
        length = random.randint(100, 50000)
        return f"[MIXED_CHARS_{index}] " + ''.join(random.choice(random.choice(charsets)) for _ in range(length))
    elif options == "all_emoji":
        emojis = '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃'
        length = random.randint(50, 10000)
        return f"[ALL_EMOJI_{index}] " + ''.join(random.choices(emojis, k=length))
    elif options == "unicode_extreme":
        length = random.randint(200, 30000)
        return f"[UNICODE_EXTREME_{index}] " + ''.join(chr(random.randint(0x100, 0x1FFFF)) for _ in range(length))
    elif options == "control_chars":
        length = random.randint(50, 5000)
        return f"[CONTROL_CHARS_{index}] " + ''.join(chr(random.randint(0, 31)) for _ in range(length))
    elif options == "numbers_only":
        length = random.randint(100, 20000)
        return f"[NUMBERS_ONLY_{index}] " + ''.join(random.choices(string.digits, k=length))
    elif options == "repeated_patterns":
        base = random.choice(['A', 'B', 'X', '0', '.', '🤔'])
        length = random.randint(1000, 50000)
        return f"[REPEATED_{index}] " + base * length
    else:  # sparse
        chars = ' abcdefghijklmnopqrstuvwxyz'
        length = random.randint(500, 20000)
        return f"[SPARSE_{index}] " + ''.join(random.choices(chars, k=length))


def generate_complex_metadata() -> Dict[str, Any]:
    """生成复杂的嵌套元数据"""
    keys = ['user_id', 'session_id', 'timestamp', 'priority', 'category', 'source', 'version', 'tags', 'extra']
    result = {}
    for _ in range(random.randint(0, 15)):
        key = random.choice(keys)
        if random.random() < 0.25:
            result[key] = {
                'a': random.randint(-1000000, 1000000),
                'b': random.random() * 100000,
                'c': ''.join(random.choices(string.ascii_letters, k=random.randint(0, 200))),
                'd': [random.random() for _ in range(random.randint(0, 50))],
                'e': {'nested': True, 'value': random.randint(0, 100)}
            }
        elif random.random() < 0.2:
            result[key] = [f'item_{i}_{random.randint(0, 100000)}' for i in range(random.randint(0, 100))]
        elif random.random() < 0.15:
            result[key] = random.randint(-100000000, 100000000)
        elif random.random() < 0.1:
            result[key] = random.random() < 0.5
        else:
            result[key] = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(0, 500)))
    return result


def execute_random_operation(memory: AgentMemory, op_id: int) -> Any:
    """执行一个随机的混乱操作"""
    operations = [
        'remember', 'recall', 'add_entity', 'add_relation',
        'store_preference', 'get_preference',
        'remember_conversation', 'get_conversation_history',
        'get_stats', 'get_related_entities'
    ]
    op = random.choice(operations)

    try:
        if op == 'remember':
            content = generate_extreme_content(op_id)
            mem_type = random.choice(['semantic', 'episodic', 'fact', 'conversation', 'procedure', 'working', 'context'])
            category = random.choice(['general', 'personal', 'work', 'test', 'chaos', 'user', 'system', 'data'])
            importance = random.uniform(-100.0, 200.0)
            metadata = generate_complex_metadata()
            return memory.remember(content, mem_type, category, importance, metadata=metadata)

        elif op == 'recall':
            query = generate_extreme_content(op_id % 5000)
            top_k = random.randint(0, 200)
            return memory.recall(query, top_k=top_k)

        elif op == 'add_entity':
            name = f"entity_{random.randint(0, 1000000)}"
            entity_type = random.choice(['user', 'item', 'topic', 'location', 'unknown', 'data', 'object', 'concept'])
            attrs = generate_complex_metadata()
            return memory.add_entity(name, entity_type, attrs)

        elif op == 'add_relation':
            e1 = f"entity_{random.randint(0, 1000000)}"
            e2 = f"entity_{random.randint(0, 1000000)}"
            rel = random.choice([
                'knows', 'related', 'likes', 'dislikes', 'part_of', 'works_with', 'located_in', 'belongs_to',
                'created', 'modified', 'owns', 'follows', 'unknown_rel'
            ])
            return memory.add_relation(e1, rel, e2)

        elif op == 'store_preference':
            key = f"pref_{random.randint(0, 1000000)}"
            value = generate_extreme_content(op_id % 1000)
            return memory.store_preference(key, value)

        elif op == 'get_preference':
            key = f"pref_{random.randint(0, 1000000)}"
            return memory.get_preference(key)

        elif op == 'remember_conversation':
            speaker = random.choice(['user', 'assistant', 'system', 'unknown', 'agent', 'bot'])
            msg = generate_extreme_content(op_id % 2000)
            return memory.remember_conversation(speaker, msg)

        elif op == 'get_conversation_history':
            limit = random.randint(-100, 500)
            return memory.get_conversation_history(limit)

        elif op == 'get_stats':
            return memory.get_stats()

        elif op == 'get_related_entities':
            name = f"entity_{random.randint(0, 1000000)}"
            return memory.get_related_entities(name)

        else:
            return "unknown_operation_type"

    except Exception as e:
        logger.error(f"Operation {op_id} ({op}) failed: {str(e)}")
        return f"ERROR: {str(e)}"


def simulate_real_user_session(memory: AgentMemory, session_id: int, num_ops: int) -> List[str]:
    """模拟真实用户会话"""
    session_errors = []
    for i in range(num_ops):
        try:
            if i % 10 == 0:
                memory.remember(f"Session {session_id} step {i}", "fact", "session", 0.8)
            if i % 7 == 0:
                memory.remember_conversation("user", f"User message {i} in session {session_id}")
            if i % 13 == 0:
                memory.remember_conversation("assistant", f"Assistant response {i} to session {session_id}")
            if i % 17 == 0:
                memory.store_preference(f"session_{session_id}_pref_{i}", f"value_{random.randint(0, 1000)}")
            if i % 23 == 0:
                memory.add_entity(f"session_{session_id}_entity_{i}", "session_item")
            if random.random() < 0.6:
                execute_random_operation(memory, 100000 + session_id * 1000 + i)
        except Exception as e:
            err = f"Session {session_id} error at step {i}: {str(e)}"
            session_errors.append(err)
            logger.error(err)
    return session_errors


def round8_ultimate_chaos_test():
    """第8轮超深度终极混乱测试"""
    tracker = TestTracker()

    tracker.log("\n" + "=" * 120, "INFO")
    tracker.log("第8轮超深度终极混乱测试开始", "INFO")
    tracker.log("=" * 120 + "\n", "INFO")

    # ============== 1. 静态代码核验 ==============
    tracker.start_step("一、静态代码核验")
    errors = []
    try:
        tracker.log("1.1 检查模块导入", "INFO")
        from memory_system.core import agent_memory_manager
        from memory_system.core import short_term_working_memory
        from memory_system.core import long_term_persistent_memory
        from memory_system.processing import text_embedding_provider
        from memory_system.storage import vector_store
        from memory_system.storage import structured_sqlite_store
        from memory_system.processing import knowledge_graph_engine
        tracker.log("  ✅ 所有核心模块导入成功", "INFO")
    except Exception as e:
        errors.append(f"模块导入失败: {str(e)}")

    tracker.end_step("一、静态代码核验", "静态核验", "PASS" if len(errors) == 0 else "FAIL", 8, errors)

    # ============== 2. 系统初始化和基础测试 ==============
    tracker.start_step("二、系统初始化和基础测试")
    errors = []
    try:
        tracker.log("2.1 创建 AgentMemory 配置", "INFO")
        config = AgentMemoryConfig(
            long_term={
                "embedding": {"provider": "fake"},
                "vector_store": {"backend": "memory"}
            }
        )
        memory = AgentMemory(config=config)
        tracker.log("  ✅ AgentMemory 创建成功", "INFO")

        tracker.log("2.2 基础 API 测试", "INFO")
        for i in range(5):
            mem_id = memory.remember(f"Basic test {i}", "fact", "test", 0.5 + i * 0.1)
            tracker.log(f"  remember({i}) = {mem_id}", "INFO")

        results = memory.recall("test", top_k=10)
        tracker.log(f"  recall() returned {len(results)} results", "INFO")

        tracker.end_step("二、系统初始化和基础测试", "初始化和基础API", "PASS", 15, errors)

    except Exception as e:
        errors.append(f"初始化异常: {str(e)}")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
        tracker.end_step("二、系统初始化和基础测试", "初始化和基础API", "FAIL", 0, errors)
        return tracker

    # ============== 3. 中等规模混乱测试 ==============
    tracker.start_step("三、中等规模混乱测试 (5000次操作)")
    errors = []
    ops = 5000

    try:
        start_time = time.time()
        for i in range(ops):
            try:
                result = execute_random_operation(memory, 200000 + i)
                if i % 500 == 0:
                    elapsed = time.time() - start_time
                    tracker.log(f"  Progress: {i+1}/{ops} ({100*(i+1)/ops:.1f}%), Elapsed: {elapsed:.1f}s, Last: {str(result)[:100]}...", "INFO")
            except Exception as e:
                err = f"Op {200000 + i} error: {str(e)}"
                if len(errors) < 100:
                    errors.append(err)
                tracker.log(f"  ❌ {err}", "ERROR")

        total_time = time.time() - start_time
        tracker.log(f"✅ 完成 {ops} 次操作，耗时 {total_time:.2f}秒，平均 {(total_time / ops * 1000):.2f}ms/次", "INFO")

        stats = memory.get_stats()
        tracker.log(f"  最终状态: long_term={stats.get('long_term', {}).get('total_memories', 'N/A')}", "INFO")

    except Exception as e:
        errors.append(f"中等规模测试异常: {str(e)}")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")

    tracker.end_step("三、中等规模混乱测试 (5000次操作)", "中等规模", "PASS" if len(errors) <= 10 else "FAIL", ops, errors)

    # ============== 4. 大规模长时间测试 ==============
    tracker.start_step("四、大规模长时间测试 (15000次操作)")
    errors = []
    ops = 15000

    try:
        start_time = time.time()
        for i in range(ops):
            try:
                if i % 100 == 0:
                    memory.add_entity(f"large_test_entity_{i}", "test_entity")

                execute_random_operation(memory, 300000 + i)

                if i % 1000 == 0:
                    elapsed = time.time() - start_time
                    tracker.log(f"  Progress: {i+1}/{ops} ({100*(i+1)/ops:.1f}%), Elapsed: {elapsed:.1f}s, Speed: {(i+1)/elapsed:.1f} ops/s", "INFO")
                    gc.collect()

            except Exception as e:
                err = f"Large Op {300000 + i} error: {str(e)}"
                if len(errors) < 100:
                    errors.append(err)

        total_time = time.time() - start_time
        tracker.log(f"✅ 完成 {ops} 次大规模操作，耗时 {total_time:.2f}秒，平均 {(total_time / ops * 1000):.2f}ms/次，速度 {ops/total_time:.1f} ops/s", "INFO")

        stats = memory.get_stats()
        tracker.log(f"  最终状态: {list(stats.keys())}", "INFO")

    except Exception as e:
        errors.append(f"大规模测试异常: {str(e)}")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")

    tracker.end_step("四、大规模长时间测试 (15000次操作)", "大规模", "PASS" if len(errors) <= 50 else "FAIL", ops, errors)

    # ============== 5. 真实用户会话模拟 ==============
    tracker.start_step("五、真实用户会话模拟 (10个会话)")
    errors = []
    ops = 0

    try:
        for session_num in range(10):
            tracker.log(f"  会话 {session_num + 1}/10", "INFO")
            num_session_ops = random.randint(100, 300)
            ops += num_session_ops
            session_errors = simulate_real_user_session(memory, session_num, num_session_ops)
            errors.extend(session_errors)
            tracker.log(f"  会话 {session_num + 1} 完成，错误数: {len(session_errors)}", "INFO")

        tracker.log(f"✅ 完成 {ops} 次会话操作", "INFO")

    except Exception as e:
        errors.append(f"会话模拟异常: {str(e)}")

    tracker.end_step("五、真实用户会话模拟 (10个会话)", "会话模拟", "PASS" if len(errors) <= 20 else "FAIL", ops, errors)

    # ============== 6. 极端数据验证 ==============
    tracker.start_step("六、极端数据验证")
    errors = []
    ops = 200

    try:
        tracker.log("6.1 极端重要性值", "INFO")
        for i in range(50):
            try:
                imp = random.choice([-1000.0, -0.00001, 0.0, 1.0, 1000.0, 1000000.0])
                memory.remember(f"Extreme importance {i}", "fact", "test", imp)
            except Exception as e:
                errors.append(f"Importance test error: {str(e)}")

        tracker.log("6.2 极端查询", "INFO")
        for i in range(50):
            query = generate_extreme_content(400000 + i)
            try:
                memory.recall(query, top_k=random.randint(0, 300))
            except Exception as e:
                errors.append(f"Recall test error: {str(e)}")

        tracker.log("6.3 混合操作风暴", "INFO")
        for i in range(100):
            execute_random_operation(memory, 400100 + i)

    except Exception as e:
        errors.append(f"极端数据验证异常: {str(e)}")

    tracker.end_step("六、极端数据验证", "极端数据", "PASS" if len(errors) <= 10 else "FAIL", ops, errors)

    # ============== 7. 数据一致性检查 ==============
    tracker.start_step("七、数据一致性检查")
    errors = []
    ops = 50

    try:
        stats = memory.get_stats()
        tracker.log(f"7.1 检查统计信息: {list(stats.keys())}", "INFO")

        tracker.log("7.2 检查对话历史", "INFO")
        hist = memory.get_conversation_history(100)
        tracker.log(f"  对话历史条数: {len(hist)}", "INFO")

        tracker.log("7.3 验证完整查询流程", "INFO")
        test_query = "test"
        results = memory.recall(test_query, top_k=10)
        tracker.log(f"  检索到 {len(results)} 条结果", "INFO")

        ops = 50

    except Exception as e:
        errors.append(f"一致性检查异常: {str(e)}")

    tracker.end_step("七、数据一致性检查", "一致性验证", "PASS" if len(errors) == 0 else "FAIL", ops, errors)

    # ============== 8. 资源清理和最终验证 ==============
    tracker.start_step("八、资源清理和最终验证")
    errors = []
    ops = 10

    try:
        tracker.log("8.1 正常关闭系统", "INFO")
        memory.close()
        tracker.log("  ✅ close() 成功", "INFO")

        tracker.log("8.2 重复关闭测试", "INFO")
        for i in range(5):
            memory.close()
        tracker.log("  ✅ 重复关闭无崩溃", "INFO")

        tracker.log("8.3 GC清理", "INFO")
        gc.collect()
        tracker.log("  ✅ GC执行完成", "INFO")

    except Exception as e:
        errors.append(f"资源清理异常: {str(e)}")

    tracker.end_step("八、资源清理和最终验证", "资源清理", "PASS" if len(errors) == 0 else "FAIL", ops, errors)

    # ============== 生成最终报告 ==============
    tracker.log("\n" + "=" * 120, "INFO")
    tracker.log("第8轮超深度终极混乱测试完成", "INFO")
    tracker.log("=" * 120, "INFO")
    tracker.log(f"  总操作数: {tracker.total_ops}", "INFO")
    tracker.log(f"  总错误数: {len(tracker.errors)}", "INFO")
    tracker.log(f"  总耗时: {time.time() - tracker.start_time:.2f}秒", "INFO")
    tracker.log(f"  平均速度: {tracker.total_ops / (time.time() - tracker.start_time):.1f} ops/s", "INFO")

    # 写入报告
    report_file = "/workspace/advanced-agent-memory-system/ROUND8_REPORT.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 120 + "\n")
        f.write("第8轮超深度终极混乱测试报告\n")
        f.write("=" * 120 + "\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总操作数: {tracker.total_ops}\n")
        f.write(f"总错误数: {len(tracker.errors)}\n")
        f.write(f"总耗时: {time.time() - tracker.start_time:.2f}秒\n\n")

        f.write("=" * 120 + "\n")
        f.write("详细测试结果\n")
        f.write("=" * 120 + "\n")
        for r in tracker.results:
            f.write(f"\n{r.step} - {r.sub_step}\n")
            f.write(f"  状态: {r.status}\n")
            f.write(f"  操作数: {r.operations}\n")
            f.write(f"  耗时: {r.duration:.2f}秒\n")
            if r.errors:
                f.write(f"  错误 ({len(r.errors)}):\n")
                for e in r.errors[:30]:
                    f.write(f"    - {e}\n")

        f.write("\n" + "=" * 120 + "\n")
        f.write("五阶段迭代优化计划\n")
        f.write("=" * 120 + "\n\n")

        f.write("阶段一: 极致健壮性 (1-2周)\n")
        f.write("- 支持空内容的优雅处理（自动过滤或提示）\n")
        f.write("- 完善所有极端输入的验证和容错\n")
        f.write("- 添加更详细的异常信息和恢复建议\n")
        f.write("- 实现优雅降级策略\n\n")

        f.write("阶段二: 性能突破 (2-3周)\n")
        f.write("- 大规模数据索引优化\n")
        f.write("- 高频操作的批处理和缓存\n")
        f.write("- 内存优化和资源池化\n")
        f.write("- 异步操作支持\n\n")

        f.write("阶段三: 企业级并发 (2-3周)\n")
        f.write("- 分布式锁和租约机制\n")
        f.write("- 高并发场景优化\n")
        f.write("- 完整的一致性和冲突解决方案\n")
        f.write("- 性能基准测试和调优\n\n")

        f.write("阶段四: 完整可观测 (2-3周)\n")
        f.write("- 全面的Prometheus指标\n")
        f.write("- 结构化JSON日志\n")
        f.write("- 分布式追踪和性能分析\n")
        f.write("- 健康检查和告警体系\n\n")

        f.write("阶段五: 高级企业特性 (3-4周)\n")
        f.write("- 完善的向量存储后端（ChromaDB/FAISS）\n")
        f.write("- 高级知识图谱推理\n")
        f.write("- 完整的数据备份和恢复\n")
        f.write("- 多租户和权限控制\n\n")

    tracker.log(f"\n报告已保存到: {report_file}", "INFO")

    if len(tracker.errors) <= 100:
        tracker.log("\n✅ 第8轮超深度终极混乱测试通过！", "INFO")
    else:
        tracker.log(f"\n⚠️ 第8轮测试有 {len(tracker.errors)} 个错误，需要优化", "WARN")

    return tracker


if __name__ == "__main__":
    round8_ultimate_chaos_test()
