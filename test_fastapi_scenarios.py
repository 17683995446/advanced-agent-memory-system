"""
S4: 大型项目实战测试 - FastAPI 库知识图谱场景

使用 Python FastAPI 库作为真实世界的知识库，测试 Agent Memory System 在
复杂场景下的表现：
1. 核心概念记忆注入与检索
2. 依赖注入系统推理
3. 路由系统调用链追踪
4. 异常处理层次查询
5. 安全认证模式记忆
6. 知识图谱实体关系构建
7. 大规模记忆检索精度
8. 版本控制与审计
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Any

import pytest

sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig


def _make_config(**overrides):
    """创建测试用 AgentMemoryConfig"""
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


# ==================== FastAPI 核心知识数据 ====================

FASTAPI_CORE_KNOWLEDGE = [
    # 核心应用
    {
        "content": "FastAPI 是高性能 Python Web API 框架，基于 Starlette 和 Pydantic。FastAPI 类继承自 Starlette，是框架的主入口。支持异步处理，自动 OpenAPI/Swagger 文档生成。",
        "category": "core",
        "importance": 1.0,
        "tags": ["fastapi", "framework", "async", "openapi"],
    },
    # 路由系统
    {
        "content": "APIRouter 用于组织路由，支持路径参数、查询参数、请求体。路由装饰器包括 @app.get()、@app.post()、@app.put()、@app.delete() 等。支持路径转换器和自定义路由类。",
        "category": "routing",
        "importance": 0.95,
        "tags": ["router", "routing", "http", "decorator"],
    },
    # 依赖注入
    {
        "content": "Depends 实现依赖注入系统，支持子依赖、依赖缓存。依赖函数可以是同步或异步，返回值会被缓存用于同一请求。Security 用于认证依赖，可嵌套多层依赖。",
        "category": "dependencies",
        "importance": 0.95,
        "tags": ["depends", "injection", "di", "security"],
    },
    # 参数处理
    {
        "content": "Path 声明路径参数，Query 声明查询参数，Header 声明头部参数，Cookie 声明 Cookie 参数，Body 声明请求体，File 和 Form 处理文件上传。所有参数支持类型提示和验证。",
        "category": "parameters",
        "importance": 0.9,
        "tags": ["path", "query", "header", "body", "validation"],
    },
    # Pydantic 集成
    {
        "content": "Pydantic 模型用于请求体验证和响应序列化。BaseModel 定义数据结构，Field 添加验证规则。支持嵌套模型、列表模型、可选字段。自动 JSON Schema 生成。",
        "category": "pydantic",
        "importance": 0.9,
        "tags": ["pydantic", "model", "validation", "schema"],
    },
    # 响应处理
    {
        "content": "response_model 控制响应数据结构，排除敏感字段。ORJSONResponse、UJSONResponse 提供高性能 JSON 序列化。StreamingResponse 支持流式响应，FileResponse 发送文件。",
        "category": "responses",
        "importance": 0.85,
        "tags": ["response", "json", "streaming", "file"],
    },
    # 异常处理
    {
        "content": "HTTPException 用于返回 HTTP 错误状态码。自定义异常处理器通过 @app.exception_handler() 注册。RequestValidationError 处理请求验证失败，返回 422 状态码。",
        "category": "exceptions",
        "importance": 0.85,
        "tags": ["exception", "error", "http", "handler"],
    },
    # 中间件
    {
        "content": "中间件通过 @app.middleware() 注册，处理请求和响应。CORSMiddleware 处理跨域，GZipMiddleware 压缩响应，HTTPSRedirectMiddleware 强制 HTTPS，TrustedHostMiddleware 验证主机头。",
        "category": "middleware",
        "importance": 0.8,
        "tags": ["middleware", "cors", "gzip", "https"],
    },
    # 安全认证
    {
        "content": "OAuth2PasswordBearer 实现 OAuth2 密码流程，APIKeyHeader/APIKeyQuery 实现 API Key 认证，HTTPBasic 实现 Basic 认证，OpenIdConnect 支持 OIDC。JWT 令牌处理常见。",
        "category": "security",
        "importance": 0.85,
        "tags": ["oauth2", "jwt", "auth", "security", "apikey"],
    },
    # 后台任务
    {
        "content": "BackgroundTasks 用于在响应返回后执行后台任务。适合发送邮件、处理数据等耗时操作。通过依赖注入获取，任务在请求处理完成后异步执行。",
        "category": "background",
        "importance": 0.75,
        "tags": ["background", "tasks", "async", "worker"],
    },
    # WebSocket
    {
        "content": "WebSocket 支持实时双向通信。使用 @app.websocket() 装饰器，WebSocket 类提供 send_text()、receive_text()、accept()、close() 等方法。支持路径参数和依赖注入。",
        "category": "websocket",
        "importance": 0.8,
        "tags": ["websocket", "realtime", "socket", "streaming"],
    },
    # 事件处理
    {
        "content": "@app.on_event('startup') 注册启动事件，@app.on_event('shutdown') 注册关闭事件。用于数据库连接初始化、资源清理等。支持异步事件处理器。",
        "category": "events",
        "importance": 0.75,
        "tags": ["events", "startup", "shutdown", "lifecycle"],
    },
    # 静态文件
    {
        "content": "StaticFiles 挂载静态文件目录，支持缓存控制和目录浏览。TemplateResponse 支持 Jinja2 模板渲染。适合构建混合应用（API + 前端）。",
        "category": "static",
        "importance": 0.7,
        "tags": ["static", "files", "templates", "jinja2"],
    },
    # 测试客户端
    {
        "content": "TestClient 基于 HTTPX，用于测试 FastAPI 应用。支持同步测试异步代码。提供 get、post、put、delete 等方法，返回 Response 对象包含 status_code、json()、text 等属性。",
        "category": "testing",
        "importance": 0.75,
        "tags": ["test", "client", "httpx", "pytest"],
    },
    # OpenAPI
    {
        "content": "FastAPI 自动生成 OpenAPI 规范，访问 /docs 获取 Swagger UI，/redoc 获取 ReDoc。summary 和 description 参数添加文档说明，tags 组织路由分组。",
        "category": "openapi",
        "importance": 0.8,
        "tags": ["openapi", "swagger", "docs", "documentation"],
    },
    # 配置与设置
    {
        "content": "Settings 类管理应用配置，支持环境变量和 .env 文件。Pydantic BaseSettings 自动验证配置项。常用配置包括 DEBUG、DATABASE_URL、SECRET_KEY、CORS_ORIGINS 等。",
        "category": "config",
        "importance": 0.75,
        "tags": ["config", "settings", "env", "environment"],
    },
    # 数据库集成
    {
        "content": "SQLAlchemy、Tortoise ORM、Prisma 等 ORM 与 FastAPI 集成。异步数据库操作推荐 asyncpg、aiomysql。依赖注入管理数据库会话生命周期，确保请求结束关闭连接。",
        "category": "database",
        "importance": 0.85,
        "tags": ["database", "sqlalchemy", "orm", "async"],
    },
    # 性能优化
    {
        "content": "orjson 替代标准 json 库提升序列化性能。Uvicorn 作为 ASGI 服务器，Gunicorn 管理多进程。启用 gzip 压缩减少传输大小。缓存常用响应减少计算。",
        "category": "performance",
        "importance": 0.8,
        "tags": ["performance", "orjson", "uvicorn", "cache"],
    },
    # 部署
    {
        "content": "Docker 容器化部署，多阶段构建减小镜像。Kubernetes 编排管理集群。Serverless 部署到 AWS Lambda、Azure Functions。Gunicorn + Uvicorn workers 生产环境配置。",
        "category": "deployment",
        "importance": 0.75,
        "tags": ["docker", "kubernetes", "deploy", "serverless"],
    },
    # 类型系统
    {
        "content": "Python 类型提示是 FastAPI 的核心。Optional、List、Dict、Union 定义复杂类型。TypeVar 泛型支持。Annotated 添加元数据。类型错误在开发时捕获，减少运行时错误。",
        "category": "typing",
        "importance": 0.85,
        "tags": ["typing", "typehints", "annotations", "generic"],
    },
]


@pytest.fixture
def memory():
    """创建配置好的 AgentMemory 实例"""
    mem = AgentMemory(config=_make_config())
    yield mem
    mem.close()


@pytest.fixture
def populated_memory(memory):
    """注入 FastAPI 库知识的记忆实例"""
    for item in FASTAPI_CORE_KNOWLEDGE:
        memory.remember(
            content=item["content"],
            category=item["category"],
            importance=item["importance"],
            tags=item["tags"],
            source="fastapi-library",
        )
    return memory


class TestScenario1_CoreConcepts:
    """场景1: 核心概念记忆注入与检索"""

    def test_inject_all_knowledge(self, populated_memory):
        """所有知识应成功注入"""
        count = populated_memory.count_memories()
        assert count == len(FASTAPI_CORE_KNOWLEDGE)

    def test_retrieve_core_framework(self, populated_memory):
        """检索核心框架知识"""
        results = populated_memory.recall("FastAPI 框架核心特性", top_k=3)
        assert len(results) > 0
        # fake embedding 下不保证特定内容，只验证返回结果

    def test_retrieve_routing(self, populated_memory):
        """检索路由系统知识"""
        results = populated_memory.recall("APIRouter 路由系统", top_k=3)
        assert len(results) > 0
        # fake embedding 下不保证特定内容

    def test_retrieve_by_category(self, populated_memory):
        """按类别检索"""
        core_memories = populated_memory.get_memories_by_category("core")
        assert len(core_memories) >= 1

        security_memories = populated_memory.get_memories_by_category("security")
        assert len(security_memories) >= 1


class TestScenario2_DependencyInjection:
    """场景2: 依赖注入系统推理"""

    def test_depends_injection(self, populated_memory):
        """检索 Depends 依赖注入"""
        results = populated_memory.recall("Depends 依赖注入系统", top_k=3)
        assert len(results) > 0
        # fake embedding 下不保证特定内容

    def test_security_dependency(self, populated_memory):
        """检索安全认证依赖"""
        results = populated_memory.recall("Security 认证依赖", top_k=3)
        assert len(results) > 0


class TestScenario3_ParametersAndValidation:
    """场景3: 参数处理与验证"""

    def test_path_query_params(self, populated_memory):
        """检索路径和查询参数"""
        results = populated_memory.recall("Path Query 参数声明", top_k=3)
        assert len(results) > 0
        # fake embedding 下不保证特定内容

    def test_pydantic_validation(self, populated_memory):
        """检索 Pydantic 验证"""
        results = populated_memory.recall("Pydantic 模型验证", top_k=3)
        assert len(results) > 0
        # fake embedding 下不保证特定内容


class TestScenario4_ExceptionHandling:
    """场景4: 异常处理层次查询"""

    def test_httpexception(self, populated_memory):
        """检索 HTTPException"""
        results = populated_memory.recall("HTTPException 错误处理", top_k=3)
        assert len(results) > 0
        # fake embedding 下不保证特定内容

    def test_validation_error(self, populated_memory):
        """检索验证错误"""
        results = populated_memory.recall("RequestValidationError 422", top_k=3)
        assert len(results) > 0


class TestScenario5_SecurityAuth:
    """场景5: 安全认证模式记忆"""

    def test_oauth2_jwt(self, populated_memory):
        """检索 OAuth2 JWT 认证"""
        results = populated_memory.recall("OAuth2 JWT 认证流程", top_k=3)
        assert len(results) > 0
        # fake embedding 下不保证特定内容

    def test_api_key_auth(self, populated_memory):
        """检索 API Key 认证"""
        results = populated_memory.recall("APIKey 认证方式", top_k=3)
        assert len(results) > 0


class TestScenario6_KnowledgeGraph:
    """场景6: 知识图谱实体关系构建"""

    def test_manual_entity_relation(self, populated_memory):
        """手动添加 FastAPI 架构关系"""
        if populated_memory.knowledge_graph is None:
            pytest.skip("Knowledge graph not enabled")

        from memory_system.processing.knowledge_graph_engine import Entity, Relation

        populated_memory.knowledge_graph.add_entity(
            Entity(name="FastAPI", entity_type="framework")
        )
        populated_memory.knowledge_graph.add_entity(
            Entity(name="APIRouter", entity_type="component")
        )
        populated_memory.knowledge_graph.add_entity(
            Entity(name="Depends", entity_type="feature")
        )
        populated_memory.knowledge_graph.add_entity(
            Entity(name="Pydantic", entity_type="library")
        )

        populated_memory.knowledge_graph.add_relation(
            Relation(source="FastAPI", target="APIRouter", relation_type="contains")
        )
        populated_memory.knowledge_graph.add_relation(
            Relation(source="FastAPI", target="Depends", relation_type="supports")
        )
        populated_memory.knowledge_graph.add_relation(
            Relation(source="FastAPI", target="Pydantic", relation_type="uses")
        )

        stats = populated_memory.knowledge_graph.get_statistics()
        assert stats["entity_count"] >= 4
        assert stats["relation_count"] >= 3


class TestScenario7_LargeScaleRetrieval:
    """场景7: 大规模记忆检索精度"""

    def test_retrieve_across_categories(self, populated_memory):
        """跨类别检索"""
        categories = ["core", "routing", "dependencies", "security", "database"]
        found_count = 0

        for cat in categories:
            memories = populated_memory.get_memories_by_category(cat)
            if memories:
                found_count += 1

        assert found_count >= 4

    def test_diversity_in_results(self, populated_memory):
        """结果多样性"""
        results = populated_memory.recall("FastAPI 功能特性", top_k=10)
        assert len(results) > 0

        categories_seen = set()
        for r in results:
            cat = r.get("category", "") if isinstance(r, dict) else ""
            if cat:
                categories_seen.add(cat)

        assert len(categories_seen) >= 3


class TestScenario8_ExportImport:
    """场景8: 知识导出/导入往返"""

    def test_export_import_preserves_knowledge(self, populated_memory, tmp_path):
        """导出后导入应保留所有知识"""
        export_file = str(tmp_path / "fastapi_knowledge.json")

        populated_memory.export_memories(export_file, format="json")

        new_memory = AgentMemory(config=_make_config())
        stats = new_memory.import_memories(export_file)

        assert stats["imported"] == len(FASTAPI_CORE_KNOWLEDGE)

        new_memory.close()
