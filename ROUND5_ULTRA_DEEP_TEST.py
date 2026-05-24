#!/usr/bin/env python3
"""
Agent Memory System - 第5轮超深度多阶段迭代测试
- 更复杂的场景
- 更长时间的压力
- 超大规模并发
- 极端混乱数据
- 详细日志记录每一步
- 每句代码后都打印日志验证
"""

import sys
import time
import random
import string
import threading
import logging
import gc
import tracemalloc
import psutil
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

# 配置超详细的日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler('/workspace/advanced-agent-memory-system/round5_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('round5_deep_test')


def generate_mega_chaos_content(min_len=10, max_len=200000):
    """生成超大规模混乱内容 - 每一步都记录日志"""
    logger.debug(f"[generate] 开始生成混乱内容, min_len={min_len}, max_len={max_len}")
    try:
        length = random.randint(min_len, max_len)
        logger.debug(f"[generate] 目标长度: {length}")
        
        charsets = [
            string.ascii_letters * 50,
            string.digits * 30,
            '中文测试内容日本語韓國語Русскийالعربيةहिन्दीPortuguêsDeutschFrançais',
            '!@#$%^&*()_+-=[]{}|;:,.<>?/\\~`"\'',
            '🎉🎊💻🔧🚀⭐🎯✅❌🔥💯❤️👍👎🤔😎😂🙄😐😴😵🤯💀👻🤡🎃',
            '\n\r\t\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0b\x0c',
        ]
        
        content = []
        for i in range(length):
            if i % 50000 == 0 and i > 0:
                logger.debug(f"[generate] 已生成 {i} 个字符...")
            charset = random.choice(charsets)
            content.append(random.choice(charset))
        
        result = ''.join(content)
        logger.debug(f"[generate] 生成完成, 最终长度={len(result)}")
        return result
    except Exception as e:
        logger.error(f"[generate] 生成内容失败: {type(e).__name__}: {e}")
        return "FALLBACK_CONTENT"


class UltraDeepTestWorker(threading.Thread):
    """超深度测试工作线程 - 每步都打印详细日志"""
    
    def __init__(self, worker_id, duration_seconds, result_dict):
        super().__init__(name=f'Round5-Worker-{worker_id:03d}')
        self.worker_id = worker_id
        self.duration_seconds = duration_seconds
        self.result_dict = result_dict
        
        self.operations = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'by_type': {},
            'error_types': {},
            'step_timings': {},
        }
        self.errors = []
        self.memory = None
        self.start_time = None
        self.end_time = None
        self.memory_start = 0
        self.memory_end = 0
    
    def log_step(self, step_name: str, success: bool, details: str = "", duration: float = 0.0):
        """记录每一步的详细日志"""
        timestamp = datetime.now().isoformat()
        self.operations['by_type'][step_name] = self.operations['by_type'].get(step_name, 0) + 1
        if duration > 0:
            if step_name not in self.operations['step_timings']:
                self.operations['step_timings'][step_name] = []
            self.operations['step_timings'][step_name].append(duration)
        logger.info(f"[{self.name}] [{timestamp}] {'✅' if success else '❌'} {step_name}: {details} (耗时: {duration:.3f}s)")
    
    def init_memory_system(self):
        """初始化记忆系统 - 详细日志记录每一步"""
        logger.info(f"[{self.name}] 开始初始化记忆系统...")
        step_start = time.time()
        
        try:
            from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig
            logger.debug(f"[{self.name}] 导入模块成功")
            
            config = AgentMemoryConfig(
                long_term=LongTermMemoryConfig(
                    embedding={"provider": "fake", "fake_dimension": 64},
                    vector_store={"backend": "memory"}
                ),
                knowledge_graph={"enabled": True},
                structured_store={"enabled": True, "db_path": ":memory:"}
            )
            logger.debug(f"[{self.name}] 配置创建成功")
            
            self.memory = AgentMemory(config)
            logger.debug(f"[{self.name}] AgentMemory 实例化成功")
            
            step_end = time.time()
            self.log_step("init_memory", True, "记忆系统初始化成功", step_end - step_start)
            return True
        except Exception as e:
            step_end = time.time()
            self.log_step("init_memory", False, f"初始化失败: {type(e).__name__}: {e}", step_end - step_start)
            self.errors.append(("init", type(e).__name__, str(e)))
            return False
    
    def run_test_scenario(self):
        """运行测试场景 - 详细日志记录每个操作"""
        logger.info(f"[{self.name}] 开始测试场景运行 (持续 {self.duration_seconds}s)...")
        start_time = time.time()
        last_log_time = start_time
        
        ops_list = [
            'remember', 'recall', 'add_entity', 'add_relation',
            'store_preference', 'get_preference', 'remember_conversation',
            'get_conversation_history', 'add_to_working', 'consolidate',
            'get_stats',
        ]
        
        logger.debug(f"[{self.name}] 操作列表: {ops_list}")
        
        while time.time() - start_time < self.duration_seconds:
            try:
                op = random.choice(ops_list)
                self.operations['total'] += 1
                op_start = time.time()
                
                success = False
                details = ""
                
                if op == 'remember':
                    success, details = self._do_remember()
                elif op == 'recall':
                    success, details = self._do_recall()
                elif op == 'add_entity':
                    success, details = self._do_add_entity()
                elif op == 'add_relation':
                    success, details = self._do_add_relation()
                elif op == 'store_preference':
                    success, details = self._do_store_preference()
                elif op == 'get_preference':
                    success, details = self._do_get_preference()
                elif op == 'remember_conversation':
                    success, details = self._do_remember_conversation()
                elif op == 'get_conversation_history':
                    success, details = self._do_get_conversation_history()
                elif op == 'add_to_working':
                    success, details = self._do_add_to_working()
                elif op == 'consolidate':
                    success, details = self._do_consolidate()
                elif op == 'get_stats':
                    success, details = self._do_get_stats()
                
                op_end = time.time()
                duration = op_end - op_start
                
                if success:
                    self.operations['success'] += 1
                else:
                    self.operations['failed'] += 1
                    error_type = details.split(':')[0] if ':' in details else "Unknown"
                    self.operations['error_types'][error_type] = self.operations['error_types'].get(error_type, 0) + 1
                
                self.log_step(op, success, details, duration)
                
                if random.random() < 0.01:
                    time.sleep(random.uniform(0.0001, 0.005))
                
                if time.time() - last_log_time > 10:
                    logger.info(f"[{self.name}] 运行中... 总计={self.operations['total']}, 成功={self.operations['success']}, 失败={self.operations['failed']}")
                    last_log_time = time.time()
            
            except Exception as e:
                logger.error(f"[{self.name}] 主循环异常: {type(e).__name__}: {e}")
                self.operations['failed'] += 1
                self.operations['error_types']['main_loop_exception'] = self.operations['error_types'].get('main_loop_exception', 0) + 1
                self.errors.append(("main_loop", type(e).__name__, str(e)))
    
    def _do_remember(self):
        """执行 remember 操作 - 详细日志"""
        logger.debug(f"[{self.name}] 开始 remember")
        try:
            content = generate_mega_chaos_content(10, 10000)
            mem_type = random.choice(['fact', 'semantic', 'episodic', 'procedural', 'conversation'])
            importance = random.uniform(0.0, 1.0)
            
            logger.debug(f"[{self.name}] remember 参数: content_len={len(content)}, type={mem_type}, importance={importance}")
            
            result = self.memory.remember(
                content=content,
                memory_type=mem_type,
                importance=importance,
            )
            
            logger.debug(f"[{self.name}] remember 执行完成")
            return True, f"success, content_len={len(content)}, type={mem_type}"
        except Exception as e:
            logger.error(f"[{self.name}] remember 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_recall(self):
        """执行 recall 操作"""
        try:
            query = generate_mega_chaos_content(1, 1000) if random.random() < 0.8 else ""
            top_k = random.randint(1, 20)
            
            logger.debug(f"[{self.name}] recall 参数: query_len={len(query)}, top_k={top_k}")
            
            results = self.memory.recall(query, top_k=top_k)
            return True, f"success, found={len(results)}"
        except Exception as e:
            logger.error(f"[{self.name}] recall 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_add_entity(self):
        """执行 add_entity 操作"""
        try:
            name = generate_mega_chaos_content(1, 50)
            entity_type = random.choice(['person', 'concept', 'tool', 'item', 'unknown', 'place', 'event'])
            desc = generate_mega_chaos_content(0, 500)
            
            logger.debug(f"[{self.name}] add_entity 参数: name={name[:30]}, type={entity_type}")
            
            self.memory.add_entity(name=name, entity_type=entity_type, description=desc)
            return True, f"success, name_len={len(name)}, type={entity_type}"
        except Exception as e:
            logger.error(f"[{self.name}] add_entity 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_add_relation(self):
        """执行 add_relation 操作"""
        try:
            source = generate_mega_chaos_content(1, 30)
            target = generate_mega_chaos_content(1, 30)
            rel_type = random.choice(['related_to', 'uses', 'contains', 'part_of', 'causes'])
            
            logger.debug(f"[{self.name}] add_relation: source={source}, target={target}, type={rel_type}")
            
            self.memory.add_entity(name=source, entity_type='concept', description='')
            self.memory.add_entity(name=target, entity_type='concept', description='')
            self.memory.add_relation(source=source, target=target, relation_type=rel_type)
            return True, f"success, relation={rel_type}"
        except Exception as e:
            logger.error(f"[{self.name}] add_relation 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_store_preference(self):
        """执行 store_preference 操作"""
        try:
            key = generate_mega_chaos_content(1, 50)
            value = generate_mega_chaos_content(1, 2000)
            category = random.choice(['ui', 'setting', 'user', 'system', 'custom'])
            
            logger.debug(f"[{self.name}] store_preference: key={key}, category={category}")
            
            self.memory.store_preference(key=key, value=value, category=category)
            return True, f"success, key_len={len(key)}, category={category}"
        except Exception as e:
            logger.error(f"[{self.name}] store_preference 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_get_preference(self):
        """执行 get_preference 操作"""
        try:
            key = generate_mega_chaos_content(1, 30)
            logger.debug(f"[{self.name}] get_preference: key={key}")
            
            pref = self.memory.get_preference(key)
            return True, f"success, found={pref is not None}"
        except Exception as e:
            logger.error(f"[{self.name}] get_preference 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_remember_conversation(self):
        """执行 remember_conversation 操作"""
        try:
            speaker = random.choice(['user', 'assistant', 'system'])
            content = generate_mega_chaos_content(10, 3000)
            important = random.random() > 0.5
            
            logger.debug(f"[{self.name}] remember_conversation: speaker={speaker}, important={important}")
            
            self.memory.remember_conversation(content=content, speaker=speaker, important=important)
            return True, f"success, speaker={speaker}, important={important}"
        except Exception as e:
            logger.error(f"[{self.name}] remember_conversation 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_get_conversation_history(self):
        """执行 get_conversation_history 操作"""
        try:
            limit = random.randint(1, 100)
            logger.debug(f"[{self.name}] get_conversation_history: limit={limit}")
            
            history = self.memory.get_conversation_history(limit=limit)
            return True, f"success, history_len={len(history)}"
        except Exception as e:
            logger.error(f"[{self.name}] get_conversation_history 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_add_to_working(self):
        """执行 add_to_working_memory 操作"""
        try:
            key = f"wk_{self.worker_id}_{int(time.time() * 1000000)}"
            content = generate_mega_chaos_content(1, 2000)
            importance = random.random()
            
            logger.debug(f"[{self.name}] add_to_working: key={key}")
            
            self.memory.add_to_working_memory(key=key, content=content, importance=importance)
            return True, f"success, key_len={len(key)}"
        except Exception as e:
            logger.error(f"[{self.name}] add_to_working 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_consolidate(self):
        """执行 consolidate 操作"""
        try:
            logger.debug(f"[{self.name}] consolidate...")
            
            if hasattr(self.memory, 'consolidate'):
                self.memory.consolidate()
            return True, "success"
        except Exception as e:
            logger.error(f"[{self.name}] consolidate 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def _do_get_stats(self):
        """执行 get_stats 操作"""
        try:
            logger.debug(f"[{self.name}] get_stats...")
            
            if hasattr(self.memory, 'get_stats'):
                stats = self.memory.get_stats()
                return True, f"success, stats={list(stats.keys()) if isinstance(stats, dict) else 'N/A'}"
            return True, "success"
        except Exception as e:
            logger.error(f"[{self.name}] get_stats 失败: {type(e).__name__}: {e}")
            return False, f"{type(e).__name__}: {str(e)[:100]}"
    
    def close_memory_system(self):
        """关闭记忆系统 - 详细日志"""
        logger.info(f"[{self.name}] 关闭记忆系统...")
        try:
            if self.memory:
                self.memory.close()
                logger.debug(f"[{self.name}] close() 调用成功")
                self.log_step("close_memory", True, "记忆系统关闭成功")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] 关闭失败: {type(e).__name__}: {e}")
            self.log_step("close_memory", False, f"关闭失败: {type(e).__name__}: {e}")
            return False
    
    def run(self):
        """运行完整的测试"""
        logger.info(f"[{self.name}] ==== 开始测试 ====")
        self.start_time = time.time()
        self.memory_start = get_memory_usage_mb()
        
        if not self.init_memory_system():
            logger.error(f"[{self.name}] 初始化失败，中止")
            self.result_dict[f'worker_{self.worker_id}'] = {'status': 'init_failed'}
            return
        
        try:
            self.run_test_scenario()
        except Exception as e:
            logger.error(f"[{self.name}] 运行异常: {type(e).__name__}: {e}")
        
        self.close_memory_system()
        
        self.end_time = time.time()
        self.memory_end = get_memory_usage_mb()
        duration = self.end_time - self.start_time
        memory_change = self.memory_end - self.memory_start
        
        success_rate = self.operations['success'] / self.operations['total'] * 100 if self.operations['total'] > 0 else 0
        
        logger.info(f"[{self.name}] ==== 测试结束 ====")
        logger.info(f"[{self.name}] 总操作: {self.operations['total']}")
        logger.info(f"[{self.name}] 成功: {self.operations['success']}")
        logger.info(f"[{self.name}] 失败: {self.operations['failed']}")
        logger.info(f"[{self.name}] 成功率: {success_rate:.2f}%")
        logger.info(f"[{self.name}] 耗时: {duration:.2f}s")
        logger.info(f"[{self.name}] 内存变化: {memory_change:+.2f}MB")
        
        self.result_dict[f'worker_{self.worker_id}'] = {
            'status': 'completed',
            'operations': self.operations,
            'errors': self.errors,
            'duration': duration,
            'memory_change': memory_change,
        }


def get_memory_usage_mb():
    """获取当前进程内存使用"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def run_phase(num_workers, duration, phase_name):
    """运行一个测试阶段"""
    print("\n" + "=" * 160)
    print(f"🚀 第5轮测试 - {phase_name}: {num_workers}线程 x {duration}秒")
    print("=" * 160)
    
    result_dict = {}
    workers = []
    phase_start = time.time()
    phase_memory_start = get_memory_usage_mb()
    
    for i in range(num_workers):
        worker = UltraDeepTestWorker(i, duration, result_dict)
        workers.append(worker)
    
    logger.info(f"启动 {len(workers)} 个工作线程...")
    for worker in workers:
        worker.start()
    
    logger.info("所有线程启动完成，等待完成...")
    for worker in workers:
        worker.join()
    
    phase_end = time.time()
    phase_memory_end = get_memory_usage_mb()
    phase_duration = phase_end - phase_start
    phase_memory_change = phase_memory_end - phase_memory_start
    
    total_ops = sum(w['operations']['total'] for w in result_dict.values() if 'operations' in w)
    total_success = sum(w['operations']['success'] for w in result_dict.values() if 'operations' in w)
    total_failed = sum(w['operations']['failed'] for w in result_dict.values() if 'operations' in w)
    success_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print(f"\n📊 {phase_name} 结果:")
    print(f"   总操作: {total_ops:,}")
    print(f"   成功: {total_success:,}")
    print(f"   失败: {total_failed:,}")
    print(f"   成功率: {success_rate:.2f}%")
    print(f"   耗时: {phase_duration:.2f}s")
    print(f"   内存变化: {phase_memory_change:+.2f}MB")
    
    return total_ops, total_success, total_failed, success_rate, phase_duration, phase_memory_change


def main():
    print("\n" + "=" * 160)
    print("🚀 Agent Memory System - 第5轮超深度多阶段迭代测试")
    print("=" * 160)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("测试特点: 超大规模并发、超长内容、极端混乱数据、详细日志记录每一步")
    
    overall_start = time.time()
    overall_memory_start = get_memory_usage_mb()
    
    # 三个阶段的测试
    phases = [
        (20, 10, "阶段1: 20线程预热"),
        (100, 30, "阶段2: 100线程压力测试"),
        (200, 60, "阶段3: 200线程极限测试"),
    ]
    
    all_results = []
    total_ops = 0
    total_success = 0
    total_failed = 0
    
    for workers, duration, name in phases:
        ops, success, failed, rate, time_taken, mem_change = run_phase(workers, duration, name)
        all_results.append((name, ops, success, failed, rate, time_taken, mem_change))
        total_ops += ops
        total_success += success
        total_failed += failed
    
    overall_end = time.time()
    overall_memory_end = get_memory_usage_mb()
    overall_duration = overall_end - overall_start
    overall_memory_change = overall_memory_end - overall_memory_start
    overall_rate = total_success / total_ops * 100 if total_ops > 0 else 0
    
    print("\n" + "=" * 160)
    print("🏆 第5轮超深度测试完整总结")
    print("=" * 160)
    
    print(f"\n总耗时: {overall_duration:.2f}s ({overall_duration / 60:.1f} 分钟)")
    print(f"初始内存: {overall_memory_start:.2f}MB")
    print(f"最终内存: {overall_memory_end:.2f}MB")
    print(f"内存变化: {overall_memory_change:+.2f}MB")
    
    print(f"\n📈 总体:")
    print(f"   总操作: {total_ops:,}")
    print(f"   成功: {total_success:,}")
    print(f"   失败: {total_failed:,}")
    print(f"   总体成功率: {overall_rate:.2f}%")
    
    if overall_rate >= 99:
        print("\n🏆🏆🏆 完美！系统极其稳定！")
    elif overall_rate >= 95:
        print("\n✅ 优秀！系统非常稳定！")
    elif overall_rate >= 90:
        print("\n✅ 良好！系统稳定！")
    elif overall_rate >= 80:
        print("\n⚠️ 基本可用！")
    else:
        print("\n❌ 需要修复！")
    
    print("\n📊 分阶段结果:")
    for name, ops, success, failed, rate, time_taken, mem_change in all_results:
        print(f"   {name}: {ops:,} ops, {rate:.2f}%, 内存变化 {mem_change:+.2f}MB")
    
    print(f"\n详细日志已保存到: /workspace/advanced-agent-memory-system/round5_test.log")
    print("=" * 160)
    
    return overall_rate


if __name__ == '__main__':
    gc.enable()
    gc.collect()
    final_rate = main()
    sys.exit(0 if final_rate >= 90 else 1)
