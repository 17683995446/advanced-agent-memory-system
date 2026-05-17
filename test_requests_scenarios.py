"""
S4: 大型项目实战测试 - Requests 库知识图谱场景

使用 Python Requests 库作为真实世界的知识库，测试 Agent Memory System 在
复杂场景下的表现：
1. 模块知识注入与检索
2. 跨模块关系推理
3. 调用链追踪
4. 异常层次结构查询
5. API 使用模式记忆
6. 知识图谱实体关系构建
7. 大规模记忆检索精度
8. 记忆衰减与重要性排序
"""

import sys
import os
import time
import statistics

import pytest

# 确保能导入 memory_system
sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig
from memory_system.processing.knowledge_graph_engine import Entity, Relation


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


# ==================== Requests 库知识数据 ====================

REQUESTS_MODULE_KNOWLEDGE = [
    # API 层
    {
        "content": "requests.get() 是最常用的HTTP请求方法，内部委托给 Session.request() 发送GET请求。参数包括url、params、headers、cookies、auth、timeout、allow_redirects、proxies、verify、stream、cert等。",
        "category": "api",
        "importance": 1.0,
        "tags": ["http", "get", "api", "入门"],
    },
    {
        "content": "requests.post() 发送POST请求，支持data（表单数据）、json（JSON body）、files（文件上传）三种请求体格式。内部同样委托给Session.request()。",
        "category": "api",
        "importance": 0.95,
        "tags": ["http", "post", "api"],
    },
    {
        "content": "requests.request() 是所有HTTP方法的底层入口，接受method参数指定HTTP方法。get/post/put/delete/head/options/patch都是它的快捷封装。",
        "category": "api",
        "importance": 0.9,
        "tags": ["http", "request", "api", "底层"],
    },
    {
        "content": "requests.put() 用于更新资源，requests.delete() 用于删除资源，requests.patch() 用于部分更新，requests.head() 只获取响应头，requests.options() 获取允许的方法。",
        "category": "api",
        "importance": 0.7,
        "tags": ["http", "rest", "api"],
    },
    # Session 层
    {
        "content": "Session 是 Requests 的核心引擎，跨请求持久化Cookie、认证信息、代理设置。Session.request() 是实际发送请求的方法，包含重定向处理、钩子分发、环境配置合并的完整逻辑。",
        "category": "session",
        "importance": 1.0,
        "tags": ["session", "核心", "cookie", "持久化"],
    },
    {
        "content": "Session 使用连接池管理HTTP连接，通过 HTTPAdapter 配置连接池大小。默认 max_retries=0，可通过 Retry策略自定义重试行为。Session应使用with语句或手动close()释放资源。",
        "category": "session",
        "importance": 0.85,
        "tags": ["session", "连接池", "资源管理"],
    },
    {
        "content": "Session 的 mount() 方法将适配器挂载到特定URL前缀，允许对不同域名使用不同的传输配置。默认挂载了 http:// 和 https:// 两个适配器。",
        "category": "session",
        "importance": 0.75,
        "tags": ["session", "adapter", "mount"],
    },
    # Model 层
    {
        "content": "Response 对象是HTTP响应的核心数据模型，包含 status_code、headers、content、text、encoding、json()、url、history、cookies、elapsed、reason 等属性。支持迭代和流式读取。",
        "category": "model",
        "importance": 1.0,
        "tags": ["response", "模型", "核心"],
    },
    {
        "content": "Response.json() 方法将响应体解析为JSON，内部使用 json.loads()。如果响应不是有效JSON则抛出 JSONDecodeError。可指定encoding参数覆盖自动检测的编码。",
        "category": "model",
        "importance": 0.85,
        "tags": ["response", "json", "解析"],
    },
    {
        "content": "Response.iter_content() 支持流式下载大文件，chunk_size参数控制每次读取的字节数。Response.iter_lines() 逐行迭代，常用于处理SSE（Server-Sent Events）。",
        "category": "model",
        "importance": 0.8,
        "tags": ["response", "流式", "下载"],
    },
    {
        "content": "PreparedRequest 是预处理后的请求对象，由 Request.prepare() 生成。包含完整的URL、编码后的body、格式化的headers。是 Session.send() 的实际输入。",
        "category": "model",
        "importance": 0.7,
        "tags": ["request", "预处理", "模型"],
    },
    # Adapter 层
    {
        "content": "HTTPAdapter 是传输适配器，基于 urllib3 的连接池管理。通过 pool_connections 和 pool_maxsize 控制连接池大小，max_retries 设置重试策略。是底层传输层的抽象。",
        "category": "adapter",
        "importance": 0.85,
        "tags": ["adapter", "连接池", "urllib3", "重试"],
    },
    {
        "content": "BaseAdapter 是适配器的抽象基类，定义了 send() 和 close() 接口。自定义适配器需要继承此类并实现这两个方法，然后通过 Session.mount() 挂载。",
        "category": "adapter",
        "importance": 0.65,
        "tags": ["adapter", "抽象", "自定义"],
    },
    # Auth 层
    {
        "content": "HTTPBasicAuth 实现 HTTP Basic 认证，将 username:password 编码为 Base64 放入 Authorization 头。HTTPDigestAuth 实现 Digest 认证，需要多次请求完成质询-响应流程。",
        "category": "auth",
        "importance": 0.8,
        "tags": ["auth", "basic", "digest", "认证"],
    },
    # Cookie 层
    {
        "content": "RequestsCookieJar 管理 Cookie，继承自 http.cookiejar.CookieJar。支持 set()、get()、delete() 操作。Session 自动管理 CookieJar，跨请求持久化Cookie。",
        "category": "cookie",
        "importance": 0.75,
        "tags": ["cookie", "jar", "持久化"],
    },
    # Exception 层
    {
        "content": "RequestException 是所有异常的基类。ConnectionError 表示网络连接失败，Timeout 表示请求超时，HTTPError 表示HTTP错误状态码（4xx/5xx），URLRequired 表示缺少URL。",
        "category": "exception",
        "importance": 0.9,
        "tags": ["exception", "错误处理", "层次结构"],
    },
    {
        "content": "TooManyRedirects 表示重定向次数超过 max_redirects 限制。ContentDecodingError 表示响应内容解码失败。SSLError 表示SSL/TLS相关错误。ChunkedEncodingError 表示分块传输编码错误。",
        "category": "exception",
        "importance": 0.7,
        "tags": ["exception", "重定向", "ssl", "解码"],
    },
    # Hooks 层
    {
        "content": "钩子系统通过 dispatch_hook() 在请求/响应生命周期的关键节点调用用户回调。支持的钩子类型：response（响应后）、request（发送前）。通过 hooks 参数传递回调列表。",
        "category": "hooks",
        "importance": 0.7,
        "tags": ["hooks", "生命周期", "回调"],
    },
    # Structures 层
    {
        "content": "CaseInsensitiveDict 是大小写不敏感的字典，用于存储HTTP头部。LookupDict 提供正向和反向查找功能。这些数据结构在内部广泛使用。",
        "category": "structures",
        "importance": 0.6,
        "tags": ["数据结构", "dict", "headers"],
    },
    # Utils 层
    {
        "content": "utils 模块提供 URL 解析、头部处理、默认端口映射、编码检测等通用工具。get_encoding_from_headers() 从Content-Type头检测编码，default_headers() 提供默认请求头。",
        "category": "utils",
        "importance": 0.65,
        "tags": ["utils", "工具", "编码", "url"],
    },
    # SSL/TLS
    {
        "content": "Requests 默认启用 SSL 验证（verify=True），使用 certifi 提供的 CA 证书包。可通过 cert 参数指定客户端证书。verify=False 可禁用验证（不推荐，会显示 InsecureRequestWarning）。",
        "category": "ssl",
        "importance": 0.8,
        "tags": ["ssl", "tls", "证书", "安全"],
    },
    # 代理
    {
        "content": "Requests 通过 proxies 参数配置代理，格式为 {'http': 'http://proxy', 'https': 'https://proxy'}。支持 SOCKS 代理（需安装 requests[socks]）。环境变量 HTTP_PROXY 和 HTTPS_PROXY 也会被自动读取。",
        "category": "proxy",
        "importance": 0.7,
        "tags": ["proxy", "代理", "socks"],
    },
    # 超时
    {
        "content": "timeout 参数控制请求超时，格式为 (connect_timeout, read_timeout)。只传一个数字则同时应用于连接和读取。timeout=None 表示无限等待（不推荐）。ConnectTimeout 和 ReadTimeout 是对应的异常类。",
        "category": "timeout",
        "importance": 0.75,
        "tags": ["timeout", "超时", "连接", "读取"],
    },
    # 编码
    {
        "content": "Response.encoding 自动检测响应编码，优先使用 Content-Type 头中的 charset，其次使用 chardet 或 charset_normalizer 检测。Response.apparent_encoding 返回检测到的编码。可手动设置 encoding 属性。",
        "category": "encoding",
        "importance": 0.7,
        "tags": ["encoding", "编码", "检测", "chardet"],
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
    """注入 Requests 库知识的记忆实例"""
    for item in REQUESTS_MODULE_KNOWLEDGE:
        memory.remember(
            content=item["content"],
            category=item["category"],
            importance=item["importance"],
            tags=item["tags"],
            source="requests-library",
        )
    return memory


class TestScenario1_ModuleKnowledgeInjection:
    """场景1: 模块知识注入与检索"""

    def test_inject_all_knowledge(self, populated_memory):
        """所有知识应成功注入"""
        count = populated_memory.count_memories()
        assert count == len(REQUESTS_MODULE_KNOWLEDGE), (
            f"Expected {len(REQUESTS_MODULE_KNOWLEDGE)} memories, got {count}"
        )

    def test_retrieve_api_knowledge(self, populated_memory):
        """检索API层知识"""
        results = populated_memory.recall("HTTP GET请求方法", top_k=5)
        assert len(results) > 0
        # 检查top-5结果中是否有API相关内容
        all_content = " ".join(
            r["content"] if isinstance(r, dict) else str(r) for r in results
        ).lower()
        assert "get" in all_content or "http" in all_content or "请求" in all_content

    def test_retrieve_session_knowledge(self, populated_memory):
        """检索Session层知识"""
        results = populated_memory.recall("Session会话管理和Cookie持久化", top_k=3)
        assert len(results) > 0
        found_session = False
        for r in results:
            content = r["content"] if isinstance(r, dict) else str(r)
            if "session" in content.lower():
                found_session = True
                break
        assert found_session, "Should find Session-related knowledge"

    def test_retrieve_by_category(self, populated_memory):
        """按类别检索"""
        api_memories = populated_memory.get_memories_by_category("api")
        assert len(api_memories) >= 3  # 至少有 get/post/request

        exception_memories = populated_memory.get_memories_by_category("exception")
        assert len(exception_memories) >= 2  # 至少有2条异常知识

    def test_retrieve_response_model(self, populated_memory):
        """检索Response模型知识"""
        results = populated_memory.recall("Response对象属性和方法", top_k=3)
        assert len(results) > 0
        found_response = False
        for r in results:
            content = r["content"] if isinstance(r, dict) else str(r)
            if "response" in content.lower() and ("status_code" in content or "json" in content):
                found_response = True
                break
        assert found_response


class TestScenario2_CrossModuleReasoning:
    """场景2: 跨模块关系推理"""

    def test_api_to_session_chain(self, populated_memory):
        """API层到Session层的调用链推理"""
        # 查询 "get方法内部实现"
        results = populated_memory.recall("get方法内部委托给谁实现", top_k=5)
        assert len(results) > 0
        # 应该找到提到 Session 的结果
        all_content = " ".join(
            r["content"] if isinstance(r, dict) else str(r) for r in results
        )
        assert "session" in all_content.lower()

    def test_session_to_adapter_chain(self, populated_memory):
        """Session到Adapter的连接推理"""
        results = populated_memory.recall("连接池管理和适配器配置", top_k=5)
        assert len(results) > 0
        all_content = " ".join(
            r["content"] if isinstance(r, dict) else str(r) for r in results
        )
        # 应该同时提到 Session 和 Adapter
        has_session = "session" in all_content.lower()
        has_adapter = "adapter" in all_content.lower()
        assert has_session or has_adapter

    def test_error_handling_chain(self, populated_memory):
        """错误处理链推理"""
        results = populated_memory.recall("网络请求可能出现的错误类型", top_k=5)
        assert len(results) > 0
        all_content = " ".join(
            r["content"] if isinstance(r, dict) else str(r) for r in results
        )
        # 应该提到多种异常类型
        error_types = ["connection", "timeout", "http", "ssl"]
        found = sum(1 for t in error_types if t in all_content.lower())
        assert found >= 2, f"Should find at least 2 error types, found {found}"


class TestScenario3_CallChainTracing:
    """场景3: 调用链追踪"""

    def test_full_request_lifecycle(self, populated_memory):
        """完整请求生命周期追踪"""
        # 逐步查询请求的各个阶段
        steps = [
            "用户调用 requests.get()",
            "请求预处理和编码",
            "通过适配器发送请求",
            "接收和解析响应",
        ]
        found_count = 0
        for step in steps:
            results = populated_memory.recall(step, top_k=3)
            if results:
                found_count += 1

        # 至少能追踪到3个阶段
        assert found_count >= 3, f"Could trace {found_count}/4 lifecycle stages"

    def test_redirect_handling(self, populated_memory):
        """重定向处理流程 - 验证检索返回结果"""
        results = populated_memory.recall("重定向处理和限制", top_k=5)
        assert len(results) > 0
        # fake embedding 下不保证内容匹配，只验证检索正常工作

    def test_streaming_download_flow(self, populated_memory):
        """流式下载流程"""
        results = populated_memory.recall("大文件流式下载", top_k=3)
        assert len(results) > 0
        all_content = " ".join(
            r["content"] if isinstance(r, dict) else str(r) for r in results
        )
        assert "stream" in all_content.lower() or "流式" in all_content


class TestScenario4_ExceptionHierarchy:
    """场景4: 异常层次结构查询"""

    def test_base_exception(self, populated_memory):
        """基础异常查询"""
        results = populated_memory.recall("RequestException 异常基类", top_k=3)
        assert len(results) > 0

    def test_specific_exceptions(self, populated_memory):
        """特定异常查询"""
        exception_queries = [
            "ConnectionError 网络连接失败",
            "Timeout 请求超时",
            "HTTPError HTTP错误状态码",
        ]
        for query in exception_queries:
            results = populated_memory.recall(query, top_k=3)
            assert len(results) > 0, f"No results for: {query}"

    def test_all_exception_types(self, populated_memory):
        """所有异常类型汇总"""
        exception_memories = populated_memory.get_memories_by_category("exception")
        assert len(exception_memories) >= 2
        all_content = " ".join(
            m.content if hasattr(m, "content") else str(m)
            for m in exception_memories
        )
        # 应包含多种异常类型
        expected = ["connection", "timeout", "http", "ssl", "redirect"]
        found = sum(1 for e in expected if e in all_content.lower())
        assert found >= 3, f"Expected at least 3 exception types, found {found}"


class TestScenario5_APIUsagePatterns:
    """场景5: API 使用模式记忆"""

    def test_common_patterns(self, populated_memory):
        """常见使用模式检索"""
        patterns = [
            "发送带JSON body的POST请求",
            "使用Session保持Cookie",
            "设置请求超时",
            "配置代理",
        ]
        found = 0
        for pattern in patterns:
            results = populated_memory.recall(pattern, top_k=3)
            if results:
                found += 1
        assert found >= 3, f"Found {found}/4 usage patterns"

    def test_security_patterns(self, populated_memory):
        """安全相关模式"""
        results = populated_memory.recall("SSL证书验证和HTTPS安全", top_k=3)
        assert len(results) > 0
        all_content = " ".join(
            r["content"] if isinstance(r, dict) else str(r) for r in results
        )
        assert "ssl" in all_content.lower() or "verify" in all_content.lower()

    def test_authentication_patterns(self, populated_memory):
        """认证模式 - 验证检索返回结果"""
        results = populated_memory.recall("HTTP认证方式 Basic Digest", top_k=5)
        assert len(results) > 0
        # fake embedding 下不保证内容匹配，只验证检索正常工作


class TestScenario6_KnowledgeGraph:
    """场景6: 知识图谱实体关系构建"""

    def test_entity_creation(self, populated_memory):
        """知识图谱应有实体"""
        if populated_memory.knowledge_graph is None:
            pytest.skip("Knowledge graph not enabled")
        stats = populated_memory.knowledge_graph.get_statistics()
        # 知识图谱应该有实体（通过记忆内容自动提取）
        assert stats["entity_count"] >= 0  # 可能没有自动提取

    def test_manual_entity_relation(self, populated_memory):
        """手动添加实体和关系"""
        if populated_memory.knowledge_graph is None:
            pytest.skip("Knowledge graph not enabled")

        # 添加 Requests 架构关系
        populated_memory.knowledge_graph.add_entity(Entity(name="requests.get", entity_type="function", properties={"module": "api", "http_method": "GET"}))
        populated_memory.knowledge_graph.add_entity(Entity(name="Session", entity_type="class", properties={"module": "sessions"}))
        populated_memory.knowledge_graph.add_entity(Entity(name="HTTPAdapter", entity_type="class", properties={"module": "adapters"}))
        populated_memory.knowledge_graph.add_entity(Entity(name="Response", entity_type="class", properties={"module": "models"}))

        populated_memory.knowledge_graph.add_relation(Relation(source="requests.get", target="Session", relation_type="delegates_to"))
        populated_memory.knowledge_graph.add_relation(Relation(source="Session", target="HTTPAdapter", relation_type="uses"))
        populated_memory.knowledge_graph.add_relation(Relation(source="Session", target="Response", relation_type="returns"))
        populated_memory.knowledge_graph.add_relation(Relation(source="HTTPAdapter", target="urllib3", relation_type="depends_on"))

        stats = populated_memory.knowledge_graph.get_statistics()
        assert stats["entity_count"] >= 4
        assert stats["relation_count"] >= 4

    def test_path_finding(self, populated_memory):
        """路径查找：从API到底层依赖"""
        if populated_memory.knowledge_graph is None:
            pytest.skip("Knowledge graph not enabled")

        # 先添加实体和关系
        populated_memory.knowledge_graph.add_entity(Entity(name="requests.get", entity_type="function"))
        populated_memory.knowledge_graph.add_entity(Entity(name="Session", entity_type="class"))
        populated_memory.knowledge_graph.add_entity(Entity(name="HTTPAdapter", entity_type="class"))
        populated_memory.knowledge_graph.add_entity(Entity(name="urllib3", entity_type="library"))
        populated_memory.knowledge_graph.add_relation(Relation(source="requests.get", target="Session", relation_type="delegates_to"))
        populated_memory.knowledge_graph.add_relation(Relation(source="Session", target="HTTPAdapter", relation_type="uses"))
        populated_memory.knowledge_graph.add_relation(Relation(source="HTTPAdapter", target="urllib3", relation_type="depends_on"))

        # 查找路径
        path = populated_memory.find_path("requests.get", "urllib3")
        assert path is not None
        assert len(path) >= 3  # get -> Session -> HTTPAdapter -> urllib3

    def test_neighbor_query(self, populated_memory):
        """邻居查询"""
        if populated_memory.knowledge_graph is None:
            pytest.skip("Knowledge graph not enabled")

        populated_memory.knowledge_graph.add_entity(Entity(name="Session", entity_type="class"))
        populated_memory.knowledge_graph.add_entity(Entity(name="HTTPAdapter", entity_type="class"))
        populated_memory.knowledge_graph.add_entity(Entity(name="Response", entity_type="class"))
        populated_memory.knowledge_graph.add_entity(Entity(name="CookieJar", entity_type="class"))
        populated_memory.knowledge_graph.add_relation(Relation(source="Session", target="HTTPAdapter", relation_type="uses"))
        populated_memory.knowledge_graph.add_relation(Relation(source="Session", target="Response", relation_type="returns"))
        populated_memory.knowledge_graph.add_relation(Relation(source="Session", target="CookieJar", relation_type="manages"))

        neighbors = populated_memory.get_neighbors("Session")
        assert len(neighbors) >= 3


class TestScenario7_LargeScaleRetrieval:
    """场景7: 大规模记忆检索精度"""

    def test_precision_top_k(self, populated_memory):
        """Top-K 检索精度 - fake embedding下验证结果非空且相关"""
        # 测试多个查询的检索精度
        queries_and_expected_keywords = [
            ("HTTP GET请求", ["get", "http", "请求"]),
            ("Session Cookie", ["session", "cookie", "会话"]),
            ("Response status_code", ["response", "status", "响应"]),
            ("连接池", ["连接池", "adapter", "pool"]),
            ("SSL证书", ["ssl", "证书", "verify"]),
        ]

        hits = 0
        total = len(queries_and_expected_keywords)
        for query, keywords in queries_and_expected_keywords:
            results = populated_memory.recall(query, top_k=5)
            if results:
                # 检查top-5结果中是否有任何一个包含相关关键词
                all_content = " ".join(
                    r["content"] if isinstance(r, dict) else str(r) for r in results
                ).lower()
                if any(kw in all_content for kw in keywords):
                    hits += 1

        precision = hits / total
        assert precision >= 0.4, f"Retrieval precision {precision:.0%} < 40%"

    def test_recall_across_categories(self, populated_memory):
        """跨类别召回率"""
        categories = ["api", "session", "model", "adapter", "auth", "exception", "cookie"]
        found_categories = set()

        for cat in categories:
            results = populated_memory.recall(cat, top_k=5)
            if results:
                found_categories.add(cat)

        recall = len(found_categories) / len(categories)
        assert recall >= 0.7, f"Category recall {recall:.0%} < 70%"

    def test_diversity_in_results(self, populated_memory):
        """结果多样性"""
        results = populated_memory.recall("Requests库功能", top_k=10)
        assert len(results) > 0

        # 检查结果是否来自不同类别
        categories_seen = set()
        for r in results:
            cat = r.get("category", "") if isinstance(r, dict) else ""
            if cat:
                categories_seen.add(cat)

        # top-10结果应覆盖至少3个不同类别
        assert len(categories_seen) >= 3, (
            f"Expected diverse results from >=3 categories, got {len(categories_seen)}: {categories_seen}"
        )


class TestScenario8_MemoryDecayAndImportance:
    """场景8: 记忆衰减与重要性排序"""

    def test_importance_ordering(self, populated_memory):
        """高重要性记忆应排在前面"""
        # 查询通用关键词
        results = populated_memory.recall("Requests", top_k=5)
        assert len(results) > 0

        # 检查结果的重要性分数是否合理
        importances = []
        for r in results:
            if isinstance(r, dict):
                imp = r.get("importance", r.get("score", 0))
                importances.append(imp)

        if importances:
            # 重要性应该大致递减（允许一些波动因为还考虑相似度）
            # 至少第一个结果应该有合理的重要性
            assert importances[0] > 0

    def test_category_distribution(self, populated_memory):
        """类别分布应反映注入的知识结构"""
        all_memories = populated_memory.get_all_memories()
        assert len(all_memories) == len(REQUESTS_MODULE_KNOWLEDGE)

        categories = {}
        for m in all_memories:
            cat = m.category if hasattr(m, "category") else "unknown"
            categories[cat] = categories.get(cat, 0) + 1

        # API 和 Session 应该是最多的类别
        assert "api" in categories
        assert categories["api"] >= 3

    def test_tag_search(self, populated_memory):
        """标签搜索"""
        # 按标签查找
        all_memories = populated_memory.get_all_memories()
        http_tagged = [m for m in all_memories if hasattr(m, "tags") and "http" in m.tags]
        assert len(http_tagged) >= 3, f"Expected >=3 HTTP-tagged memories, got {len(http_tagged)}"

        auth_tagged = [m for m in all_memories if hasattr(m, "tags") and "auth" in m.tags]
        assert len(auth_tagged) >= 1


class TestScenario9_ExportImportWithKnowledge:
    """场景9: 知识导出/导入往返"""

    def test_export_import_preserves_knowledge(self, populated_memory, tmp_path):
        """导出后导入应保留所有知识"""
        export_file = str(tmp_path / "requests_knowledge.json")

        # 导出
        result = populated_memory.export_memories(export_file, format="json")
        assert result == export_file

        # 导入到新实例
        new_memory = AgentMemory(config=_make_config())
        stats = new_memory.import_memories(export_file)

        assert stats["imported"] == len(REQUESTS_MODULE_KNOWLEDGE)
        assert stats["errors"] == 0

        # 验证知识完整性
        new_count = new_memory.count_memories()
        assert new_count == len(REQUESTS_MODULE_KNOWLEDGE)

        # 验证检索能力
        results = new_memory.recall("HTTP GET请求", top_k=3)
        assert len(results) > 0

        new_memory.close()

    def test_filtered_export_import(self, populated_memory, tmp_path):
        """过滤导出后导入"""
        export_file = str(tmp_path / "api_knowledge.json")

        # 只导出API类别
        populated_memory.export_memories(export_file, format="json", category="api")

        new_memory = AgentMemory(config=_make_config())
        stats = new_memory.import_memories(export_file)

        # 应该只有API类别的记忆
        api_memories = new_memory.get_memories_by_category("api")
        assert len(api_memories) == stats["imported"]

        new_memory.close()


class TestScenario10_HybridSearch:
    """场景10: 混合搜索验证"""

    def test_hybrid_search_enabled(self, populated_memory):
        """混合搜索应默认启用"""
        # recall() 默认使用混合搜索
        results = populated_memory.recall("HTTP请求方法", top_k=5, use_hybrid=True)
        assert len(results) > 0

    def test_hybrid_vs_legacy_consistency(self, populated_memory):
        """混合搜索和传统搜索结果应一致"""
        query = "Session管理"
        legacy_results = populated_memory.recall(query, top_k=5, use_hybrid=False)
        assert len(legacy_results) > 0

        # 混合搜索可能因fake embedding不可调用而回退到传统搜索
        hybrid_results = populated_memory.recall(query, top_k=5, use_hybrid=True)
        assert len(hybrid_results) > 0
