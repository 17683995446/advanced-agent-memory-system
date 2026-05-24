# 第6轮超深度测试 - 测试前置分析

## 一、基准定调

### 1.1 设计文档分析

根据 README.md 和代码架构，系统架构如下：

- **主入口**: `AgentMemory` 类 (agent_memory_manager.py)
- **核心模块**:
  - 短期记忆 (ShortTermMemory)
  - 长期记忆 (LongTermMemory)
  - 知识图谱 (KnowledgeGraph)
  - 结构化存储 (StructuredStore)
  - 混合搜索引擎 (HybridSearchEngine)

### 1.2 设计原则
- 模块化设计，每个模块可独立使用
- 可插拔后端（ChromaDB, FAISS, 内存）
- Pydantic 配置验证
- 并发安全（已在前几轮验证）

---

## 二、测试前置动作

### 2.1 代码分层拆解

#### 层级结构
```
1. API 层 (入口)
   └── memory_manager.py (AgentMemory)

2. 核心协调层
   ├── agent_memory_manager.py (主协调)
   ├── hybrid_search_engine.py (混合搜索)
   ├── memory_consolidation.py (记忆巩固)
   └── memory_decay_engine.py (记忆衰减)

3. 业务逻辑层
   ├── short_term_working_memory.py (短期记忆)
   └── long_term_persistent_memory.py (长期记忆)

4. 处理层
   ├── text_embedding_provider.py (嵌入)
   ├── knowledge_graph_engine.py (知识图谱)
   └── chinese_english_tokenizer.py (分词)

5. 存储层
   ├── vector_store/ (向量存储)
   └── structured_sqlite_store.py (结构化存储)

6. 基础设施层
   ├── circuit_breaker_pattern.py (熔断器)
   ├── distributed_lock_manager.py (分布式锁)
   └── dynamic_config_manager.py (配置)
```

### 2.2 核心调用链路

```
AgentMemory.remember()
  ├── ShortTermMemory.add()
  ├── LongTermMemory.remember()
  │   ├── EmbeddingProvider.get_embedding()
  │   └── VectorStoreBackend.add()
  ├── KnowledgeGraph.add_entity() (可选)
  └── StructuredStore.insert() (可选)

AgentMemory.recall()
  └── HybridSearchEngine.search()
      ├── VectorSearchStrategy.search()
      ├── KeywordSearchStrategy.search()
      ├── KnowledgeGraphSearchStrategy.search()
      └── RRF 融合排序
```

### 2.3 入口和出口

| 功能 | 入口函数 | 出口点 |
|------|----------|--------|
| 记忆存储 | `remember()` | 返回 memory_id |
| 记忆检索 | `recall()` | 返回 SearchResult 列表 |
| 知识图谱 | `add_entity()`, `add_relation()` | 无返回/返回实体ID |
| 偏好存储 | `store_preference()`, `get_preference()` | 存储/获取偏好 |
| 对话记忆 | `remember_conversation()`, `get_conversation_history()` | 存储/获取对话 |

### 2.4 参数规则提取

#### AgentMemoryConfig
- `short_term`: 短期记忆配置 dict
- `long_term`: LongTermMemoryConfig
- `knowledge_graph`: 知识图谱配置 dict
- `structured_store`: 结构化存储配置 dict
- `consolidation_threshold`: float, 默认 0.6
- `auto_consolidate`: bool, 默认 True
- `default_top_k`: int, 默认 5

#### remember() 参数
- `content`: str (必需)
- `memory_type`: str (可选, 默认 "semantic")
- `importance`: float (可选, 默认 0.5, 范围 0.0-1.0)
- `category`: str (可选, 默认 "general")
- `metadata`: dict (可选)

#### recall() 参数
- `query`: str (必需)
- `top_k`: int (可选, 默认从配置读取)
- `threshold`: float (可选, 相似度阈值)

### 2.5 判断条件和边界阈值

| 条件 | 阈值 | 位置 |
|------|------|------|
| 记忆重要性 | 0.0-1.0 | remember() |
| 巩固阈值 | config.consolidation_threshold | _MemoryConsolidator |
| 工作记忆容量 | config.short_term["working_memory_capacity"] | ShortTermMemory |
| 历史限制 | config.short_term["history_limit"] | ShortTermMemory |
| 默认检索数量 | config.default_top_k | recall() |

### 2.6 默认逻辑

- 默认使用 `FakeEmbeddingProvider` (避免下载大模型)
- 默认使用 `MemoryVectorStore` (内存存储)
- 默认启用知识图谱和结构化存储
- 默认使用 `:memory:` SQLite 数据库 (临时存储)

### 2.7 异常捕获

系统已定义的异常类：
- `MemoryError`: 基类
- `EmbeddingError`: 嵌入相关错误
- `VectorStoreError`: 向量存储错误
- `KnowledgeGraphError`: 知识图谱错误
- `StructuredStoreError`: 结构化存储错误
- `EntityNotFoundError`: 实体未找到
- `TableNotFoundError`: 表未找到

### 2.8 数据流向梳理

```
数据写入路径:
用户输入 → AgentMemory.remember()
  ├──→ ShortTermMemory.add_to_working_memory()
  ├──→ LongTermMemory.remember()
  │   ├──→ EmbeddingProvider.get_embedding()
  │   └──→ VectorStoreBackend.add()
  └── (可选) → StructuredStore.insert()
        (可选) → KnowledgeGraph.add_entity()

数据读取路径:
用户查询 → AgentMemory.recall()
  └──→ HybridSearchEngine.search()
      ├──→ VectorSearchStrategy.search()
      ├──→ KeywordSearchStrategy.search()
      ├──→ (可选) KnowledgeGraphSearchStrategy.search()
      └──→ RRF 融合排序 → 返回给用户
```

### 2.9 状态变更和事务逻辑

- 短期记忆状态: 工作记忆缓冲区，FIFO/LRU 淘汰
- 长期记忆状态: 追加写入，不删除，衰减降低重要性
- 知识图谱状态: 节点和边的增删改
- 结构化存储状态: SQLite 表数据变更
- 无显式事务，但有并发安全锁保护

### 2.10 隐藏隐性规则

1. **记忆衰减**: 旧记忆重要性随时间指数衰减
2. **巩固触发**: 自动巩固在 remember() 调用时触发
3. **混合搜索权重**: 向量搜索 1.0，关键词 0.8，知识图谱 0.6
4. **索引同步**: 每次 remember() 都会更新索引
5. **资源释放**: close() 方法需显式调用，或通过 try-finally 确保

---

## 三、测试计划

### 3.1 静态代码核验
- 代码逻辑合理性检查
- 冗余代码排查
- 资源泄漏检查
- 书写隐患检查

### 3.2 单元全覆盖测试
- 所有 if/else 分支覆盖
- 循环边界测试
- 特殊场景测试

### 3.3 模块集成联调
- 跨模块调用验证
- 参数传递验证
- 状态同步验证

### 3.4 接口全量遍历
- 所有公共 API 测试
- 正常请求测试
- 异常入参测试
- 超限参数测试
- 空值测试
- 非法格式测试

### 3.5 业务场景闭环
- 正向场景
- 逆向场景
- 中断场景
- 重复操作场景

### 3.6 数据一致性校验
- 增删改查一致性
- 数据存储验证
- 关联关系验证
- 数据回显验证

### 3.7 异常容错测试
- 超时测试
- 断连模拟
- 报错测试
- 兜底降级测试
- 重试机制测试

### 3.8 基础性能核验
- 高频核心流程
- 响应稳定性
- 无卡顿/阻塞
- 无内存溢出

---

准备就绪，开始执行完整8步测试！
