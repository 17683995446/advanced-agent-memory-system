#!/usr/bin/env python3
"""
超级复杂测试场景 - 带有详细日志记录
遵循慢工出细活原则，通过日志追踪每一步操作
"""

import sys
import time
import random
import string
import threading
import logging
from typing import Dict, List, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s',
    handlers=[
        logging.FileHandler('super_complex_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def log_step(step: str, details: str = ""):
    """记录每一步操作"""
    logger.info(f"✓ {step}" + (f" - {details}" if details else ""))


def log_warning(warning: str):
    """记录警告"""
    logger.warning(f"⚠️ {warning}")


def log_error(error: str):
    """记录错误"""
    logger.error(f"❌ {error}")


class SuperComplexTester:
    """超级复杂场景测试器"""
    
    def __init__(self):
        self.results = {
            "total_ops": 0,
            "success_ops": 0,
            "failed_ops": 0,
            "errors": [],
            "warnings": []
        }
        self.lock = threading.Lock()
        self.test_memory = None
    
    def setup(self):
        """设置测试环境"""
        log_step("初始化测试环境")
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"},
            ),
            short_term={"working_memory_capacity": 50, "history_limit": 200},
            knowledge_graph={"enabled": True}
        )
        self.test_memory = AgentMemory(config=config)
        log_step("AgentMemory实例创建成功")
        
        # 预填充数据
        log_step("开始预填充测试数据")
        for i in range(100):
            content = f"预填充数据 {i}: 这是一段测试内容，用于验证系统的各种功能"
            mem_id = self.test_memory.remember(
                content=content,
                memory_type=random.choice(["fact", "semantic", "episodic"]),
                importance=random.uniform(0.1, 0.9)
            )
            if (i+1) % 20 == 0:
                log_step(f"已预填充 {i+1}/100 条记录", f"ID: {mem_id[:12]}")
        
        log_step("预填充完成", f"系统统计: {self.test_memory.get_stats()}")
    
    def test_complex_scenario(self, scenario_id: int, operations: int = 50):
        """测试复杂场景"""
        log_step(f"开始场景 {scenario_id} 测试", f"计划执行 {operations} 次操作")
        
        for op_idx in range(operations):
            try:
                operation_type = random.choice([
                    "remember", "recall", "update", "forget", 
                    "add_entity", "search_entity", "add_interaction", "get_history"
                ])
                
                start_time = time.time()
                
                if operation_type == "remember":
                    content_size = random.randint(10, 1000)
                    content = generate_complex_content(content_size)
                    mem_id = self.test_memory.remember(
                        content=content,
                        memory_type=random.choice(["fact", "semantic", "episodic"]),
                        category=random.choice(["test", "complex", "scenario"]),
                        importance=random.uniform(0.1, 0.9),
                        tags=[generate_tag() for _ in range(random.randint(0, 5))]
                    )
                    log_step(f"场景{scenario_id}-操作{op_idx}", f"remember - ID: {mem_id[:12]}, 内容长度: {len(content)}")
                
                elif operation_type == "recall":
                    query = generate_complex_content(random.randint(5, 30))
                    results = self.test_memory.recall(query, top_k=random.randint(1, 10))
                    log_step(f"场景{scenario_id}-操作{op_idx}", f"recall - 查询: '{query[:30]}...', 结果数: {len(results)}")
                
                elif operation_type == "update":
                    stats = self.test_memory.get_stats()
                    if stats.get("long_term", {}).get("total_memories", 0) > 0:
                        from memory_system.storage.vector_store import MemoryRecord
                        all_records = self.test_memory.long_term.store.list_all(limit=100)
                        if all_records:
                            record = random.choice(all_records)
                            new_content = generate_complex_content(random.randint(50, 200))
                            success = self.test_memory.long_term.update(record.id, content=new_content)
                            log_step(f"场景{scenario_id}-操作{op_idx}", f"update - ID: {record.id[:12]}, 成功: {success}")
                
                elif operation_type == "forget":
                    stats = self.test_memory.get_stats()
                    if stats.get("long_term", {}).get("total_memories", 0) > 0:
                        all_records = self.test_memory.long_term.store.list_all(limit=100)
                        if all_records:
                            record = random.choice(all_records)
                            success = self.test_memory.forget_memory(record.id)  # 使用正确的API
                            log_step(f"场景{scenario_id}-操作{op_idx}", f"forget - ID: {record.id[:12]}, 成功: {success}")
                
                elif operation_type == "add_entity":
                    entity_name = f"Entity_{scenario_id}_{op_idx}_{generate_tag()}"
                    entity_type = random.choice(["concept", "person", "tool", "project"])
                    description = generate_complex_content(50)
                    try:
                        entity_id = self.test_memory.add_entity(
                            name=entity_name,
                            entity_type=entity_type,
                            description=description
                        )
                        log_step(f"场景{scenario_id}-操作{op_idx}", f"add_entity - 名称: {entity_name}, ID: {entity_id[:12]}")
                    except Exception as e:
                        log_warning(f"add_entity 失败: {e}")
                
                elif operation_type == "search_entity":
                    query = generate_tag()
                    try:
                        results = self.test_memory.search_entities(query, top_k=5)
                        log_step(f"场景{scenario_id}-操作{op_idx}", f"search_entity - 查询: '{query}', 结果数: {len(results)}")
                    except Exception as e:
                        log_warning(f"search_entity 失败: {e}")
                
                elif operation_type == "add_interaction":
                    role = random.choice(["user", "assistant"])
                    content = generate_complex_content(random.randint(20, 100))
                    self.test_memory.add_interaction(role=role, content=content)
                    log_step(f"场景{scenario_id}-操作{op_idx}", f"add_interaction - 角色: {role}, 长度: {len(content)}")
                
                elif operation_type == "get_history":
                    history = self.test_memory.get_conversation_history()
                    log_step(f"场景{scenario_id}-操作{op_idx}", f"get_history - 历史长度: {len(history)}")
                
                latency = time.time() - start_time
                with self.lock:
                    self.results["total_ops"] += 1
                    self.results["success_ops"] += 1
                
                # 随机延迟模拟真实场景
                if random.random() < 0.3:
                    time.sleep(random.uniform(0.001, 0.01))
                
            except Exception as e:
                error_msg = f"场景{scenario_id}-操作{op_idx} 失败: {type(e).__name__}: {e}"
                log_error(error_msg)
                with self.lock:
                    self.results["total_ops"] += 1
                    self.results["failed_ops"] += 1
                    self.results["errors"].append({
                        "scenario": scenario_id,
                        "operation": op_idx,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
    
    def run_super_complex_test(self, num_scenarios: int = 10, ops_per_scenario: int = 100):
        """运行超级复杂测试"""
        logger.info("\n" + "="*100)
        logger.info("🔥 超级复杂测试场景开始 - 慢工出细活")
        logger.info("="*100)
        logger.info(f"测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"场景数量: {num_scenarios}")
        logger.info(f"每个场景操作数: {ops_per_scenario}")
        logger.info(f"预期总操作数: {num_scenarios * ops_per_scenario}")
        
        # 设置
        self.setup()
        
        # 运行测试
        logger.info(f"\n开始运行 {num_scenarios} 个并发场景...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self.test_complex_scenario, i, ops_per_scenario)
                for i in range(num_scenarios)
            ]
            
            # 监控进度
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    future.result()
                except Exception as e:
                    log_error(f"场景执行异常: {e}")
                logger.info(f"已完成 {completed}/{num_scenarios} 场景")
        
        # 清理和总结
        try:
            self.test_memory.close()
            log_step("测试完成，关闭内存系统")
        except Exception as e:
            log_warning(f"关闭时警告: {e}")
        
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        logger.info("\n" + "="*100)
        logger.info("📊 超级复杂测试报告")
        logger.info("="*100)
        
        total = self.results["total_ops"]
        success = self.results["success_ops"]
        failed = self.results["failed_ops"]
        success_rate = (success / total) * 100 if total > 0 else 0
        
        logger.info(f"\n操作统计:")
        logger.info(f"  总操作数: {total:,}")
        logger.info(f"  成功操作: {success:,}")
        logger.info(f"  失败操作: {failed:,}")
        logger.info(f"  成功率: {success_rate:.2f}%")
        
        if self.results["errors"]:
            logger.info(f"\n错误详情 (前5条):")
            for i, err in enumerate(self.results["errors"][:5]):
                logger.info(f"  {i+1}. 场景{err['scenario']}-操作{err['operation']}: {err['error'][:100]}")
        
        logger.info(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*100)
        
        if success_rate >= 99:
            logger.info("\n🎉 测试通过！系统运行完美！")
        elif success_rate >= 95:
            logger.info("\n✅ 测试基本通过！")
        elif success_rate >= 90:
            logger.info("\n⚠️ 测试基本通过，但有一些问题需要关注")
        else:
            logger.info("\n❌ 测试未通过，需要修复问题")
        
        # 返回结果
        return {
            "success": success_rate >= 95,
            "success_rate": success_rate,
            "total_ops": total,
            "errors": len(self.results["errors"])
        }


def generate_complex_content(length: int) -> str:
    """生成复杂内容"""
    chars = string.ascii_letters + string.digits + "中文测试日本語한국어"
    return ''.join(random.choice(chars) for _ in range(length))


def generate_tag() -> str:
    """生成标签"""
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(8))


def main():
    """主函数"""
    logger.info("="*100)
    logger.info("启动超级复杂测试")
    logger.info("="*100)
    
    tester = SuperComplexTester()
    result = tester.run_super_complex_test(num_scenarios=10, ops_per_scenario=100)
    
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
