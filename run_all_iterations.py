#!/usr/bin/env python3
"""
Agent Memory System - 多次迭代超级压力测试 - 主程序
按顺序执行所有5次迭代测试
"""

import sys
import time
import subprocess
from datetime import datetime

print("\n" + "="*100)
print("🎯 Agent Memory System - 多次迭代超级压力测试")
print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print("="*100)

# 测试脚本列表
iterations = [
    ("第1次迭代: 超大规模并发测试", "iteration1_stress_test.py"),
    ("第2次迭代: 超大数据量测试", "iteration2_data_volume_test.py"),
    ("第3次迭代: 极度混乱场景测试", "iteration3_chaos_test.py"),
    ("第4次迭代: 边界条件测试", "iteration4_boundary_test.py"),
    ("第5次迭代: 最终综合验证", "iteration5_final_verification.py"),
]

results = []
start_time = time.time()

for i, (name, script) in enumerate(iterations, 1):
    print("\n" + "="*100)
    print(f"🚀 开始执行: {name}")
    print("="*100)

    iter_start = time.time()

    try:
        result = subprocess.run(
            ['python', script],
            cwd='/workspace/advanced-agent-memory-system',
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        iter_time = time.time() - iter_start
        success = result.returncode == 0

        results.append({
            'iteration': i,
            'name': name,
            'success': success,
            'time': iter_time,
            'returncode': result.returncode
        })

        if success:
            print(f"\n✅ {name} - 通过 ({iter_time:.1f}s)")
        else:
            print(f"\n❌ {name} - 失败 ({iter_time:.1f}s)")
            print(f"错误输出:\n{result.stderr[:500]}")

    except subprocess.TimeoutExpired:
        print(f"\n⏱️ {name} - 超时 (>600s)")
        results.append({
            'iteration': i,
            'name': name,
            'success': False,
            'time': 600,
            'returncode': -1
        })

    except Exception as e:
        print(f"\n❌ {name} - 异常: {e}")
        results.append({
            'iteration': i,
            'name': name,
            'success': False,
            'time': 0,
            'returncode': -2
        })

# 最终总结
total_time = time.time() - start_time
passed = sum(1 for r in results if r['success'])

print("\n" + "="*100)
print("🎯 多次迭代测试 - 最终总结")
print("="*100)

print(f"\n执行时间: {total_time:.1f}s ({total_time/60:.1f}分钟)")
print(f"通过: {passed}/{len(results)}")

for r in results:
    status = "✅" if r['success'] else "❌"
    print(f"{status} {r['name']}: {r['time']:.1f}s")

if passed == len(results):
    print("\n🎉 所有5次迭代测试全部通过！")
    print("系统已完全通过多次迭代压力测试，达到生产环境标准！")
    sys.exit(0)
else:
    print(f"\n⚠️  有 {len(results)-passed} 次迭代失败，需要进一步调查")
    sys.exit(1)
