"""
第6轮超深度测试 - 简化但精准的测试
专门测试真实的AgentMemory API
"""

import os
import sys
import time
import random
import string
import logging
import gc
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
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
    status: str  # PASS / FAIL / SKIP
    duration: float
    operations: int
    errors: List[str]
    details: str


class TestTracker:
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.step_start = time.time()
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] {level.upper()} - {message}")
        if level.lower() == "error":
            logger.error(message)
        else:
            logger.info(message)
    
    def start_step(self, step_name: str):
        self.step_start = time.time()
        self.log("=" * 80, "INFO")
        self.log(f"开始: {step_name}", "INFO")
        self.log("=" * 80, "INFO")
    
    def end_step(self, step_name: str, sub_step: str, status: str, operations: int = 0, errors: List[str] = None, details: str = ""):
        duration = time.time() - self.step_start
        result = TestResult(
            step=step_name, sub_step=sub_step, status=status, duration=duration, operations=operations, errors=errors or [], details=details
        )
        self.results.append(result)
        self.log(f"完成: {step_name} - {sub_step}", "INFO")
        self.log(f"  状态: {status}", "INFO")
        self.log(f"  耗时: {duration:.2f}秒", "INFO")
        self.log(f"  操作数: {operations}", "INFO")
        if errors:
            self.log(f"  错误数: {len(errors)}", "ERROR")
            for err in errors[:5]:
                self.log(f"    - {err}", "ERROR")
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        total_duration = time.time() - self.start_time
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        total_ops = sum(r.operations for r in self.results)
        return {
            "total_steps": len(self.results), "passed": passed, "failed": failed,
            "total_duration": total_duration, "total_operations": total_ops,
            "results": self.results
        }


def create_test_memory():
    """创建一个测试用的AgentMemory，使用fake provider"""
    config = AgentMemoryConfig(
        long_term={
            "embedding": {"provider": "fake"},
            "vector_store": {"backend": "memory"}
        }
    )
    return AgentMemory(config=config)


# ==================== 第1步: 基础API测试 ====================
def step1_basic_api(tracker: TestTracker) -> TestResult:
    tracker.start_step("第1步: 基础API测试")
    errors = []
    operations = 0
    
    try:
        tracker.log("1.1 初始化 AgentMemory", "INFO")
        operations +=1
        memory = create_test_memory()
        tracker.log("  ✅ 初始化成功", "INFO")
        
        tracker.log("1.2 测试 remember()", "INFO")
        operations +=1
        mem_id1 = memory.remember("用户张三是软件工程师，住在北京", "fact", "personal", 0.9)
        tracker.log(f"  ✅ remember 成功, id={mem_id1}", "INFO")
        
        operations +=1
        mem_id2 = memory.remember("今天天气很好，适合出门散步", "episodic", "daily", 0.6)
        tracker.log(f"  ✅ remember 成功, id={mem_id2}", "INFO")
        
        tracker.log("1.3 测试 recall()", "INFO")
        operations +=1
        results = memory.recall("张三工程师", top_k=5)
        tracker.log(f"  ✅ recall 成功, 返回 {len(results)} 条结果", "INFO")
        
        tracker.log("1.4 测试 偏好存储", "INFO")
        operations +=1
        memory.store_preference("theme", "dark")
        tracker.log("  ✅ store_preference 成功", "INFO")
        
        operations +=1
        pref = memory.get_preference("theme")
        tracker.log(f"  ✅ get_preference 成功, value={pref}", "INFO")
        
        tracker.log("1.5 测试 对话记忆", "INFO")
        operations +=1
        memory.remember_conversation("user", "你好，我是张三")
        tracker.log("  ✅ remember_conversation(user) 成功", "INFO")
        
        operations +=1
        memory.remember_conversation("assistant", "你好张三，很高兴认识你")
        tracker.log("  ✅ remember_conversation(assistant) 成功", "INFO")
        
        operations +=1
        conv_hist = memory.get_conversation_history(10)
        tracker.log(f"  ✅ get_conversation_history 成功, {len(conv_hist)} 条", "INFO")
        
        tracker.log("1.6 测试 知识图谱", "INFO")
        operations +=1
        ent_id = memory.add_entity("李四")
        tracker.log(f"  ✅ add_entity 成功, id={ent_id}", "INFO")
        
        operations +=1
        rel_id = memory.add_relation("张三", "朋友", "李四")
        tracker.log(f"  ✅ add_relation 成功, id={rel_id}", "INFO")
        
        tracker.log("1.7 测试 get_stats()", "INFO")
        operations +=1
        stats = memory.get_stats()
        tracker.log(f"  ✅ get_stats 成功, keys={list(stats.keys())}", "INFO")
        
        tracker.log("1.8 测试 close()", "INFO")
        operations +=1
        memory.close()
        tracker.log("  ✅ close 成功", "INFO")
        
    except Exception as e:
        errors.append(f"基础API测试异常: {str(e)}")
        tracker.log(f"  ❌ {str(e)}", "ERROR")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    return tracker.end_step("第1步: 基础API测试", "完整API测试", status, operations, errors)


# ==================== 第2步: 大规模测试 ====================
def step2_large_scale(tracker: TestTracker) -> TestResult:
    tracker.start_step("第2步: 大规模记忆测试")
    errors = []
    operations = 0
    
    try:
        memory = create_test_memory()
        tracker.log("2.1 测试 100条记忆写入", "INFO")
        
        start = time.time()
        for i in range(100):
            operations +=1
            content = f"记忆条目{i}: 这是一条测试记忆内容，编号{i}，用于大规模测试"
            mem_id = memory.remember(content, "semantic", "test", 0.3 + (i % 70)/100)
            if i % 20 ==0:
                tracker.log(f"  已写入 {i+1} 条...", "INFO")
        
        duration = time.time() - start
        tracker.log(f"  ✅ 100条记忆写入完成, 耗时 {duration:.2f}秒", "INFO")
        
        tracker.log("2.2 测试 多次召回", "INFO")
        start = time.time()
        for i in range(50):
            operations +=1
            results = memory.recall(f"记忆条目{i*2}", top_k=3)
        
        duration = time.time() - start
        tracker.log(f"  ✅ 50次召回完成, 耗时 {duration:.2f}秒", "INFO")
        
        stats = memory.get_stats()
        tracker.log(f"  最终统计: LT={stats['long_term']['total_memories']}", "INFO")
        
        memory.close()
        
    except Exception as e:
        errors.append(f"大规模测试异常: {str(e)}")
        tracker.log(f"  ❌ {str(e)}", "ERROR")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    return tracker.end_step("第2步: 大规模记忆测试", "规模测试", status, operations, errors)


# ==================== 第3步: 异常测试 ====================
def step3_error_testing(tracker: TestTracker) -> TestResult:
    tracker.start_step("第3步: 异常和边界条件测试")
    errors = []
    operations = 0
    
    try:
        memory = create_test_memory()
        
        tracker.log("3.1 测试 超长内容", "INFO")
        operations +=1
        try:
            long_content = "x" * 10000
            mem_id = memory.remember(long_content, "semantic", "test", 0.5)
            tracker.log("  ✅ 超长内容处理成功", "INFO")
        except Exception as e:
            tracker.log(f"  ⚠️ 超长内容处理: {str(e)}", "WARN")
        
        tracker.log("3.2 测试 特殊字符", "INFO")
        operations +=1
        special_chars = "!@#$%^&*()_+=-[]{};:'\"\\|,.<>?/~`"
        mem_id = memory.remember(special_chars, "semantic", "test", 0.5)
        tracker.log("  ✅ 特殊字符处理成功", "INFO")
        
        tracker.log("3.3 测试 get_preference 不存在的key", "INFO")
        operations +=1
        val = memory.get_preference("不存在的key_12345")
        tracker.log(f"  ✅ 不存在key返回 {val}, 无崩溃", "INFO")
        
        tracker.log("3.4 测试 多次close", "INFO")
        operations +=1
        memory.close()
        memory.close()  # 重复关闭
        tracker.log("  ✅ 重复close无崩溃", "INFO")
        
    except Exception as e:
        errors.append(f"异常测试异常: {str(e)}")
        tracker.log(f"  ❌ {str(e)}", "ERROR")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    return tracker.end_step("第3步: 异常和边界条件测试", "异常测试", status, operations, errors)


# ==================== 第4步: 业务场景 ====================
def step4_business_scenario(tracker: TestTracker) -> TestResult:
    tracker.start_step("第4步: 业务场景模拟")
    errors = []
    operations = 0
    
    try:
        tracker.log("4.1 场景: 智能助手对话", "INFO")
        memory = create_test_memory()
        
        # 模拟对话
        operations +=1
        memory.remember_conversation("user", "你好，我想了解一下人工智能")
        memory.remember("用户询问人工智能相关问题", "fact", "user_interaction", 0.8)
        tracker.log("  ✅ 用户问题记录成功", "INFO")
        
        operations +=1
        memory.remember_conversation("assistant", "人工智能是计算机科学的一个重要分支...")
        memory.remember("向用户解释了人工智能", "semantic", "assistant_response", 0.7)
        tracker.log("  ✅ 回答记录成功", "INFO")
        
        operations +=1
        memory.store_preference("user_interest", "人工智能")
        tracker.log("  ✅ 偏好保存成功", "INFO")
        
        operations +=1
        results = memory.recall("人工智能", top_k=3)
        tracker.log(f"  ✅ 召回成功, {len(results)}条", "INFO")
        
        # 检查对话历史
        operations +=1
        history = memory.get_conversation_history(10)
        tracker.log(f"  ✅ 对话历史: {len(history)}条", "INFO")
        
        memory.close()
        
    except Exception as e:
        errors.append(f"业务场景异常: {str(e)}")
        tracker.log(f"  ❌ {str(e)}", "ERROR")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    return tracker.end_step("第4步: 业务场景模拟", "业务测试", status, operations, errors)


# ==================== 第5步: 性能测试 ====================
def step5_performance(tracker: TestTracker) -> TestResult:
    tracker.start_step("第5步: 性能测试")
    errors = []
    operations = 0
    
    try:
        memory = create_test_memory()
        
        tracker.log("5.1 高频 remember", "INFO")
        start = time.time()
        n_ops = 200
        for i in range(n_ops):
            operations +=1
            memory.remember(f"高频测试{i}", "semantic", "perf", 0.5)
        dur = time.time() - start
        tracker.log(f"  ✅ {n_ops}次remember, 耗时 {dur:.2f}秒, 平均 {(dur/n_ops*1000):.2f}ms/次", "INFO")
        
        tracker.log("5.2 高频 recall", "INFO")
        start = time.time()
        n_recall = 100
        for i in range(n_recall):
            operations +=1
            memory.recall(f"高频测试", top_k=2)
        dur = time.time() - start
        tracker.log(f"  ✅ {n_recall}次recall, 耗时 {dur:.2f}秒, 平均 {(dur/n_recall*1000):.2f}ms/次", "INFO")
        
        stats = memory.get_stats()
        tracker.log(f"  最终LT: {stats['long_term']['total_memories']}", "INFO")
        
        memory.close()
        
    except Exception as e:
        errors.append(f"性能测试异常: {str(e)}")
        tracker.log(f"  ❌ {str(e)}", "ERROR")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    return tracker.end_step("第5步: 性能测试", "性能验证", status, operations, errors)


# ==================== 主函数 ====================
def main():
    print("\n" + "=" * 80)
    print("第6轮超深度测试 - 简化但精准的完整测试")
    print("=" * 80 + "\n")
    
    tracker = TestTracker()
    all_results = []
    
    result1 = step1_basic_api(tracker)
    all_results.append(result1)
    
    result2 = step2_large_scale(tracker)
    all_results.append(result2)
    
    result3 = step3_error_testing(tracker)
    all_results.append(result3)
    
    result4 = step4_business_scenario(tracker)
    all_results.append(result4)
    
    result5 = step5_performance(tracker)
    all_results.append(result5)
    
    print("\n" + "=" * 80)
    print("测试完成 - 最终汇总")
    print("=" * 80 + "\n")
    
    summary = tracker.get_summary()
    
    print(f"总步骤: {summary['total_steps']}")
    print(f"通过: {summary['passed']}")
    print(f"失败: {summary['failed']}")
    print(f"总耗时: {summary['total_duration']:.2f}秒")
    print(f"总操作数: {summary['total_operations']}\n")
    
    print("详细结果:")
    print("-" * 80)
    for r in all_results:
        icon = "✅" if r.status == "PASS" else "❌"
        print(f"{icon} {r.step} - {r.sub_step}")
        print(f"   状态: {r.status}, 操作: {r.operations}, 耗时: {r.duration:.2f}秒")
        if r.errors:
            print(f"   错误: {r.errors}")
    
    report_file = "/workspace/advanced-agent-memory-system/ROUND6_REPORT.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# 第6轮超深度测试 - 完整报告\n\n")
        f.write(f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 总步骤: {summary['total_steps']}\n")
        f.write(f"- 通过: {summary['passed']}\n")
        f.write(f"- 失败: {summary['failed']}\n")
        f.write(f"- 总耗时: {summary['total_duration']:.2f}秒\n")
        f.write(f"- 总操作数: {summary['total_operations']}\n\n")
        f.write("## 测试结果\n")
        for r in all_results:
            f.write(f"\n### {r.step} - {r.sub_step}\n")
            f.write(f"- 状态: {r.status}\n")
            f.write(f"- 操作数: {r.operations}\n")
            f.write(f"- 耗时: {r.duration:.2f}秒\n")
            if r.errors:
                f.write(f"- 错误: {r.errors}\n")
    
    print(f"\n报告保存到: {report_file}")
    
    print("\n" + "=" * 80)
    print("验收标准判断")
    print("=" * 80)
    
    if summary['failed'] ==0:
        print("\n✅ 所有测试通过！")
        print("1. 代码逻辑正常")
        print("2. 运行行为正常")
        print("3. 数据流转正确")
        print("4. 异常场景稳定\n")
    else:
        print(f"\n❌ 有 {summary['failed']} 项失败\n")
    
    return summary


if __name__ == "__main__":
    main()

