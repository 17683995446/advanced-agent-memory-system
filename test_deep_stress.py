"""
深度压力测试与边界测试 - 在实践中发现Agent Memory System的隐藏问题

测试方向：
1. 边界条件：空输入、超长文本、特殊字符、None值
2. 异常路径：关闭后操作、无效参数、重复关闭
3. 数据一致性：大量数据后检索准确性、去重
4. API契约：返回值类型、参数验证、错误消息
5. 资源管理：内存泄漏、重复初始化
"""

import sys
import time
import threading
import traceback

sys.path.insert(0, '/workspace/agent_memory_system')

from memory_system import AgentMemory

issues_found = []


def record_issue(severity, category, description, expected, actual):
    """记录发现的问题"""
    issues_found.append({
        "severity": severity,
        "category": category,
        "description": description,
        "expected": expected,
        "actual": actual,
    })
    icon = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
    print(f"  {icon} [{severity.upper()}] {category}: {description}")
    print(f"     期望: {expected}")
    print(f"     实际: {actual}")


# ============================================================
# 1. 边界条件测试
# ============================================================
def test_edge_cases():
    """边界条件测试"""
    print("\n" + "="*70)
    print("🧪 1. 边界条件测试")
    print("="*70)

    memory = AgentMemory()

    # 1.1 空字符串输入
    try:
        mid = memory.remember("", memory_type="fact", category="test", importance=0.5, source="test")
        if mid is not None:
            results = memory.recall("", top_k=5)
            # 空字符串是否能被存储和检索
            print(f"  ℹ️ 空字符串: 存储成功(id={mid[:8]}...), 检索返回{len(results)}条")
    except Exception as e:
        record_issue("medium", "空输入", "remember('')应优雅处理", "不抛异常或返回有意义的错误", str(e))

    # 1.2 超长文本
    try:
        long_text = "测试内容" * 10000  # ~40000字符
        mid = memory.remember(long_text, memory_type="fact", category="test", importance=0.5, source="test")
        results = memory.recall("测试内容", top_k=3)
        print(f"  ℹ️ 超长文本(40000字符): 存储+检索正常, 返回{len(results)}条")
    except Exception as e:
        record_issue("high", "超长文本", "应支持超长文本存储", "正常存储和检索", str(e))

    # 1.3 特殊字符
    try:
        special_text = "中文测试 🎉 emoji \t\n\r 特殊符号 <>&\"' \\x00 null"
        mid = memory.remember(special_text, memory_type="fact", category="test", importance=0.5, source="test")
        results = memory.recall("中文测试", top_k=3)
        if results:
            print(f"  ℹ️ 特殊字符: 存储+检索正常")
        else:
            record_issue("medium", "特殊字符", "含特殊字符的文本应能被检索", "检索到结果", "无结果")
    except Exception as e:
        record_issue("medium", "特殊字符", "应支持特殊字符", "正常存储和检索", str(e))

    # 1.4 None值参数
    try:
        mid = memory.remember(None, memory_type="fact", category="test", importance=0.5, source="test")
        record_issue("medium", "None输入", "remember(None)不应静默成功", "抛出ValueError或TypeError", f"返回了id={mid}")
    except (ValueError, TypeError):
        print(f"  ✅ None输入: 正确抛出异常")
    except Exception as e:
        record_issue("low", "None输入", "异常类型应明确", "ValueError或TypeError", type(e).__name__)

    # 1.5 recall空查询
    try:
        results = memory.recall("", top_k=5)
        if len(results) > 0:
            record_issue("low", "空查询", "空字符串查询可能返回过多无关结果", "空结果或有限结果", f"返回{len(results)}条")
        else:
            print(f"  ✅ 空查询: 返回空结果")
    except Exception as e:
        record_issue("medium", "空查询", "空查询应优雅处理", "返回空列表", str(e))

    # 1.6 top_k=0
    try:
        results = memory.recall("test", top_k=0)
        if len(results) != 0:
            record_issue("medium", "top_k=0", "top_k=0应返回空列表", "空列表", f"返回{len(results)}条")
        else:
            print(f"  ✅ top_k=0: 返回空列表")
    except Exception as e:
        record_issue("low", "top_k=0", "top_k=0应优雅处理", "返回空列表", str(e))

    # 1.7 负数importance
    try:
        mid = memory.remember("负数重要性测试", memory_type="fact", category="test", importance=-1.0, source="test")
        print(f"  ℹ️ 负数importance: 存储(id={mid[:8]}...)")
    except Exception as e:
        record_issue("low", "负数importance", "负数importance应被拒绝或钳制", "抛出ValueError或钳制到[0,1]", str(e))

    # 1.8 超大top_k
    try:
        results = memory.recall("test", top_k=999999)
        print(f"  ℹ️ 超大top_k(999999): 返回{len(results)}条(不超过存储总量)")
    except Exception as e:
        record_issue("medium", "超大top_k", "超大top_k应优雅处理", "返回所有结果", str(e))

    memory.close()
    return True


# ============================================================
# 2. 异常路径测试
# ============================================================
def test_exception_paths():
    """异常路径测试"""
    print("\n" + "="*70)
    print("🧪 2. 异常路径测试")
    print("="*70)

    # 2.1 关闭后操作
    try:
        memory = AgentMemory()
        memory.close()
        memory.remember("关闭后存储", memory_type="fact", category="test", importance=0.5, source="test")
        record_issue("high", "关闭后操作", "close()后操作应抛出明确异常", "抛出RuntimeError", "无异常")
    except RuntimeError:
        print(f"  ✅ 关闭后操作: 正确抛出RuntimeError")
    except Exception as e:
        record_issue("medium", "关闭后操作", "异常类型应为RuntimeError", "RuntimeError", type(e).__name__)

    # 2.2 重复关闭
    try:
        memory = AgentMemory()
        memory.close()
        memory.close()
        print(f"  ℹ️ 重复关闭: 未抛异常(幂等)")
    except Exception as e:
        print(f"  ℹ️ 重复关闭: 抛出{type(e).__name__}({e})")

    # 2.3 无效memory_type
    try:
        memory = AgentMemory()
        mid = memory.remember("测试", memory_type="invalid_type", category="test", importance=0.5, source="test")
        print(f"  ℹ️ 无效memory_type: 存储(id={mid[:8]}...)")
    except Exception as e:
        record_issue("low", "无效memory_type", "无效memory_type应有明确错误", "ValueError", str(e))
    finally:
        memory.close()

    # 2.4 get_stats在close后
    try:
        memory = AgentMemory()
        memory.close()
        stats = memory.get_stats()
        if stats is not None:
            record_issue("medium", "close后get_stats", "close()后get_stats应失败", "抛出异常", f"返回了{type(stats)}")
    except Exception:
        print(f"  ✅ close后get_stats: 正确抛出异常")

    return True


# ============================================================
# 3. 数据一致性测试
# ============================================================
def test_data_consistency():
    """数据一致性测试"""
    print("\n" + "="*70)
    print("🧪 3. 数据一致性测试")
    print("="*70)

    memory = AgentMemory()

    # 3.1 存储后立即检索
    test_content = "唯一标识符XYZ123的测试内容"
    memory.remember(test_content, memory_type="fact", category="consistency", importance=0.9, source="test")
    results = memory.recall("XYZ123", top_k=5)
    found = any("XYZ123" in r["content"] for r in results)
    if not found:
        record_issue("high", "即时一致性", "存储后应能立即检索到", "检索到包含XYZ123的结果", "未找到")
    else:
        print(f"  ✅ 即时一致性: 存储后立即检索成功")

    # 3.2 相似内容去重
    memory.remember("Python是一种编程语言", memory_type="fact", category="consistency", importance=0.8, source="test")
    memory.remember("Python是一种编程语言", memory_type="fact", category="consistency", importance=0.8, source="test")
    memory.remember("Python是一种编程语言", memory_type="fact", category="consistency", importance=0.8, source="test")
    results = memory.recall("Python编程语言", top_k=10)
    exact_matches = sum(1 for r in results if "Python是一种编程语言" in r["content"])
    if exact_matches > 1:
        record_issue("medium", "内容去重", "相同内容不应重复存储", "最多1条完全匹配", f"找到{exact_matches}条")
    else:
        print(f"  ✅ 内容去重: 相同内容存储{exact_matches}条")

    # 3.3 大量数据后检索准确性
    for i in range(50):
        memory.remember(
            f"第{i}条测试数据，内容是关于机器学习的",
            memory_type="fact",
            category="consistency",
            importance=0.5,
            source="test",
            tags=[f"item-{i}"]
        )

    results = memory.recall("机器学习", top_k=5)
    if len(results) < 3:
        record_issue("medium", "大量数据检索", "50条数据中检索'机器学习'应返回多条", "至少3条", f"返回{len(results)}条")
    else:
        print(f"  ✅ 大量数据检索: 50条数据中检索'机器学习'返回{len(results)}条")

    # 3.4 更新后检索
    memory.set_preference("test_key", "original_value")
    memory.set_preference("test_key", "updated_value")
    pref = memory.get_preference("test_key")
    if pref != "updated_value":
        record_issue("high", "偏好更新", "重复set_preference应覆盖旧值", "updated_value", str(pref))
    else:
        print(f"  ✅ 偏好更新: 重复设置正确覆盖")

    memory.close()
    return True


# ============================================================
# 4. API契约测试
# ============================================================
def test_api_contract():
    """API契约测试"""
    print("\n" + "="*70)
    print("🧪 4. API契约测试")
    print("="*70)

    memory = AgentMemory()

    # 4.1 remember返回值类型
    mid = memory.remember("测试", memory_type="fact", category="test", importance=0.5, source="test")
    if not isinstance(mid, str):
        record_issue("high", "remember返回值", "remember应返回str类型的ID", "str", type(mid).__name__)
    else:
        print(f"  ✅ remember返回值: str类型(id={mid[:16]}...)")

    # 4.2 recall返回值结构
    memory.remember("API契约测试内容", memory_type="fact", category="test", importance=0.8, source="test")
    results = memory.recall("API契约", top_k=3)
    if results:
        r = results[0]
        required_keys = ["content"]
        missing = [k for k in required_keys if k not in r]
        if missing:
            record_issue("high", "recall返回值结构", f"recall结果应包含{required_keys}", f"包含{required_keys}", f"缺少{missing}")
        else:
            print(f"  ✅ recall返回值结构: 包含必要字段")
            # 检查额外字段
            extra_keys = sorted(set(r.keys()) - {"content"})
            print(f"     额外字段: {extra_keys}")
    else:
        record_issue("medium", "recall返回值", "recall应返回非空列表", "非空列表", "空列表")

    # 4.3 get_stats返回值结构
    stats = memory.get_stats()
    if not isinstance(stats, dict):
        record_issue("high", "get_stats返回值", "get_stats应返回dict", "dict", type(stats).__name__)
    else:
        required_sections = ["session", "short_term", "long_term"]
        missing = [s for s in required_sections if s not in stats]
        if missing:
            record_issue("medium", "get_stats结构", f"应包含{required_sections}分区", f"包含{required_sections}", f"缺少{missing}")
        else:
            print(f"  ✅ get_stats结构: 包含session/short_term/long_term分区")

    # 4.4 get_session_context不存在的key
    ctx = memory.get_session_context("nonexistent_key")
    if ctx is not None:
        record_issue("low", "不存在的上下文", "不存在的key应返回None", "None", repr(ctx))
    else:
        print(f"  ✅ 不存在的上下文: 返回None")

    # 4.5 get_preference不存在的key
    pref = memory.get_preference("nonexistent_key")
    if pref is not None:
        record_issue("low", "不存在的偏好", "不存在的key应返回None", "None", repr(pref))
    else:
        print(f"  ✅ 不存在的偏好: 返回None")

    # 4.6 exclude_sources参数
    memory.remember("排除测试A", memory_type="fact", category="exclude-test", importance=0.8, source="source-A")
    memory.remember("排除测试B", memory_type="fact", category="exclude-test", importance=0.8, source="source-B")
    results_all = memory.recall("排除测试", top_k=10)
    results_filtered = memory.recall("排除测试", top_k=10, exclude_sources=["source-A"])
    if len(results_filtered) >= len(results_all):
        record_issue("medium", "exclude_sources", "exclude_sources应减少结果数", "过滤后<过滤前", f"过滤后{len(results_filtered)} >= 过滤前{len(results_all)}")
    else:
        print(f"  ✅ exclude_sources: 过滤前{len(results_all)}条, 过滤后{len(results_filtered)}条")

    memory.close()
    return True


# ============================================================
# 5. 资源管理测试
# ============================================================
def test_resource_management():
    """资源管理测试"""
    print("\n" + "="*70)
    print("🧪 5. 资源管理测试")
    print("="*70)

    # 5.1 多实例内存泄漏
    try:
        instances = []
        for i in range(20):
            m = AgentMemory()
            m.remember(f"实例{i}的测试数据", memory_type="fact", category="leak-test", importance=0.5, source="test")
            instances.append(m)

        # 关闭所有实例
        for m in instances:
            m.close()

        print(f"  ✅ 多实例创建/销毁: 20个实例无异常")
    except Exception as e:
        record_issue("high", "多实例", "创建/销毁多实例应无异常", "无异常", str(e))

    # 5.2 单实例大量操作
    try:
        memory = AgentMemory()
        start_mem = 0
        for i in range(200):
            memory.remember(f"压力测试数据{i}", memory_type="fact", category="stress", importance=0.5, source="test")

        stats = memory.get_stats()
        total = stats["long_term"].get("total_memories", 0)
        if total < 200:
            record_issue("medium", "大量存储", f"存储200条后应有200条记忆", "200", str(total))
        else:
            print(f"  ✅ 单实例大量操作: 存储200条, 实际{total}条")

        memory.close()
    except Exception as e:
        record_issue("high", "大量操作", "大量操作应无异常", "无异常", str(e))

    # 5.3 并发安全基础测试
    try:
        memory = AgentMemory()
        errors = []

        def worker(worker_id):
            try:
                for i in range(10):
                    memory.remember(
                        f"并发测试 worker={worker_id} i={i}",
                        memory_type="fact",
                        category="concurrency",
                        importance=0.5,
                        source="test"
                    )
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        if errors:
            record_issue("high", "并发安全", "多线程并发写入应无异常", "无异常", f"{len(errors)}个错误: {errors[0]}")
        else:
            stats = memory.get_stats()
            total = stats["long_term"].get("total_memories", 0)
            print(f"  ✅ 并发安全: 5线程x10次写入, 共{total}条, 无异常")

        memory.close()
    except Exception as e:
        record_issue("high", "并发测试", "并发测试框架应无异常", "无异常", str(e))

    return True


# ============================================================
# 6. 知识图谱深度测试
# ============================================================
def test_knowledge_graph_deep():
    """知识图谱深度测试"""
    print("\n" + "="*70)
    print("🧪 6. 知识图谱深度测试")
    print("="*70)

    memory = AgentMemory()

    # 6.1 大量实体和关系
    entities = ["Flask", "Django", "FastAPI", "Werkzeug", "Jinja2", "SQLAlchemy",
                "Pydantic", "Starlette", "Uvicorn", "Redis", "PostgreSQL", "Docker"]
    relations_text = []
    for i, e1 in enumerate(entities):
        for e2 in entities[i+1:i+3]:
            relations_text.append(f"{e1}与{e2}有合作关系")

    for text in relations_text:
        memory.remember(text, memory_type="fact", category="kg-deep", importance=0.8, source="test")

    # 检查知识图谱统计
    stats = memory.get_stats()
    kg = stats.get("knowledge_graph", {})
    entity_count = kg.get("entity_count", 0)
    relation_count = kg.get("relation_count", 0)

    print(f"  存储了{len(relations_text)}条关系文本")
    print(f"  知识图谱: {entity_count}个实体, {relation_count}个关系")

    if entity_count == 0 and relation_count == 0:
        record_issue("medium", "知识图谱构建", "存储关系文本后应自动构建知识图谱", "实体和关系>0", "均为0")
    else:
        print(f"  ✅ 知识图谱自动构建: {entity_count}实体, {relation_count}关系")

    # 6.2 实体搜索
    try:
        results = memory.search_entities("Flask", top_k=5)
        if results:
            print(f"  ✅ 实体搜索'Flask': 返回{len(results)}条")
        else:
            print(f"  ℹ️ 实体搜索'Flask': 无结果(知识图谱可能未提取到Flask实体)")
    except Exception as e:
        record_issue("medium", "实体搜索", "search_entities应正常工作", "返回结果列表", str(e))

    memory.close()
    return True


# ============================================================
# 主函数
# ============================================================
def main():
    print("\n" + "="*70)
    print("🔍 Agent Memory System - 深度压力测试与边界测试")
    print("="*70)

    tests = [
        ("边界条件", test_edge_cases),
        ("异常路径", test_exception_paths),
        ("数据一致性", test_data_consistency),
        ("API契约", test_api_contract),
        ("资源管理", test_resource_management),
        ("知识图谱深度", test_knowledge_graph_deep),
    ]

    passed = 0
    failed = 0
    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"\n  ❌ 测试框架异常: {name}: {e}")
            traceback.print_exc()
            failed += 1

    # 汇总报告
    print("\n" + "="*70)
    print("📊 问题发现报告")
    print("="*70)

    high = [i for i in issues_found if i["severity"] == "high"]
    medium = [i for i in issues_found if i["severity"] == "medium"]
    low = [i for i in issues_found if i["severity"] == "low"]

    print(f"\n  测试套件: {passed}/{passed+failed} 通过")
    print(f"\n  发现问题总计: {len(issues_found)}")
    print(f"  🔴 高严重度: {len(high)}")
    print(f"  🟡 中严重度: {len(medium)}")
    print(f"  🟢 低严重度: {len(low)}")

    if high:
        print(f"\n  高严重度问题详情:")
        for i, issue in enumerate(high, 1):
            print(f"    {i}. [{issue['category']}] {issue['description']}")
            print(f"       期望: {issue['expected']}")
            print(f"       实际: {issue['actual']}")

    if medium:
        print(f"\n  中严重度问题详情:")
        for i, issue in enumerate(medium, 1):
            print(f"    {i}. [{issue['category']}] {issue['description']}")

    return len(issues_found)


if __name__ == "__main__":
    count = main()
    print(f"\n  共发现 {count} 个问题")
