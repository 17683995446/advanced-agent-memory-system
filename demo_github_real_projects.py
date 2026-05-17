"""
GitHub真实大型项目测试 - 模拟AI助手分析开源项目代码

测试场景：
1. 分析Flask框架源码结构
2. 分析Requests库API设计
3. 跨项目代码模式对比
4. 大型项目记忆管理性能测试
"""

import sys
import time
from memory_system import AgentMemory

# 真实GitHub项目代码片段 - Flask框架
FLASK_APP_PY = '''
class Flask(App):
    """The flask object implements a WSGI application and acts as the central
    object. It is passed the name of the module or package of the application.
    """
    default_config = ImmutableDict({
        "DEBUG": None,
        "TESTING": False,
        "PROPAGATE_EXCEPTIONS": None,
        "SECRET_KEY": None,
        "PERMANENT_SESSION_LIFETIME": timedelta(days=31),
        "USE_X_SENDFILE": False,
        "SESSION_COOKIE_NAME": "session",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SECURE": False,
    })
    
    request_class: type[Request] = Request
    response_class: type[Response] = Response
    session_interface: SessionInterface = SecureCookieSessionInterface()
    
    def __init__(
        self,
        import_name: str,
        static_url_path: str | None = None,
        static_folder: str | os.PathLike[str] | None = "static",
        template_folder: str | os.PathLike[str] | None = "templates",
        instance_path: str | None = None,
    ):
        super().__init__(import_name=import_name, ...)
        self.cli = cli.AppGroup()
'''

FLASK_ROUTING = '''
class Rule:
    """A Rule represents one URL pattern."""
    def __init__(
        self,
        string: str,
        endpoint: str | None = None,
        methods: t.Iterable[str] | None = None,
        redirect_to: str | t.Callable[..., str] | None = None,
    ):
        self.rule = string
        self.endpoint = endpoint
        self.methods = methods
        
class MapAdapter:
    """Does the matching against the URL map."""
    def match(self, path_info: str | None = None) -> tuple[str, t.Mapping[str, t.Any]]:
        for rule in self.map._rules:
            if rule.matches(path_info):
                return rule.endpoint, rule.get_values()
'''

# 真实GitHub项目代码片段 - Requests库
REQUESTS_API = '''
def request(method: str, url: _t.UriType, **kwargs) -> Response:
    """Constructs and sends a Request.
    :param method: HTTP method (GET, POST, PUT, DELETE, etc.)
    :param url: URL for the request
    :param params: Dictionary for query string
    :param data: Dictionary or bytes for request body
    :param json: JSON serializable Python object
    :param headers: Dictionary of HTTP Headers
    :param timeout: Seconds to wait for server response
    """
    with sessions.Session() as session:
        return session.request(method=method, url=url, **kwargs)

def get(url, params=None, **kwargs) -> Response:
    """Sends a GET request."""
    return request("get", url, params=params, **kwargs)

def post(url, data=None, json=None, **kwargs) -> Response:
    """Sends a POST request."""
    return request("post", url, data=data, json=json, **kwargs)
'''

REQUESTS_SESSION = '''
class Session(SessionRedirectMixin):
    """A Requests session.
    Provides cookie persistence, connection-pooling, and configuration.
    """
    def __init__(self):
        self.headers = default_user_agent()
        self.auth = None
        self.proxies = {}
        self.hooks = default_hooks()
        self.params = {}
        self.stream = False
        self.verify = True
        self.cert = None
        self.max_redirects = DEFAULT_REDIRECT_LIMIT
        self.trust_env = True
        self.cookies = cookiejar_from_dict({})
        
    def request(self, method, url, **kwargs):
        # Build and send the request
        req = Request(method=method, url=url, **kwargs)
        prep = self.prepare_request(req)
        return self.send(prep, **send_kwargs)
'''

# Django项目代码片段
DJANGO_MODELS = '''
class Model(metaclass=ModelBase):
    """Base class for all models."""
    class Meta:
        abstract = True
        
    def __init__(self, *args, **kwargs):
        # Initialize model instance
        for field in self._meta.fields:
            setattr(self, field.name, kwargs.get(field.name))
    
    def save(self, force_insert=False, force_update=False, using=None):
        """Save the current instance."""
        self._save_table(
            raw=False,
            force_insert=force_insert,
            force_update=force_update,
            using=using,
        )
        
    def delete(self, using=None, keep_parents=False):
        """Delete the current instance."""
        using = using or router.db_for_write(self.__class__, instance=self)
        return self._do_delete(using)
'''

DJANGO_VIEWS = '''
class View:
    """Intentionally simple parent class for all views."""
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @classonlymethod
    def as_view(cls, **initkwargs):
        """Main entry point for a request-response process."""
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)
            self.setup(request, *args, **kwargs)
            return self.dispatch(request, *args, **kwargs)
        return view
    
    def dispatch(self, request, *args, **kwargs):
        handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        return handler(request, *args, **kwargs)
'''

# FastAPI项目代码片段
FASTAPI_MAIN = '''
class FastAPI(Starlette):
    """FastAPI application class."""
    def __init__(
        self,
        *,
        debug: bool = False,
        title: str = "FastAPI",
        description: str = "",
        version: str = "0.1.0",
        openapi_url: Optional[str] = "/openapi.json",
        docs_url: Optional[str] = "/docs",
    ):
        self.title = title
        self.description = description
        self.version = version
        self.openapi_url = openapi_url
        self.docs_url = docs_url
        self.router = APIRouter()
        
    def get(self, path: str, **kwargs):
        """Register a GET route."""
        return self.router.get(path, **kwargs)
    
    def post(self, path: str, **kwargs):
        """Register a POST route."""
        return self.router.post(path, **kwargs)
'''

FASTAPI_DEPENDENCY = '''
class Depends:
    """Dependency injection marker."""
    def __init__(self, dependency: Callable[..., Any] = None, *, use_cache: bool = True):
        self.dependency = dependency
        self.use_cache = use_cache

def solve_dependencies(
    request: Request,
    dependant: Dependant,
    body: Optional[Union[Dict[str, Any], FormData]] = None,
) -> Tuple[Dict[str, Any], List[ErrorWrapper], Optional[BackgroundTasks]]:
    """Solve all dependencies for a request."""
    values: Dict[str, Any] = {}
    errors: List[ErrorWrapper] = []
    
    for sub_dependant in dependant.dependencies:
        sub_values, sub_errors, _ = solve_dependencies(request, sub_dependant)
        values.update(sub_values)
        errors.extend(sub_errors)
    
    return values, errors, None
'''


def test_flask_code_analysis():
    """测试1: Flask框架代码分析记忆"""
    print("\n" + "="*70)
    print("📌 测试1: Flask框架源码分析")
    print("="*70)
    
    memory = AgentMemory()
    
    # 存储Flask相关代码片段
    memory.remember(
        content=FLASK_APP_PY,
        memory_type="code",
        category="flask",
        importance=0.9,
        source="github.com/pallets/flask",
        tags=["flask", "wsgi", "app", "framework"],
        metadata={
            "file": "src/flask/app.py",
            "lines": "class Flask",
            "language": "python"
        }
    )
    
    memory.remember(
        content=FLASK_ROUTING,
        memory_type="code",
        category="flask",
        importance=0.85,
        source="github.com/pallets/flask",
        tags=["flask", "routing", "url", "rule"],
        metadata={
            "file": "src/flask/routing.py",
            "lines": "class Rule, class MapAdapter",
            "language": "python"
        }
    )
    
    # 存储Flask架构知识
    memory.remember(
        content="Flask使用WSGI协议与Web服务器通信，核心类Flask继承自App类",
        memory_type="fact",
        category="flask",
        importance=0.8,
        source="analysis",
        tags=["flask", "architecture", "wsgi"]
    )
    
    memory.remember(
        content="Flask的路由系统基于Werkzeug的Rule和MapAdapter实现",
        memory_type="fact",
        category="flask",
        importance=0.8,
        source="analysis",
        tags=["flask", "routing", "werkzeug"]
    )
    
    # 测试检索
    print("\n🔍 检索 'Flask类初始化参数':")
    results = memory.recall("Flask类初始化参数", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    print("\n🔍 检索 '路由匹配机制':")
    results = memory.recall("路由匹配机制", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    stats = memory.get_stats()
    print(f"\n📊 Flask分析记忆统计: 长期记忆={stats['long_term'].get('total_memories', 0)}条")
    
    memory.close()
    return True


def test_requests_code_analysis():
    """测试2: Requests库代码分析记忆"""
    print("\n" + "="*70)
    print("📌 测试2: Requests库源码分析")
    print("="*70)
    
    memory = AgentMemory()
    
    # 存储Requests相关代码
    memory.remember(
        content=REQUESTS_API,
        memory_type="code",
        category="requests",
        importance=0.9,
        source="github.com/psf/requests",
        tags=["requests", "http", "api", "client"],
        metadata={
            "file": "src/requests/api.py",
            "lines": "def request, def get, def post",
            "language": "python"
        }
    )
    
    memory.remember(
        content=REQUESTS_SESSION,
        memory_type="code",
        category="requests",
        importance=0.85,
        source="github.com/psf/requests",
        tags=["requests", "session", "connection", "pool"],
        metadata={
            "file": "src/requests/sessions.py",
            "lines": "class Session",
            "language": "python"
        }
    )
    
    # 存储设计模式分析
    memory.remember(
        content="Requests使用Session类实现连接池和Cookie持久化，采用上下文管理器模式",
        memory_type="fact",
        category="requests",
        importance=0.8,
        source="analysis",
        tags=["requests", "session", "connection-pool", "pattern"]
    )
    
    memory.remember(
        content="Requests API设计采用函数式接口(get/post/put)和面向对象Session两种风格",
        memory_type="fact",
        category="requests",
        importance=0.75,
        source="analysis",
        tags=["requests", "api-design", "functional", "oop"]
    )
    
    # 测试检索
    print("\n🔍 检索 'Session连接池':")
    results = memory.recall("Session连接池", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    print("\n🔍 检索 'HTTP请求方法':")
    results = memory.recall("HTTP请求方法", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    stats = memory.get_stats()
    print(f"\n📊 Requests分析记忆统计: 长期记忆={stats['long_term'].get('total_memories', 0)}条")
    
    memory.close()
    return True


def test_django_code_analysis():
    """测试3: Django框架代码分析记忆"""
    print("\n" + "="*70)
    print("📌 测试3: Django框架源码分析")
    print("="*70)
    
    memory = AgentMemory()
    
    # 存储Django相关代码
    memory.remember(
        content=DJANGO_MODELS,
        memory_type="code",
        category="django",
        importance=0.9,
        source="github.com/django/django",
        tags=["django", "model", "orm", "database"],
        metadata={
            "file": "django/db/models/base.py",
            "lines": "class Model",
            "language": "python"
        }
    )
    
    memory.remember(
        content=DJANGO_VIEWS,
        memory_type="code",
        category="django",
        importance=0.85,
        source="github.com/django/django",
        tags=["django", "view", "http", "dispatch"],
        metadata={
            "file": "django/views/generic/base.py",
            "lines": "class View",
            "language": "python"
        }
    )
    
    # 存储Django架构知识
    memory.remember(
        content="Django采用MTV模式(Model-Template-View)，Model负责数据层，View负责业务逻辑",
        memory_type="fact",
        category="django",
        importance=0.8,
        source="analysis",
        tags=["django", "mtv", "architecture", "pattern"]
    )
    
    memory.remember(
        content="Django的Model使用元类ModelBase实现字段映射和数据库表关联",
        memory_type="fact",
        category="django",
        importance=0.75,
        source="analysis",
        tags=["django", "model", "metaclass", "orm"]
    )
    
    # 测试检索
    print("\n🔍 检索 'Django模型保存机制':")
    results = memory.recall("Django模型保存机制", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    print("\n🔍 检索 'View分发逻辑':")
    results = memory.recall("View分发逻辑", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    stats = memory.get_stats()
    print(f"\n📊 Django分析记忆统计: 长期记忆={stats['long_term'].get('total_memories', 0)}条")
    
    memory.close()
    return True


def test_fastapi_code_analysis():
    """测试4: FastAPI框架代码分析记忆"""
    print("\n" + "="*70)
    print("📌 测试4: FastAPI框架源码分析")
    print("="*70)
    
    memory = AgentMemory()
    
    # 存储FastAPI相关代码
    memory.remember(
        content=FASTAPI_MAIN,
        memory_type="code",
        category="fastapi",
        importance=0.9,
        source="github.com/tiangolo/fastapi",
        tags=["fastapi", "app", "router", "openapi"],
        metadata={
            "file": "fastapi/main.py",
            "lines": "class FastAPI",
            "language": "python"
        }
    )
    
    memory.remember(
        content=FASTAPI_DEPENDENCY,
        memory_type="code",
        category="fastapi",
        importance=0.85,
        source="github.com/tiangolo/fastapi",
        tags=["fastapi", "dependency", "injection", "di"],
        metadata={
            "file": "fastapi/dependencies/utils.py",
            "lines": "class Depends, def solve_dependencies",
            "language": "python"
        }
    )
    
    # 存储FastAPI特性
    memory.remember(
        content="FastAPI基于Starlette和Pydantic，支持异步处理、自动API文档生成",
        memory_type="fact",
        category="fastapi",
        importance=0.8,
        source="analysis",
        tags=["fastapi", "async", "pydantic", "openapi"]
    )
    
    memory.remember(
        content="FastAPI的依赖注入系统通过Depends类标记依赖，支持缓存和嵌套依赖",
        memory_type="fact",
        category="fastapi",
        importance=0.8,
        source="analysis",
        tags=["fastapi", "dependency-injection", "depends", "cache"]
    )
    
    # 测试检索
    print("\n🔍 检索 'FastAPI路由注册':")
    results = memory.recall("FastAPI路由注册", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    print("\n🔍 检索 '依赖注入实现':")
    results = memory.recall("依赖注入实现", top_k=3)
    for r in results:
        print(f"  - [{r['source']}] {r['content'][:80]}...")
    
    stats = memory.get_stats()
    print(f"\n📊 FastAPI分析记忆统计: 长期记忆={stats['long_term'].get('total_memories', 0)}条")
    
    memory.close()
    return True


def test_cross_project_patterns():
    """测试5: 跨项目代码模式对比记忆"""
    print("\n" + "="*70)
    print("📌 测试5: 跨项目设计模式对比")
    print("="*70)
    
    memory = AgentMemory()
    
    # 存储跨项目分析
    memory.remember(
        content="Flask和FastAPI都使用装饰器模式注册路由，但FastAPI支持类型注解自动验证",
        memory_type="fact",
        category="comparison",
        importance=0.85,
        source="cross-project-analysis",
        tags=["flask", "fastapi", "routing", "decorator", "comparison"]
    )
    
    memory.remember(
        content="Django使用类继承实现视图(View类)，Flask使用函数装饰器，FastAPI支持两者",
        memory_type="fact",
        category="comparison",
        importance=0.85,
        source="cross-project-analysis",
        tags=["django", "flask", "fastapi", "view", "comparison"]
    )
    
    memory.remember(
        content="Requests和HTTPX都提供同步和异步API，但HTTPX原生支持async/await",
        memory_type="fact",
        category="comparison",
        importance=0.8,
        source="cross-project-analysis",
        tags=["requests", "httpx", "async", "http-client", "comparison"]
    )
    
    memory.remember(
        content="四大Web框架的依赖注入对比：Flask使用扩展，Django使用中间件，FastAPI原生支持",
        memory_type="fact",
        category="comparison",
        importance=0.8,
        source="cross-project-analysis",
        tags=["flask", "django", "fastapi", "dependency-injection", "comparison"]
    )
    
    # 测试跨项目检索
    print("\n🔍 检索 'Web框架路由机制对比':")
    results = memory.recall("Web框架路由机制对比", top_k=5)
    for r in results:
        print(f"  - [{r['category']}] {r['content'][:80]}...")
    
    print("\n🔍 检索 '依赖注入实现差异':")
    results = memory.recall("依赖注入实现差异", top_k=5)
    for r in results:
        print(f"  - [{r['category']}] {r['content'][:80]}...")
    
    stats = memory.get_stats()
    print(f"\n📊 跨项目分析记忆统计: 长期记忆={stats['long_term'].get('total_memories', 0)}条")
    
    memory.close()
    return True


def test_large_scale_memory():
    """测试6: 大规模代码记忆性能测试"""
    print("\n" + "="*70)
    print("📌 测试6: 大规模代码记忆性能测试")
    print("="*70)
    
    memory = AgentMemory()
    
    # 模拟存储大量代码片段
    projects = ["flask", "django", "fastapi", "requests", "httpx", "sqlalchemy", "pytest"]
    file_types = ["models.py", "views.py", "urls.py", "serializers.py", "tests.py"]
    
    start_time = time.time()
    stored_count = 0
    
    for i in range(100):  # 存储100个代码片段
        project = projects[i % len(projects)]
        file_type = file_types[i % len(file_types)]
        
        code_snippet = f'''
# {project}/{file_type} - 片段{i}
def function_{i}(request, *args, **kwargs):
    """Auto-generated function for testing."""
    data = request.data
    result = process_data(data)
    return Response(result)
'''
        memory.remember(
            content=code_snippet,
            memory_type="code",
            category=project,
            importance=0.5 + (i % 5) * 0.1,
            source=f"github.com/test/{project}",
            tags=[project, "code", f"snippet-{i}"],
            metadata={
                "file": file_type,
                "index": i,
                "project": project
            }
        )
        stored_count += 1
    
    store_time = time.time() - start_time
    print(f"\n💾 存储 {stored_count} 个代码片段，耗时: {store_time:.2f}s")
    print(f"   平均每个片段: {store_time/stored_count*1000:.2f}ms")
    
    # 测试检索性能
    start_time = time.time()
    for query in ["function", "process_data", "Response", "request", "kwargs"]:
        results = memory.recall(query, top_k=10)
    search_time = time.time() - start_time
    
    print(f"\n🔍 执行5次检索，耗时: {search_time:.2f}s")
    print(f"   平均每次检索: {search_time/5*1000:.2f}ms")
    
    # 统计
    stats = memory.get_stats()
    print(f"\n📊 大规模测试统计:")
    print(f"   长期记忆: {stats['long_term'].get('total_memories', 0)}条")
    print(f"   工作记忆: {stats['short_term']['working_memory_size']}条")
    print(f"   会话交互: {stats['session']['interaction_count']}次")
    
    memory.close()
    return True


def test_project_context_management():
    """测试7: 多项目上下文管理"""
    print("\n" + "="*70)
    print("📌 测试7: 多项目上下文管理")
    print("="*70)
    
    memory = AgentMemory()
    
    # 设置当前项目上下文
    memory.set_session_context("current_project", "flask")
    memory.set_session_context("analysis_mode", "deep")
    
    # 存储Flask相关记忆
    memory.remember(
        content="Flask 2.0+支持异步视图函数，使用async/await语法",
        memory_type="fact",
        category="flask",
        importance=0.8,
        source="github.com/pallets/flask",
        tags=["flask", "async", "await"]
    )
    
    # 切换项目上下文
    memory.set_session_context("current_project", "django")
    
    memory.remember(
        content="Django 4.0+支持异步视图和中间件，但ORM仍需同步",
        memory_type="fact",
        category="django",
        importance=0.8,
        source="github.com/django/django",
        tags=["django", "async", "orm"]
    )
    
    # 检索时考虑上下文
    current_project = memory.get_session_context("current_project")
    print(f"\n🎯 当前项目上下文: {current_project}")
    
    print(f"\n🔍 在'{current_project}'上下文中检索 'async':")
    results = memory.recall("async", top_k=5)
    for r in results:
        print(f"  - [{r['category']}] {r['content'][:60]}...")
    
    # 测试偏好设置
    memory.set_preference("code_style", "pep8")
    memory.set_preference("analysis_depth", "detailed")
    
    pref = memory.get_preference("code_style")
    print(f"\n⚙️ 用户偏好 - 代码风格: {pref}")
    
    stats = memory.get_stats()
    print(f"\n📊 多项目上下文统计: 长期记忆={stats['long_term'].get('total_memories', 0)}条")
    
    memory.close()
    return True


def main():
    """主测试函数"""
    print("\n" + "="*70)
    print("🚀 GitHub真实大型项目测试 - Agent Memory System")
    print("="*70)
    print("\n测试项目:")
    print("  1. Flask - WSGI Web框架 (66K+ stars)")
    print("  2. Requests - HTTP客户端 (52K+ stars)")
    print("  3. Django - MTV Web框架 (80K+ stars)")
    print("  4. FastAPI - 异步Web框架 (80K+ stars)")
    
    results = []
    
    try:
        results.append(("Flask分析", test_flask_code_analysis()))
    except Exception as e:
        print(f"❌ Flask分析失败: {e}")
        results.append(("Flask分析", False))
    
    try:
        results.append(("Requests分析", test_requests_code_analysis()))
    except Exception as e:
        print(f"❌ Requests分析失败: {e}")
        results.append(("Requests分析", False))
    
    try:
        results.append(("Django分析", test_django_code_analysis()))
    except Exception as e:
        print(f"❌ Django分析失败: {e}")
        results.append(("Django分析", False))
    
    try:
        results.append(("FastAPI分析", test_fastapi_code_analysis()))
    except Exception as e:
        print(f"❌ FastAPI分析失败: {e}")
        results.append(("FastAPI分析", False))
    
    try:
        results.append(("跨项目对比", test_cross_project_patterns()))
    except Exception as e:
        print(f"❌ 跨项目对比失败: {e}")
        results.append(("跨项目对比", False))
    
    try:
        results.append(("大规模性能", test_large_scale_memory()))
    except Exception as e:
        print(f"❌ 大规模性能测试失败: {e}")
        results.append(("大规模性能", False))
    
    try:
        results.append(("多项目上下文", test_project_context_management()))
    except Exception as e:
        print(f"❌ 多项目上下文测试失败: {e}")
        results.append(("多项目上下文", False))
    
    # 最终报告
    print("\n" + "="*70)
    print("📊 测试总结")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
