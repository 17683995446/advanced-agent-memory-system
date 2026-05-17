"""
Agent Memory System v5.1 创新功能测试

测试内容：
1. 记忆衰减引擎（MemoryDecayEngine）
2. LRU 容量管理与驱逐策略（MemoryVectorStore）
3. 衰减引擎与 AgentMemory 的集成
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from memory_system.core.memory_decay_engine import (
    MemoryDecayEngine, DecayConfig, DecayCurve, MemoryDecayState,
)
from memory_system.storage.vector_store.in_memory_backend import (
    MemoryVectorStore, EvictionPolicy,
)
from memory_system.storage.vector_store.models import MemoryRecord
from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig
from memory_system.core.long_term_persistent_memory import LongTermMemoryConfig
from memory_system.processing.text_embedding_provider import EmbeddingConfig


DIM = 64


def _make_config(**overrides):
    defaults = {
        "long_term": LongTermMemoryConfig(
            embedding=EmbeddingConfig(provider="fake", fake_dimension=DIM),
            vector_store={"backend": "memory"},
            auto_consolidate=False,
        ),
        "auto_consolidate": False,
        "structured_store": {"db_path": ":memory:", "enabled": True},
        "knowledge_graph": {"enabled": True},
    }
    defaults.update(overrides)
    return AgentMemoryConfig(**defaults)


def _make_record(content="test", importance=0.5, rid=None):
    return MemoryRecord(
        id=rid or f"mem_{int(time.time()*1000)}_{id(content)}",
        content=content,
        embedding=[0.1] * DIM,
        importance=importance,
    )


# ====================================================================
# 测试1: 衰减引擎核心功能
# ====================================================================
def test_decay_engine_basic():
    """测试衰减引擎的基本功能。"""
    print("\n" + "=" * 60)
    print("测试1: 衰减引擎核心功能")
    print("=" * 60)

    issues = []

    # 测试注册和查询
    engine = MemoryDecayEngine(DecayConfig(enabled=True))
    engine.register("mem_1", base_importance=0.9)
    engine.register("mem_2", base_importance=0.5)
    engine.register("mem_3", base_importance=0.1)

    eff1 = engine.get_effective_importance("mem_1")
    eff2 = engine.get_effective_importance("mem_2")

    if eff1 < 0.89 or eff1 > 0.91:
        issues.append(f"HIGH: 新注册记忆的有效重要性应为~0.9，实际 {eff1}")
    else:
        print(f"  ✅ 新注册记忆有效重要性正确: {eff1:.4f}")

    if eff2 < 0.49 or eff2 > 0.51:
        issues.append(f"HIGH: 低重要性记忆应为~0.5，实际 {eff2}")
    else:
        print(f"  ✅ 低重要性记忆正确: {eff2:.4f}")

    # 测试访问加成
    for _ in range(5):
        engine.record_access("mem_2")
    eff2_after = engine.get_effective_importance("mem_2")
    if eff2_after <= eff2:
        issues.append(f"MEDIUM: 访问后重要性应提升: {eff2} -> {eff2_after}")
    else:
        print(f"  ✅ 访问加成生效: {eff2:.4f} -> {eff2_after:.4f}")

    # 测试取消注册
    engine.unregister("mem_3")
    eff3 = engine.get_effective_importance("mem_3")
    if eff3 != 0.0:
        issues.append(f"MEDIUM: 取消注册后应返回0.0，实际 {eff3}")
    else:
        print(f"  ✅ 取消注册后返回0.0")

    # 测试统计
    stats = engine.get_stats()
    if stats["registered_count"] != 2:
        issues.append(f"MEDIUM: 注册数应为2，实际 {stats['registered_count']}")
    else:
        print(f"  ✅ 统计正确: {stats}")

    # 测试手动刷新
    refresh_stats = engine.refresh_once()
    if refresh_stats["total_decays"] >= 0:
        print(f"  ✅ 手动刷新成功: {refresh_stats['total_decays']} 次衰减")

    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    return issues


# ====================================================================
# 测试2: 衰减曲线类型
# ====================================================================
def test_decay_curves():
    """测试四种衰减曲线。"""
    print("\n" + "=" * 60)
    print("测试2: 衰减曲线类型")
    print("=" * 60)

    issues = []
    curves = [
        DecayCurve.EXPONENTIAL,
        DecayCurve.LINEAR,
        DecayCurve.STEP,
        DecayCurve.LOGARITHMIC,
    ]

    for curve in curves:
        config = DecayConfig(
            enabled=True,
            curve=curve,
            half_life=100.0,      # 100秒半衰期（测试用）
            max_age=200.0,       # 200秒最大年龄
            step_interval=50.0,  # 50秒一步
            log_scale=100.0,     # 100秒尺度
        )
        engine = MemoryDecayEngine(config)
        engine.register("test", base_importance=1.0)

        # 模拟时间流逝：修改 created_at
        state = engine._states["test"]
        state.created_at = time.time() - 150  # 150秒前

        eff = engine.get_effective_importance("test")
        if eff >= 1.0:
            issues.append(f"MEDIUM: {curve.value} 衰减后应 < 1.0，实际 {eff}")
        elif eff <= 0.0:
            issues.append(f"MEDIUM: {curve.value} 衰减后应 > 0.0，实际 {eff}")
        else:
            print(f"  ✅ {curve.value:15s}: 150秒后有效重要性 = {eff:.4f}")

    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    return issues


# ====================================================================
# 测试3: 容量压力加速衰减
# ====================================================================
def test_capacity_pressure():
    """测试容量压力下的加速衰减。"""
    print("\n" + "=" * 60)
    print("测试3: 容量压力加速衰减")
    print("=" * 60)

    issues = []

    config = DecayConfig(
        enabled=True,
        capacity_limit=5,  # 容量上限5条
    )
    engine = MemoryDecayEngine(config)

    # 注册10条记忆（超过容量上限5）
    for i in range(10):
        engine.register(f"mem_{i}", base_importance=0.8)

    effs = engine.get_all_effective_importances()
    avg_eff = sum(effs.values()) / len(effs) if effs else 0

    # 容量超限时应有加速衰减（capacity_factor < 1）
    if avg_eff >= 0.8:
        issues.append(f"MEDIUM: 容量超限时应有加速衰减，平均 {avg_eff:.4f}")
    else:
        print(f"  ✅ 容量压力加速衰减生效: 平均 {avg_eff:.4f}")

    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    return issues


# ====================================================================
# 测试4: LRU 驱逐策略
# ====================================================================
def test_lru_eviction():
    """测试 MemoryVectorStore 的 LRU 驱逐。"""
    print("\n" + "=" * 60)
    print("测试4: LRU 驱逐策略")
    print("=" * 60)

    issues = []
    evicted_records = []

    def on_evict(record):
        evicted_records.append(record)

    store = MemoryVectorStore(
        max_records=5,
        eviction_policy=EvictionPolicy.LRU,
        on_evict_callback=on_evict,
    )

    # 添加6条记录（超过上限5）
    for i in range(6):
        store.add(_make_record(content=f"content_{i}", rid=f"mem_{i}"))

    if store.count() != 5:
        issues.append(f"HIGH: 存储数应为5，实际 {store.count()}")
    else:
        print(f"  ✅ 容量限制生效: {store.count()}/5")

    if len(evicted_records) != 1:
        issues.append(f"MEDIUM: 应驱逐1条，实际驱逐 {len(evicted_records)}")
    else:
        print(f"  ✅ 驱逐了1条记录: {evicted_records[0].id}")

    if store._total_evictions != 1:
        issues.append(f"LOW: 驱逐计数应为1，实际 {store._total_evictions}")

    # 验证最早添加的记录被驱逐（LRU）
    # mem_0 应该被驱逐（最早添加，未被访问）
    if store.get("mem_0") is not None:
        issues.append("MEDIUM: mem_0 应被LRU驱逐但仍存在")
    else:
        print(f"  ✅ mem_0 被正确驱逐（LRU策略）")

    # 验证最新记录仍在
    if store.get("mem_5") is None:
        issues.append("MEDIUM: mem_5 应保留但不存在")
    else:
        print(f"  ✅ mem_5 保留（最新添加）")

    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    return issues


# ====================================================================
# 测试5: 多种驱逐策略
# ====================================================================
def test_eviction_policies():
    """测试四种驱逐策略。"""
    print("\n" + "=" * 60)
    print("测试5: 多种驱逐策略")
    print("=" * 60)

    issues = []

    policies = [
        (EvictionPolicy.LRU, "LRU"),
        (EvictionPolicy.LFU, "LFU"),
        (EvictionPolicy.FIFO, "FIFO"),
        (EvictionPolicy.IMPORTANCE, "IMPORTANCE"),
    ]

    for policy, name in policies:
        evicted = []
        store = MemoryVectorStore(
            max_records=3,
            eviction_policy=policy,
            on_evict_callback=lambda r, lst=evicted: lst.append(r),
        )

        # 添加4条不同重要性的记录
        for i in range(4):
            importance = [0.9, 0.3, 0.7, 0.1][i]
            store.add(_make_record(
                content=f"content_{i}",
                importance=importance,
                rid=f"{name}_{i}",
            ))

        if store.count() != 3:
            issues.append(f"MEDIUM: {name} 存储数应为3，实际 {store.count()}")
            continue

        if len(evicted) != 1:
            issues.append(f"MEDIUM: {name} 应驱逐1条，实际 {len(evicted)}")
            continue

        print(f"  ✅ {name:15s}: 驱逐 {evicted[0].id} (importance={evicted[0].importance})")

    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    return issues


# ====================================================================
# 测试6: 衰减引擎与 AgentMemory 集成
# ====================================================================
def test_decay_integration():
    """测试衰减引擎与 AgentMemory 的集成。"""
    print("\n" + "=" * 60)
    print("测试6: 衰减引擎集成")
    print("=" * 60)

    issues = []
    config = _make_config()
    memory = AgentMemory(config)

    # 存储记忆
    mid1 = memory.remember("Python is a programming language", importance=0.9)
    mid2 = memory.remember("JavaScript is a scripting language", importance=0.5)
    mid3 = memory.remember("Rust is a systems programming language", importance=0.7)

    # 验证衰减引擎已注册
    decay_stats = memory._decay_engine.get_stats()
    if decay_stats["registered_count"] != 3:
        issues.append(
            f"HIGH: 衰减引擎应注册3条，实际 {decay_stats['registered_count']}"
        )
    else:
        print(f"  ✅ 衰减引擎注册: {decay_stats['registered_count']} 条")

    # 验证有效重要性
    eff1 = memory._decay_engine.get_effective_importance(mid1)
    if eff1 < 0.89 or eff1 > 0.91:
        issues.append(f"MEDIUM: 新记忆有效重要性应为~0.9，实际 {eff1}")
    else:
        print(f"  ✅ 有效重要性正确: {eff1:.4f}")

    # 执行检索（应记录访问）
    results = memory.recall("programming language", top_k=2)
    decay_stats_after = memory._decay_engine.get_stats()

    if decay_stats_after["total_access_boosts"] > 0:
        print(f"  ✅ 检索触发访问加成: {decay_stats_after['total_access_boosts']} 次")
    else:
        issues.append("MEDIUM: 检索应触发访问加成")

    # 测试可驱逐列表
    evictable = memory._decay_engine.get_evictable_memories(limit=10)
    print(f"  可驱逐记忆: {len(evictable)} 条")

    # 测试手动刷新
    refresh_stats = memory._decay_engine.refresh_once()
    print(f"  ✅ 手动刷新: {refresh_stats}")

    memory.close()

    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    return issues


# ====================================================================
# 测试7: 后台线程衰减
# ====================================================================
def test_background_decay():
    """测试后台衰减线程。"""
    print("\n" + "=" * 60)
    print("测试7: 后台线程衰减")
    print("=" * 60)

    issues = []

    config = DecayConfig(
        enabled=True,
        refresh_interval=0.5,  # 0.5秒刷新（测试用）
        half_life=1.0,          # 1秒半衰期（测试用）
    )
    engine = MemoryDecayEngine(config)
    engine.register("mem_1", base_importance=1.0)

    eff_before = engine.get_effective_importance("mem_1")
    engine.start()

    if not engine.is_running:
        issues.append("HIGH: 后台线程未启动")
    else:
        print(f"  ✅ 后台线程已启动")

    # 等待2秒（2个半衰期）
    time.sleep(2.0)

    eff_after = engine.get_effective_importance("mem_1")
    # 2个半衰期后，重要性应约为 0.25
    if eff_after >= 0.5:
        issues.append(f"MEDIUM: 2个半衰期后应 < 0.5，实际 {eff_after:.4f}")
    else:
        print(f"  ✅ 后台衰减生效: {eff_before:.4f} -> {eff_after:.4f}")

    engine.stop()

    if engine.is_running:
        issues.append("MEDIUM: 停止后线程仍在运行")
    else:
        print(f"  ✅ 后台线程已停止")

    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    return issues


# ====================================================================
# 主函数
# ====================================================================
def main():
    print("=" * 60)
    print("  Agent Memory System v5.1 创新功能测试")
    print("=" * 60)

    all_issues = []
    test_results = {}

    tests = [
        ("衰减引擎核心功能", test_decay_engine_basic),
        ("衰减曲线类型", test_decay_curves),
        ("容量压力加速衰减", test_capacity_pressure),
        ("LRU驱逐策略", test_lru_eviction),
        ("多种驱逐策略", test_eviction_policies),
        ("衰减引擎集成", test_decay_integration),
        ("后台线程衰减", test_background_decay),
    ]

    for name, func in tests:
        try:
            issues = func()
            test_results[name] = len(issues)
            all_issues.extend(issues)
        except Exception as e:
            print(f"\n❌ {name} 异常: {e}")
            import traceback
            traceback.print_exc()
            test_results[name] = -1
            all_issues.append(f"CRITICAL: {name}: {e}")

    # 汇总
    print("\n" + "=" * 60)
    print("  测试汇总")
    print("=" * 60)

    for name, count in test_results.items():
        status = "✅ 通过" if count == 0 else f"⚠ {count} 问题"
        if count < 0:
            status = "❌ 异常"
        print(f"  {name}: {status}")

    severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for issue in all_issues:
        for sev in severity:
            if issue.startswith(sev):
                severity[sev] += 1
                break

    print(f"\n  总问题: {len(all_issues)}")
    for sev, count in severity.items():
        if count > 0:
            print(f"    {sev}: {count}")

    return all_issues, test_results


if __name__ == "__main__":
    main()
