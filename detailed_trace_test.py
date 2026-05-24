#!/usr/bin/env python3
"""
超级详细的代码追踪日志系统
通过在每句关键代码后打印日志，实时追踪系统运行状态
"""

import sys
import time
import random
import string
import threading
import logging
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Set

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

# ================ 超级详细的日志配置 ================
logger = logging.getLogger('detailed_trace')
logger.setLevel(logging.DEBUG)

# 文件处理器 - 保存详细日志
file_handler = logging.FileHandler('detailed_trace_test.log', mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# 控制台处理器 - 仅显示关键信息
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ================ 追踪装饰器 ================
def trace_function(func):
    """追踪函数调用的装饰器"""
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"▶ ENTER: {func_name}()")
        if args:
            logger.debug(f"  Args: {[repr(arg)[:100] for arg in args]}")
        if kwargs:
            logger.debug(f"  Kwargs: {kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"◀ EXIT: {func_name}() - Success")
            if result is not None:
                logger.debug(f"  Result: {repr(result)[:100]}")
            return result
        except Exception as e:
            logger.error(f"✗ EXCEPTION: {func_name}() - {type(e).__name__}: {e}")
            logger.debug(f"  Traceback: {traceback.format_exc()}")
            raise
    return wrapper

# ================ 极端混乱测试场景 ================
class ExtremeChaosTester:
    """极端混乱场景测试器"""
    
    def __init__(self):
        self.results = {
            'total_ops': 0,
            'success_ops': 0,
            'failed_ops': 0,
            'errors': [],
            'warnings': []
        }
        self.active_memory_ids: Set[str] = set()
        self.active_entities: Set[str] = set()
        self._lock = threading.RLock()
        self.stopped = False
    
    @trace_function
    def generate_chaos_content(self, min_len: int = 10, max_len: int = 5000) -> str:
        """生成极端混乱的内容"""
        length = random.randint(min_len, max_len)
        content = []
        
        # 混合各种内容
        for _ in range(length):
            c = random.choice([
                random.choice(string.ascii_letters),
                random.choice(string.digits),
                random.choice('中文测试日本語한국어'),
                random.choice('!@#$%^&*()_+-=[]{}|;:,.<>?'),
                random.choice(string.whitespace)
            ])
            content.append(c)
        
        return ''.join(content)
    
    @trace_function
    def generate_chaos_tags(self, num_tags: Optional[int] = None) -> List[str]:
        """生成极端混乱的标签"""
        if num_tags is None:
            num_tags = random.randint(0, 20)
        tags = []
        for _ in range(num_tags):
            tag_length = random.randint(1, 30)
            tag = ''.join(random.choice(string.ascii_letters + string.digits) 
                          for _ in range(tag_length))
            tags.append(tag)
        return tags
    
    @trace_function
    def extreme_remember_operation(self, worker_id: int, memory) -> Dict[str, Any]:
        """极端混乱的记住操作"""
        operation_id = f"{worker_id}_{int(time.time()*1000000)}"
        logger.debug(f"[{operation_id}] Starting REMEMBER operation")
        
        try:
            content = self.generate_chaos_content()
            memory_type = random.choice([
                "fact", "semantic", "episodic", "procedural", "conversation"
            ])
            category = random.choice([
                "chaos", "test", "general", "personal", "work", "memory"
            ])
            importance = random.uniform(0.0, 1.0)
            tags = self.generate_chaos_tags()
            
            logger.debug(f"[{operation_id}] Memory parameters: type={memory_type}, "
                       f"category={category}, importance={importance:.3f}, tags={len(tags)}")
            
            memory_id = memory.remember(
                content=content,
                memory_type=memory_type,
                category=category,
                importance=importance,
                tags=tags
            )
            
            with self._lock:
                self.active_memory_ids.add(memory_id)
            
            logger.info(f"[{operation_id}] ✅ REMEMBER successful - ID: {memory_id[:16]}")
            return {'success': True, 'memory_id': memory_id}
            
        except Exception as e:
            logger.error(f"[{operation_id}] ❌ REMEMBER failed: {type(e).__name__}: {e}")
            with self._lock:
                self.results['errors'].append({
                    'type': 'remember',
                    'worker': worker_id,
                    'error': str(e),
                    'time': datetime.now().isoformat()
                })
            return {'success': False, 'error': str(e)}
    
    @trace_function
    def extreme_recall_operation(self, worker_id: int, memory) -> Dict[str, Any]:
        """极端混乱的搜索操作"""
        operation_id = f"{worker_id}_{int(time.time()*1000000)}"
        logger.debug(f"[{operation_id}] Starting RECALL operation")
        
        try:
            query = self.generate_chaos_content(1, 50)
            top_k = random.randint(1, 50)
            
            logger.debug(f"[{operation_id}] Recall parameters: query={repr(query)[:30]}, top_k={top_k}")
            
            results = memory.recall(query, top_k=top_k)
            logger.info(f"[{operation_id}] ✅ RECALL successful - found {len(results)} results")
            return {'success': True, 'results_count': len(results)}
            
        except Exception as e:
            logger.error(f"[{operation_id}] ❌ RECALL failed: {type(e).__name__}: {e}")
            with self._lock:
                self.results['errors'].append({
                    'type': 'recall',
                    'worker': worker_id,
                    'error': str(e),
                    'time': datetime.now().isoformat()
                })
            return {'success': False, 'error': str(e)}
    
    @trace_function
    def extreme_forget_operation(self, worker_id: int, memory) -> Dict[str, Any]:
        """极端混乱的删除操作"""
        operation_id = f"{worker_id}_{int(time.time()*1000000)}"
        logger.debug(f"[{operation_id}] Starting FORGET operation")
        
        try:
            target_id = None
            with self._lock:
                if self.active_memory_ids and random.random() < 0.8:
                    # 80% 概率删除真实存在的
                    target_id = random.choice(list(self.active_memory_ids))
                else:
                    # 20% 概率删除不存在的
                    target_id = f"fake_{random.randint(1, 999999)}"
            
            logger.debug(f"[{operation_id}] Forgetting ID: {target_id[:16] if target_id else None}")
            
            success = memory.forget_memory(target_id) if target_id else False
            
            if success and target_id:
                with self._lock:
                    if target_id in self.active_memory_ids:
                        self.active_memory_ids.remove(target_id)
            
            logger.info(f"[{operation_id}] {'✅' if success else '⚠️'} FORGET {'successful' if success else 'skipped'}")
            return {'success': True, 'result': success}
            
        except Exception as e:
            logger.error(f"[{operation_id}] ❌ FORGET failed: {type(e).__name__}: {e}")
            with self._lock:
                self.results['errors'].append({
                    'type': 'forget',
                    'worker': worker_id,
                    'error': str(e),
                    'time': datetime.now().isoformat()
                })
            return {'success': False, 'error': str(e)}
    
    @trace_function
    def extreme_entity_operation(self, worker_id: int, memory) -> Dict[str, Any]:
        """极端混乱的知识图谱操作"""
        operation_id = f"{worker_id}_{int(time.time()*1000000)}"
        logger.debug(f"[{operation_id}] Starting ENTITY operation")
        
        try:
            entity_name = f"Chaos_{random.randint(1, 99999)}_" + self.generate_chaos_content(5, 20)
            entity_type = random.choice(['concept', 'person', 'tool', 'project', 'item', 'unknown'])
            description = self.generate_chaos_content(10, 200)
            
            logger.debug(f"[{operation_id}] Adding entity: {entity_name[:30]}...")
            
            result = memory.add_entity(
                name=entity_name,
                entity_type=entity_type,
                description=description
            )
            
            with self._lock:
                self.active_entities.add(entity_name)
            
            logger.info(f"[{operation_id}] ✅ ADD_ENTITY successful: {entity_name[:30]}...")
            return {'success': True, 'entity': entity_name}
            
        except Exception as e:
            logger.error(f"[{operation_id}] ❌ ADD_ENTITY failed: {type(e).__name__}: {e}")
            with self._lock:
                self.results['errors'].append({
                    'type': 'entity',
                    'worker': worker_id,
                    'error': str(e),
                    'time': datetime.now().isoformat()
                })
            return {'success': False, 'error': str(e)}
    
    @trace_function
    def extreme_chaos_worker(self, worker_id: int, duration_seconds: float, memory):
        """极端混乱的工作线程"""
        worker_name = f"ChaosWorker-{worker_id:02d}"
        logger.info(f"🚀 [{worker_name}] Starting chaos operations for {duration_seconds}s")
        
        start_time = time.time()
        local_ops = 0
        
        while time.time() - start_time < duration_seconds and not self.stopped:
            try:
                # 随机选择操作
                op_type = random.choice([
                    'remember', 'recall', 'forget', 'entity', 
                    'add_interaction', 'short_term'
                ])
                
                logger.debug(f"[{worker_name}] Performing operation: {op_type}")
                
                if op_type == 'remember':
                    self.extreme_remember_operation(worker_id, memory)
                elif op_type == 'recall':
                    self.extreme_recall_operation(worker_id, memory)
                elif op_type == 'forget':
                    self.extreme_forget_operation(worker_id, memory)
                elif op_type == 'entity':
                    self.extreme_entity_operation(worker_id, memory)
                elif op_type == 'add_interaction':
                    try:
                        role = random.choice(['user', 'assistant', 'system'])
                        content = self.generate_chaos_content(10, 200)
                        memory.add_interaction(role=role, content=content)
                    except Exception as e:
                        logger.warning(f"[{worker_name}] add_interaction skipped: {e}")
                elif op_type == 'short_term':
                    try:
                        key = f"temp_{random.randint(1, 999999)}"
                        content = self.generate_chaos_content(10, 500)
                        importance = random.uniform(0.0, 1.0)
                        memory.add_to_working_memory(
                            key=key,
                            content=content,
                            importance=importance
                        )
                    except Exception as e:
                        logger.warning(f"[{worker_name}] short_term skipped: {e}")
                
                local_ops += 1
                
                # 随机延迟 - 模拟真实场景
                delay = random.uniform(0.0001, 0.05)
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"[{worker_name}] Exception in worker: {type(e).__name__}: {e}")
        
        logger.info(f"🏁 [{worker_name}] Completed {local_ops} operations in {time.time() - start_time:.2f}s")
        return {'worker_id': worker_id, 'operations': local_ops}
    
    @trace_function
    def run_extreme_chaos_test(
        self, 
        num_workers: int = 20, 
        duration_seconds: int = 120,
        initial_memories: int = 100
    ):
        """运行极端混乱场景测试"""
        logger.info("=" * 100)
        logger.info("🔥 EXTREME CHAOS SCENARIO TEST - Slow and Steady")
        logger.info("=" * 100)
        logger.info(f"Workers: {num_workers}")
        logger.info(f"Duration: {duration_seconds}s")
        logger.info(f"Initial memories: {initial_memories}")
        logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 初始化系统
        logger.info("\n[1/3] Initializing memory system...")
        try:
            from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig
            config = AgentMemoryConfig(
                long_term=LongTermMemoryConfig(
                    embedding={"provider": "fake", "fake_dimension": 64},
                    vector_store={"backend": "memory"}
                ),
                knowledge_graph={"enabled": True},
                structured_store={"enabled": True, "db_path": ":memory:"}
            )
            memory = AgentMemory(config)
            logger.info("✅ Memory system initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize memory system: {e}")
            raise
        
        # 预填充初始数据
        logger.info(f"\n[2/3] Pre-filling {initial_memories} initial memories...")
        try:
            for i in range(initial_memories):
                content = self.generate_chaos_content(50, 200)
                mem_id = memory.remember(
                    content=content,
                    importance=random.uniform(0.0, 1.0)
                )
                with self._lock:
                    self.active_memory_ids.add(mem_id)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"  Pre-filled {i + 1}/{initial_memories} memories")
            
            logger.info(f"✅ Pre-filled {initial_memories} memories successfully")
        except Exception as e:
            logger.error(f"❌ Failed to pre-fill memories: {e}")
            raise
        
        # 运行极端混乱测试
        logger.info(f"\n[3/3] Starting {num_workers} chaos workers...")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                future = executor.submit(
                    self.extreme_chaos_worker,
                    worker_id,
                    duration_seconds,
                    memory
                )
                futures.append(future)
            
            # 监控进度
            completed = 0
            while completed < num_workers:
                time.sleep(5)
                
                # 获取统计信息
                try:
                    stats = memory.get_stats()
                    logger.info(f"\n📊 [STATUS] Elapsed: {time.time() - start_time:.1f}s")
                    logger.info(f"  - Active memories: {len(self.active_memory_ids)}")
                    logger.info(f"  - Active entities: {len(self.active_entities)}")
                    logger.info(f"  - System stats: {stats}")
                except Exception as e:
                    logger.warning(f"  (Failed to get stats: {e})")
                
                # 检查完成的工作
                completed = sum(1 for f in futures if f.done())
                if completed > 0:
                    logger.info(f"  - Workers completed: {completed}/{num_workers}")
        
        total_time = time.time() - start_time
        
        # 最终总结
        logger.info("\n" + "=" * 100)
        logger.info("🎉 EXTREME CHAOS TEST - FINAL REPORT")
        logger.info("=" * 100)
        
        logger.info(f"\nTotal duration: {total_time:.2f}s ({total_time/60:.1f} minutes)")
        
        if self.results['errors']:
            logger.error(f"\n❌ ERRORS FOUND: {len(self.results['errors'])}")
            for i, err in enumerate(self.results['errors'][:10]):
                logger.error(f"  {i+1}. [{err['type']}] [{err['time']}] {err['error'][:100]}")
        else:
            logger.info("\n✅ NO ERRORS FOUND!")
        
        logger.info(f"\nActive memories: {len(self.active_memory_ids)}")
        logger.info(f"Active entities: {len(self.active_entities)}")
        
        logger.info("\n" + "=" * 100)
        
        try:
            memory.close()
            logger.info("✅ Memory system closed properly")
        except Exception as e:
            logger.warning(f"⚠️ Warning while closing: {e}")
        
        return {'success': len(self.results['errors']) == 0, 'errors_count': len(self.results['errors'])}

# ================ 主函数 ================
@trace_function
def main():
    """主函数"""
    print("\n" + "=" * 100)
    print("🔥 超级详细的极端混乱测试 - 慢工出细活")
    print("=" * 100)
    print("\n🔍 每句关键代码都会打印详细日志")
    print("   请查看 detailed_trace_test.log 查看完整执行追踪")
    print("\n" + "=" * 100 + "\n")
    
    tester = ExtremeChaosTester()
    result = tester.run_extreme_chaos_test(
        num_workers=20,
        duration_seconds=60,  # 1分钟快速测试，可改为更长
        initial_memories=100
    )
    
    return 0 if result['success'] else 1

if __name__ == "__main__":
    sys.exit(main())
