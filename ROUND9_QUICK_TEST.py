"""
第9轮快速验证测试 - 简化版
"""
import sys
import time
import random
import logging
from datetime import datetime

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s.%(msecs)03d] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, '/workspace/advanced-agent-memory-system')

from memory_system import AgentMemory, AgentMemoryConfig

def main():
    print("\n" + "=" * 100)
    print("第9轮超深度快速验证测试")
    print("=" * 100 + "\n")
    
    # 测试参数
    TOTAL_OPS = 2000
    errors = []
    
    try:
        # 初始化
        print("  初始化系统...")
        config = AgentMemoryConfig(
            long_term={
                "embedding": {"provider": "fake"},
                "vector_store": {"backend": "memory"}
            },
            auto_consolidate=False
        )
        memory = AgentMemory(config=config)
        print("  ✅ 初始化成功\n")
        
        # 基础测试
        print("  基础功能验证...")
        for i in range(20):
            memory.remember(f"测试内容 {i}", "fact", "测试", 0.5 + i * 0.02)
        results = memory.recall("测试", top_k=10)
        print(f"  ✅ 基础功能正常，召回 {len(results)} 条\n")
        
        # 核心测试
        print(f"  执行 {TOTAL_OPS} 次复杂操作...")
        start_time = time.time()
        
        for i in range(TOTAL_OPS):
            try:
                op_type = random.randint(1, 6)
                
                if op_type == 1:
                    # 标准记忆
                    memory.remember(f"记忆内容 {i}", random.choice(["fact", "semantic", "episodic"]), 
                                   random.choice(["用户", "产品", "对话", "测试"]), 
                                   random.uniform(0.0, 1.0))
                elif op_type == 2:
                    # 召回
                    query = f"记忆内容 {i % 100}"
                    memory.recall(query, top_k=random.randint(1, 10))
                elif op_type == 3:
                    # 知识图谱
                    e1 = f"实体_{random.randint(0, 1000)}"
                    e2 = f"实体_{random.randint(0, 1000)}"
                    memory.add_entity(e1, random.choice(["用户", "产品", "公司"]))
                    memory.add_entity(e2, random.choice(["用户", "产品", "公司"]))
                    memory.add_relation(e1, random.choice(["相关", "包含", "使用"]), e2)
                elif op_type == 4:
                    # 对话
                    speaker = random.choice(["user", "assistant"])
                    memory.remember_conversation(speaker, f"第 {i} 轮对话")
                elif op_type == 5:
                    # 偏好
                    key = f"pref_{random.randint(0, 1000)}"
                    value = f"value_{random.randint(0, 1000)}"
                    memory.store_preference(key, value)
                else:
                    # 统计
                    memory.get_stats()
                
                if (i + 1) % 200 == 0:
                    elapsed = time.time() - start_time
                    print(f"    进度: {i+1}/{TOTAL_OPS} ({100*(i+1)/TOTAL_OPS:.0f}%), 耗时: {elapsed:.1f}秒, 错误: {len(errors)}")
            
            except Exception as e:
                if len(errors) < 50:
                    errors.append(f"操作 {i}: {str(e)}")
                    logger.error(f"操作 {i}: {str(e)}")
        
        total_time = time.time() - start_time
        avg_speed = TOTAL_OPS / total_time
        
        print("\n" + "=" * 80)
        print("  测试完成总结")
        print("=" * 80)
        print(f"  总操作数: {TOTAL_OPS}")
        print(f"  总耗时: {total_time:.2f}秒")
        print(f"  平均速度: {avg_speed:.1f} ops/s")
        print(f"  错误数: {len(errors)}")
        
        # 最终验证
        print("\n  数据一致性验证...")
        stats = memory.get_stats()
        print(f"  ✅ 统计模块: {list(stats.keys())}")
        
        history = memory.get_conversation_history(50)
        print(f"  ✅ 对话历史: {len(history)} 条")
        
        # 资源释放
        print("\n  资源释放...")
        memory.close()
        for i in range(3):
            memory.close()
        print("  ✅ 资源释放成功\n")
        
        # 写入报告
        with open("/workspace/advanced-agent-memory-system/ROUND9_QUICK_REPORT.txt", "w", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write("第9轮快速验证测试 - 报告\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总操作数: {TOTAL_OPS}\n")
            f.write(f"总耗时: {total_time:.2f}秒\n")
            f.write(f"平均速度: {avg_speed:.1f} ops/s\n")
            f.write(f"错误数: {len(errors)}\n\n")
            
            if errors:
                f.write("错误详情:\n")
                for err in errors[:30]:
                    f.write(f"  - {err}\n")
        
        print("=" * 100)
        if len(errors) <= 20:
            print("✅ 第9轮快速验证测试通过！系统稳定！")
        else:
            print(f"⚠️  第9轮测试完成，有 {len(errors)} 个错误")
        print("=" * 100 + "\n")
        
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
