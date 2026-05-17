"""
Django 大型项目复杂场景测试 - Agent Memory System v4.8

用 Django（905个Python文件，16万+行代码）作为真实大型项目，
测试 Agent Memory System 在复杂真实场景下的表现，发现深层问题。

测试场景：
1. 跨模块架构知识图谱构建
2. 大规模代码模式挖掘与去重压力
3. 安全漏洞模式识别与关联推理
4. API 兼容性变更追踪（多版本模拟）
5. 设计模式自动检测与分类
6. 代码审查助手（批量处理）
7. 并发批量写入压力测试
8. 知识图谱规模扩展测试
"""

import os
import sys
import time
import traceback

# 确保能导入 memory_system
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


DJANGO_ROOT = "/workspace/django_project/django"


def collect_python_files(root, max_files=200):
    """递归收集Python文件，限制数量避免测试过长。"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".py") and not f.startswith("__"):
                files.append(os.path.join(dirpath, f))
                if len(files) >= max_files:
                    return files
    return files


def read_file_content(filepath, max_chars=3000):
    """读取文件内容，截断避免过长。"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...[truncated]"
        return content
    except Exception:
        return ""


# ====================================================================
# 场景1: 跨模块架构知识图谱构建
# ====================================================================
def test_cross_module_architecture_graph():
    """
    场景：将 Django 各模块的核心类和函数存入记忆系统，
    构建跨模块知识图谱，测试关联查询能力。
    """
    print("\n" + "=" * 70)
    print("场景1: 跨模块架构知识图谱构建")
    print("=" * 70)
    
    issues = []
    memory = AgentMemory()
    
    # 选取 Django 核心模块
    modules = {
        "db": os.path.join(DJANGO_ROOT, "db"),
        "http": os.path.join(DJANGO_ROOT, "http"),
        "forms": os.path.join(DJANGO_ROOT, "forms"),
        "views": os.path.join(DJANGO_ROOT, "views"),
        "middleware": os.path.join(DJANGO_ROOT, "middleware"),
        "template": os.path.join(DJANGO_ROOT, "template"),
        "urls": os.path.join(DJANGO_ROOT, "urls"),
        "core": os.path.join(DJANGO_ROOT, "core"),
    }
    
    module_classes = {}
    total_stored = 0
    
    for mod_name, mod_path in modules.items():
        full_path = os.path.join(DJANGO_ROOT, mod_path)
        if not os.path.isdir(full_path):
            continue
        
        # 收集该模块的类和函数
        classes_found = []
        py_files = collect_python_files(full_path, max_files=15)
        
        for filepath in py_files:
            content = read_file_content(filepath, max_chars=2000)
            if not content:
                continue
            
            # 简单提取类名和函数名
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("class ") and "(" in line:
                    class_name = line.split("(")[0].replace("class ", "").strip(":")
                    classes_found.append(class_name)
                elif line.startswith("def ") and not line.startswith("def _"):
                    func_name = line.split("(")[0].replace("def ", "").strip()
                    if len(func_name) > 2:
                        classes_found.append(func_name)
        
        module_classes[mod_name] = classes_found[:20]  # 每模块最多20个
        
        # 存入记忆系统
        for cls in classes_found[:20]:
            desc = f"[{mod_name}] {cls}: Django {mod_name} module component"
            try:
                memory.remember(
                    desc,
                    memory_type="semantic",
                    category=f"django.{mod_name}",
                    importance=0.7,
                    source="django_source",
                    tags=["django", mod_name, "architecture"],
                )
                total_stored += 1
            except Exception as e:
                issues.append(f"HIGH: 存储失败 [{mod_name}.{cls}]: {e}")
    
    print(f"  存储了 {total_stored} 个架构组件")
    print(f"  覆盖模块: {list(module_classes.keys())}")
    
    # 测试跨模块关联查询
    test_queries = [
        ("database query ORM model", "db"),
        ("HTTP request response handler", "http"),
        ("form validation field widget", "forms"),
        ("URL routing path converter", "urls"),
        ("template rendering context processor", "template"),
    ]
    
    for query, expected_mod in test_queries:
        try:
            results = memory.recall(query, top_k=5, from_short_term=False)
            if not results:
                issues.append(f"MEDIUM: 查询 '{query}' 返回空结果")
            else:
                # 检查结果是否包含期望模块
                found_modules = set()
                for r in results:
                    cat = r.get("category", "")
                    if cat.startswith("django."):
                        found_modules.add(cat.split(".")[1])
                
                if expected_mod not in found_modules:
                    issues.append(
                        f"LOW: 查询 '{query}' 期望模块 {expected_mod}，"
                        f"实际返回模块 {found_modules}"
                    )
        except Exception as e:
            issues.append(f"HIGH: 查询异常 [{query}]: {e}")
    
    # 测试知识图谱实体
    try:
        entities = memory.get_all_entities()
        print(f"  知识图谱实体数: {len(entities)}")
        
        relations = memory.get_entity_relationships()
        print(f"  知识图谱关系数: {len(relations)}")
    except Exception as e:
        issues.append(f"MEDIUM: 知识图谱查询异常: {e}")
    
    stats = memory.get_stats()
    print(f"  系统统计: {stats}")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 场景2: 大规模代码模式挖掘与去重压力
# ====================================================================
def test_large_scale_dedup_stress():
    """
    场景：模拟大规模代码存储，测试去重机制在大量数据下的表现。
    同时测试批量操作的性能和正确性。
    """
    print("\n" + "=" * 70)
    print("场景2: 大规模代码模式挖掘与去重压力")
    print("=" * 70)
    
    issues = []
    memory = AgentMemory()
    
    # 收集 Django 代码片段
    py_files = collect_python_files(DJANGO_ROOT, max_files=100)
    code_snippets = []
    
    for filepath in py_files[:80]:
        content = read_file_content(filepath, max_chars=500)
        if content and len(content) > 50:
            code_snippets.append(content)
    
    print(f"  收集了 {len(code_snippets)} 个代码片段")
    
    # 测试1: 批量存储去重
    start_time = time.time()
    unique_ids = set()
    duplicate_count = 0
    
    for i, snippet in enumerate(code_snippets):
        try:
            mid = memory.remember(
                snippet,
                memory_type="semantic",
                category="code_pattern",
                importance=0.5,
                source="django_code",
                tags=["code", "pattern", "dedup_test"],
            )
            if mid in unique_ids:
                duplicate_count += 1
            unique_ids.add(mid)
        except Exception as e:
            if i < 5:  # 只报告前5个错误
                issues.append(f"HIGH: 批量存储异常 [{i}]: {e}")
    
    batch_time = time.time() - start_time
    
    print(f"  批量存储耗时: {batch_time:.2f}s")
    print(f"  唯一记忆ID数: {len(unique_ids)}")
    print(f"  检测到重复: {duplicate_count}")
    
    # 测试2: 重复存储同一内容
    test_content = "def clean_data(self): return self.cleaned_data"
    id1 = memory.remember(test_content, category="dedup_verify", source="test")
    id2 = memory.remember(test_content, category="dedup_verify", source="test")
    id3 = memory.remember(test_content, category="dedup_verify", source="test")
    
    if id1 != id2 or id2 != id3:
        issues.append(
            f"HIGH: 去重失败 - 同一内容返回不同ID: {id1}, {id2}, {id3}"
        )
    else:
        print(f"  ✅ 去重验证通过: 3次存储返回相同ID = {id1}")
    
    # 测试3: 相似但不完全相同的内容（应该产生不同ID）
    similar_content = "def clean_data(self): return self.cleaned_data\n# extra comment"
    id4 = memory.remember(similar_content, category="dedup_verify", source="test")
    
    if id4 == id1:
        issues.append(
            f"MEDIUM: 过度去重 - 不同内容返回相同ID: {id1}"
        )
    else:
        print(f"  ✅ 相似内容区分正确: 不同ID = {id4}")
    
    # 测试4: 大规模查询性能
    start_time = time.time()
    for i in range(10):
        results = memory.recall("database model field query", top_k=5)
    query_time = time.time() - start_time
    
    print(f"  10次查询总耗时: {query_time:.2f}s (平均 {query_time/10*1000:.0f}ms/次)")
    
    if query_time / 10 > 1.0:
        issues.append(
            f"MEDIUM: 查询性能慢 - 平均 {query_time/10*1000:.0f}ms/次"
        )
    
    # 测试5: 统计信息准确性
    stats = memory.get_stats()
    stored_count = stats.get("long_term", {}).get("total_memories", 0)
    
    # 总存储数应该 = 唯一代码片段 + 去重验证(1个) + 相似内容(1个)
    expected_min = len(code_snippets)  # 至少有这么多（去重可能减少）
    expected_max = len(code_snippets) + 2  # 最多多2个（去重验证+相似内容）
    
    print(f"  统计存储数: {stored_count}, 预期范围: [{expected_min}, {expected_max}]")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 场景3: 安全漏洞模式识别与关联推理
# ====================================================================
def test_security_pattern_detection():
    """
    场景：存储已知安全漏洞模式，然后用 Django 代码进行匹配，
    测试系统的模式识别和关联推理能力。
    """
    print("\n" + "=" * 70)
    print("场景3: 安全漏洞模式识别与关联推理")
    print("=" * 70)
    
    issues = []
    memory = AgentMemory()
    
    # 存储安全漏洞模式知识库
    vuln_patterns = [
        ("SQL注入", "raw SQL query string concatenation user input execute cursor",
         ["security", "sql_injection", "critical"], 0.95),
        ("XSS跨站脚本", "escape HTML output template render untrusted user content mark_safe",
         ["security", "xss", "high"], 0.9),
        ("CSRF跨站请求伪造", "CSRF token missing POST request form protection middleware",
         ["security", "csrf", "high"], 0.9),
        ("命令注入", "subprocess shell=True os.system command injection user input",
         ["security", "command_injection", "critical"], 0.95),
        ("路径遍历", "file path traversal os.path.join user input directory access",
         ["security", "path_traversal", "high"], 0.85),
        ("不安全的反序列化", "pickle.loads yaml.load deserialize untrusted data",
         ["security", "deserialization", "critical"], 0.95),
        ("敏感信息泄露", "DEBUG=True SECRET_KEY hardcoded password token log",
         ["security", "info_leak", "medium"], 0.8),
        ("不安全的重定向", "redirect URL validation open redirect user input",
         ["security", "open_redirect", "medium"], 0.8),
    ]
    
    for name, desc, tags, importance in vuln_patterns:
        memory.remember(
            f"安全漏洞模式 [{name}]: {desc}",
            memory_type="semantic",
            category="security.vulnerability",
            importance=importance,
            source="security_kb",
            tags=tags,
        )
    
    print(f"  存储了 {len(vuln_patterns)} 个安全漏洞模式")
    
    # 从 Django 代码中搜索可能的安全相关代码
    security_related_files = []
    for dirpath, dirnames, filenames in os.walk(DJANGO_ROOT):
        for f in filenames:
            if f.endswith(".py"):
                filepath = os.path.join(dirpath, f)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                    # 搜索安全相关关键词
                    security_keywords = [
                        "csrf", "xss", "escape", "sanitize", "validate",
                        "SECRET_KEY", "DEBUG", "permission", "authenticate",
                    ]
                    for kw in security_keywords:
                        if kw.lower() in content.lower():
                            security_related_files.append(filepath)
                            break
                except Exception:
                    pass
    
    # 去重并限制数量
    security_related_files = list(set(security_related_files))[:30]
    print(f"  找到 {len(security_related_files)} 个安全相关文件")
    
    # 将安全相关代码片段存入记忆
    for filepath in security_related_files[:20]:
        content = read_file_content(filepath, max_chars=1000)
        if content and len(content) > 100:
            rel_path = os.path.relpath(filepath, DJANGO_ROOT)
            memory.remember(
                f"[Django安全代码] {rel_path}: {content[:500]}",
                memory_type="semantic",
                category="security.django_code",
                importance=0.6,
                source="django_security",
                tags=["django", "security", "code"],
            )
    
    # 测试漏洞模式匹配
    test_queries = [
        ("SQL injection raw query user input", "sql_injection"),
        ("cross-site scripting HTML escape", "xss"),
        ("CSRF token protection form", "csrf"),
        ("command injection subprocess shell", "command_injection"),
        ("path traversal file access", "path_traversal"),
    ]
    
    for query, expected_tag in test_queries:
        try:
            results = memory.recall(query, top_k=5)
            if not results:
                issues.append(f"MEDIUM: 安全查询 '{query}' 无结果")
                continue
            
            # 检查是否匹配到漏洞模式
            found_vuln = False
            for r in results:
                cat = r.get("category", "")
                if "vulnerability" in cat:
                    found_vuln = True
                    break
            
            if not found_vuln:
                issues.append(
                    f"LOW: 安全查询 '{query}' 未匹配到漏洞模式类别"
                )
            else:
                print(f"  ✅ 安全模式匹配: '{query}' → 漏洞模式")
        except Exception as e:
            issues.append(f"HIGH: 安全查询异常 [{query}]: {e}")
    
    # 测试标签过滤
    try:
        tagged_results = memory.recall(
            "security vulnerability",
            top_k=10,
            tags=["critical"],
        )
        print(f"  标签过滤[critical]: 返回 {len(tagged_results)} 条结果")
    except Exception as e:
        issues.append(f"MEDIUM: 标签过滤异常: {e}")
    
    # 测试类别过滤
    try:
        cat_results = memory.recall(
            "code security",
            top_k=10,
            category="security.vulnerability",
        )
        print(f"  类别过滤[vulnerability]: 返回 {len(cat_results)} 条结果")
        
        # 验证所有结果确实属于该类别
        for r in cat_results:
            if r.get("category") != "security.vulnerability":
                issues.append(
                    f"HIGH: 类别过滤失效 - 期望 security.vulnerability, "
                    f"实际 {r.get('category')}"
                )
                break
    except Exception as e:
        issues.append(f"MEDIUM: 类别过滤异常: {e}")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 场景4: API 兼容性变更追踪（多版本模拟）
# ====================================================================
def test_api_compatibility_tracking():
    """
    场景：模拟 Django API 的多版本变更，测试记忆系统在追踪
    API 演进、检测破坏性变更方面的能力。
    """
    print("\n" + "=" * 70)
    print("场景4: API 兼容性变更追踪")
    print("=" * 70)
    
    issues = []
    memory = AgentMemory()
    
    # 模拟 Django 各版本的 API 变更记录
    api_changes = [
        {
            "version": "2.0",
            "module": "django.urls",
            "change": "url() 函数被移除，统一使用 path() 和 re_path()",
            "type": "breaking",
            "importance": 0.95,
        },
        {
            "version": "2.0",
            "module": "django.contrib.auth",
            "change": "User 模型的 backend 认证路径变更",
            "type": "breaking",
            "importance": 0.9,
        },
        {
            "version": "2.1",
            "module": "django.forms",
            "change": "BaseForm._html_output() 方法签名变更",
            "type": "breaking",
            "importance": 0.8,
        },
        {
            "version": "2.2",
            "module": "django.db.models",
            "change": "QuerySet.iterator() 新增 chunk_size 参数",
            "type": "feature",
            "importance": 0.6,
        },
        {
            "version": "3.0",
            "module": "django.forms",
            "change": "RadioSelect 和 CheckboxSelectMultiple 渲染变更",
            "type": "breaking",
            "importance": 0.85,
        },
        {
            "version": "3.0",
            "module": "django.core.signing",
            "change": "JSONSerializer 成为默认签名序列化器",
            "type": "breaking",
            "importance": 0.9,
        },
        {
            "version": "3.1",
            "module": "django.core.asgi",
            "change": "新增 ASGI 应用支持",
            "type": "feature",
            "importance": 0.7,
        },
        {
            "version": "3.2",
            "module": "django.db",
            "change": "DEFAULT_AUTO_FIELD 配置变更",
            "type": "breaking",
            "importance": 0.95,
        },
        {
            "version": "4.0",
            "module": "django.forms",
            "change": "Form.field_order 默认行为变更",
            "type": "breaking",
            "importance": 0.75,
        },
        {
            "version": "4.0",
            "module": "django.db.models",
            "change": "ForeignKey 的 on_delete 默认值变更",
            "type": "breaking",
            "importance": 0.95,
        },
        {
            "version": "4.2",
            "module": "django.core.handlers",
            "change": "异步视图支持 ASGI",
            "type": "feature",
            "importance": 0.7,
        },
        {
            "version": "5.0",
            "module": "django.db.models",
            "change": "移除 QuerySet.select_related() 的缓存行为变更",
            "type": "breaking",
            "importance": 0.8,
        },
    ]
    
    for change in api_changes:
        memory.remember(
            f"[Django {change['version']}] {change['module']}: {change['change']}",
            memory_type="semantic",
            category=f"api_change.{change['type']}",
            importance=change["importance"],
            source="django_changelog",
            tags=["django", "api", change["type"], change["version"], change["module"]],
        )
    
    print(f"  存储了 {len(api_changes)} 条 API 变更记录")
    
    # 测试1: 查询特定模块的所有变更
    module_queries = [
        ("django.forms breaking changes", "forms"),
        ("django.db.models API changes", "db.models"),
        ("django authentication user backend", "auth"),
    ]
    
    for query, expected_module in module_queries:
        try:
            results = memory.recall(query, top_k=5)
            if not results:
                issues.append(f"MEDIUM: 模块变更查询无结果 [{expected_module}]")
            else:
                # 检查结果是否包含期望模块
                relevant = 0
                for r in results:
                    content = r.get("content", "")
                    if expected_module.split(".")[0] in content:
                        relevant += 1
                
                if relevant == 0:
                    issues.append(
                        f"LOW: 查询 '{query}' 未找到 {expected_module} 相关结果"
                    )
                else:
                    print(f"  ✅ 模块变更查询: '{query}' → {relevant}/{len(results)} 相关")
        except Exception as e:
            issues.append(f"HIGH: 模块变更查询异常 [{query}]: {e}")
    
    # 测试2: 查询破坏性变更
    try:
        breaking_results = memory.recall(
            "breaking change migration upgrade",
            top_k=10,
            category="api_change.breaking",
        )
        print(f"  破坏性变更查询: {len(breaking_results)} 条结果")
        
        # 验证所有结果确实是 breaking 类型
        for r in breaking_results:
            if r.get("category") != "api_change.breaking":
                issues.append(
                    f"HIGH: 类别过滤失效 - 期望 api_change.breaking, "
                    f"实际 {r.get('category')}"
                )
                break
    except Exception as e:
        issues.append(f"HIGH: 破坏性变更查询异常: {e}")
    
    # 测试3: 版本间变更对比
    try:
        v3_results = memory.recall("Django 3.0 changes", top_k=5)
        v4_results = memory.recall("Django 4.0 changes", top_k=5)
        print(f"  Django 3.0 变更: {len(v3_results)} 条")
        print(f"  Django 4.0 变更: {len(v4_results)} 条")
        
        # 检查版本间是否有重叠（不应该有）
        v3_contents = {r.get("id") for r in v3_results}
        v4_contents = {r.get("id") for r in v4_results}
        overlap = v3_contents & v4_contents
        
        if overlap:
            issues.append(
                f"MEDIUM: 版本间查询结果有重叠: {len(overlap)} 条"
            )
    except Exception as e:
        issues.append(f"MEDIUM: 版本对比查询异常: {e}")
    
    # 测试4: 按重要性排序
    try:
        important_results = memory.recall(
            "critical breaking changes",
            top_k=5,
        )
        if important_results:
            scores = [r.get("score", 0) for r in important_results]
            # 检查是否按分数降序排列
            is_sorted = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
            if not is_sorted:
                issues.append("MEDIUM: recall 结果未按分数降序排列")
            else:
                print(f"  ✅ 结果排序正确: 分数范围 [{min(scores):.4f}, {max(scores):.4f}]")
    except Exception as e:
        issues.append(f"LOW: 排序验证异常: {e}")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 场景5: 设计模式自动检测与分类
# ====================================================================
def test_design_pattern_detection():
    """
    场景：存储常见设计模式的描述，然后从 Django 代码中检测
    这些模式的使用情况，测试系统的分类和匹配能力。
    """
    print("\n" + "=" * 70)
    print("场景5: 设计模式自动检测与分类")
    print("=" * 70)
    
    issues = []
    memory = AgentMemory()
    
    # 存储设计模式知识
    design_patterns = [
        ("单例模式 Singleton", "确保一个类只有一个实例，全局访问点",
         ["pattern", "singleton", "creational"], 0.8),
        ("工厂模式 Factory", "定义创建对象的接口，让子类决定实例化哪个类",
         ["pattern", "factory", "creational"], 0.8),
        ("观察者模式 Observer", "定义对象间一对多的依赖关系，状态变更自动通知",
         ["pattern", "observer", "behavioral"], 0.8),
        ("策略模式 Strategy", "定义一系列算法，封装并使它们可以互相替换",
         ["pattern", "strategy", "behavioral"], 0.8),
        ("装饰器模式 Decorator", "动态地给对象添加额外的职责",
         ["pattern", "decorator", "structural"], 0.8),
        ("中间件模式 Middleware", "在请求/响应处理链中插入自定义处理逻辑",
         ["pattern", "middleware", "architectural"], 0.85),
        ("模板方法模式 Template Method", "定义算法骨架，将某些步骤延迟到子类",
         ["pattern", "template_method", "behavioral"], 0.8),
        ("注册表模式 Registry", "维护一个对象注册表，通过名称查找和获取对象",
         ["pattern", "registry", "architectural"], 0.8),
        ("信号-槽模式 Signal-Slot", "对象发出信号，其他对象监听并响应",
         ["pattern", "signal_slot", "behavioral"], 0.85),
        ("ORM模式 Object-Relational Mapping", "将数据库表映射为Python对象",
         ["pattern", "orm", "architectural"], 0.9),
    ]
    
    for name, desc, tags, importance in design_patterns:
        memory.remember(
            f"设计模式 [{name}]: {desc}",
            memory_type="semantic",
            category="design_pattern",
            importance=importance,
            source="pattern_kb",
            tags=tags,
        )
    
    print(f"  存储了 {len(design_patterns)} 个设计模式")
    
    # 从 Django 代码中搜索设计模式的使用
    pattern_files = {
        "middleware": os.path.join(DJANGO_ROOT, "middleware"),
        "dispatch": os.path.join(DJANGO_ROOT, "dispatch"),  # Signal-Slot
        "db": os.path.join(DJANGO_ROOT, "db"),  # ORM
        "template": os.path.join(DJANGO_ROOT, "template"),  # Template Method
        "forms": os.path.join(DJANGO_ROOT, "forms"),  # Factory
    }
    
    pattern_code_count = 0
    for pattern_name, search_dir in pattern_files.items():
        if not os.path.isdir(search_dir):
            continue
        py_files = collect_python_files(search_dir, max_files=5)
        for filepath in py_files:
            content = read_file_content(filepath, max_chars=800)
            if content and len(content) > 100:
                rel_path = os.path.relpath(filepath, DJANGO_ROOT)
                memory.remember(
                    f"[Django模式实例] {pattern_name} in {rel_path}: {content[:400]}",
                    memory_type="semantic",
                    category="pattern_instance",
                    importance=0.6,
                    source="django_pattern",
                    tags=["django", "pattern_instance", pattern_name],
                )
                pattern_code_count += 1
    
    print(f"  存储了 {pattern_code_count} 个 Django 模式实例代码")
    
    # 测试设计模式匹配
    pattern_queries = [
        ("middleware request response processing chain", "middleware"),
        ("signal dispatch observer event notification", "signal_slot"),
        ("ORM database model field mapping query", "orm"),
        ("template method skeleton algorithm subclass", "template_method"),
        ("factory create object instance class", "factory"),
    ]
    
    for query, expected_pattern in pattern_queries:
        try:
            results = memory.recall(query, top_k=5)
            if not results:
                issues.append(f"LOW: 设计模式查询无结果 [{expected_pattern}]")
                continue
            
            # 检查是否匹配到设计模式知识
            pattern_matched = False
            instance_matched = False
            for r in results:
                cat = r.get("category", "")
                if cat == "design_pattern":
                    pattern_matched = True
                elif cat == "pattern_instance":
                    instance_matched = True
            
            status = []
            if pattern_matched:
                status.append("知识匹配✅")
            if instance_matched:
                status.append("实例匹配✅")
            
            if pattern_matched or instance_matched:
                print(f"  ✅ 模式检测: '{query}' → {', '.join(status)}")
            else:
                issues.append(
                    f"LOW: 模式检测失败 [{expected_pattern}]"
                )
        except Exception as e:
            issues.append(f"MEDIUM: 设计模式查询异常 [{query}]: {e}")
    
    # 测试: 排除来源过滤
    try:
        all_results = memory.recall("design pattern", top_k=10)
        no_kb_results = memory.recall(
            "design pattern", top_k=10, exclude_sources=["pattern_kb"]
        )
        
        if len(no_kb_results) >= len(all_results):
            issues.append(
                f"MEDIUM: exclude_sources 无效 - "
                f"过滤后({len(no_kb_results)}) >= 过滤前({len(all_results)})"
            )
        else:
            print(f"  ✅ exclude_sources 有效: {len(all_results)} → {len(no_kb_results)}")
    except Exception as e:
        issues.append(f"MEDIUM: exclude_sources 测试异常: {e}")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 场景6: 代码审查助手（批量处理）
# ====================================================================
def test_code_review_assistant():
    """
    场景：模拟代码审查助手，批量处理 Django 核心模块的代码，
    存储审查意见并测试检索能力。
    """
    print("\n" + "=" * 70)
    print("场景6: 代码审查助手（批量处理）")
    print("=" * 70)
    
    issues = []
    memory = AgentMemory()
    
    # 收集 Django 核心模块文件
    review_files = []
    for subdir in ["core", "db", "http", "views"]:
        dir_path = os.path.join(DJANGO_ROOT, subdir)
        if os.path.isdir(dir_path):
            py_files = collect_python_files(dir_path, max_files=10)
            review_files.extend(py_files)
    
    print(f"  待审查文件: {len(review_files)} 个")
    
    # 模拟代码审查：存储代码片段和审查意见
    review_categories = {
        "code_quality": "代码质量",
        "performance": "性能优化",
        "security": "安全审查",
        "maintainability": "可维护性",
        "documentation": "文档完整性",
    }
    
    review_count = 0
    for filepath in review_files[:30]:
        content = read_file_content(filepath, max_chars=1500)
        if not content or len(content) < 100:
            continue
        
        rel_path = os.path.relpath(filepath, DJANGO_ROOT)
        
        # 模拟生成审查意见
        review_notes = []
        if "TODO" in content or "FIXME" in content:
            review_notes.append("存在未完成的TODO/FIXME标记")
        if len(content) > 1000 and "#" not in content[:200]:
            review_notes.append("文件头部缺少文档注释")
        if "import *" in content:
            review_notes.append("使用了通配符导入")
        if "except:" in content and "except Exception" not in content:
            review_notes.append("使用了裸except子句")
        
        # 存储代码片段
        try:
            memory.remember(
                f"[代码审查] {rel_path}: {content[:800]}",
                memory_type="semantic",
                category="code_review.source",
                importance=0.5,
                source="django_review",
                tags=["django", "code_review", "source"],
            )
        except Exception as e:
            issues.append(f"HIGH: 代码存储失败 [{rel_path}]: {e}")
            continue
        
        # 存储审查意见
        if review_notes:
            for note in review_notes:
                memory.remember(
                    f"[审查意见] {rel_path}: {note}",
                    memory_type="semantic",
                    category="code_review.finding",
                    importance=0.7,
                    source="reviewer",
                    tags=["django", "code_review", "finding"],
                )
            review_count += 1
    
    print(f"  完成审查: {review_count} 个文件有审查意见")
    
    # 测试1: 检索特定类型的审查意见
    review_queries = [
        ("TODO FIXME incomplete code marker", "code_review.finding"),
        ("wildcard import star namespace", "code_review.finding"),
        ("bare except clause error handling", "code_review.finding"),
    ]
    
    for query, expected_cat in review_queries:
        try:
            results = memory.recall(query, top_k=5)
            if not results:
                print(f"  ⚠ 无审查结果: '{query}'")
                continue
            
            finding_count = sum(
                1 for r in results if r.get("category") == expected_cat
            )
            print(f"  审查检索: '{query}' → {finding_count}/{len(results)} 审查意见")
        except Exception as e:
            issues.append(f"MEDIUM: 审查检索异常 [{query}]: {e}")
    
    # 测试2: 混合检索（代码+意见）
    try:
        mixed_results = memory.recall("error handling exception", top_k=10)
        source_types = {}
        for r in mixed_results:
            src = r.get("source", "unknown")
            source_types[src] = source_types.get(src, 0) + 1
        
        print(f"  混合检索来源分布: {source_types}")
        
        if len(source_types) < 2:
            issues.append(
                f"LOW: 混合检索来源单一: {source_types}"
            )
    except Exception as e:
        issues.append(f"MEDIUM: 混合检索异常: {e}")
    
    # 测试3: 对话记忆集成
    try:
        memory.remember_conversation(
            "请审查 django/db/models/query.py 的性能问题",
            speaker="developer",
            important=True,
        )
        memory.remember_conversation(
            "该文件的 QuerySet 优化已经完成，主要改进了批量操作",
            speaker="reviewer",
            important=True,
        )
        
        # 检索对话历史
        history = memory.get_interaction_history(limit=5)
        if len(history) < 2:
            issues.append("MEDIUM: 对话历史记录不完整")
        else:
            print(f"  ✅ 对话历史: {len(history)} 条记录")
    except Exception as e:
        issues.append(f"MEDIUM: 对话记忆异常: {e}")
    
    # 测试4: 偏好设置
    try:
        memory.store_preference("review_severity_threshold", "medium", "code_review")
        memory.store_preference("auto_assign_reviewer", "true", "code_review")
        
        threshold = memory.get_preference("review_severity_threshold")
        auto_assign = memory.get_preference("auto_assign_reviewer")
        
        if threshold != "medium":
            issues.append(f"HIGH: 偏好读取错误: 期望 'medium', 实际 '{threshold}'")
        if auto_assign != "true":
            issues.append(f"HIGH: 偏好读取错误: 期望 'true', 实际 '{auto_assign}'")
        else:
            print(f"  ✅ 偏好设置: threshold={threshold}, auto_assign={auto_assign}")
    except Exception as e:
        issues.append(f"MEDIUM: 偏好设置异常: {e}")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 场景7: 并发批量写入压力测试
# ====================================================================
def test_concurrent_batch_writes():
    """
    场景：多线程并发写入大量数据，测试线程安全性和数据一致性。
    """
    print("\n" + "=" * 70)
    print("场景7: 并发批量写入压力测试")
    print("=" * 70)
    
    issues = []
    import threading
    
    memory = AgentMemory()
    
    # 预存一些数据
    for i in range(50):
        memory.remember(
            f"预存数据 #{i}: Django ORM query optimization technique",
            memory_type="semantic",
            category="concurrent_test",
            importance=0.5,
            source="preload",
        )
    
    initial_count = memory.long_term.count()
    print(f"  初始记忆数: {initial_count}")
    
    # 并发写入
    num_threads = 5
    items_per_thread = 20
    errors = []
    results_lock = threading.Lock()
    
    def writer_thread(thread_id):
        thread_errors = []
        for i in range(items_per_thread):
            try:
                mid = memory.remember(
                    f"[线程{thread_id}] 并发写入 #{i}: "
                    f"Django database transaction isolation level",
                    memory_type="semantic",
                    category="concurrent_test",
                    importance=0.5,
                    source=f"thread_{thread_id}",
                )
                if not mid:
                    thread_errors.append(f"线程{thread_id}: 返回空ID")
            except Exception as e:
                thread_errors.append(f"线程{thread_id}: {e}")
        
        with results_lock:
            errors.extend(thread_errors)
    
    threads = []
    start_time = time.time()
    
    for t in range(num_threads):
        thread = threading.Thread(target=writer_thread, args=(t,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join(timeout=30)
    
    write_time = time.time() - start_time
    
    final_count = memory.long_term.count()
    expected_new = num_threads * items_per_thread
    
    print(f"  并发写入: {num_threads} 线程 × {items_per_thread} 条")
    print(f"  写入耗时: {write_time:.2f}s")
    print(f"  最终记忆数: {final_count} (新增 {final_count - initial_count})")
    print(f"  期望新增: {expected_new}")
    
    # 验证数据一致性
    actual_new = final_count - initial_count
    
    # 注意：由于去重机制，相同内容不会重复存储
    # 但不同线程的内容包含线程ID，所以应该是不同的
    if actual_new < expected_new * 0.9:
        issues.append(
            f"MEDIUM: 并发写入数据丢失 - "
            f"期望 {expected_new}, 实际 {actual_new}"
        )
    elif actual_new > expected_new:
        issues.append(
            f"HIGH: 并发写入数据膨胀 - "
            f"期望 {expected_new}, 实际 {actual_new}"
        )
    else:
        print(f"  ✅ 并发写入数据一致")
    
    if errors:
        error_summary = {}
        for e in errors:
            key = str(e)[:50]
            error_summary[key] = error_summary.get(key, 0) + 1
        issues.append(
            f"MEDIUM: 并发写入错误: {error_summary}"
        )
    else:
        print(f"  ✅ 无并发错误")
    
    # 并发读取测试
    read_errors = []
    
    def reader_thread(thread_id):
        try:
            results = memory.recall(
                "Django database transaction",
                top_k=5,
                from_short_term=False,
            )
            if not results:
                with results_lock:
                    read_errors.append(f"线程{thread_id}: 查询无结果")
        except Exception as e:
            with results_lock:
                read_errors.append(f"线程{thread_id}: {e}")
    
    threads = []
    for t in range(num_threads):
        thread = threading.Thread(target=reader_thread, args=(t,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join(timeout=10)
    
    if read_errors:
        issues.append(f"MEDIUM: 并发读取错误: {read_errors[:3]}")
    else:
        print(f"  ✅ 并发读取正常")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 场景8: 知识图谱规模扩展测试
# ====================================================================
def test_knowledge_graph_scale():
    """
    场景：构建大规模知识图谱，测试实体和关系的扩展能力。
    """
    print("\n" + "=" * 70)
    print("场景8: 知识图谱规模扩展测试")
    print("=" * 70)
    
    issues = []
    memory = AgentMemory()
    
    # 构建 Django 模块依赖关系图谱
    django_modules = [
        ("django.db", "数据库层", ["django.db.models", "django.db.backends", "django.db.migrations"]),
        ("django.http", "HTTP处理层", ["django.http.request", "django.http.response"]),
        ("django.views", "视图层", ["django.views.generic", "django.views.decorators"]),
        ("django.forms", "表单层", ["django.forms.fields", "django.forms.widgets", "django.forms.models"]),
        ("django.template", "模板层", ["django.template.loader", "django.template.context", "django.template.backends"]),
        ("django.middleware", "中间件层", ["django.middleware.common", "django.middleware.csrf", "django.middleware.security"]),
        ("django.urls", "路由层", ["django.urls.resolvers", "django.urls.converters"]),
        ("django.core", "核心层", ["django.core.handlers", "django.core.management", "django.core.validators"]),
        ("django.contrib.auth", "认证模块", ["django.contrib.auth.models", "django.contrib.auth.backends"]),
        ("django.contrib.admin", "管理后台", ["django.contrib.admin.sites", "django.contrib.admin.options"]),
    ]
    
    # 添加实体
    entity_ids = {}
    for mod_name, mod_desc, sub_modules in django_modules:
        try:
            eid = memory.add_entity(
                name=mod_name,
                entity_type="module",
                properties={"description": mod_desc, "sub_modules": ", ".join(sub_modules)},
            )
            entity_ids[mod_name] = eid
        except Exception as e:
            issues.append(f"MEDIUM: 添加实体失败 [{mod_name}]: {e}")
    
    print(f"  添加了 {len(entity_ids)} 个模块实体")
    
    # 添加关系
    module_dependencies = [
        ("django.views", "depends_on", "django.http"),
        ("django.views", "depends_on", "django.template"),
        ("django.views", "depends_on", "django.urls"),
        ("django.contrib.admin", "depends_on", "django.contrib.auth"),
        ("django.contrib.admin", "depends_on", "django.views"),
        ("django.contrib.admin", "depends_on", "django.forms"),
        ("django.contrib.admin", "depends_on", "django.urls"),
        ("django.forms", "depends_on", "django.core.validators"),
        ("django.middleware", "depends_on", "django.http"),
        ("django.middleware.csrf", "depends_on", "django.http"),
        ("django.db.migrations", "depends_on", "django.db.models"),
        ("django.template", "depends_on", "django.http"),
        ("django.urls", "depends_on", "django.http"),
        ("django.contrib.auth", "depends_on", "django.db"),
        ("django.core.handlers", "depends_on", "django.urls"),
        ("django.core.handlers", "depends_on", "django.middleware"),
        ("django.core.management", "depends_on", "django.db.migrations"),
    ]
    
    relation_count = 0
    for from_mod, rel_type, to_mod in module_dependencies:
        try:
            memory.add_relation(
                source=from_mod,
                target=to_mod,
                relation_type=rel_type,
                weight=1.0,
                project="django",
            )
            relation_count += 1
        except Exception as e:
            issues.append(f"MEDIUM: 添加关系失败 [{from_mod}→{to_mod}]: {e}")
    
    print(f"  添加了 {relation_count} 条依赖关系")
    
    # 测试知识图谱查询
    try:
        all_entities = memory.get_all_entities()
        print(f"  实体总数: {len(all_entities)}")
        
        all_relations = memory.get_entity_relationships()
        print(f"  关系总数: {len(all_relations)}")
    except Exception as e:
        issues.append(f"HIGH: 知识图谱查询失败: {e}")
    
    # 测试: 查找特定实体的关系
    try:
        admin_relations = memory.get_entity_relationships(
            entity_name="django.contrib.admin"
        )
        print(f"  django.contrib.admin 的依赖数: {len(admin_relations)}")

        if len(admin_relations) < 3:
            issues.append(
                f"LOW: admin 依赖关系过少: {len(admin_relations)}"
            )
    except Exception as e:
        issues.append(f"MEDIUM: 实体关系查询异常: {e}")
    
    # 测试: 使用 remember_fact 存储并检索
    try:
        fact_id = memory.remember_fact(
            "Django使用MTV(Model-Template-View)架构模式",
            category="architecture",
            source="django_docs",
            confidence=0.95,
        )
        
        # 检索事实
        fact_results = memory.recall("Django MTV architecture pattern", top_k=3)
        if not fact_results:
            issues.append("LOW: 事实检索无结果")
        else:
            print(f"  ✅ 事实检索成功: {len(fact_results)} 条结果")
    except Exception as e:
        issues.append(f"MEDIUM: 事实存储/检索异常: {e}")
    
    # 测试: 删除实体后的图谱一致性
    try:
        deleted = memory.delete_entity("django.core")
        if deleted:
            # 检查关系是否也清理了
            remaining = memory.get_entity_relationships(
                entity_name="django.core"
            )
            if remaining:
                issues.append(
                    f"MEDIUM: 删除实体后关系未清理: {len(remaining)} 条残留"
                )
            else:
                print(f"  ✅ 实体删除后关系已清理")
        else:
            issues.append("LOW: 实体删除返回False")
    except Exception as e:
        issues.append(f"MEDIUM: 实体删除异常: {e}")
    
    memory.close()
    
    print(f"  发现问题: {len(issues)}")
    for issue in issues:
        print(f"    ⚠ {issue}")
    
    return issues


# ====================================================================
# 主函数
# ====================================================================
def main():
    print("=" * 70)
    print("  Django 大型项目复杂场景测试 - Agent Memory System v4.8")
    print("  Django: 905 Python 文件, 164,375 行代码")
    print("=" * 70)
    
    all_issues = []
    test_results = {}
    
    test_functions = [
        ("场景1: 跨模块架构知识图谱", test_cross_module_architecture_graph),
        ("场景2: 大规模去重压力", test_large_scale_dedup_stress),
        ("场景3: 安全漏洞模式识别", test_security_pattern_detection),
        ("场景4: API兼容性变更追踪", test_api_compatibility_tracking),
        ("场景5: 设计模式检测", test_design_pattern_detection),
        ("场景6: 代码审查助手", test_code_review_assistant),
        ("场景7: 并发写入压力", test_concurrent_batch_writes),
        ("场景8: 知识图谱扩展", test_knowledge_graph_scale),
    ]
    
    for name, func in test_functions:
        try:
            issues = func()
            test_results[name] = len(issues)
            all_issues.extend(issues)
        except Exception as e:
            print(f"\n❌ {name} 执行异常: {e}")
            traceback.print_exc()
            test_results[name] = -1
            all_issues.append(f"CRITICAL: {name} 执行异常: {e}")
    
    # 汇总报告
    print("\n" + "=" * 70)
    print("  测试汇总报告")
    print("=" * 70)
    
    for name, issue_count in test_results.items():
        status = "✅ 通过" if issue_count == 0 else f"⚠ {issue_count} 问题"
        if issue_count < 0:
            status = "❌ 异常"
        print(f"  {name}: {status}")
    
    # 按严重度分类
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for issue in all_issues:
        for sev in severity_counts:
            if issue.startswith(sev):
                severity_counts[sev] += 1
                break
    
    print(f"\n  问题严重度分布:")
    for sev, count in severity_counts.items():
        if count > 0:
            print(f"    {sev}: {count}")
    
    print(f"\n  总问题数: {len(all_issues)}")
    print(f"  严重/高: {severity_counts['CRITICAL'] + severity_counts['HIGH']}")
    print(f"  中/低: {severity_counts['MEDIUM'] + severity_counts['LOW']}")
    
    return all_issues, test_results, severity_counts


if __name__ == "__main__":
    main()
