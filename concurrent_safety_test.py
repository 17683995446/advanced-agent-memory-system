#!/usr/bin/env python3
"""
并发安全漏洞验证测试 - 慢工出细活
验证 LongTermMemory 中 _content_hash_index 的并发安全问题
"""

import sys
import time
import random
import threading
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


class ConcurrentSafetyTester:
    """并发安全测试器"""
    
    def __init__(self):
        self.errors = []
        self.duplicate_issues = 0
        self.lock = threading.Lock()
        self.success_count = 0
        self.attempt_count = 0
    
    def test_duplicate_content(self, worker_id: int, num_ops: int = 100) -> None:
        """测试重复内容的并发写入"""
        # 每个线程重复写入相同的内容多次
        same_content = f"这是测试内容，用于检查并发去重 - {datetime.now().isoformat()}"
        
        for i in range(num_ops):
            self.attempt_count += 1
            try:
                config = AgentMemoryConfig(
                    long_term=LongTermMemoryConfig(
                        embedding={"provider": "fake", "fake_dimension": 64},
                        vector_store={"backend": "memory"},
                    ),
                )
                memory = AgentMemory(config=config)
                
                # 关键测试：所有线程都写入 SAME_CONTENT 5次
                ids = []
                for _ in range(5):
                    mem_id = memory.remember(
                        content=same_content,
                        importance=random.uniform(0.1, 0.9)
                    )
                    ids.append(mem_id)
                
                # 检查：所有5次记住返回的ID应该相同！
                unique_ids = set(ids)
                if len(unique_ids) > 1:
                    with self.lock:
                        self.duplicate_issues += 1
                        self.errors.append({
                            "worker_id": worker_id,
                            "iteration": i,
                            "issue": f"发现重复ID！应该1个但有{len(unique_ids)}个",
                            "ids": list(unique_ids)[:5],
                            "time": datetime.now().isoformat()
                        })
                else:
                    with self.lock:
                        self.success_count += 1
                
                memory.close()
                
            except Exception as e:
                with self.lock:
                    self.errors.append({
                        "worker_id": worker_id,
                        "error": str(e),
                        "time": datetime.now().isoformat()
                    })
    
    def test_high_concurrency_hash_index(self, duration_seconds: int = 30) -> Dict:
        """极高并发测试哈希索引的安全性"""
        print(f"\n{'='*90}")
        print(f"🔥 并发安全漏洞验证测试")
        print(f"{'='*90}")
        print(f"测试目标：验证 LongTermMemory 的 _content_hash_index 并发安全性")
        print(f"测试持续：{duration_seconds}秒")
        print(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        num_workers = 25
        start_time = time.time()
        
        print(f"\n启动 {num_workers} 个并发线程进行重复内容写入测试...")
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(self.test_duplicate_content, worker_id)
                for worker_id in range(num_workers)
            ]
            
            # 监控
            while any(f.running() for f in futures) and (time.time() - start_time) < duration_seconds:
                time.sleep(5)
                with self.lock:
                    print(f"  [状态] 尝试次数: {self.attempt_count}, 成功: {self.success_count}, 问题: {self.duplicate_issues}")
            
            for f in futures:
                try:
                    f.result(timeout=5)
                except Exception as e:
                    print(f"  线程异常: {e}")
        
        total_time = time.time() - start_time
        
        # 总结
        print(f"\n{'='*90}")
        print(f"并发安全测试 - 最终报告")
        print(f"{'='*90}")
        
        print(f"\n总运行时间: {total_time:.2f}秒")
        print(f"总尝试次数: {self.attempt_count}")
        print(f"成功次数: {self.success_count}")
        print(f"重复内容问题: {self.duplicate_issues}")
        
        if self.duplicate_issues > 0:
            print(f"\n❌ 发现严重并发安全漏洞！")
            print(f"   问题位置: LongTermMemory._content_hash_index")
            print(f"   原因: 哈希索引没有加锁保护")
            if len(self.errors) > 0:
                print(f"\n错误详情 (前5条):")
                for i, err in enumerate(self.errors[:5]):
                    print(f"  {i+1}. {err}")
            status = "FAIL"
        else:
            print(f"\n✅ 并发安全测试通过！")
            status = "PASS"
        
        print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return {
            "status": status,
            "total_attempts": self.attempt_count,
            "success_count": self.success_count,
            "duplicate_issues": self.duplicate_issues,
            "errors": len(self.errors),
            "duration": total_time
        }


def main():
    """主函数"""
    tester = ConcurrentSafetyTester()
    result = tester.test_high_concurrency_hash_index(30)
    
    if result["status"] == "PASS":
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
