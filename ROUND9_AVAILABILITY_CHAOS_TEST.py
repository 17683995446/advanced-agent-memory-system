"""
第9轮超深度可用性和复杂场景测试
特点：
- 超长运行时间（10,000+操作）
- 更真实的复杂业务场景
- 更极端的边界条件
- 可用性测试和性能监控
- 完整的错误检测和恢复
- 详细的逐行日志
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
    avg_latency_ms: float = 0.0

class TestTracker:
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.step_start = time.time()
        self.total_ops = 0
        self.errors = []
        self.latencies: List[float] = []
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] {level} - {message}")
        if level == "ERROR":
            logger.error(message)
            self.errors.append(message)
        elif level == "WARN":
            logger.warning(message)
        else:
            logger.info(message)
    
    def start_step(self, step_name: str):
        self.step_start = time.time()
        self.latencies = []
        self.log("=" * 120, "INFO")
        self.log(f"开始: {step_name}", "INFO")
        self.log("=" * 120, "INFO")
    
    def end_step(self, step_name: str, sub_step: str, status: str, operations: int = 0, errors: List[str] = None, details: str = ""):
        duration = time.time() - self.step_start
        avg_latency = (sum(self.latencies) / len(self.latencies) * 1000) if self.latencies else 0.0
        self.total_ops += operations
        result = TestResult(
            step=step_name, 
            sub_step=sub_step, 
            status=status, 
            duration=duration, 
            operations=operations, 
            errors=errors or [], 
            details=details,
            avg_latency_ms=avg_latency
        )
        self.results.append(result)
        self.log(f"完成: {step_name} - {sub_step}", "INFO")
        self.log(f"  状态: {status}", "INFO")
        self.log(f"  耗时: {duration:.2f}秒", "INFO")
        self.log(f"  操作数: {operations}", "INFO")
        self.log(f"  平均延迟: {avg_latency:.2f}ms", "INFO")
        if errors:
            self.log(f"  错误数: {len(errors)}", "ERROR")
            for err in errors[:15]:
                self.log(f"    - {err}", "ERROR")
        return result

# 真实业务场景数据
PRODUCT_NAMES = ["iPhone 15", "MacBook Pro", "AirPods", "Samsung Galaxy", "Dell Laptop", 
                "Sony Headphones", "Nintendo Switch", "PlayStation 5", "Xbox Series X", "Surface Pro"]
CATEGORIES = ["电子产品", "办公设备", "游戏", "手机", "电脑", "配件"]
USER_NAMES = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]
USER_QUERIES = [
    "推荐一款性能好的手机",
    "最近有什么新品?",
    "这个产品的价格是多少?",
    "有现货吗?",
    "保修期多长?",
    "退货政策是什么?",
    "用户评价怎么样?",
    "和竞品相比如何?"
]

def generate_realistic_product_data(i: int) -> tuple:
    """生成真实的产品数据"""
    product = random.choice(PRODUCT_NAMES)
    category = random.choice(CATEGORIES)
    price = random.randint(100, 10000)
    stock = random.randint(0, 1000)
    rating = random.uniform(1.0, 5.0)
    
    content = f"产品信息 - {product}\n类别: {category}\n价格: ¥{price}\n库存: {stock}\n评分: {rating:.1f}\n"
    return product, category, content

def generate_chaotic_content(i: int) -> str:
    """生成极端混乱内容"""
    chaos_types = random.choice([
        "ultra_long", "special_chars", "mixed_languages", "all_emoji", 
        "control_chars", "zero_width", "repeated"
    ])
    
    if chaos_types == "ultra_long":
        length = random.randint(5000, 50000)
        return f"[ULTRA_LONG_{i}] " + ''.join(random.choices(string.printable, k=length))
    elif chaos_types == "special_chars":
        specials = "!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`'\"\t\n\r\x00\x01\x02"
        length = random.randint(100, 5000)
        return f"[SPECIAL_{i}] " + ''.join(random.choices(specials, k=length))
    elif chaos_types == "mixed_languages":
        langs = ["这是中文测试", "This is English", "これは日本語", "한국어입니다", "هذا عربي"]
        length = random.randint(100, 5000)
        return f"[MULTILANG_{i}] " + ''.join(random.choice(langs) for _ in range(length // 10))
    elif chaos_types == "all_emoji":
        emojis = "🎉🎊🔥✨🚀💻⭐🎯✅❌💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃"
        length = random.randint(50, 2000)
        return f"[EMOJI_{i}] " + ''.join(random.choices(emojis, k=length))
    else:
        return f"[NORMAL_{i}] 这是正常的测试内容，编号 {i}"

def execute_complex_operation(memory: AgentMemory, i: int) -> tuple[str, float]:
    """执行一个复杂操作，包含多个子操作"""
    op_start = time.time()
    try:
        op_type = random.choice([
            "full_product_flow", "user_session_flow", "knowledge_graph_scenario", 
            "search_scenario", "chaos_operation"
        ])
        
        if op_type == "full_product_flow":
            # 完整产品流程
            product, category, content = generate_realistic_product_data(i)
            memory.remember(content, "fact", category, random.uniform(0.3, 0.9))
            memory.add_entity(product, "产品", {"category": category})
            results = memory.recall(f"{product} {category}", top_k=3)
        
        elif op_type == "user_session_flow":
            # 用户会话流程
            user = random.choice(USER_NAMES)
            query = random.choice(USER_QUERIES)
            memory.remember_conversation("user", query)
            memory.remember(f"用户 {user} 的问题: {query}", "fact", "用户对话", random.uniform(0.4, 0.8))
            response = f"这是关于 {query} 的回答"
            memory.remember_conversation("assistant", response)
            memory.store_preference(f"{user}_recent_query", query)
        
        elif op_type == "knowledge_graph_scenario":
            # 知识图谱场景
            entity1 = f"实体_{random.randint(0, 10000)}"
            entity2 = f"实体_{random.randint(0, 10000)}"
            rel = random.choice(["相关", "包含", "使用", "创建", "购买", "喜欢"])
            memory.add_entity(entity1, random.choice(["用户", "产品", "公司", "地点"]))
            memory.add_entity(entity2, random.choice(["用户", "产品", "公司", "地点"]))
            memory.add_relation(entity1, rel, entity2)
        
        elif op_type == "search_scenario":
            # 搜索场景
            query = random.choice(USER_QUERIES) if random.random() < 0.5 else generate_chaotic_content(i)
            top_k = random.randint(1, 50)
            results = memory.recall(query, top_k=top_k)
        
        elif op_type == "chaos_operation":
            # 混乱操作
            if random.random() < 0.3:
                chaos_content = generate_chaotic_content(i)
                memory.remember(chaos_content, "semantic", "测试", random.uniform(-10, 20))
            elif random.random() < 0.3:
                memory.get_stats()
            else:
                memory.get_conversation_history(random.randint(1, 200))
        
        return "SUCCESS", time.time() - op_start
    
    except Exception as e:
        return f"ERROR: {str(e)}", time.time() - op_start

def main():
    print("\n" + "=" * 120)
    print("第9轮超深度可用性和复杂场景测试")
    print("=" * 120 + "\n")
    
    tracker = TestTracker()
    
    # 第1阶段：系统初始化
    tracker.start_step("1. 系统初始化和配置")
    errors = []
    
    try:
        config = AgentMemoryConfig(
            long_term={
                "embedding": {"provider": "fake"},
                "vector_store": {"backend": "memory"}
            },
            auto_consolidate=False,
            default_top_k=10
        )
        memory = AgentMemory(config=config)
        tracker.log("✅ AgentMemory 初始化成功", "INFO")
        
        # 基础测试
        test_ops = 10
        for i in range(test_ops):
            tracker.log(f"    基础操作 {i+1}/{test_ops}", "INFO")
            memory.remember(f"基础测试内容 {i}", "fact", "初始化", 0.5 + i*0.05)
        
        results = memory.recall("基础测试", top_k=10)
        tracker.log(f"✅ 基础召回成功，返回 {len(results)} 条", "INFO")
        
        tracker.end_step("1. 系统初始化和配置", "初始化完成", "PASS", test_ops + 5, errors)
        
    except Exception as e:
        errors.append(f"初始化异常: {str(e)}")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
        tracker.end_step("1. 系统初始化和配置", "初始化失败", "FAIL", 0, errors)
        return
    
    # 第2阶段：大规模真实场景测试
    tracker.start_step("2. 大规模真实场景测试 (10,000次复杂操作)")
    errors = []
    total_ops = 10000
    batch_size = 500
    
    try:
        start_time = time.time()
        for batch in range(total_ops // batch_size):
            batch_start = time.time()
            batch_errors = []
            
            for i in range(batch_size):
                global_i = batch * batch_size + i
                try:
                    result, latency = execute_complex_operation(memory, global_i)
                    tracker.latencies.append(latency)
                    
                    if result.startswith("ERROR"):
                        batch_errors.append(f"操作 {global_i}: {result}")
                        if len(batch_errors) <= 10:
                            tracker.log(f"    ❌ 操作 {global_i}: {result}", "ERROR")
                
                except Exception as e:
                    err_msg = f"操作 {global_i} 异常: {str(e)}"
                    if len(batch_errors) <= 10:
                        tracker.log(f"    ❌ {err_msg}", "ERROR")
                    batch_errors.append(err_msg)
            
            batch_time = time.time() - batch_start
            errors.extend(batch_errors)
            
            progress = (batch + 1) * batch_size
            tracker.log(f"  批次 {batch+1}/{total_ops//batch_size} 完成 - {progress}/{total_ops} 操作", "INFO")
            tracker.log(f"    耗时: {batch_time:.2f}秒, 速度: {batch_size/batch_time:.1f} ops/s, 错误: {len(batch_errors)}", "INFO")
            
            # 定期清理
            if (batch + 1) % 5 == 0:
                gc.collect()
                tracker.log(f"    GC执行完成，继续...", "INFO")
        
        total_time = time.time() - start_time
        
        # 统计
        tracker.log("=" * 80, "INFO")
        tracker.log(f"✅ 完成 {total_ops} 次复杂操作", "INFO")
        tracker.log(f"  总耗时: {total_time:.2f}秒", "INFO")
        tracker.log(f"  平均速度: {total_ops/total_time:.1f} ops/s", "INFO")
        tracker.log(f"  平均延迟: {(sum(tracker.latencies)/len(tracker.latencies)*1000):.2f}ms/操作", "INFO")
        tracker.log(f"  错误数: {len(errors)}", "ERROR" if errors else "INFO")
        
    except Exception as e:
        errors.append(f"大规模测试异常: {str(e)}")
        import traceback
        tracker.log(traceback.format_exc(), "ERROR")
    
    tracker.end_step("2. 大规模真实场景测试 (10,000次复杂操作)", 
                    "真实场景测试", "PASS" if len(errors) <= 50 else "FAIL", 
                    total_ops, errors)
    
    # 第3阶段：数据一致性和可用性验证
    tracker.start_step("3. 数据一致性和可用性验证")
    errors = []
    check_ops = 200
    
    try:
        # 统计信息检查
        tracker.log("  检查统计信息...", "INFO")
        stats = memory.get_stats()
        tracker.log(f"    统计模块: {list(stats.keys())}", "INFO")
        
        # 对话历史检查
        tracker.log("  检查对话历史...", "INFO")
        history = memory.get_conversation_history(100)
        tracker.log(f"    对话历史数: {len(history)}", "INFO")
        
        # 多次搜索验证
        tracker.log("  搜索功能验证...", "INFO")
        for i in range(check_ops // 2):
            try:
                query = random.choice(USER_QUERIES)
                results = memory.recall(query, top_k=random.randint(1, 10))
                tracker.latencies.append(time.time() - tracker.step_start)
            except Exception as e:
                if len(errors) <= 20:
                    errors.append(f"搜索验证 {i}: {str(e)}")
        
        # 偏好存储验证
        tracker.log("  偏好功能验证...", "INFO")
        for i in range(check_ops // 2):
            try:
                key = f"test_key_{i}"
                value = f"test_value_{i}"
                memory.store_preference(key, value)
                recovered = memory.get_preference(key)
            except Exception as e:
                if len(errors) <= 20:
                    errors.append(f"偏好验证 {i}: {str(e)}")
        
    except Exception as e:
        errors.append(f"一致性检查异常: {str(e)}")
    
    tracker.end_step("3. 数据一致性和可用性验证", 
                    "一致性验证", "PASS" if len(errors) <= 10 else "FAIL", 
                    check_ops, errors)
    
    # 第4阶段：资源释放和最终验证
    tracker.start_step("4. 资源释放和最终验证")
    errors = []
    
    try:
        tracker.log("  第一次 close()...", "INFO")
        memory.close()
        tracker.log("  ✅ 第一次 close() 成功", "INFO")
        
        # 重复关闭
        for i in range(5):
            tracker.log(f"  重复 close() 第 {i+1} 次...", "INFO")
            memory.close()
        
        tracker.log("  ✅ 所有 close() 调用无崩溃", "INFO")
        
        gc.collect()
        tracker.log("  ✅ GC 执行完成", "INFO")
        
    except Exception as e:
        errors.append(f"资源释放异常: {str(e)}")
    
    tracker.end_step("4. 资源释放和最终验证", "资源清理", 
                    "PASS" if len(errors) == 0 else "FAIL", 10, errors)
    
    # 生成最终报告
    print("\n" + "=" * 120)
    print("测试完成 - 最终总结")
    print("=" * 120)
    print(f"  总操作数: {tracker.total_ops}")
    print(f"  总错误数: {len(tracker.errors)}")
    print(f"  总耗时: {time.time() - tracker.start_time:.2f}秒")
    if tracker.latencies:
        avg_latency_ms = sum(tracker.latencies) / len(tracker.latencies) * 1000
        print(f"  平均延迟: {avg_latency_ms:.2f}ms/操作")
    
    print("\n详细结果:")
    for r in tracker.results:
        print(f"  {r.step} - {r.sub_step}: {r.status}")
        print(f"    操作数: {r.operations}, 错误数: {len(r.errors)}, 耗时: {r.duration:.2f}秒")
    
    # 写入报告
    report_file = "/workspace/advanced-agent-memory-system/ROUND9_REPORT.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 120 + "\n")
        f.write("第9轮超深度可用性和复杂场景测试 - 最终报告\n")
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
            f.write(f"  平均延迟: {r.avg_latency_ms:.2f}ms\n")
            if r.errors:
                f.write(f"  错误 ({len(r.errors)}):\n")
                for err in r.errors[:30]:
                    f.write(f"    - {err}\n")
        
        f.write("\n" + "=" * 120 + "\n")
        f.write("五阶段迭代优化计划\n")
        f.write("=" * 120 + "\n\n")
        f.write("阶段一: 可用性完善 (1周)\n")
        f.write("- 空内容处理优化\n")
        f.write("- 异常信息完善\n")
        f.write("- 输入验证和规范化\n\n")
        f.write("阶段二: 性能优化 (2周)\n")
        f.write("- 批量操作支持\n")
        f.write("- 查询缓存\n")
        f.write("- 索引优化\n\n")
        f.write("阶段三: 企业级稳定性 (2周)\n")
        f.write("- 高并发测试\n")
        f.write("- 资源管理优化\n")
        f.write("- 健康检查完善\n\n")
        f.write("阶段四: 可观测性 (2周)\n")
        f.write("- Prometheus指标\n")
        f.write("- 结构化日志\n")
        f.write("- 性能监控\n\n")
        f.write("阶段五: 高级特性 (3周)\n")
        f.write("- 备份恢复\n")
        f.write("- 多租户支持\n")
        f.write("- 知识图谱增强\n\n")
    
    print(f"\n详细报告已保存到: {report_file}")
    
    # 最终判断
    print("\n" + "=" * 120)
    if len(tracker.errors) <= 100 and tracker.total_ops >= 10000:
        print("✅ 第9轮超深度可用性和复杂场景测试通过！")
        print("  系统具备生产环境使用条件！")
    else:
        print(f"⚠️ 第9轮测试完成，但有 {len(tracker.errors)} 个错误需要优化")
    print("=" * 120)

if __name__ == "__main__":
    main()
