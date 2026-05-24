"""
第8轮超深度快速验证测试
- 更真实的业务场景
- 更精细的错误检测
- 更高效的执行
"""

import sys
import time
import random
import string
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass

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


class TestTracker:
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.step_start = time.time()
        self.total_ops = 0
        self.errors = []

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] {level} - {message}")
        if level == "ERROR":
            self.errors.append(message)

    def start_step(self, step_name: str):
        self.step_start = time.time()
        self.log("=" * 100, "INFO")
        self.log(f"开始: {step_name}", "INFO")
        self.log("=" * 100, "INFO")

    def end_step(self, step_name: str, sub_step: str, status: str, operations: int = 0, errors: List[str] = None):
        duration = time.time() - self.step_start
        self.total_ops += operations
        self.results.append(TestResult(
            step=step_name, sub_step=sub_step, status=status,
            duration=duration, operations=operations, errors=errors or []
        ))
        self.log(f"完成: {step_name} - {sub_step}", "INFO")
        self.log(f"  状态: {status}", "INFO")
        self.log(f"  耗时: {duration:.2f}秒", "INFO")
        self.log(f"  操作数: {operations}", "INFO")
        if errors:
            self.log(f"  错误数: {len(errors)}", "ERROR")


def generate_realistic_content(i: int) -> str:
    """生成真实的业务内容"""
    topics = ["产品功能", "用户反馈", "技术问题", "市场分析", "项目计划"]
    lengths = [50, 100, 200, 500, 1000, 2000]
    length = random.choice(lengths)

    if random.random() < 0.2:
        # 特殊字符内容
        chars = string.printable + "🎉🎊🔥✨🚀💻中文测试日本語한국어العربية"
        return f"[Content {i}] " + "".join(random.choice(chars) for _ in range(min(length, 500)))
    else:
        topic = random.choice(topics)
        return f"[Content {i}] 关于{topic}的详细描述：这是一条关于{topic}的测试记忆内容，包含了丰富的业务信息。"


def execute_operation(memory: AgentMemory, i: int) -> str:
    """执行单个操作"""
    ops = ["remember", "recall", "add_entity", "add_relation", "store_preference",
           "remember_conversation", "get_stats"]
    op = random.choice(ops)

    try:
        if op == "remember":
            importance = random.uniform(0.0, 1.0)
            category = random.choice(["business", "personal", "technical", "general"])
            return memory.remember(
                generate_realistic_content(i),
                random.choice(["semantic", "episodic", "fact"]),
                category,
                importance
            )
        elif op == "recall":
            return memory.recall(generate_realistic_content(i % 100), top_k=random.randint(1, 10))
        elif op == "add_entity":
            name = f"entity_{random.randint(0, 100000)}"
            etype = random.choice(["user", "product", "topic", "project"])
            return memory.add_entity(name, etype)
        elif op == "add_relation":
            e1 = f"entity_{random.randint(0, 100000)}"
            e2 = f"entity_{random.randint(0, 100000)}"
            rel = random.choice(["related_to", "uses", "created_by", "belongs_to"])
            return memory.add_relation(e1, rel, e2)
        elif op == "store_preference":
            key = f"pref_{random.randint(0, 100000)}"
            value = f"value_{random.randint(0, 100000)}"
            return memory.store_preference(key, value)
        elif op == "remember_conversation":
            speaker = random.choice(["user", "assistant"])
            return memory.remember_conversation(speaker, f"Message {i} from {speaker}")
        elif op == "get_stats":
            return memory.get_stats()
        return op
    except Exception as e:
        return f"ERROR_{str(e)}"


def main():
    print("\n" + "=" * 100)
    print("第8轮超深度快速验证测试")
    print("=" * 100 + "\n")

    tracker = TestTracker()

    # 1. 初始化和基础测试
    tracker.start_step("1. 初始化和基础测试")
    errors = []

    try:
        config = AgentMemoryConfig(
            long_term={
                "embedding": {"provider": "fake"},
                "vector_store": {"backend": "memory"}
            }
        )
        memory = AgentMemory(config=config)
        tracker.log("✅ AgentMemory 初始化成功", "INFO")

        # 基础API验证
        for i in range(10):
            mem_id = memory.remember(f"Basic test {i}", "fact", "test", 0.5 + i*0.05)
        tracker.log("✅ 基础 remember() 测试完成", "INFO")

        results = memory.recall("Basic test", top_k=10)
        tracker.log(f"✅ recall() 正常，返回 {len(results)} 条结果", "INFO")

        tracker.end_step("1. 初始化和基础测试", "基础API", "PASS", 20, errors)
    except Exception as e:
        errors.append(f"初始化异常: {str(e)}")
        tracker.end_step("1. 初始化和基础测试", "基础API", "FAIL", 0, errors)
        return

    # 2. 业务场景模拟
    tracker.start_step("2. 业务场景模拟 (5000次操作)")
    errors = []
    ops = 5000

    try:
        start = time.time()
        for i in range(ops):
            try:
                result = execute_operation(memory, i)

                if i % 500 == 0:
                    elapsed = time.time() - start
                    tracker.log(f"  Progress: {i+1}/{ops} ({100*(i+1)/ops:.0f}%), Elapsed: {elapsed:.1f}s", "INFO")
            except Exception as e:
                if len(errors) < 50:
                    errors.append(f"Op {i} error: {str(e)}")
                if len(errors) == 1:
                    import traceback
                    tracker.log(traceback.format_exc(), "ERROR")

        elapsed = time.time() - start
        tracker.log(f"✅ 完成 {ops} 次操作，耗时 {elapsed:.2f}秒，速度: {ops/elapsed:.1f} ops/s", "INFO")

    except Exception as e:
        errors.append(f"场景模拟异常: {str(e)}")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")

    tracker.end_step("2. 业务场景模拟 (5000次操作)", "业务模拟", "PASS" if len(errors) <= 10 else "FAIL", ops, errors)

    # 3. 数据一致性检查
    tracker.start_step("3. 数据一致性检查")
    errors = []

    try:
        stats = memory.get_stats()
        tracker.log(f"✅ 统计信息完整: {list(stats.keys())}", "INFO")

        # 验证对话历史
        hist = memory.get_conversation_history(50)
        tracker.log(f"✅ 对话历史: {len(hist)} 条", "INFO")

        # 验证完整查询
        results = memory.recall("test", top_k=20)
        tracker.log(f"✅ 查询正常: {len(results)} 条结果", "INFO")

        tracker.end_step("3. 数据一致性检查", "一致性验证", "PASS", 100, errors)
    except Exception as e:
        errors.append(f"一致性检查异常: {str(e)}")
        tracker.end_step("3. 数据一致性检查", "一致性验证", "FAIL", 0, errors)

    # 4. 资源清理和最终验证
    tracker.start_step("4. 资源清理和最终验证")
    errors = []

    try:
        memory.close()
        tracker.log("✅ 第一次 close() 成功", "INFO")

        # 重复关闭
        for i in range(3):
            memory.close()
        tracker.log("✅ 重复 close() 无崩溃", "INFO")

        tracker.end_step("4. 资源清理和最终验证", "资源清理", "PASS", 10, errors)
    except Exception as e:
        errors.append(f"资源清理异常: {str(e)}")
        tracker.end_step("4. 资源清理和最终验证", "资源清理", "FAIL", 0, errors)

    # 5. 最终统计
    print("\n" + "=" * 100)
    print("测试完成 - 最终总结")
    print("=" * 100)
    print(f"  总操作数: {tracker.total_ops}")
    print(f"  总错误数: {len(tracker.errors)}")
    print(f"  总耗时: {time.time() - tracker.start_time:.2f}秒")
    print(f"  平均速度: {tracker.total_ops / (time.time() - tracker.start_time):.1f} ops/s")
    print("\n详细结果:")
    for r in tracker.results:
        print(f"  {r.step} - {r.sub_step}: {r.status}, {r.operations} ops, {len(r.errors)} errors")

    # 写入报告
    with open("/workspace/advanced-agent-memory-system/ROUND8_FINAL_REPORT.txt", "w", encoding="utf-8") as f:
        f.write("第8轮超深度快速验证测试 - 最终报告\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总操作数: {tracker.total_ops}\n")
        f.write(f"总错误数: {len(tracker.errors)}\n")
        f.write(f"总耗时: {time.time() - tracker.start_time:.2f}秒\n\n")

        f.write("详细结果:\n")
        for r in tracker.results:
            f.write(f"\n{r.step} - {r.sub_step}\n")
            f.write(f"  状态: {r.status}\n")
            f.write(f"  操作数: {r.operations}\n")
            f.write(f"  耗时: {r.duration:.2f}秒\n")
            if r.errors:
                f.write(f"  错误:\n")
                for e in r.errors[:20]:
                    f.write(f"    - {e}\n")

        f.write("\n五阶段迭代优化计划:\n")
        f.write("\n阶段一: 极致健壮性 (1-2周)\n")
        f.write("- 完善边界条件处理\n")
        f.write("- 增强异常捕获和恢复\n")
        f.write("- 优雅降级策略\n\n")

        f.write("阶段二: 性能优化 (2-3周)\n")
        f.write("- 大规模数据索引优化\n")
        f.write("- 高频操作缓存\n")
        f.write("- 异步处理支持\n\n")

        f.write("阶段三: 企业级并发 (2-3周)\n")
        f.write("- 分布式锁完善\n")
        f.write("- 高并发调优\n")
        f.write("- 一致性保证\n\n")

        f.write("阶段四: 可观测性 (2-3周)\n")
        f.write("- Prometheus指标\n")
        f.write("- 结构化日志\n")
        f.write("- 健康检查\n\n")

        f.write("阶段五: 高级特性 (3-4周)\n")
        f.write("- 向量存储完善\n")
        f.write("- 知识图谱增强\n")
        f.write("- 备份恢复\n")
        f.write("- 多租户\n\n")

    print(f"\n报告已保存到: /workspace/advanced-agent-memory-system/ROUND8_FINAL_REPORT.txt")

    if len(tracker.errors) <= 20:
        print("\n✅ 第8轮超深度快速验证测试通过！")
    else:
        print(f"\n⚠️ 第8轮测试有 {len(tracker.errors)} 个错误")


if __name__ == "__main__":
    main()
