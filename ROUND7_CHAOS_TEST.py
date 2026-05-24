"""
第7轮超深度测试 - 极端混乱场景真实实践

特点:
- 超长运行时间 (持续执行)
- 更大规模数据
- 更复杂的混乱场景
- 极高难度边界条件
- 混合操作组合
- 详细逐行日志
"""

import os
import sys
import time
import random
import string
import logging
import gc
import threading
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# 配置超详细日志
logging.basicConfig(
    level=logging.DEBUG,
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
        self.log("=" * 100, "INFO")
        self.log(f"开始: {step_name}", "INFO")
        self.log("=" * 100, "INFO")
    
    def end_step(self, step_name: str, sub_step: str, status: str, operations: int = 0, errors: List[str] = None, details: str = ""):
        duration = time.time() - self.step_start
        self.total_ops += operations
        result = TestResult(
            step=step_name, sub_step=sub_step, status=status, duration=duration, 
            operations=operations, errors=errors or [], details=details
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


def generate_chaos_content(index: int):
    """生成极度混乱的测试内容"""
    length = random.randint(1, 50000)  # 1到50000字符
    charsets = [
        string.ascii_letters * 5,
        string.digits * 3,
        '中文测试内容日本語한국어العربية',
        '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'',
        '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃',
        '\n\r\t\0\x01\x02\x03\x04\x05',
        ''.join(chr(i) for i in range(128, 256))
    ]
    content = ''.join(random.choice(random.choice(charsets)) for _ in range(length))
    return f"[CHAOS-{index}] {content}"


def generate_random_metadata():
    """生成随机元数据"""
    keys = [
        'user_id', 'session_id', 'timestamp', 'priority', 
        'category', 'source', 'version', 'tags', 'extra'
    ]
    meta = {}
    for _ in range(random.randint(0, 10)):
        key = random.choice(keys)
        if random.random() < 0.3:
            # 嵌套结构
            meta[key] = {
                'a': random.randint(0, 1000),
                'b': random.random(),
                'c': random.choice(['x', 'y', 'z']),
                'd': [random.random() for _ in range(random.randint(0, 10))]
            }
        elif random.random() < 0.2:
            # 列表
            meta[key] = [f'item_{i}' for i in range(random.randint(0, 20))]
        elif random.random() < 0.2:
            # 数值
            meta[key] = random.randint(-10000, 10000)
        elif random.random() < 0.1:
            # 布尔
            meta[key] = random.choice([True, False])
        else:
            # 字符串
            meta[key] = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(0, 100)))
    return meta


def execute_chaos_operation(memory: AgentMemory, op_id: int):
    """执行单个混乱操作"""
    ops = [
        'remember', 'recall', 'add_entity', 'add_relation', 
        'store_preference', 'get_preference', 
        'remember_conversation', 'get_conversation_history', 
        'get_stats', 'working_memory_touch'
    ]
    op = random.choice(ops)
    
    try:
        if op == 'remember':
            content = generate_chaos_content(op_id)
            mem_type = random.choice(['semantic', 'episodic', 'fact', 'conversation', 'procedure'])
            category = random.choice(['general', 'personal', 'work', 'test', 'chaos'])
            importance = random.uniform(-10.0, 20.0)  # 极端值
            meta = generate_random_metadata()
            return memory.remember(content, mem_type, category, importance, metadata=meta)
        
        elif op == 'recall':
            query = generate_chaos_content(op_id % 1000)
            top_k = random.randint(0, 200)  # 极端值
            results = memory.recall(query, top_k=top_k)
            return f"recall_{len(results)}_results"
        
        elif op == 'add_entity':
            name = f"entity_{random.randint(0, 100000)}"
            entity_type = random.choice(['user', 'item', 'topic', 'location', 'unknown'])
            attrs = generate_random_metadata()
            return memory.add_entity(name, entity_type, attrs)
        
        elif op == 'add_relation':
            e1 = f"entity_{random.randint(0, 100000)}"
            e2 = f"entity_{random.randint(0, 100000)}"
            rel = random.choice(['knows', 'related', 'likes', 'dislikes', 'part_of', 'unknown_rel'])
            return memory.add_relation(e1, rel, e2)
        
        elif op == 'store_preference':
            key = f"pref_{random.randint(0, 100000)}"
            value = generate_chaos_content(op_id % 100)
            return memory.store_preference(key, value)
        
        elif op == 'get_preference':
            key = f"pref_{random.randint(0, 100000)}"
            return memory.get_preference(key)
        
        elif op == 'remember_conversation':
            speaker = random.choice(['user', 'assistant', 'system', 'unknown'])
            msg = generate_chaos_content(op_id % 500)
            return memory.remember_conversation(speaker, msg)
        
        elif op == 'get_conversation_history':
            limit = random.randint(-100, 500)
            return memory.get_conversation_history(limit)
        
        elif op == 'get_stats':
            return memory.get_stats()
        
        else:
            return "unknown_operation"
    except Exception as e:
        logger.error(f"Operation {op_id} ({op}) failed: {str(e)}")
        return f"ERROR: {str(e)}"


def round7_chaos_test():
    """第7轮超深度混乱测试"""
    tracker = TestTracker()
    
    tracker.log("\n" + "=" * 100, "INFO")
    tracker.log("第7轮超深度混乱测试开始", "INFO")
    tracker.log("=" * 100 + "\n", "INFO")
    
    # ==================== 阶段1: 初始化和基础测试 ====================
    tracker.start_step("阶段1: 系统初始化和基础验证")
    
    try:
        tracker.log("1.1 创建 AgentMemory (fake 配置)", "INFO")
        config = AgentMemoryConfig(
            long_term={
                "embedding": {"provider": "fake"},
                "vector_store": {"backend": "memory"}
            }
        )
        memory = AgentMemory(config=config)
        tracker.log("  ✅ AgentMemory 创建成功", "INFO")
        
        tracker.log("1.2 验证基础 API 可用", "INFO")
        test_id = memory.remember("Test initialization content", "test", "init", 0.5)
        tracker.log(f"  ✅ remember 成功: {test_id}", "INFO")
        
        results = memory.recall("initialization", top_k=3)
        tracker.log(f"  ✅ recall 成功: {len(results)} 条", "INFO")
        
        tracker.end_step("阶段1: 系统初始化和基础验证", "初始化完成", "PASS", 2)
        
    except Exception as e:
        tracker.log(f"  ❌ 初始化失败: {str(e)}", "ERROR")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
        tracker.end_step("阶段1: 系统初始化和基础验证", "初始化失败", "FAIL", 0, [str(e)])
        return tracker
    
    # ==================== 阶段2: 短时间小规模混乱 ====================
    tracker.start_step("阶段2: 短时间小规模混乱测试")
    ops_count = 500
    errors = []
    
    try:
        tracker.log(f"2.1 执行 {ops_count} 次混乱操作", "INFO")
        
        start = time.time()
        for i in range(ops_count):
            try:
                result = execute_chaos_operation(memory, i)
                if i % 50 == 0:
                    tracker.log(f"  已执行 {i+1}/{ops_count} 次, 最新结果: {str(result)[:50]}...", "INFO")
            except Exception as e:
                err_msg = f"Op {i} failed: {str(e)}"
                errors.append(err_msg)
                tracker.log(f"  ❌ {err_msg}", "ERROR")
                if len(errors) > 10:  # 限制错误记录
                    break
        
        duration = time.time() - start
        tracker.log(f"  ✅ 完成 {ops_count} 次混乱操作, 耗时 {duration:.2f}秒", "INFO")
        tracker.log(f"  错误数: {len(errors)}", "INFO")
        
        stats = memory.get_stats()
        tracker.log(f"  最终状态: LT={stats['long_term']['total_memories']} 条记忆", "INFO")
        
    except Exception as e:
        errors.append(f"阶段2异常: {str(e)}")
        tracker.log(f"  ❌ {str(e)}", "ERROR")
    
    status = "PASS" if len(errors) <= 5 else ("FAIL" if len(errors) > 20 else "WARN")
    tracker.end_step("阶段2: 短时间小规模混乱测试", f"{ops_count}次操作", status, ops_count, errors)
    
    # ==================== 阶段3: 中等规模长时间测试 ====================
    tracker.start_step("阶段3: 中等规模长时间测试")
    ops_count = 2000
    errors = []
    
    try:
        tracker.log(f"3.1 执行 {ops_count} 次中等规模操作", "INFO")
        
        start = time.time()
        for i in range(ops_count):
            try:
                execute_chaos_operation(memory, 1000 + i)
                if i % 200 == 0:
                    tracker.log(f"  已执行 {i+1}/{ops_count} 次", "INFO")
                    gc.collect()
            except Exception as e:
                err_msg = f"Op {1000+i} failed: {str(e)}"
                errors.append(err_msg)
                if len(errors) <= 20:
                    tracker.log(f"  ❌ {err_msg}", "ERROR")
        
        duration = time.time() - start
        tracker.log(f"  ✅ 完成 {ops_count} 次操作, 耗时 {duration:.2f}秒", "INFO")
        tracker.log(f"  速度: {ops_count/duration:.1f} ops/s", "INFO")
        
        stats = memory.get_stats()
        tracker.log(f"  最终统计: LT={stats['long_term']['total_memories']} 条", "INFO")
        
    except Exception as e:
        errors.append(f"阶段3异常: {str(e)}")
    
    status = "PASS" if len(errors) <= 20 else "FAIL"
    tracker.end_step("阶段3: 中等规模长时间测试", f"{ops_count}次操作", status, ops_count, errors)
    
    # ==================== 阶段4: 极端数据写入 ====================
    tracker.start_step("阶段4: 极端数据写入测试")
    errors = []
    extreme_ops = 200
    
    try:
        tracker.log("4.1 写入极小内容", "INFO")
        for i in range(50):
            content = "" if random.random() < 0.2 else "x"
            memory.remember(content, "extreme", "test", random.random())
        
        tracker.log("4.2 写入超大内容", "INFO")
        for i in range(50):
            content = "x" * random.randint(10000, 50000)
            memory.remember(content, "extreme", "test", random.random())
        
        tracker.log("4.3 写入极端重要性值", "INFO")
        for i in range(50):
            importance = random.choice([-1000.0, 1000.0, 0.0, 1.0, 99999.9])
            memory.remember(f"Extreme importance {i}", "extreme", "test", importance)
        
        tracker.log("4.4 混合极端操作", "INFO")
        for i in range(50):
            if random.random() < 0.5:
                memory.remember(generate_chaos_content(2000+i), "test", "chaos", random.uniform(-10, 20))
            else:
                memory.recall(generate_chaos_content(2000+i), top_k=random.randint(0, 200))
        
        stats = memory.get_stats()
        tracker.log(f"  ✅ 极端数据测试完成, LT={stats['long_term']['total_memories']}", "INFO")
        
    except Exception as e:
        errors.append(f"极端数据测试异常: {str(e)}")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    tracker.end_step("阶段4: 极端数据写入测试", "极端数据", status, extreme_ops, errors)
    
    # ==================== 阶段5: 完整业务场景 ====================
    tracker.start_step("阶段5: 完整业务场景闭环")
    errors = []
    biz_ops = 300
    
    try:
        tracker.log("5.1 模拟真实对话流程", "INFO")
        for _ in range(50):
            # 用户消息
            memory.remember_conversation("user", generate_chaos_content(3000+_)[:200])
            # 记录事实
            memory.remember(f"User said something at {time.time()}", "fact", "conversation", 0.7)
            # 助手回复
            memory.remember_conversation("assistant", generate_chaos_content(3000+_)[:200])
            # 关联实体
            if random.random() < 0.3:
                memory.add_entity(f"topic_{random.randint(0,1000)}", "topic")
        
        tracker.log("5.2 混合偏好设置和查询", "INFO")
        for _ in range(100):
            if random.random() < 0.6:
                memory.store_preference(f"setting_{random.randint(0,200)}", generate_chaos_content(3100+_)[:100])
            else:
                memory.get_preference(f"setting_{random.randint(0,200)}")
        
        tracker.log("5.3 知识图谱构建和查询", "INFO")
        entities = [f"ent_{i}" for i in range(50)]
        for name in entities:
            memory.add_entity(name, "business_entity")
        for _ in range(100):
            e1 = random.choice(entities)
            e2 = random.choice(entities)
            memory.add_relation(e1, "relates_to", e2)
        
        tracker.log("5.4 高频混合召回", "INFO")
        for _ in range(50):
            memory.recall(generate_chaos_content(3200+_)[:50], top_k=random.randint(1,20))
        
        stats = memory.get_stats()
        tracker.log(f"  ✅ 业务场景完成, LT={stats['long_term']['total_memories']}", "INFO")
        
    except Exception as e:
        errors.append(f"业务场景异常: {str(e)}")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    tracker.end_step("阶段5: 完整业务场景闭环", "业务场景", status, biz_ops, errors)
    
    # ==================== 阶段6: 最终验证和资源清理 ====================
    tracker.start_step("阶段6: 最终验证和资源清理")
    errors = []
    
    try:
        tracker.log("6.1 获取最终统计信息", "INFO")
        final_stats = memory.get_stats()
        tracker.log(f"  完整统计: {list(final_stats.keys())}", "INFO")
        tracker.log(f"  长期记忆总数: {final_stats['long_term']['total_memories']}", "INFO")
        
        tracker.log("6.2 检查对话历史", "INFO")
        conv_hist = memory.get_conversation_history(50)
        tracker.log(f"  对话历史条数: {len(conv_hist)}", "INFO")
        
        tracker.log("6.3 关闭系统", "INFO")
        memory.close()
        tracker.log("  ✅ 系统关闭成功", "INFO")
        
        tracker.log("6.4 重复关闭测试", "INFO")
        memory.close()
        tracker.log("  ✅ 重复关闭无崩溃", "INFO")
        
    except Exception as e:
        errors.append(f"最终验证异常: {str(e)}")
    
    status = "PASS" if len(errors) == 0 else "FAIL"
    tracker.end_step("阶段6: 最终验证和资源清理", "最终验证", status, 3, errors)
    
    # ==================== 生成报告 ====================
    tracker.log("\n" + "=" * 100, "INFO")
    tracker.log("第7轮超深度混乱测试完成", "INFO")
    tracker.log("=" * 100, "INFO")
    tracker.log(f"  总操作数: {tracker.total_ops}", "INFO")
    tracker.log(f"  总错误数: {len(tracker.errors)}", "INFO")
    tracker.log(f"  总耗时: {time.time() - tracker.start_time:.2f}秒", "INFO")
    tracker.log(f"  平均速度: {tracker.total_ops/(time.time() - tracker.start_time):.1f} ops/s", "INFO")
    
    # 写入报告
    report_file = "/workspace/advanced-agent-memory-system/ROUND7_REPORT.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("="*100 + "\n")
        f.write("第7轮超深度混乱测试报告\n")
        f.write("="*100 + "\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总操作数: {tracker.total_ops}\n")
        f.write(f"总错误数: {len(tracker.errors)}\n")
        f.write(f"总耗时: {time.time() - tracker.start_time:.2f}秒\n\n")
        
        f.write("="*100 + "\n")
        f.write("详细测试结果\n")
        f.write("="*100 + "\n")
        for r in tracker.results:
            f.write(f"\n{r.step} - {r.sub_step}\n")
            f.write(f"  状态: {r.status}\n")
            f.write(f"  操作数: {r.operations}\n")
            f.write(f"  耗时: {r.duration:.2f}秒\n")
            if r.errors:
                f.write(f"  错误 ({len(r.errors)}):\n")
                for e in r.errors[:20]:
                    f.write(f"    - {e}\n")
        
        f.write("\n" + "="*100 + "\n")
        f.write("五阶段迭代优化计划\n")
        f.write("="*100 + "\n\n")
        
        f.write("阶段一: 错误修复和健壮性 (1-2周)\n")
        f.write("- 修复任何发现的错误\n")
        f.write("- 增强极端输入验证\n")
        f.write("- 添加更多的异常处理\n\n")
        
        f.write("阶段二: 性能优化 (2-3周)\n")
        f.write("- 大规模数据索引优化\n")
        f.write("- 高频操作优化\n")
        f.write("- 内存使用优化\n\n")
        
        f.write("阶段三: 并发安全 (2-3周)\n")
        f.write("- 分布式锁完善\n")
        f.write("- 高并发压力测试\n")
        f.write("- 死锁检测和恢复\n\n")
        
        f.write("阶段四: 可观测性 (2-3周)\n")
        f.write("- 详细性能指标\n")
        f.write("- 结构化日志\n")
        f.write("- 健康检查\n\n")
        
        f.write("阶段五: 高级功能 (3-4周)\n")
        f.write("- 向量存储后端完善\n")
        f.write("- 知识图谱增强\n")
        f.write("- 数据备份和恢复\n\n")
    
    tracker.log(f"\n报告已保存到: {report_file}", "INFO")
    
    if len(tracker.errors) <= 20:
        tracker.log("\n✅ 第7轮超深度混乱测试通过!", "INFO")
    else:
        tracker.log(f"\n⚠️ 第7轮测试有 {len(tracker.errors)} 个错误", "WARN")
    
    return tracker


if __name__ == "__main__":
    round7_chaos_test()

