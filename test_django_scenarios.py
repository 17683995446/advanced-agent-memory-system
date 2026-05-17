"""
S4: 大型项目实战测试 - Django 库知识图谱场景

使用 Python Django 库作为真实世界的知识库，测试 Agent Memory System 在
复杂场景下的表现，特别验证 v6.0 新增的集成功能：
1. 核心概念记忆注入与检索
2. ORM 系统知识推理
3. 生命周期维护（lifecycle_maintenance）
4. 健康检查（health_check）
5. 版本控制集成验证
6. 冲突检测集成验证
7. 知识图谱实体关系构建
8. 导出/导入往返验证
"""

import sys

import pytest

sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


def _make_config(**overrides):
    defaults = {
        "short_term": {"working_memory_capacity": 10, "history_limit": 50},
        "long_term": {
            "embedding": {"provider": "fake", "fake_dimension": 128},
            "vector_store": {"backend": "memory"},
        },
        "knowledge_graph": {"enabled": True},
        "structured_store": {"enabled": True},
        "auto_consolidate": False,
    }
    defaults.update(overrides)
    return AgentMemoryConfig(**defaults)


DJANGO_CORE_KNOWLEDGE = [
    {
        "content": "Django 是 Python 高级 Web 框架，鼓励快速开发和简洁实用设计。遵循 MTV（Model-Template-View）架构模式。提供 ORM、管理后台、URL 路由、模板引擎、表单处理等核心功能。",
        "category": "core",
        "importance": 1.0,
        "tags": ["django", "framework", "mtv", "web"],
    },
    {
        "content": "Django ORM 通过 Model 类定义数据库表结构。Field 类型包括 CharField、IntegerField、DateField、ForeignKey、ManyToManyField 等。Manager 提供 QuerySet API 进行数据库查询。",
        "category": "orm",
        "importance": 0.95,
        "tags": ["orm", "model", "field", "queryset"],
    },
    {
        "content": "QuerySet 是 Django ORM 的核心查询接口，支持链式调用。filter() 过滤、exclude() 排除、annotate() 注解、aggregate() 聚合、select_related() 优化外键查询、prefetch_related() 优化多对多查询。",
        "category": "orm",
        "importance": 0.95,
        "tags": ["queryset", "filter", "annotate", "aggregate"],
    },
    {
        "content": "Django 通用视图（CBV）基于类的视图，提供 ListView、DetailView、CreateView、UpdateView、DeleteView、FormView 等。减少重复代码，支持 mixin 组合自定义行为。",
        "category": "views",
        "importance": 0.9,
        "tags": ["cbv", "views", "listview", "detailview"],
    },
    {
        "content": "Django 中间件是请求/响应处理的钩子系统。CommonMiddleware 处理 URL 斜杠和 www 前缀，AuthenticationMiddleware 添加用户认证，CsrfViewMiddleware 防止 CSRF 攻击，SessionMiddleware 管理 Cookie 会话。",
        "category": "middleware",
        "importance": 0.85,
        "tags": ["middleware", "csrf", "auth", "session"],
    },
    {
        "content": "Django 信号系统（django.dispatch）实现发布-订阅模式。pre_save/post_save、pre_delete/post_delete、request_started/request_finished 等信号用于解耦组件间通信。",
        "category": "signals",
        "importance": 0.8,
        "tags": ["signals", "dispatch", "pre_save", "post_save"],
    },
    {
        "content": "Django 模板引擎支持继承、过滤器、标签和自定义模板标签。{% extends %} 继承父模板，{% block %} 定义可覆盖块，{{ variable|filter }} 应用过滤器。",
        "category": "template",
        "importance": 0.8,
        "tags": ["template", "extends", "block", "filter"],
    },
    {
        "content": "Django 表单系统处理 HTML 表单生成、数据验证和清洗。ModelForm 自动从 Model 生成表单，FormSet 管理多个表单实例。支持自定义字段验证器和清洗方法。",
        "category": "forms",
        "importance": 0.85,
        "tags": ["forms", "modelform", "validation", "formset"],
    },
    {
        "content": "Django REST Framework（DRF）是 Django 的 REST API 扩展。提供 Serializer、ViewSet、Router、认证和权限类。支持 JWT 认证、API 文档自动生成、请求限流。",
        "category": "api",
        "importance": 0.85,
        "tags": ["drf", "rest", "api", "serializer", "viewset"],
    },
    {
        "content": "Django 迁移系统管理数据库 Schema 变更。makemigrations 生成迁移文件，migrate 应用迁移。支持数据迁移和自定义迁移操作。迁移文件是数据库变更的版本控制。",
        "category": "migrations",
        "importance": 0.8,
        "tags": ["migrations", "makemigrations", "migrate", "schema"],
    },
    {
        "content": "Django 管理后台（django.contrib.admin）提供开箱即用的数据管理界面。ModelAdmin 自定义列表显示、搜索、过滤和编辑表单。支持内联编辑和权限控制。",
        "category": "admin",
        "importance": 0.8,
        "tags": ["admin", "modeladmin", "inline", "permissions"],
    },
    {
        "content": "Django 认证系统提供 User、Group、Permission 模型。支持用户注册、登录、注销、密码重置。AuthenticationBackend 自定义认证后端。login_required 装饰器保护视图。",
        "category": "auth",
        "importance": 0.85,
        "tags": ["auth", "user", "login", "permission"],
    },
    {
        "content": "Django 缓存框架支持多种后端：Memcached、Redis、数据库缓存、文件缓存。cache_page 装饰器缓存整个视图。缓存 API 提供 get/set/delete 操作和缓存版本控制。",
        "category": "cache",
        "importance": 0.75,
        "tags": ["cache", "redis", "memcached", "performance"],
    },
    {
        "content": "Django 测试客户端模拟浏览器行为，支持 GET/POST 请求、Cookie 管理、会话跟踪。TestCase 提供数据库事务回滚。pytest-django 集成 pytest 测试框架。",
        "category": "testing",
        "importance": 0.75,
        "tags": ["testing", "client", "testcase", "pytest"],
    },
    {
        "content": "Django URL 路由系统使用 path() 和 re_path() 定义 URL 模式。include() 嵌套应用 URL。name 参数创建 URL 名称，reverse() 反向解析 URL。支持命名空间防止冲突。",
        "category": "urls",
        "importance": 0.85,
        "tags": ["urls", "path", "reverse", "include"],
    },
    {
        "content": "Django 安全特性包括：CSRF 保护、XSS 防护（自动转义）、SQL 注入防护（ORM 参数化查询）、点击劫持防护、SSL/HTTPS 强制、Host 头验证、SECRET_KEY 加密签名。",
        "category": "security",
        "importance": 0.85,
        "tags": ["security", "csrf", "xss", "sql_injection", "ssl"],
    },
    {
        "content": "Django 异步支持（ASGI）允许定义异步视图和中间件。async def view() 处理异步请求。数据库查询仍需使用 sync_to_async 包装。Channels 扩展支持 WebSocket。",
        "category": "async",
        "importance": 0.75,
        "tags": ["async", "asgi", "websocket", "channels"],
    },
    {
        "content": "Django 部署推荐使用 WSGI（Gunicorn）或 ASGI（Daphne/Uvicorn）服务器。WhiteNoise 提供静态文件服务。Docker 容器化部署。settings 模块区分 DEBUG/PRODUCTION 配置。",
        "category": "deployment",
        "importance": 0.7,
        "tags": ["deploy", "gunicorn", "asgi", "docker"],
    },
]


@pytest.fixture
def memory():
    mem = AgentMemory(config=_make_config())
    yield mem
    mem.close()


@pytest.fixture
def populated_memory(memory):
    for item in DJANGO_CORE_KNOWLEDGE:
        memory.remember(
            content=item["content"],
            category=item["category"],
            importance=item["importance"],
            tags=item["tags"],
            source="django-library",
        )
    return memory


class TestScenario1_KnowledgeInjection:
    """场景1: Django 核心知识注入与检索"""

    def test_inject_all_knowledge(self, populated_memory):
        assert populated_memory.count_memories() == len(DJANGO_CORE_KNOWLEDGE)

    def test_retrieve_framework(self, populated_memory):
        results = populated_memory.recall("Django Web 框架", top_k=3)
        assert len(results) > 0

    def test_retrieve_orm(self, populated_memory):
        results = populated_memory.recall("ORM QuerySet 查询", top_k=3)
        assert len(results) > 0

    def test_category_distribution(self, populated_memory):
        categories = set()
        for item in DJANGO_CORE_KNOWLEDGE:
            categories.add(item["category"])
        assert len(categories) >= 10


class TestScenario2_VersionControlIntegration:
    """场景2: 版本控制集成验证"""

    def test_remember_creates_version(self, populated_memory):
        history = populated_memory.get_version_history(
            list(populated_memory.get_all_memories())[0].id
        )
        assert len(history) == 1
        assert history[0]["change_type"] == "create"

    def test_update_creates_new_version(self, populated_memory):
        all_mems = populated_memory.get_all_memories()
        mem_id = all_mems[0].id
        populated_memory.update_memory(mem_id, content="Updated Django knowledge")

        history = populated_memory.get_version_history(mem_id)
        assert len(history) == 2
        assert history[1]["change_type"] == "update"

    def test_delete_creates_version(self, populated_memory):
        all_mems = populated_memory.get_all_memories()
        mem_id = all_mems[0].id
        populated_memory.delete_memory(mem_id)

        history = populated_memory.get_version_history(mem_id)
        assert any(v["change_type"] == "delete" for v in history)

    def test_rollback_works(self, populated_memory):
        all_mems = populated_memory.get_all_memories()
        mem_id = all_mems[0].id
        original_content = all_mems[0].content

        populated_memory.update_memory(mem_id, content="Completely different content")
        history = populated_memory.get_version_history(mem_id)
        first_version_id = history[0]["version_id"]

        result = populated_memory.rollback_memory(mem_id, first_version_id)
        assert result == original_content

    def test_audit_log_complete(self, populated_memory):
        log = populated_memory.get_audit_log()
        assert len(log) >= len(DJANGO_CORE_KNOWLEDGE)

    def test_audit_log_filter(self, populated_memory):
        create_log = populated_memory.get_audit_log(change_type="create")
        assert len(create_log) >= len(DJANGO_CORE_KNOWLEDGE)


class TestScenario3_LifecycleMaintenance:
    """场景3: 生命周期维护验证"""

    def test_lifecycle_maintenance_runs(self, populated_memory):
        report = populated_memory.lifecycle_maintenance(auto_compress=False)
        assert report["memory_count"] == len(DJANGO_CORE_KNOWLEDGE)
        assert report["conflicts"] is not None
        assert report["decay_stats"] is not None
        assert report["version_stats"] is not None

    def test_health_check(self, populated_memory):
        health = populated_memory.health_check()
        assert health["status"] in ("healthy", "needs_attention")
        assert health["memory_count"] == len(DJANGO_CORE_KNOWLEDGE)
        assert "engines" in health
        assert health["engines"]["hybrid_search"] == "active"

    def test_health_check_empty(self, memory):
        health = memory.health_check()
        assert health["memory_count"] == 0
        assert health["status"] == "needs_attention"


class TestScenario4_ConflictDetection:
    """场景4: 冲突检测集成验证"""

    def test_detect_no_conflicts(self, populated_memory):
        result = populated_memory.detect_conflicts()
        assert "conflicts_found" in result
        assert "duration_ms" in result

    def test_detect_with_contradictions(self, populated_memory):
        populated_memory.remember(
            "Django ORM 不支持多对多关系",
            category="orm",
            importance=0.5,
        )
        result = populated_memory.detect_conflicts(conflict_types=["factual"])
        assert "conflicts_found" in result


class TestScenario5_StatsIntegration:
    """场景5: 统计信息集成验证"""

    def test_stats_include_all_engines(self, populated_memory):
        stats = populated_memory.get_stats()
        assert "compression" in stats
        assert "conflict_resolver" in stats
        assert "version_control" in stats
        assert "decay_engine" in stats

    def test_version_control_stats(self, populated_memory):
        stats = populated_memory.get_stats()
        vc = stats["version_control"]
        assert vc["total_memories_with_versions"] > 0
        assert vc["total_versions"] > 0


class TestScenario6_KnowledgeGraph:
    """场景6: 知识图谱实体关系"""

    def test_django_architecture_graph(self, populated_memory):
        if populated_memory.knowledge_graph is None:
            pytest.skip("Knowledge graph not enabled")

        from memory_system.processing.knowledge_graph_engine import Entity, Relation

        entities = [
            Entity(name="Django", entity_type="framework"),
            Entity(name="ORM", entity_type="component"),
            Entity(name="View", entity_type="pattern"),
            Entity(name="Template", entity_type="component"),
            Entity(name="Middleware", entity_type="component"),
            Entity(name="URL", entity_type="component"),
        ]
        for e in entities:
            populated_memory.knowledge_graph.add_entity(e)

        relations = [
            Relation(source="Django", target="ORM", relation_type="contains"),
            Relation(source="Django", target="View", relation_type="contains"),
            Relation(source="Django", target="Template", relation_type="contains"),
            Relation(source="Django", target="Middleware", relation_type="contains"),
            Relation(source="View", target="Template", relation_type="uses"),
            Relation(source="View", target="ORM", relation_type="queries"),
            Relation(source="URL", target="View", relation_type="routes_to"),
        ]
        for r in relations:
            populated_memory.knowledge_graph.add_relation(r)

        stats = populated_memory.knowledge_graph.get_statistics()
        assert stats["entity_count"] >= 6
        assert stats["relation_count"] >= 7

    def test_path_finding(self, populated_memory):
        if populated_memory.knowledge_graph is None:
            pytest.skip("Knowledge graph not enabled")

        from memory_system.processing.knowledge_graph_engine import Entity, Relation

        populated_memory.knowledge_graph.add_entity(Entity(name="URL", entity_type="component"))
        populated_memory.knowledge_graph.add_entity(Entity(name="View", entity_type="pattern"))
        populated_memory.knowledge_graph.add_entity(Entity(name="ORM", entity_type="component"))
        populated_memory.knowledge_graph.add_relation(Relation(source="URL", target="View", relation_type="routes_to"))
        populated_memory.knowledge_graph.add_relation(Relation(source="View", target="ORM", relation_type="queries"))

        path = populated_memory.find_path("URL", "ORM")
        assert path is not None
        assert len(path) >= 3


class TestScenario7_ExportImport:
    """场景7: 导出/导入往返验证"""

    def test_export_import_roundtrip(self, populated_memory, tmp_path):
        export_file = str(tmp_path / "django_knowledge.json")
        populated_memory.export_memories(export_file, format="json")

        new_memory = AgentMemory(config=_make_config())
        stats = new_memory.import_memories(export_file)

        assert stats["imported"] == len(DJANGO_CORE_KNOWLEDGE)
        assert stats["errors"] == 0

        # 验证版本控制在新实例中独立工作
        new_memory.close()

    def test_filtered_export(self, populated_memory, tmp_path):
        export_file = str(tmp_path / "orm_knowledge.json")
        populated_memory.export_memories(export_file, format="json", category="orm")

        new_memory = AgentMemory(config=_make_config())
        stats = new_memory.import_memories(export_file)

        orm_memories = new_memory.get_memories_by_category("orm")
        assert len(orm_memories) == stats["imported"]

        new_memory.close()
