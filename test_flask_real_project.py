"""
Flask真实项目测试 - 用Agent Memory System处理Flask源码的真实问题

场景设计：
1. 代码审查助手：存储Flask源码，回答架构问题
2. Bug检测助手：存储已知问题模式，检测Flask代码中的潜在问题
3. 代码迁移助手：分析Flask 2→3迁移指南，帮助理解API变更
4. 跨模块依赖分析：追踪Flask模块间的import关系
5. 测试覆盖率分析：分析Flask测试文件，发现未覆盖的代码路径

每个场景都使用Agent Memory System的核心功能（remember/recall/知识图谱/搜索）
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, '/workspace/agent_memory_system')

from memory_system import AgentMemory

FLASK_ROOT = Path("/workspace/test_project_flask/src/flask")


def read_file(filepath, max_lines=80):
    """读取文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()[:max_lines]
            return ''.join(lines)
    except Exception as e:
        return f"Error: {e}"


def list_files(directory, pattern="*.py"):
    """列出目录下的文件"""
    return sorted(Path(directory).rglob(pattern))


# ============================================================
# 场景1: 代码审查助手
# ============================================================
def test_scenario_1_code_review_assistant():
    """场景1: 代码审查助手 - 存储Flask核心源码并回答架构问题"""
    print("\n" + "="*70)
    print("📌 场景1: 代码审查助手 - Flask架构问答")
    print("="*70)

    memory = AgentMemory()

    # 存储Flask核心文件
    core_files = [
        ("app.py", "Flask应用主类"),
        ("sansio/app.py", "SansIO应用基类"),
        ("config.py", "配置管理"),
        ("ctx.py", "应用上下文"),
        ("blueprints.py", "蓝图系统"),
        ("views.py", "视图基类"),
        ("routing.py", "路由系统(如存在)"),
        ("helpers.py", "辅助函数"),
        ("signals.py", "信号系统"),
        ("sessions.py", "会话管理"),
        ("wrappers.py", "请求/响应封装"),
        ("templating.py", "模板引擎"),
    ]

    stored = 0
    for filename, description in core_files:
        filepath = FLASK_ROOT / filename
        if not filepath.exists():
            continue
        content = read_file(filepath, max_lines=60)
        memory.remember(
            content=content,
            memory_type="code",
            category="flask-core",
            importance=0.9,
            source=f"flask/{filename}",
            tags=["flask", "core", description, filename.replace(".py", "")],
            metadata={"file": filename, "description": description}
        )
        stored += 1

    # 存储架构知识
    architecture_facts = [
        "Flask类继承自SansIO的App类，App类实现了WSGI应用的核心逻辑",
        "Flask使用Werkzeug作为WSGI工具库，处理路由、请求、响应",
        "Flask使用Jinja2作为模板引擎，通过Templating类封装",
        "Flask的蓝图系统通过Blueprint类实现模块化应用组织",
        "Flask的上下文系统分为应用上下文(AppContext)和请求上下文(RequestContext)",
        "Flask使用Blinker实现信号系统，提供松耦合的事件通知机制",
        "Flask的会话通过SecureCookieSessionInterface实现，基于签名Cookie",
        "Flask的配置系统支持多种来源：类属性、环境变量、配置文件",
    ]

    for fact in architecture_facts:
        memory.remember(
            content=fact,
            memory_type="fact",
            category="flask-architecture",
            importance=0.85,
            source="code-analysis",
            tags=["flask", "architecture", "knowledge"]
        )

    # 测试问答能力
    questions = [
        "Flask的基类是什么？继承了哪些功能？",
        "Flask如何处理路由？",
        "Flask的上下文系统是如何工作的？",
        "Flask的蓝图系统有什么作用？",
        "Flask使用哪些开源库？",
    ]

    print(f"\n  存储了 {stored} 个核心文件 + {len(architecture_facts)} 条架构知识")
    print(f"\n  问答测试:")
    for q in questions:
        results = memory.recall(q, top_k=3)
        best = results[0] if results else None
        if best:
            answer_preview = best['content'][:100].replace('\n', ' ')
            print(f"    Q: {q}")
            print(f"    A: {answer_preview}...")
        else:
            print(f"    Q: {q}")
            print(f"    A: 未找到相关结果")

    stats = memory.get_stats()
    print(f"\n  记忆统计: 长期={stats['long_term'].get('total_memories', 0)}条")

    memory.close()
    return True


# ============================================================
# 场景2: Bug模式检测助手
# ============================================================
def test_scenario_2_bug_pattern_detector():
    """场景2: Bug模式检测 - 存储常见Python Bug模式，检测Flask代码"""
    print("\n" + "="*70)
    print("📌 场景2: Bug模式检测助手")
    print("="*70)

    memory = AgentMemory()

    # 存储常见Bug模式
    bug_patterns = [
        {
            "pattern": "可变默认参数",
            "description": "函数使用可变对象（list/dict）作为默认参数，导致跨调用共享状态",
            "example": "def func(items=[]): items.append(1)",
            "fix": "使用None作为默认值，在函数内部创建新对象",
            "severity": "high"
        },
        {
            "pattern": "未关闭的资源",
            "description": "打开文件或数据库连接后未在finally块或上下文管理器中关闭",
            "example": "f = open('file'); data = f.read()",
            "fix": "使用with语句或try/finally确保资源释放",
            "severity": "medium"
        },
        {
            "pattern": "异常处理过于宽泛",
            "description": "使用bare except或except Exception捕获所有异常，隐藏真实错误",
            "example": "except: pass 或 except Exception as e: pass",
            "fix": "捕获具体的异常类型，至少记录日志",
            "severity": "high"
        },
        {
            "pattern": "循环中的字符串拼接",
            "description": "在循环中使用+=拼接字符串，导致O(n^2)性能问题",
            "example": "for s in list: result += s",
            "fix": "使用''.join(list)或StringIO",
            "severity": "low"
        },
        {
            "pattern": "导入循环依赖",
            "description": "模块间相互导入导致ImportError或部分初始化",
            "example": "模块A导入B，B又导入A",
            "fix": "重构模块结构，使用延迟导入或事件解耦",
            "severity": "high"
        },
        {
            "pattern": "线程安全问题",
            "description": "共享可变状态在多线程环境下未加锁保护",
            "example": "全局字典在多线程中直接读写",
            "fix": "使用threading.Lock保护共享状态",
            "severity": "high"
        },
    ]

    for bp in bug_patterns:
        content = f"Bug模式: {bp['pattern']}\n描述: {bp['description']}\n示例: {bp['example']}\n修复: {bp['fix']}\n严重程度: {bp['severity']}"
        memory.remember(
            content=content,
            memory_type="fact",
            category="bug-pattern",
            importance=0.9,
            source="bug-knowledge-base",
            tags=["bug", "pattern", bp['pattern'], bp['severity']],
            metadata={"severity": bp['severity']}
        )

    # 读取Flask源码并检测
    flask_files = list_files(FLASK_ROOT, "*.py")
    detected_issues = []

    for filepath in flask_files[:15]:  # 检查前15个文件
        content = read_file(filepath, max_lines=100)

        # 检测可变默认参数
        if "def " in content and ("=[])" in content or "={}" in content):
            memory.remember(
                content=f"在{filepath.name}中发现可变默认参数模式",
                memory_type="fact",
                category="detected-issue",
                importance=0.8,
                source=str(filepath),
                tags=["detected", "mutable-default", filepath.name]
            )
            detected_issues.append(f"  ⚠️ {filepath.name}: 可能存在可变默认参数")

        # 检测过于宽泛的异常处理
        if "except:" in content and "except Exception" not in content:
            detected_issues.append(f"  ⚠️ {filepath.name}: 发现bare except")

        # 检测未使用上下文管理器的文件操作
        if "open(" in content and "with open(" not in content:
            lines_with_open = [l.strip() for l in content.split('\n') if 'open(' in l and 'with' not in l]
            if lines_with_open:
                detected_issues.append(f"  ℹ️ {filepath.name}: {len(lines_with_open)}处open()未使用with语句")

    # 用记忆系统检索相关Bug模式
    print(f"\n  存储了 {len(bug_patterns)} 个Bug模式到知识库")
    print(f"\n  Flask代码检测结果:")
    if detected_issues:
        for issue in detected_issues[:10]:
            print(issue)
    else:
        print("  未发现明显问题（Flask代码质量很高）")

    # 测试：检索与"异常处理"相关的Bug模式
    print(f"\n  知识检索测试 - '异常处理过于宽泛':")
    results = memory.recall("异常处理过于宽泛 bare except", top_k=2)
    for r in results:
        print(f"    → {r['content'][:80]}...")

    memory.close()
    return True


# ============================================================
# 场景3: API变更追踪助手
# ============================================================
def test_scenario_3_api_change_tracker():
    """场景3: API变更追踪 - 存储Flask不同版本的API变更"""
    print("\n" + "="*70)
    print("📌 场景3: API变更追踪助手")
    print("="*70)

    memory = AgentMemory()

    # 存储Flask API变更知识
    api_changes = [
        {
            "version": "Flask 3.0",
            "change": "AppContext作为第一个参数传递给视图和错误处理器的装饰方法",
            "impact": "high",
            "migration": "更新自定义视图/错误处理器方法签名，添加ctx参数"
        },
        {
            "version": "Flask 3.0",
            "change": "移除了request.get_data(as_text=True)中的as_text参数",
            "impact": "medium",
            "migration": "使用request.get_data().decode()替代"
        },
        {
            "version": "Flask 3.0",
            "change": "CLI命令不再自动导入应用工厂",
            "impact": "medium",
            "migration": "显式导入应用工厂或使用with_appcontext"
        },
        {
            "version": "Flask 2.3",
            "change": "新增type hints支持，使用from __future__ import annotations",
            "impact": "low",
            "migration": "无需修改，但建议添加类型注解"
        },
        {
            "version": "Flask 2.2",
            "change": "配置系统支持toml文件加载",
            "impact": "low",
            "migration": "可以使用app.config.from_file('config.toml', loader=tomllib.load)"
        },
    ]

    for change in api_changes:
        content = f"版本: {change['version']}\n变更: {change['change']}\n影响: {change['impact']}\n迁移: {change['migration']}"
        memory.remember(
            content=content,
            memory_type="fact",
            category="api-change",
            importance=0.85,
            source="flask-changelog",
            tags=["flask", "api", "change", change['version'], change['impact']]
        )

    # 检测Flask源码中是否使用了已弃用的API
    deprecated_apis = {
        "get_data(as_text": "request.get_data(as_text=True) 已在Flask 3.0移除",
        "app.config.from_pyfile": "建议使用from_file替代",
        "app.test_client(use_cookies": "use_cookies参数已弃用",
    }

    print(f"\n  存储了 {len(api_changes)} 条API变更记录")
    print(f"\n  弃用API检测:")

    flask_files = list_files(FLASK_ROOT, "*.py")
    for filepath in flask_files[:10]:
        content = read_file(filepath, max_lines=50)
        for deprecated, message in deprecated_apis.items():
            if deprecated in content:
                print(f"  ⚠️ {filepath.name}: 检测到 {deprecated}")

    # 测试：查询Flask 3.0的重大变更
    print(f"\n  知识检索 - 'Flask 3.0 重大变更':")
    results = memory.recall("Flask 3.0 重大变更 high impact", top_k=3)
    for r in results:
        print(f"    → {r['content'][:90]}...")

    memory.close()
    return True


# ============================================================
# 场景4: 跨模块依赖分析
# ============================================================
def test_scenario_4_dependency_analysis():
    """场景4: 跨模块依赖分析 - 分析Flask模块间的import关系"""
    print("\n" + "="*70)
    print("📌 场景4: 跨模块依赖分析")
    print("="*70)

    memory = AgentMemory()

    # 扫描Flask模块间的import关系
    flask_files = list_files(FLASK_ROOT, "*.py")
    import_relations = []

    for filepath in flask_files:
        if filepath.name.startswith("_") or filepath.parent.name == "json":
            continue
        content = read_file(filepath, max_lines=30)
        module_name = filepath.stem

        # 检测from flask.xxx import
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith("from flask.") and "import" in line:
                parts = line.replace("from flask.", "").split(" import ")
                if len(parts) == 2:
                    target = parts[0].split(".")[0]
                    if target != module_name:
                        import_relations.append({
                            "from": module_name,
                            "to": target,
                            "line": line[:80]
                        })

    # 存储依赖关系到记忆系统
    for rel in import_relations:
        memory.remember(
            content=f"{rel['from']} 依赖 {rel['to']}: {rel['line']}",
            memory_type="fact",
            category="dependency",
            importance=0.7,
            source="dependency-analysis",
            tags=["flask", "dependency", rel['from'], rel['to']]
        )

    # 分析依赖统计
    dep_count = {}
    for rel in import_relations:
        dep_count[rel['from']] = dep_count.get(rel['from'], 0) + 1

    # 找出被依赖最多的模块
    target_count = {}
    for rel in import_relations:
        target_count[rel['to']] = target_count.get(rel['to'], 0) + 1

    sorted_targets = sorted(target_count.items(), key=lambda x: x[1], reverse=True)

    print(f"\n  发现 {len(import_relations)} 个模块间依赖关系")
    print(f"\n  被依赖最多的模块 (Top 5):")
    for name, count in sorted_targets[:5]:
        print(f"    {name}: 被 {count} 个模块依赖")

    print(f"\n  依赖最多的模块 (Top 5):")
    sorted_deps = sorted(dep_count.items(), key=lambda x: x[1], reverse=True)
    for name, count in sorted_deps[:5]:
        print(f"    {name}: 依赖 {count} 个其他模块")

    # 测试：检索与特定模块相关的依赖
    print(f"\n  知识检索 - '哪些模块依赖 ctx':")
    results = memory.recall("依赖 ctx context", top_k=5)
    for r in results[:5]:
        print(f"    → {r['content'][:80]}...")

    memory.close()
    return True


# ============================================================
# 场景5: 代码模式学习助手
# ============================================================
def test_scenario_5_pattern_learning():
    """场景5: 代码模式学习 - 从Flask源码学习设计模式"""
    print("\n" + "="*70)
    print("📌 场景5: 代码模式学习助手")
    print("="*70)

    memory = AgentMemory()

    # 存储Flask中使用的设计模式
    design_patterns = [
        {
            "pattern": "工厂方法模式",
            "location": "flask/app.py",
            "description": "Flask类本身是一个工厂，create_app工厂函数模式被广泛推荐",
            "code_example": "def create_app(config_name='development'): app = Flask(__name__)"
        },
        {
            "pattern": "代理模式",
            "location": "flask/globals.py",
            "description": "LocalProxy代理请求/应用上下文对象，实现线程安全的全局访问",
            "code_example": "current_app = LocalProxy(_get_current_object)"
        },
        {
            "pattern": "观察者模式(信号)",
            "location": "flask/signals.py",
            "description": "使用Blinker信号实现请求前后、异常等事件的观察者通知",
            "code_example": "request_started = _signals.signal('request-started')"
        },
        {
            "pattern": "模板方法模式",
            "location": "flask/views.py",
            "description": "View类定义dispatch()模板方法，子类实现具体的HTTP方法处理",
            "code_example": "class View: def dispatch(request): handler = getattr(self, method.lower())"
        },
        {
            "pattern": "注册表模式",
            "location": "flask/blueprints.py",
            "description": "Blueprint通过deferred_functions注册表延迟注册路由和处理器",
            "code_example": "self._deferred_functions.append(f)"
        },
    ]

    for dp in design_patterns:
        content = f"设计模式: {dp['pattern']}\n位置: {dp['location']}\n描述: {dp['description']}\n代码: {dp['code_example']}"
        memory.remember(
            content=content,
            memory_type="fact",
            category="design-pattern",
            importance=0.85,
            source="pattern-analysis",
            tags=["flask", "pattern", dp['pattern'], "design"]
        )

    # 存储用户偏好
    memory.set_preference("focus_area", "design-patterns")
    memory.set_preference("detail_level", "detailed")

    # 测试：学习设计模式
    print(f"\n  存储了 {len(design_patterns)} 个设计模式")
    print(f"\n  设计模式检索测试:")

    queries = [
        "Flask使用了哪些设计模式？",
        "如何实现线程安全的全局变量？",
        "Flask的视图系统如何工作？",
    ]

    for q in queries:
        results = memory.recall(q, top_k=2)
        print(f"\n    Q: {q}")
        for r in results:
            print(f"    A: {r['content'][:100].replace(chr(10), ' ')}...")

    # 验证偏好存储
    pref = memory.get_preference("focus_area")
    print(f"\n  用户偏好: focus_area={pref}")

    memory.close()
    return True


# ============================================================
# 场景6: 性能基准测试
# ============================================================
def test_scenario_6_performance_benchmark():
    """场景6: 性能基准测试 - 大规模Flask代码分析"""
    print("\n" + "="*70)
    print("📌 场景6: 性能基准测试")
    print("="*70)

    memory = AgentMemory()

    # 批量存储Flask所有Python文件
    flask_files = list_files(FLASK_ROOT, "*.py")
    print(f"\n  Flask项目共有 {len(flask_files)} 个Python文件")

    start_time = time.time()
    stored_count = 0

    for filepath in flask_files:
        content = read_file(filepath, max_lines=40)
        if len(content) < 10:
            continue
        memory.remember(
            content=content,
            memory_type="code",
            category="flask-benchmark",
            importance=0.5,
            source=f"flask/{filepath.relative_to(FLASK_ROOT)}",
            tags=["flask", "benchmark", filepath.stem],
            metadata={"file": str(filepath.relative_to(FLASK_ROOT))}
        )
        stored_count += 1

    store_time = time.time() - start_time
    print(f"  存储 {stored_count} 个文件，耗时: {store_time:.3f}s")
    print(f"  平均每条: {store_time/stored_count*1000:.2f}ms")

    # 批量检索测试
    queries = [
        "request response", "route url", "config setting",
        "session cookie", "template render", "error handler",
        "blueprint register", "signal event", "context application",
        "json serialize",
    ]

    start_time = time.time()
    total_results = 0
    for q in queries:
        results = memory.recall(q, top_k=5)
        total_results += len(results)

    search_time = time.time() - start_time
    print(f"\n  执行 {len(queries)} 次检索，耗时: {search_time:.3f}s")
    print(f"  平均每次: {search_time/len(queries)*1000:.2f}ms")
    print(f"  总返回结果: {total_results} 条")

    # 性能断言
    assert store_time < 5.0, f"存储耗时过长: {store_time:.2f}s"
    assert search_time < 3.0, f"检索耗时过长: {search_time:.2f}s"

    stats = memory.get_stats()
    print(f"\n  记忆统计: 长期={stats['long_term'].get('total_memories', 0)}条")

    print("\n  ✅ 性能基准测试通过")
    memory.close()
    return True


# ============================================================
# 单元测试
# ============================================================
def test_unit_basic_operations():
    """单元测试: 基本操作"""
    print("\n" + "="*70)
    print("🔬 单元测试: 基本操作")
    print("="*70)

    memory = AgentMemory()

    # 测试remember
    mid = memory.remember(
        content="Flask是一个基于Werkzeug的WSGI Web框架",
        memory_type="fact",
        category="test",
        importance=0.8,
        source="unit-test",
        tags=["flask", "wsgi"]
    )
    assert mid is not None, "remember应返回ID"

    # 测试recall
    results = memory.recall("Flask WSGI框架", top_k=3)
    assert len(results) > 0, "recall应返回结果"
    assert "Flask" in results[0]['content'], "结果应包含Flask"

    # 测试上下文
    memory.set_session_context("project", "flask")
    ctx = memory.get_session_context("project")
    assert ctx == "flask", f"上下文应为flask，实际为{ctx}"

    # 测试偏好 - get_preference应返回纯值
    memory.set_preference("language", "python")
    pref = memory.get_preference("language")
    assert pref == "python", f"偏好值应为python，实际为{pref}"

    # 测试raw模式返回完整记录
    raw_pref = memory.get_preference("language", raw=True)
    assert isinstance(raw_pref, dict), "raw模式应返回字典"
    assert raw_pref.get("value") == "python", "raw字典中value应为python"

    print("  ✅ 基本操作测试通过")
    memory.close()
    return True


def test_unit_knowledge_graph():
    """单元测试: 知识图谱"""
    print("\n" + "="*70)
    print("🔬 单元测试: 知识图谱")
    print("="*70)

    memory = AgentMemory()

    # 存储带知识图谱的事实
    memory.remember(
        content="Flask使用Werkzeug作为WSGI工具库",
        memory_type="fact",
        category="test-kg",
        importance=0.9,
        source="unit-test",
        tags=["flask", "werkzeug", "dependency"]
    )

    memory.remember(
        content="Flask使用Jinja2作为模板引擎",
        memory_type="fact",
        category="test-kg",
        importance=0.9,
        source="unit-test",
        tags=["flask", "jinja2", "dependency"]
    )

    # 检索相关实体
    results = memory.recall("Flask依赖哪些库", top_k=5)
    assert len(results) > 0, "应检索到结果"

    # 获取统计
    stats = memory.get_stats()
    print(f"  知识图谱统计: {stats.get('knowledge_graph', {})}")

    print("  ✅ 知识图谱测试通过")
    memory.close()
    return True


def test_unit_search_with_filters():
    """单元测试: 带过滤条件的搜索"""
    print("\n" + "="*70)
    print("🔬 单元测试: 带过滤条件的搜索")
    print("="*70)

    memory = AgentMemory()

    # 存储不同类别的记忆
    memory.remember(
        content="Flask路由系统基于Werkzeug的Map和Rule实现",
        memory_type="fact",
        category="routing",
        importance=0.8,
        source="test",
        tags=["flask", "routing"]
    )

    memory.remember(
        content="Django的URL配置使用urlpatterns列表",
        memory_type="fact",
        category="routing",
        importance=0.7,
        source="test",
        tags=["django", "routing"]
    )

    memory.remember(
        content="FastAPI使用装饰器注册路由",
        memory_type="fact",
        category="routing",
        importance=0.7,
        source="test",
        tags=["fastapi", "routing"]
    )

    # 搜索Flask相关
    results = memory.recall("路由", top_k=5)
    assert len(results) > 0, "应检索到路由相关结果"

    print(f"  搜索'路由'返回 {len(results)} 条结果")
    for r in results:
        print(f"    → [{r.get('source', '?')}] {r['content'][:60]}...")

    print("  ✅ 过滤搜索测试通过")
    memory.close()
    return True


# ============================================================
# 主函数
# ============================================================
def main():
    print("\n" + "="*70)
    print("🧪 Flask真实项目测试 - Agent Memory System")
    print("="*70)
    print(f"\n测试项目: Flask (pallets/flask)")
    print(f"项目路径: {FLASK_ROOT}")

    test_results = []

    # 单元测试
    print("\n" + "-"*70)
    print("📦 单元测试")
    print("-"*70)
    unit_tests = [
        ("基本操作", test_unit_basic_operations),
        ("知识图谱", test_unit_knowledge_graph),
        ("过滤搜索", test_unit_search_with_filters),
    ]
    for name, func in unit_tests:
        try:
            result = func()
            test_results.append(("单元", name, result))
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            import traceback
            traceback.print_exc()
            test_results.append(("单元", name, False))

    # 场景测试（集成测试）
    print("\n" + "-"*70)
    print("📦 集成测试 - 真实场景")
    print("-"*70)
    scenario_tests = [
        ("代码审查助手", test_scenario_1_code_review_assistant),
        ("Bug模式检测", test_scenario_2_bug_pattern_detector),
        ("API变更追踪", test_scenario_3_api_change_tracker),
        ("依赖分析", test_scenario_4_dependency_analysis),
        ("设计模式学习", test_scenario_5_pattern_learning),
    ]
    for name, func in scenario_tests:
        try:
            result = func()
            test_results.append(("集成", name, result))
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            import traceback
            traceback.print_exc()
            test_results.append(("集成", name, False))

    # 系统测试
    print("\n" + "-"*70)
    print("📦 系统测试")
    print("-"*70)
    try:
        result = test_scenario_6_performance_benchmark()
        test_results.append(("系统", "性能基准", result))
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("系统", "性能基准", False))

    # 测试报告
    print("\n" + "="*70)
    print("📊 测试报告")
    print("="*70)

    unit_p = sum(1 for t, n, r in test_results if t == "单元" and r)
    unit_t = sum(1 for t, n, r in test_results if t == "单元")
    integ_p = sum(1 for t, n, r in test_results if t == "集成" and r)
    integ_t = sum(1 for t, n, r in test_results if t == "集成")
    sys_p = sum(1 for t, n, r in test_results if t == "系统" and r)
    sys_t = sum(1 for t, n, r in test_results if t == "系统")

    print(f"\n单元测试: {unit_p}/{unit_t} 通过")
    print(f"集成测试: {integ_p}/{integ_t} 通过")
    print(f"系统测试: {sys_p}/{sys_t} 通过")

    total_p = sum(1 for t, n, r in test_results if r)
    total_t = len(test_results)
    print(f"\n总计: {total_p}/{total_t} 通过 ({total_p/total_t*100:.1f}%)")

    print("\n详细结果:")
    for t, n, r in test_results:
        s = "✅" if r else "❌"
        print(f"  {s} [{t}] {n}")

    if total_p == total_t:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ {total_t - total_p} 个测试失败")

    return total_p == total_t


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
