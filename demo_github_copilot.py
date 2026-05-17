#!/usr/bin/env python3
"""
GitHub 真实场景测试 - 智能代码助手 (类似 GitHub Copilot)

模拟一个真实的 AI 编程助手，测试以下场景：
1. 代码片段记忆与检索
2. 项目上下文理解
3. 用户编程习惯学习
4. 跨文件代码关联
5. 长时间会话记忆保持
"""

import sys
import time
from datetime import datetime

sys.path.insert(0, "/workspace/agent_memory_system")

from memory_system import (
    AgentMemory,
    AgentMemoryConfig,
    HybridSearchEngine,
    KeywordSearchStrategy,
)

print("=" * 70)
print("🚀 GitHub Copilot 风格智能代码助手 - 真实场景测试")
print("=" * 70)
print()

# ============================================================
# 场景1: 初始化代码助手
# ============================================================
print("📌 场景1: 初始化代码助手")
print("-" * 50)

config = AgentMemoryConfig(
    short_term={"working_memory_capacity": 20, "history_limit": 200},
    long_term={
        "embedding": {"provider": "fake", "fake_dimension": 384},
        "vector_store": {"backend": "memory"}
    },
    knowledge_graph={"enabled": True},
    structured_store={"enabled": True, "db_path": ":memory:"},
    auto_consolidate=False,
    default_top_k=10,
)

copilot = AgentMemory(config=config)
print(f"✅ 代码助手初始化完成")
print(f"   Session: {copilot.session_id[:16]}...")
print()

# ============================================================
# 场景2: 模拟多轮编程会话
# ============================================================
print("📌 场景2: 模拟多轮编程会话")
print("-" * 50)

# 模拟一个真实的开发场景：用户正在开发一个 Web API
programming_sessions = [
    # 第一轮：项目初始化
    {
        "context": "项目初始化",
        "files": ["main.py", "requirements.txt"],
        "interactions": [
            ("user", "帮我创建一个 FastAPI 项目，需要用户认证和数据库连接"),
            ("assistant", """好的，我来帮你创建 FastAPI 项目结构：

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/")
def read_root():
    return {"message": "Hello World"}
```

需要安装：pip install fastapi uvicorn sqlalchemy"""),
        ]
    },
    # 第二轮：数据库模型设计
    {
        "context": "数据库模型设计",
        "files": ["models.py", "database.py"],
        "interactions": [
            ("user", "我需要设计用户模型，包含邮箱、密码哈希、创建时间"),
            ("assistant", """创建用户模型：

```python
# models.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
```"""),
            ("user", "还需要添加用户角色字段，支持 admin 和 user"),
            ("assistant", """添加角色字段：

```python
class User(Base):
    # ... 其他字段
    role = Column(String, default="user")  # admin 或 user
    
    def is_admin(self):
        return self.role == "admin"
```"""),
        ]
    },
    # 第三轮：API 路由开发
    {
        "context": "API 路由开发",
        "files": ["routers/users.py", "routers/auth.py"],
        "interactions": [
            ("user", "创建用户注册和登录接口"),
            ("assistant", """用户认证路由：

```python
# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

@router.post("/register")
def register(email: str, password: str):
    hashed = get_password_hash(password)
    # 保存到数据库...
    return {"email": email, "message": "User created"}
```"""),
            ("user", "登录接口需要返回 JWT token"),
            ("assistant", """添加 JWT token 支持：

```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/login")
def login(email: str, password: str):
    # 验证用户...
    access_token = create_access_token({"sub": email})
    return {"access_token": access_token, "token_type": "bearer"}
```"""),
        ]
    },
    # 第四轮：遇到错误和调试
    {
        "context": "错误调试",
        "files": ["debug.log"],
        "interactions": [
            ("user", "我遇到了 CORS 错误，前端无法访问 API"),
            ("assistant", """添加 CORS 中间件：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```"""),
            ("user", "数据库连接池出现超时错误"),
            ("assistant", """优化数据库连接池：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "postgresql://user:pass@localhost/db",
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_recycle=3600,   # 1小时后回收连接
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```"""),
        ]
    },
    # 第五轮：性能优化
    {
        "context": "性能优化",
        "files": ["cache.py", "config.py"],
        "interactions": [
            ("user", "API 响应太慢，需要添加缓存"),
            ("assistant", """使用 Redis 缓存：

```python
import redis
from functools import wraps

r = redis.Redis(host='localhost', port=6379, db=0)

def cache_response(expire=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            r.setex(cache_key, expire, json.dumps(result))
            return result
        return wrapper
    return decorator

@app.get("/users/{user_id}")
@cache_response(expire=600)
async def get_user(user_id: int):
    # 查询数据库...
    pass
```"""),
            ("user", "还需要添加请求限流"),
            ("assistant", """添加速率限制：

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "sensitive"}
```"""),
        ]
    },
]

print(f"💻 模拟 {len(programming_sessions)} 轮编程会话...")
print()

all_code_snippets = []
for i, session in enumerate(programming_sessions, 1):
    print(f"  📁 Session {i}: {session['context']}")
    print(f"     文件: {', '.join(session['files'])}")
    
    for role, content in session['interactions']:
        # 存储代码片段和上下文
        memory_type = "code_snippet" if "```" in content else "conversation"
        
        result = copilot.remember(
            content=content,
            memory_type=memory_type,
            metadata={
                "role": role,
                "session": i,
                "context": session['context'],
                "files": session['files'],
            },
            importance=0.8 if "```" in content else 0.6,
        )
        
        # 提取代码片段
        if "```" in content:
            code_blocks = content.split("```")
            for j, block in enumerate(code_blocks[1::2] if len(code_blocks) > 1 else []):
                if block.strip():
                    all_code_snippets.append({
                        "code": block.strip(),
                        "session": i,
                        "context": session['context'],
                    })
    
    print(f"     ✓ 已存储 {len(session['interactions'])} 条交互")

print()
print(f"📊 总计存储 {sum(len(s['interactions']) for s in programming_sessions)} 条交互")
print(f"   提取 {len(all_code_snippets)} 个代码片段")
print()

# ============================================================
# 场景3: 代码片段检索测试
# ============================================================
print("📌 场景3: 代码片段检索测试")
print("-" * 50)

code_queries = [
    "JWT token 怎么实现",
    "数据库连接池配置",
    "CORS 跨域设置",
    "Redis 缓存装饰器",
    "用户认证中间件",
    "SQLAlchemy 模型定义",
]

print("🔍 代码语义搜索:")
print()
for query in code_queries:
    print(f"  Query: \"{query}\"")
    results = copilot.recall(query, top_k=2, exclude_sources=["structured"])
    
    if results:
        for j, mem in enumerate(results, 1):
            content = mem.get("content", "")[:100]
            score = mem.get("score", 0)
            print(f"    {j}. [{mem.get('memory_type', 'unknown')}] {content}... (score: {score:.3f})")
    else:
        print("    (无结果)")
    print()

# ============================================================
# 场景4: 项目上下文理解
# ============================================================
print("📌 场景4: 项目上下文理解")
print("-" * 50)

# 存储项目元数据
project_info = {
    "name": "FastAPI Web API",
    "framework": "FastAPI",
    "database": "PostgreSQL",
    "cache": "Redis",
    "auth": "JWT + OAuth2",
    "python_version": "3.10+",
}

print("💾 存储项目上下文:")
for key, value in project_info.items():
    copilot.remember_fact(f"{key}: {value}", category="project")
    print(f"  ✓ {key}: {value}")

print()

# 查询项目上下文
print("🔍 查询项目技术栈:")
tech_queries = ["使用什么框架", "数据库是什么", "认证方式"]
for query in tech_queries:
    results = copilot.recall(query, top_k=1)
    if results:
        print(f"  \"{query}\" → {results[0].get('content', '')[:60]}...")

print()

# ============================================================
# 场景5: 用户编程习惯学习
# ============================================================
print("📌 场景5: 用户编程习惯学习")
print("-" * 50)

# 存储用户偏好
copilot.set_preference("code_style", "PEP8 with type hints")
copilot.set_preference("favorite_patterns", ["decorator", "context manager", "async/await"])
copilot.set_preference("docstring_format", "Google style")
copilot.set_preference("error_handling", "prefer early return with guard clauses")

print("💾 用户编程偏好:")
print(f"  - 代码风格: {copilot.get_session_context('code_style') or '未设置'}")
print(f"  - 常用模式: {copilot.get_session_context('favorite_patterns') or '未设置'}")
print()

# ============================================================
# 场景6: 跨文件代码关联
# ============================================================
print("📌 场景6: 跨文件代码关联")
print("-" * 50)

# 使用混合搜索引擎
engine = HybridSearchEngine(fusion_method="rrf")
keyword_strategy = KeywordSearchStrategy()

# 索引所有代码片段
for snippet in all_code_snippets:
    doc_id = f"code_{snippet['session']}_{hash(snippet['code']) % 10000}"
    keyword_strategy.add_document(doc_id, snippet['code'])

engine.add_strategy(keyword_strategy)

print(f"🔍 跨文件代码搜索 (索引 {len(all_code_snippets)} 个代码块):")
print()

code_search_queries = [
    "def create_access_token",
    "class User",
    "@router.post",
    "pool_size",
]

for query in code_search_queries:
    print(f"  Query: \"{query}\"")
    results = engine.search(query, top_k=2)
    
    if results:
        for j, hit in enumerate(results, 1):
            code_preview = hit.content[:80].replace('\n', ' ')
            print(f"    {j}. {code_preview}...")
    else:
        print("    (无结果)")
    print()

# ============================================================
# 场景7: 长时间会话记忆保持
# ============================================================
print("📌 场景7: 长时间会话记忆保持")
print("-" * 50)

# 获取对话历史
history = copilot.get_conversation_history(n=10)
print(f"📜 最近 {len(history)} 轮对话:")
for i, turn in enumerate(history[-5:], 1):
    role = turn.get("role", "unknown")
    content = turn.get("content", "")[:50]
    print(f"  {i}. [{role}] {content}...")

print()

# 获取知识图谱
kg_stats = copilot.get_knowledge_graph_stats()
print(f"📊 知识图谱统计:")
print(f"  - 实体: {kg_stats.get('entity_count', 0)}")
print(f"  - 关系: {kg_stats.get('relation_count', 0)}")

# 尝试获取实体（如果有）
try:
    entities = copilot.knowledge_graph.get_all_entities() if copilot.knowledge_graph else []
    if entities:
        print(f"  - 主要实体: {', '.join([e.name for e in entities[:5]])}")
except:
    pass

print()

# ============================================================
# 场景8: 模拟用户返回继续开发
# ============================================================
print("📌 场景8: 模拟用户返回继续开发")
print("-" * 50)

print("🔄 用户问: \"之前我们怎么配置的数据库连接池？\"")
results = copilot.recall("数据库连接池配置", top_k=3)

if results:
    print("💡 检索到相关记忆:")
    for i, mem in enumerate(results[:2], 1):
        content = mem.get("content", "")[:200]
        print(f"  {i}. {content}...")
else:
    print("  (未能检索到相关记忆)")

print()

print("🔄 用户问: \"JWT 的 secret key 应该怎么设置？\"")
results = copilot.recall("JWT secret key", top_k=2)

if results:
    print("💡 检索到相关记忆:")
    for i, mem in enumerate(results, 1):
        content = mem.get("content", "")[:200]
        print(f"  {i}. {content}...")
else:
    print("  (未能检索到相关记忆)")

print()

# ============================================================
# 最终统计
# ============================================================
print("=" * 70)
print("📊 最终统计")
print("=" * 70)

stats = copilot.get_stats()
print(f"""
会话信息:
  Session ID:     {copilot.session_id}
  交互次数:       {stats.get('session', {}).get('interaction_count', 0)}

记忆统计:
  长期记忆:       {stats.get('long_term', {}).get('total_memories', 0)} 条
  工作记忆:       {stats.get('short_term', {}).get('working_memory_size', 0)} 条
  对话历史:       {stats.get('short_term', {}).get('history_size', 0)} 条

知识图谱:
  实体:           {stats.get('knowledge_graph', {}).get('entity_count', 0)} 个
  关系:           {stats.get('knowledge_graph', {}).get('relation_count', 0)} 个

结构化存储:
  表:             {stats.get('structured_store', {}).get('tables', [])}
""")

# 关闭系统
copilot.close()
print("✅ GitHub Copilot 风格代码助手测试完成！")
print()
