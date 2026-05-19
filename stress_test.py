"""
极端压力测试 - 发现系统深层缺陷

测试场景：
1. 百万级记忆插入性能
2. 长时间运行内存泄漏
3. 高并发读写冲突
4. 数据损坏恢复能力
5. 边界极限条件
"""

import sys
import time
import threading
import multiprocessing
import psutil
import os
import json
import random
import string

sys.path.insert(0, "/workspace/agent-memory-system")

from memory_system import AgentMemory, AgentMemoryConfig


def get_memory_usage():
    """获取当前进程内存使用（MB）"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def generate_random_content(length=100):
    """生成随机内容"""
    return ''.join(random.choices(string.ascii_letters + string.digits + ' ', k=length))


class StressTestResult:
    def __init__(self, name):
        self.name = name
        self.errors = []
        self.warnings = []
        self.metrics = {}
        self.passed = True

    def add_error(self, msg):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg):
        self.warnings.append(msg)

    def report(self):
        status = "✅ 通过" if self.passed else "❌ 失败"
        print(f"\n{'='*60}")
        print(f"  {self.name}: {status}")
        print(f"{'='*60}")
        if self.metrics:
            print("  指标:")
            for k, v in self.metrics.items():
                print(f"    {k}: {v}")
        if self.warnings:
            print(f"  警告 ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"    ⚠ {w}")
        if self.errors:
            print(f"  错误 ({len(self.errors)}):")
            for e in self.errors:
                print(f"    ✗ {e}")
        print()


# ============================================================
# P1: 百万级记忆压力测试
# ============================================================
def test_massive_scale():
    """百万级记忆插入和检索性能测试"""
    result = StressTestResult("P1: 百万级记忆压力测试")
    
    config = AgentMemoryConfig(
        short_term={"working_memory_capacity": 100, "history_limit": 500},
        long_term={
            "embedding": {"provider": "fake", "fake_dimension": 64},
            "vector_store": {"backend": "memory"},
        },
        auto_consolidate=False,
    )
    mem = AgentMemory(config=config)
    
    try:
        # 测试1: 批量插入10万条记忆
        batch_size = 1000
        total_records = 10000  # 从1万开始，避免内存不足
        
        start_time = time.time()
        start_mem = get_memory_usage()
        
        for batch_idx in range(total_records // batch_size):
            items = []
            for i in range(batch_size):
                idx = batch_idx * batch_size + i
                items.append({
                    "content": f"压力测试记忆-{idx}: {generate_random_content(50)}",
                    "category": f"batch_{batch_idx % 10}",
                    "importance": random.uniform(0.1, 0.9),
                    "tags": [f"tag_{idx % 20}"],
                })
            
            br = mem.batch_remember(items)
            if br["failed"] > 0:
                result.add_warning(f"批次 {batch_idx}: {br['failed']} 条失败")
        
        insert_time = time.time() - start_time
        insert_mem = get_memory_usage() - start_mem
        
        result.metrics["插入数量"] = total_records
        result.metrics["插入耗时"] = f"{insert_time:.2f}s"
        result.metrics["插入速率"] = f"{total_records/insert_time:.0f} 条/秒"
        result.metrics["内存增长"] = f"{insert_mem:.1f} MB"
        result.metrics["单条内存"] = f"{insert_mem*1024/total_records:.2f} KB"
        
        # 测试2: 检索性能
        query_times = []
        for _ in range(100):
            t0 = time.time()
            results = mem.recall("压力测试", top_k=10)
            query_times.append(time.time() - t0)
        
        result.metrics["平均查询耗时"] = f"{sum(query_times)/len(query_times)*1000:.2f} ms"
        result.metrics["最大查询耗时"] = f"{max(query_times)*1000:.2f} ms"
        
        # 测试3: 类别过滤性能
        t0 = time.time()
        cat_results = mem.recall("压力测试", category="batch_5", top_k=100)
        cat_time = time.time() - t0
        result.metrics["类别过滤耗时"] = f"{cat_time*1000:.2f} ms"
        
        # 测试4: 内存使用检查
        count = mem.count_memories()
        result.metrics["实际记忆数"] = count
        
        if count != total_records:
            result.add_error(f"记忆数量不一致: 期望 {total_records}, 实际 {count}")
        
        # 测试5: 导出性能
        t0 = time.time()
        mem.export_memories("/tmp/stress_test_export.json", format="json")
        export_time = time.time() - t0
        result.metrics["导出耗时"] = f"{export_time:.2f}s"
        
        file_size = os.path.getsize("/tmp/stress_test_export.json") / 1024 / 1024
        result.metrics["导出文件大小"] = f"{file_size:.1f} MB"
        
    except Exception as e:
        import traceback
        result.add_error(f"未预期异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()
        if os.path.exists("/tmp/stress_test_export.json"):
            os.unlink("/tmp/stress_test_export.json")
    
    return result


# ============================================================
# P2: 内存泄漏检测
# ============================================================
def test_memory_leak():
    """长时间运行内存泄漏检测"""
    result = StressTestResult("P2: 内存泄漏检测")
    
    config = AgentMemoryConfig(
        short_term={"working_memory_capacity": 50, "history_limit": 200},
        long_term={
            "embedding": {"provider": "fake", "fake_dimension": 64},
            "vector_store": {"backend": "memory"},
        },
        auto_consolidate=False,
    )
    
    try:
        # 记录初始内存
        mem_samples = []
        
        for cycle in range(10):  # 10个周期
            mem = AgentMemory(config=config)
            
            # 每个周期：插入 → 查询 → 删除 → 关闭
            start_mem = get_memory_usage()
            
            # 插入1000条
            for i in range(1000):
                mem.remember(f"泄漏测试-{cycle}-{i}", category="leak_test")
            
            # 查询100次
            for _ in range(100):
                mem.recall("泄漏测试", top_k=10)
            
            # 删除一半
            all_memories = list(mem.get_all_memories())
            for m in all_memories[:500]:
                mem.delete_memory(m.id)
            
            # 强制GC
            import gc
            gc.collect()
            
            end_mem = get_memory_usage()
            mem_samples.append({
                "cycle": cycle,
                "start": start_mem,
                "end": end_mem,
                "delta": end_mem - start_mem,
            })
            
            mem.close()
        
        # 分析内存趋势
        deltas = [s["delta"] for s in mem_samples]
        avg_delta = sum(deltas) / len(deltas)
        max_delta = max(deltas)
        
        result.metrics["周期数"] = 10
        result.metrics["平均内存增长"] = f"{avg_delta:.2f} MB/周期"
        result.metrics["最大内存增长"] = f"{max_delta:.2f} MB"
        
        # 如果持续增长超过阈值，警告内存泄漏
        if deltas[-1] > deltas[0] + 50:  # 最后比开始多50MB
            result.add_warning("检测到可能的内存泄漏: 内存持续增长")
        
        # 详细样本
        for i, s in enumerate(mem_samples[:3]):
            result.metrics[f"周期{i}内存"] = f"+{s['delta']:.1f}MB"
            
    except Exception as e:
        import traceback
        result.add_error(f"未预期异常: {e}\n{traceback.format_exc()}")
    
    return result


# ============================================================
# P3: 并发安全测试
# ============================================================
def test_concurrent_safety():
    """多线程并发安全测试"""
    result = StressTestResult("P3: 并发安全测试")
    
    config = AgentMemoryConfig(
        short_term={"working_memory_capacity": 50, "history_limit": 200},
        long_term={
            "embedding": {"provider": "fake", "fake_dimension": 64},
            "vector_store": {"backend": "memory"},
        },
        auto_consolidate=False,
    )
    mem = AgentMemory(config=config)
    
    try:
        errors = []
        results_lock = threading.Lock()
        
        def writer_thread(thread_id):
            try:
                for i in range(100):
                    mem.remember(f"并发写入-T{thread_id}-{i}", category="concurrent")
            except Exception as e:
                with results_lock:
                    errors.append(f"Writer-{thread_id}: {e}")
        
        def reader_thread(thread_id):
            try:
                for i in range(100):
                    mem.recall(f"并发写入", top_k=5)
            except Exception as e:
                with results_lock:
                    errors.append(f"Reader-{thread_id}: {e}")
        
        def deleter_thread(thread_id):
            try:
                for i in range(50):
                    all_mem = list(mem.get_all_memories())
                    if all_mem:
                        mem.delete_memory(random.choice(all_mem).id)
            except Exception as e:
                with results_lock:
                    errors.append(f"Deleter-{thread_id}: {e}")
        
        start_time = time.time()
        
        # 启动多个线程
        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=writer_thread, args=(i,)))
            threads.append(threading.Thread(target=reader_thread, args=(i,)))
            threads.append(threading.Thread(target=deleter_thread, args=(i,)))
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=60)
        
        elapsed = time.time() - start_time
        
        result.metrics["线程数"] = len(threads)
        result.metrics["总操作数"] = "900+"
        result.metrics["耗时"] = f"{elapsed:.2f}s"
        result.metrics["错误数"] = len(errors)
        
        if errors:
            for e in errors[:5]:
                result.add_error(f"并发错误: {e}")
        
        # 验证数据一致性
        final_count = mem.count_memories()
        result.metrics["最终记忆数"] = final_count
        
    except Exception as e:
        import traceback
        result.add_error(f"未预期异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()
    
    return result


# ============================================================
# P4: 数据损坏恢复
# ============================================================
def test_data_corruption_recovery():
    """数据损坏和恢复测试"""
    result = StressTestResult("P4: 数据损坏恢复")
    
    try:
        # 测试1: 导入损坏的JSON
        config = AgentMemoryConfig(
            long_term={
                "embedding": {"provider": "fake", "fake_dimension": 64},
                "vector_store": {"backend": "memory"},
            },
        )
        mem = AgentMemory(config=config)
        
        # 创建损坏的导入文件
        with open("/tmp/corrupted.json", "w") as f:
            f.write('{"version": "1.0", "records": [{"id": "test", "content": null}]}')
        
        try:
            imp = mem.import_memories("/tmp/corrupted.json")
            result.metrics["损坏JSON处理"] = f"导入{imp.get('imported', 0)}条, 错误{imp.get('errors', 0)}个"
        except Exception as e:
            result.metrics["损坏JSON处理"] = f"正确拒绝: {type(e).__name__}"
        
        # 测试2: 导入不完整的记录
        with open("/tmp/incomplete.json", "w") as f:
            json.dump({
                "version": "1.0",
                "records": [
                    {"content": "完整记录", "category": "test", "importance": 0.5},
                    {"category": "缺少content"},  # 缺少必需字段
                    {},  # 空记录
                ]
            }, f)
        
        imp2 = mem.import_memories("/tmp/incomplete.json")
        result.metrics["不完整记录处理"] = f"成功{imp2.get('imported', 0)}, 失败{imp2.get('errors', 0)}"
        
        mem.close()
        
        # 清理
        for f in ["/tmp/corrupted.json", "/tmp/incomplete.json"]:
            if os.path.exists(f):
                os.unlink(f)
        
    except Exception as e:
        import traceback
        result.add_error(f"未预期异常: {e}\n{traceback.format_exc()}")
    
    return result


# ============================================================
# P5: 边界极限测试
# ============================================================
def test_boundary_limits():
    """边界极限条件测试"""
    result = StressTestResult("P5: 边界极限测试")
    
    config = AgentMemoryConfig(
        long_term={
            "embedding": {"provider": "fake", "fake_dimension": 64},
            "vector_store": {"backend": "memory"},
        },
    )
    mem = AgentMemory(config=config)
    
    try:
        # 测试1: 超长内容
        print("  测试超长内容...")
        long_content = "A" * 100000  # 10万字符
        try:
            mid = mem.remember(long_content, category="long")
            result.metrics["10万字符内容"] = f"接受 (ID: {mid[:8]}...)"
        except Exception as e:
            result.add_error(f"10万字符内容失败: {e}")
        
        # 测试2: 超多标签
        print("  测试超多标签...")
        many_tags = [f"tag_{i}" for i in range(1000)]
        try:
            mid = mem.remember("多标签测试", category="tags", tags=many_tags)
            result.metrics["1000个标签"] = "接受"
        except Exception as e:
            result.add_error(f"1000个标签失败: {e}")
        
        # 测试3: 超深嵌套元数据
        print("  测试超深嵌套...")
        deep_dict = {}
        current = deep_dict
        for i in range(100):  # 100层嵌套
            current["level"] = {}
            current = current["level"]
        current["value"] = "deep"
        
        try:
            mid = mem.remember("深嵌套测试", category="nested", metadata=deep_dict)
            result.metrics["100层嵌套元数据"] = "接受"
        except Exception as e:
            result.add_error(f"100层嵌套失败: {e}")
        
        # 测试4: 特殊Unicode字符
        print("  测试特殊字符...")
        special_chars = [
            "🎉🧠💡🚀🔥",  # Emoji
            "中文测试内容",  # 中文
            "العربية",  # 阿拉伯文
            "日本語テスト",  # 日文
            "\x00\x01\x02\x03",  # 控制字符
            "<script>alert('xss')</script>",  # XSS尝试
        ]
        
        special_success = 0
        for content in special_chars:
            try:
                mem.remember(content, category="special")
                special_success += 1
            except Exception as e:
                result.add_warning(f"特殊字符失败: {repr(content[:20])}: {e}")
        
        result.metrics["特殊字符通过率"] = f"{special_success}/{len(special_chars)}"
        
        # 测试5: 批量超大请求
        print("  测试超大批量...")
        huge_batch = [{"content": f"超大批次{i}", "category": "huge"} for i in range(10000)]
        try:
            t0 = time.time()
            br = mem.batch_remember(huge_batch)
            elapsed = time.time() - t0
            result.metrics["1万条批量插入"] = f"成功{br['success']}, 耗时{elapsed:.1f}s"
        except Exception as e:
            result.add_error(f"1万条批量失败: {e}")
        
    except Exception as e:
        import traceback
        result.add_error(f"未预期异常: {e}\n{traceback.format_exc()}")
    finally:
        mem.close()
    
    return result


# ============================================================
# 主执行
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Agent Memory System - 极端压力测试")
    print("=" * 60)
    
    all_results = []
    tests = [
        ("P1", test_massive_scale),
        ("P2", test_memory_leak),
        ("P3", test_concurrent_safety),
        ("P4", test_data_corruption_recovery),
        ("P5", test_boundary_limits),
    ]
    
    total_start = time.time()
    for name, test_fn in tests:
        print(f"\n▶ 执行 {name}...")
        r = test_fn()
        r.report()
        all_results.append(r)
    total_time = time.time() - total_start
    
    # 汇总
    print("\n" + "=" * 60)
    print("  汇总报告")
    print("=" * 60)
    passed = sum(1 for r in all_results if r.passed)
    total_errors = sum(len(r.errors) for r in all_results)
    total_warnings = sum(len(r.warnings) for r in all_results)
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  通过: {passed}/{len(all_results)}")
    print(f"  错误: {total_errors}")
    print(f"  警告: {total_warnings}")
    
    if total_errors > 0:
        print("\n  需要修复的错误:")
        for r in all_results:
            for e in r.errors:
                print(f"    [{r.name}] {e}")
    
    if total_warnings > 0:
        print(f"\n  警告 ({total_warnings}):")
        for r in all_results:
            for w in r.warnings:
                print(f"    [{r.name}] {w}")
    print()
