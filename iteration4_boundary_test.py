#!/usr/bin/env python3
"""
Agent Memory System - 多次迭代超级压力测试
第4次迭代：边界条件和异常处理测试
"""

import sys
import time
import threading
import logging

sys.path.insert(0, '/workspace/advanced-agent-memory-system')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('iteration4')

class Iteration4BoundaryTest:
    """第4次迭代：边界条件和异常处理测试"""

    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.errors = []

    def test_case(self, name: str, test_func, memory):
        """执行单个测试用例"""
        try:
            result = test_func(memory)
            if result:
                logger.info(f"✅ {name}")
                self.tests_passed += 1
                return True
            else:
                logger.error(f"❌ {name}")
                self.tests_failed += 1
                return False
        except Exception as e:
            logger.error(f"❌ {name}: {e}")
            self.errors.append({'test': name, 'error': str(e)})
            self.tests_failed += 1
            return False

    def run(self):
        """运行测试"""
        from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

        logger.info("="*80)
        logger.info("第4次迭代：边界条件和异常处理测试")
        logger.info("="*80)

        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "fake_dimension": 64},
                vector_store={"backend": "memory"}
            ),
            knowledge_graph={"enabled": True},
            structured_store={"enabled": True, "db_path": ":memory:"}
        )
        memory = AgentMemory(config)

        # 测试1: 空内容
        self.test_case("空字符串", lambda m: self._test_empty_content(m), memory)

        # 测试2: 超长内容
        self.test_case("超长内容(100KB)", lambda m: self._test_long_content(m), memory)

        # 测试3: 特殊字符
        self.test_case("特殊字符组合", lambda m: self._test_special_chars(m), memory)

        # 测试4: 重复记忆
        self.test_case("重复内容去重", lambda m: self._test_duplicate(m), memory)

        # 测试5: 删除不存在的
        self.test_case("删除不存在的ID", lambda m: self._test_delete_nonexistent(m), memory)

        # 测试6: 搜索不存在的
        self.test_case("搜索不存在的", lambda m: self._test_search_nonexistent(m), memory)

        # 测试7: None值
        self.test_case("None值处理", lambda m: self._test_none_value(m), memory)

        # 测试8: 负数重要性
        self.test_case("负数重要性", lambda m: self._test_negative_importance(m), memory)

        # 测试9: 超大重要性
        self.test_case("超大重要性(>1.0)", lambda m: self._test_large_importance(m), memory)

        # 测试10: 并发操作
        self.test_case("并发安全性", lambda m: self._test_concurrent_safety(m), memory)

        # 总结
        logger.info("="*80)
        logger.info("第4次迭代 - 最终报告")
        logger.info("="*80)
        logger.info(f"通过: {self.tests_passed}")
        logger.info(f"失败: {self.tests_failed}")

        if self.errors:
            logger.error("\n错误详情:")
            for i, err in enumerate(self.errors[:5]):
                logger.error(f"  {i+1}. {err['test']}: {err['error']}")

        memory.close()
        logger.info("测试完成")

        return {
            'success': self.tests_failed == 0,
            'passed': self.tests_passed,
            'failed': self.tests_failed
        }

    def _test_empty_content(self, memory):
        """测试空内容"""
        try:
            memory.remember(content="", importance=0.5)
            return False  # 应该抛出异常
        except ValueError:
            return True

    def _test_long_content(self, memory):
        """测试超长内容"""
        try:
            content = "X" * 100000
            mem_id = memory.remember(content=content, importance=0.5)
            return mem_id is not None
        except:
            return False

    def _test_special_chars(self, memory):
        """测试特殊字符"""
        try:
            content = "中文🎉日本語😄한국어🔧!@#$%^&*()"
            mem_id = memory.remember(content=content, importance=0.5)
            return mem_id is not None
        except:
            return False

    def _test_duplicate(self, memory):
        """测试重复内容"""
        try:
            content = "这是重复测试内容"
            id1 = memory.remember(content=content, importance=0.5)
            id2 = memory.remember(content=content, importance=0.5)
            return id1 == id2  # 应该返回相同ID
        except:
            return False

    def _test_delete_nonexistent(self, memory):
        """测试删除不存在的"""
        try:
            result = memory.forget_memory("nonexistent_id_12345")
            return result == False
        except:
            return False

    def _test_search_nonexistent(self, memory):
        """测试搜索不存在的"""
        try:
            results = memory.recall("NONEXISTENT_QUERY_XYZ_12345", top_k=5)
            return len(results) == 0
        except:
            return False

    def _test_none_value(self, memory):
        """测试None值"""
        try:
            memory.remember(content=None, importance=0.5)
            return False
        except:
            return True

    def _test_negative_importance(self, memory):
        """测试负数重要性"""
        try:
            memory.remember(content="test", importance=-0.5)
            return False
        except ValueError:
            return True

    def _test_large_importance(self, memory):
        """测试超大重要性"""
        try:
            memory.remember(content="test", importance=1.5)
            return False
        except ValueError:
            return True

    def _test_concurrent_safety(self, memory):
        """测试并发安全性"""
        import threading
        results = []
        lock = threading.Lock()

        def worker():
            for _ in range(10):
                try:
                    mem_id = memory.remember(content="concurrent test", importance=0.5)
                    with lock:
                        results.append(mem_id)
                except:
                    pass

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return len(results) == 100

if __name__ == "__main__":
    tester = Iteration4BoundaryTest()
    result = tester.run()
    sys.exit(0 if result['success'] else 1)
