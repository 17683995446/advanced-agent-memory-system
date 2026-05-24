# Agent Memory System - 完整测试前置分析文档

## 📋 一、代码分层与模块依赖分析

### 1.1 分层架构图

```
┌─────────────────────────────────────────────────────────┐
│  API层 (api/)                                           │
│  - fastapi_service_layer.py                             │
│  - fastapi_middleware_stack.py                         │
│  - command_line_interface.py                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  核心编排层 (core/)                                     │
│  - agent_memory_manager.py (主入口)                    │
│  - hybrid_search_engine.py                             │
│  - long_term_persistent_memory.py                      │
│  - short_term_working_memory.py                        │
│  - memory_compression_engine.py                        │
│  - memory_conflict_resolver.py                         │
│  - memory_version_control.py                           │
│  - memory_decay_engine.py                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  处理层 (processing/)                                   │
│  - text_embedding_provider.py                          │
│  - knowledge_graph_engine.py                           │
│  - chinese_english_tokenizer.py                        │
│  - simhash_deduplicator.py                             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  存储层 (storage/)                                      │
│  - vector_store/ (多种后端)                            │
│  - structured_sqlite_store.py                          │
│  - multi_level_memory_cache.py                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  基础设施层 (infra/)                                    │
│  - blinker_event_bus.py                                │
│  - distributed_lock_manager.py                         │
│  - circuit_breaker_pattern.py                          │
│  - api_rate_limiter.py                                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  可观测层 (observability/)                              │
│  - prometheus_metrics_collector.py                     │
│  - operation_audit_logger.py                           │
│  - service_health_checker.py                           │
└─────────────────────────────────────────────────────────┘
```

### 1.2 主要入口点

| 模块 | 文件 | 主要类/函数 |
|------|------|------------|
| 主入口 | memory_system/__init__.py | AgentMemory, AgentMemoryConfig |
| 核心管理器 | core/agent_memory_manager.py | AgentMemory |
| 长期记忆 | core/long_term_persistent_memory.py | LongTermMemory |
| 短期记忆 | core/short_term_working_memory.py | ShortTermMemory |
| 混合搜索 | core/hybrid_search_engine.py | HybridSearchEngine |

---

## 📊 二、参数规则与边界条件提取

### 2.1 AgentMemoryConfig 参数

| 参数 | 类型 | 边界条件 | 默认值 |
|------|------|---------|--------|
| short_term | dict | 任意字典 | working_memory_capacity=7, history_limit=50 |
| long_term | LongTermMemoryConfig | 必需配置 | - |
| knowledge_graph | dict | enabled=True/False | {"enabled": True} |
| structured_store | dict | db_path, enabled | {"db_path": ":memory:", "enabled": True} |
| consolidation_threshold | float | 0.0 - 1.0 | 0.6 |
| auto_consolidate | bool | True/False | True |
| default_top_k | int | >= 0 | 5 |

### 2.2 remember() 方法参数

| 参数 | 类型 | 验证规则 | 备注 |
|------|------|---------|------|
| content | str | 非空 | 必需 |
| memory_type | str | fact/semantic/episodic/procedural/conversation | 默认semantic |
| category | str | 任意字符串 | 默认general |
| importance | float | 0.0 <= x <= 1.0 | 默认0.5 |
| tags | List[str] | 可选 | - |
| metadata | Dict[str, Any] | JSON可序列化 | - |

### 2.3 recall() 方法参数

| 参数 | 类型 | 验证规则 | 备注 |
|------|------|---------|------|
| query | str | 可空 | 空查询返回空 |
| top_k | int | >= 0 | 默认default_top_k |
| from_short_term | bool | - | 默认True |
| from_long_term | bool | - | 默认True |
| use_hybrid | Optional[bool] | - | None=自动判断 |

### 2.4 异常捕获体系

| 异常类 | 来源 | 触发场景 |
|--------|------|---------|
| ValueError | remember() | content为空, importance越界 |
| ConfigurationError | 初始化 | 配置错误 |
| MemoryNotFoundError | get() | 记忆不存在 |
| VectorStoreError | 向量存储 | 存储操作失败 |
| KnowledgeGraphError | 知识图谱 | 图谱操作失败 |

---

## 🔄 三、数据流向与状态变更

### 3.1 数据流向图

```
用户输入
   ↓
AgentMemory.remember()
   ↓
├─→ 短期记忆 (add_to_working_memory)
│
├─→ 长期记忆 (LongTermMemory.remember)
│   ├─→ 生成嵌入 (EmbeddingProvider)
│   ├─→ 向量存储 (VectorStoreBackend)
│   ├─→ 关键词索引 (KeywordSearchStrategy)
│   └─→ 衰减引擎注册 (MemoryDecayEngine)
│
├─→ 知识图谱 (事实类型)
│
├─→ 结构化存储 (偏好/交互)
│
└─→ 版本控制记录 (MemoryVersionControl)

用户查询
   ↓
AgentMemory.recall()
   ↓
├─→ 混合搜索 (HybridSearchEngine)
│   ├─→ 向量搜索策略
│   ├─→ 关键词搜索策略
│   └─→ 知识图谱搜索策略
│
├─→ 短期记忆搜索
│
└─→ 结果排序与合并
```

---

## 🎯 四、核心方法调用链路

### 4.1 remember() 完整链路

```
AgentMemory.remember()
  ├─ _check_closed()
  ├─ 验证: content非空
  ├─ 验证: 0.0<=importance<=1.0
  ├─ 验证: metadata可JSON序列化
  │
  ├─ LongTermMemory.remember()
  │   ├─ 生成唯一ID
  │   ├─ 创建MemoryRecord
  │   ├─ 生成向量嵌入
  │   ├─ VectorStoreBackend.add()
  │   └─ 更新索引
  │
  ├─ KeywordSearchStrategy.add_document()
  │
  ├─ (可选) KnowledgeGraphBuilder.build_from_text()
  │
  ├─ (对话类型) remember_conversation()
  │
  ├─ MemoryDecayEngine.register()
  │
  ├─ MemoryVersionControl.record_change()
  │
  └─ 更新_metrics
```

### 4.2 recall() 完整链路

```
AgentMemory.recall()
  ├─ _check_closed()
  ├─ top_k验证
  ├─ 空查询检查 → 直接返回[]
  │
  ├─ (混合搜索激活) _recall_hybrid()
  │   ├─ HybridSearchEngine.search()
  │   │   ├─ VectorSearchStrategy.search()
  │   │   ├─ KeywordSearchStrategy.search()
  │   │   ├─ (可选) KnowledgeGraphSearchStrategy.search()
  │   │   └─ RRF融合排序
  │   ├─ 过滤与验证
  │   ├─ (可选) 短期记忆搜索
  │   └─ 返回最终结果
  │
  ├─ (传统搜索)
  │   ├─ LongTermMemory.recall()
  │   ├─ 过滤结果
  │   ├─ 短期记忆搜索
  │   └─ 返回最终结果
  │
  └─ 记录访问衰减
```

---

## 📝 五、隐藏隐性规则

1. **内存索引同步**: KeywordSearchStrategy在每次remember时自动更新，即使向量存储失败
2. **知识图谱条件**: 仅当memory_type="fact"时才触发知识图谱构建
3. **衰减引擎注册**: 所有记忆都会自动注册到衰减引擎
4. **混合搜索降级**: 混合搜索失败时自动降级到传统搜索
5. **版本控制**: 默认记录所有记忆变更
6. **top_k=0**: 返回空列表，不执行任何搜索
7. **空查询**: 返回空结果集
8. **关闭后的操作**: 调用_check_closed()检查，抛出ValueError

---

## ✅ 验收标准对照

| 标准 | 状态 | 验证方法 |
|------|------|---------|
| 代码所有逻辑分支100%可执行 | ⏳待测试 | 单元测试覆盖 |
| 运行行为与代码定义完全一致 | ⏳待测试 | 集成测试 |
| 数据流转无误 | ⏳待测试 | 数据一致性校验 |
| 异常场景可平稳兜底 | ⏳待测试 | 异常容错测试 |
| 无崩溃报错 | ⏳待测试 | 压力测试 |
