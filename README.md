# Agent 长短期记忆系统 v2.0

高度模块化的 Agent 记忆管理框架，基于开源生态构建。每个模块可独立使用、独立产品化。

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    AgentMemory (统一入口)                  │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ 短期记忆  │ 长期记忆  │ 嵌入模型  │ 知识图谱  │ 结构化存储   │
│ShortTerm │LongTerm  │Embedding │Knowledge │Structured   │
│Memory    │Memory    │Provider  │Graph     │Store        │
├──────────┼──────────┼──────────┼──────────┼─────────────┤
│工作记忆   │向量存储   │ST/OpenAI │NetworkX  │SQLite       │
│缓冲区    │后端可插拔  │/Fake     │实体关系图 │持久化       │
└──────────┴──────────┴──────────┴──────────┴─────────────┘
         ┌──────────────────────────────┐
         │  可插拔后端 (Pluggable)       │
         │  Memory | ChromaDB | FAISS   │
         └──────────────────────────────┘
```

## 模块清单 (6个独立模块)

| 模块 | 文件 | 核心类 | 依赖 | 说明 |
|------|------|--------|------|------|
| 嵌入模型 | `embedding.py` | `EmbeddingProvider` | sentence-transformers, openai | 嵌入模型，可插拔 |
| 向量存储 | `vector_store.py` | `VectorStoreBackend` | chromadb, faiss-cpu, numpy | 向量存储，3种后端 |
| 知识图谱 | `knowledge_graph.py` | `KnowledgeGraph` | networkx | 知识图谱 |
| 结构化存储 | `structured_store.py` | `StructuredStore` | sqlite3 (stdlib) | 结构化存储 |
| 短期记忆 | `short_term_memory.py` | `ShortTermMemory` | 无额外依赖 | 工作记忆 |
| 统一入口 | `memory_manager.py` | `AgentMemory` | 所有模块 | 统一入口 |

## 安装

```bash
pip install -r requirements.txt
```

`requirements.txt` 内容：

```
sentence-transformers>=2.0.0
chromadb>=0.4.0
faiss-cpu>=1.7.0
networkx>=3.0
pydantic>=2.0.0
numpy>=1.21.0
```

## 快速开始

### 1. 一行代码启动（零配置）

```python
from memory_system import AgentMemory

memory = AgentMemory()  # 自动使用 FakeEmbedding + MemoryVectorStore
```

### 2. 完整配置

```python
from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig

config = AgentMemoryConfig(
    long_term=LongTermMemoryConfig(
        embedding={"provider": "sentence-transformer", "model_name": "all-MiniLM-L6-v2"},
        vector_store={"backend": "chroma", "persist_directory": "./chroma_db"},
    ),
    knowledge_graph={"enabled": True},
    structured_store={"db_path": "./agent.db", "enabled": True},
)
memory = AgentMemory(config)
```

### 3. 核心 API

#### 存储记忆

```python
# 添加到工作记忆（短期）
memory.add_to_working_memory(
    key="user_name",
    content="用户的名字是张三",
    importance=0.9,
    memory_type="fact",
)

# 存储到长期记忆
memory_id = memory.remember(
    content="张三是一名软件工程师",
    memory_type="semantic",
    category="personal",
    importance=0.9,
)

# 记住事实（同时写入长期记忆和结构化存储）
memory_id = memory.remember_fact(
    fact="张三喜欢Python编程",
    category="preference",
    source="user",
    confidence=0.95,
)
```

#### 检索记忆

```python
# 基本检索（同时搜索短期和长期记忆）
results = memory.recall("用户是做什么工作的？", top_k=5)
for r in results:
    print(f"[{r['source']}] {r['content']} (相关度: {r['score']:.2f})")

# 获取格式化的上下文，用于构建 LLM 提示
context = memory.get_relevant_context("用户是做什么工作的？", max_items=5)
print(context)
```

#### 知识图谱

```python
# 添加实体和关系
memory.add_entity(name="张三", entity_type="person", description="软件工程师")
memory.add_entity(name="Python", entity_type="skill", description="编程语言")
memory.add_relation(source="张三", target="Python", relation_type="擅长", weight=0.9)

# 从文本自动提取实体和关系
memory.build_knowledge_from_text("张三是一名软件工程师。张三擅长Python编程。")

# 搜索和查找关联实体
entities = memory.search_entities("张三", top_k=5)
related = memory.find_related("张三", top_k=5)
```

#### 结构化存储

```python
# 存储用户偏好
memory.store_preference(key="theme", value="dark", category="ui")

# 记录交互日志
memory.log_interaction(role="user", content="你好，请帮我查一下天气。")
```

#### 对话管理

```python
# 记住对话（重要内容会自动写入长期记忆）
memory.remember_conversation(
    content="我想了解机器学习的入门知识",
    speaker="user",
    important=True,
)

# 获取对话历史
history = memory.get_conversation_history(n=10)
for msg in history:
    print(f"{msg['role']}: {msg['content']}")
```

## 模块独立使用

每个模块都可以脱离 `AgentMemory` 单独使用，适合只需要部分功能的场景。

### 独立使用 Embedding

```python
from memory_system.embedding import EmbeddingFactory

# 使用 Fake 嵌入（零依赖，适合测试）
provider = EmbeddingFactory.create("fake", dimension=128)
vec = provider.encode("你好世界")
print(f"向量维度: {provider.dimension}")

# 使用 sentence-transformer（需要安装 sentence-transformers）
st_provider = EmbeddingFactory.create("sentence-transformer", model_name="all-MiniLM-L6-v2")
vec = st_provider.encode("Hello world")

# 使用 OpenAI（需要安装 openai 并设置 API Key）
oai_provider = EmbeddingFactory.create("openai", api_key="sk-xxx")
vec = oai_provider.encode("Hello world")

# 计算相似度
score = EmbeddingProvider.similarity(vec1, vec2)
```

### 独立使用 VectorStore

```python
from memory_system.vector_store import VectorStoreFactory, MemoryRecord

# 内存后端（零依赖）
store = VectorStoreFactory.create("memory")

# ChromaDB 后端（持久化）
store = VectorStoreFactory.create("chroma", persist_directory="./my_db")

# FAISS 后端（高性能）
store = VectorStoreFactory.create("faiss", dimension=384)

# 添加记录
record = MemoryRecord(
    id="1",
    content="这是一条记忆",
    embedding=[0.1, 0.2, 0.3],  # 通常由 EmbeddingProvider 生成
    category="general",
)
store.add(record)

# 搜索
results = store.search(query_embedding=[0.1, 0.2, 0.3], top_k=5)
for r in results:
    print(f"{r.record.content} (score: {r.score:.4f})")
```

### 独立使用 KnowledgeGraph

```python
from memory_system.knowledge_graph import KnowledgeGraph, Entity, Relation, KnowledgeGraphBuilder

kg = KnowledgeGraph()

# 添加实体和关系
kg.add_entity(Entity(name="北京", entity_type="location", description="中国首都"))
kg.add_entity(Entity(name="中国", entity_type="country", description="国家"))
kg.add_relation(Relation(source="北京", target="中国", relation_type="capital_of"))

# 从文本自动构建
kg = KnowledgeGraphBuilder.build_from_text("北京是中国的首都。北京位于华北地区。")

# 搜索实体
results = kg.search_entities("北京", top_k=3)
for entity, score in results:
    print(f"{entity.name} ({entity.entity_type}): {entity.description} [score={score:.2f}]")

# 查找关联实体
related = kg.find_related("北京", top_k=5)
for r in related:
    print(f"  -> {r.entities[0].name} (score={r.score:.4f})")

# 持久化
kg.save_to_json("knowledge_graph.json")
```

### 独立使用 StructuredStore

```python
from memory_system.structured_store import StructuredStore, MemoryTable

# 创建存储
store = StructuredStore("agent.db")  # 或 ":memory:" 使用内存数据库
table = MemoryTable(store)
table.init_tables()

# 记录交互
table.log_interaction(agent_id="agent-1", role="user", content="你好！")

# 存储偏好
table.store_preference(key="language", value="zh-CN", category="settings")

# 存储事实
table.store_fact(fact="用户使用中文交流", source="conversation", confidence=0.95)

# 查询
interactions = table.get_interactions(agent_id="agent-1", limit=10)
pref = table.get_preference("language")
facts = table.get_facts(category="preference")

# 通用 CRUD
store.create_table("notes", {"title": "TEXT", "body": "TEXT"})
store.insert("notes", {"title": "备忘", "body": "重要事项"})
result = store.select("notes", where="title = ?", params=("备忘",))
```

## 可插拔后端

### Embedding Providers

| Provider | 说明 | 依赖 |
|----------|------|------|
| `fake` | 哈希模拟，零依赖，适合开发和测试 | numpy |
| `sentence-transformer` | 真实语义嵌入，支持多种 HuggingFace 模型 | sentence-transformers + torch |
| `openai` | 调用 OpenAI Embeddings API | openai |

通过 `EmbeddingFactory.create(provider, **kwargs)` 创建，支持 `"auto"` 模式自动检测可用环境。

### Vector Store Backends

| Backend | 说明 | 依赖 | 适用场景 |
|---------|------|------|----------|
| `memory` | 纯内存向量存储，基于 NumPy 余弦相似度 | numpy | 开发/测试 |
| `chroma` | 持久化向量数据库，支持过滤和元数据查询 | chromadb | 生产/中等规模 |
| `faiss` | 高性能向量索引，支持磁盘持久化 | faiss-cpu | 大规模/高性能 |

通过 `VectorStoreFactory.create(backend, **kwargs)` 创建，也支持 `register()` 注册自定义后端。

## 配置参考

`AgentMemoryConfig` 完整字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `short_term` | `dict` | `{"working_memory_capacity": 7, "history_limit": 50}` | 短期记忆配置 |
| `short_term.working_memory_capacity` | `int` | `7` | 工作记忆容量（推荐 4-9） |
| `short_term.history_limit` | `int` | `50` | 交互历史保留数量 |
| `long_term` | `LongTermMemoryConfig` | (见下) | 长期记忆配置 |
| `long_term.embedding` | `EmbeddingConfig` / `dict` | `{"provider": "auto"}` | 嵌入模型配置 |
| `long_term.embedding.provider` | `str` | `"auto"` | 嵌入提供者：auto/fake/sentence-transformer/openai |
| `long_term.embedding.model_name` | `str` | `None` | 模型名称 |
| `long_term.embedding.dimension` | `int` | `None` | 嵌入维度 |
| `long_term.vector_store` | `dict` | `{"backend": "memory"}` | 向量存储配置 |
| `long_term.vector_store.backend` | `str` | `"memory"` | 存储后端：memory/chroma/faiss |
| `long_term.vector_store.persist_directory` | `str` | `None` | 持久化目录（chroma） |
| `knowledge_graph` | `dict` | `{"enabled": True}` | 知识图谱配置 |
| `knowledge_graph.enabled` | `bool` | `True` | 是否启用知识图谱 |
| `structured_store` | `dict` | `{"db_path": ":memory:", "enabled": True}` | 结构化存储配置 |
| `structured_store.db_path` | `str` | `":memory:"` | SQLite 数据库路径 |
| `structured_store.enabled` | `bool` | `True` | 是否启用结构化存储 |
| `consolidation_threshold` | `float` | `0.6` | 记忆巩固重要性阈值 (0-1) |
| `auto_consolidate` | `bool` | `True` | 是否启用自动巩固 |
| `default_top_k` | `int` | `5` | 默认检索返回数量 |

## 在 Agent 中集成

以下是一个完整的 Agent 集成示例，展示如何在对话式 Agent 中使用记忆系统：

```python
from memory_system import AgentMemory, AgentMemoryConfig, LongTermMemoryConfig


class MyAgent:
    """带记忆系统的对话式 Agent"""

    def __init__(self, llm_client=None):
        # 初始化记忆系统
        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "sentence-transformer", "model_name": "all-MiniLM-L6-v2"},
                vector_store={"backend": "chroma", "persist_directory": "./chroma_db"},
            ),
            knowledge_graph={"enabled": True},
            structured_store={"db_path": "./agent.db", "enabled": True},
        )
        self.memory = AgentMemory(config)
        self.llm = llm_client  # 任意 LLM 客户端

    def chat(self, user_message: str) -> str:
        """处理用户消息并生成回复"""

        # 1. 记录用户消息
        self.memory.remember_conversation(
            content=user_message,
            speaker="user",
            important=self._is_important(user_message),
        )

        # 2. 从记忆中检索相关上下文
        context = self.memory.get_relevant_context(user_message, max_items=5)

        # 3. 构建提示词
        prompt = self._build_prompt(user_message, context)

        # 4. 调用 LLM 生成回复
        response = self.llm.generate(prompt)

        # 5. 记录回复
        self.memory.remember_conversation(
            content=response,
            speaker="assistant",
        )

        # 6. 执行记忆巩固（将重要短期记忆迁移到长期记忆）
        self.memory.consolidate(auto=True)

        return response

    def _is_important(self, message: str) -> bool:
        """判断消息是否重要（简单启发式规则）"""
        important_keywords = ["记住", "我的名字", "我喜欢", "偏好", "重要"]
        return any(kw in message for kw in important_keywords)

    def _build_prompt(self, user_message: str, context: str) -> str:
        """构建 LLM 提示词"""
        system_prompt = (
            "你是一个有记忆能力的 AI 助手。"
            "以下是你记忆中的相关上下文信息，请参考这些信息来回答用户问题。\n\n"
            f"{context}\n\n"
            "请用自然、友好的语气回答。"
        )
        return f"{system_prompt}\n\n用户: {user_message}\n助手:"

    def close(self):
        """关闭 Agent，保存所有数据"""
        self.memory.save()


# 使用示例
if __name__ == "__main__":
    agent = MyAgent()

    # 模拟对话
    print(agent.chat("我叫张三，是一名数据科学家。"))
    print(agent.chat("我喜欢用 Python 做数据分析。"))
    print(agent.chat("你还记得我是做什么工作的吗？"))  # Agent 会回忆起之前的信息

    agent.close()
```

## 许可证

MIT License
