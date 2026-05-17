"""
Agent 记忆系统 v2.0 - 综合使用示例

展示所有模块协同工作的完整用法，使用 FakeEmbeddingProvider 实现零依赖演示。
无需安装 sentence-transformers、ChromaDB 或 FAISS 即可运行。

运行方式:
    python examples/basic_usage.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system import (
    AgentMemory, AgentMemoryConfig,
    LongTermMemoryConfig,
    EmbeddingFactory, FakeEmbeddingProvider,
    VectorStoreFactory, MemoryVectorStore, MemoryRecord,
    KnowledgeGraph, KnowledgeGraphBuilder, Entity, Relation,
    StructuredStore, MemoryTable,
    ShortTermMemory,
)


def separator(title: str = "") -> None:
    """打印分隔线"""
    print(f"\n{'=' * 70}")
    if title:
        print(f"  {title}")
        print(f"{'=' * 70}")


def sub(title: str) -> None:
    """打印子标题"""
    print(f"\n--- {title} ---")


# =========================================================================
# Demo 1: 全模块综合演示
# =========================================================================

def demo_all_modules() -> None:
    """综合演示：展示所有模块协同工作"""

    separator("Demo 1: 全模块综合演示 (AgentMemory)")

    # ------------------------------------------------------------------
    # 1.1 初始化
    # ------------------------------------------------------------------
    sub("1.1 初始化 AgentMemory (FakeEmbedding + MemoryVectorStore + KG + SQLite)")

    config = AgentMemoryConfig(
        short_term={"working_memory_capacity": 7, "history_limit": 50},
        long_term=LongTermMemoryConfig(
            embedding={"provider": "fake", "dimension": 64},
            vector_store={"backend": "memory"},
        ),
        knowledge_graph={"enabled": True},
        structured_store={"db_path": ":memory:", "enabled": True},
        consolidation_threshold=0.6,
        auto_consolidate=False,
        default_top_k=5,
    )

    memory = AgentMemory(config=config)
    print(f"  会话ID: {memory.session_id}")
    print(f"  嵌入维度: {memory.long_term.embedder.dimension}")
    print(f"  向量存储类型: {type(memory.long_term.store).__name__}")
    print("  初始化完成!")

    # ------------------------------------------------------------------
    # 1.2 短期记忆
    # ------------------------------------------------------------------
    sub("1.2 短期记忆 - 工作记忆与焦点管理")

    memory.add_to_working_memory("user_name", "用户的名字是张三", importance=0.9, memory_type="fact")
    memory.add_to_working_memory("current_task", "当前正在讨论项目进度", importance=0.8, memory_type="goal")
    memory.add_to_working_memory("preference", "用户喜欢简洁的回答", importance=0.7, memory_type="fact")
    print("  已添加 3 条工作记忆")

    # 焦点管理
    focus = memory.short_term.working_memory.get_focus()
    print(f"  当前焦点: {focus}")
    focus_content = memory.short_term.working_memory.get_focus_content()
    print(f"  焦点内容: {focus_content}")

    # 切换焦点
    memory.short_term.working_memory.set_focus("user_name")
    print(f"  切换焦点到 'user_name' 后: {memory.short_term.working_memory.get_focus()}")

    # 工作记忆上下文
    ctx = memory.short_term.working_memory.get_context_string()
    print(f"  工作记忆上下文:\n{ctx}")

    # ------------------------------------------------------------------
    # 1.3 长期记忆
    # ------------------------------------------------------------------
    sub("1.3 长期记忆 - remember / recall 语义搜索")

    id1 = memory.remember(
        "Python是一种解释型高级编程语言，广泛用于AI和数据科学",
        memory_type="semantic", category="knowledge", importance=0.9,
        tags=["编程", "Python", "AI"],
    )
    print(f"  记住 [语义记忆]: id={id1}")

    id2 = memory.remember(
        "项目Alpha的截止日期是2025年3月15日",
        memory_type="semantic", category="work", importance=0.85,
        tags=["项目", "截止日期"],
    )
    print(f"  记住 [工作记忆]: id={id2}")

    id3 = memory.remember(
        "昨天和张三讨论了系统架构设计方案",
        memory_type="episodic", category="meetings", importance=0.7,
        tags=["会议", "架构"],
    )
    print(f"  记住 [情景记忆]: id={id3}")

    # 语义搜索
    results = memory.recall("Python编程语言", top_k=3)
    print(f"\n  语义搜索 'Python编程语言' (top 3):")
    for i, r in enumerate(results, 1):
        print(f"    {i}. [score={r['score']:.4f}] [{r['source']}] {r['content'][:60]}")

    # 按类别过滤
    results_cat = memory.recall("项目", top_k=3, category="work")
    print(f"\n  按类别过滤 (category='work'), 搜索 '项目':")
    for i, r in enumerate(results_cat, 1):
        print(f"    {i}. [score={r['score']:.4f}] {r['content'][:60]}")

    # ------------------------------------------------------------------
    # 1.4 知识图谱
    # ------------------------------------------------------------------
    sub("1.4 知识图谱 - 实体/关系/搜索/路径/文本构建")

    # 添加实体
    memory.add_entity("张三", entity_type="person", description="软件工程师，负责后端开发")
    memory.add_entity("Python", entity_type="technology", description="编程语言")
    memory.add_entity("项目Alpha", entity_type="project", description="公司核心产品")
    memory.add_entity("AI部门", entity_type="organization", description="人工智能研发部门")
    print("  已添加 4 个实体")

    # 添加关系
    memory.add_relation("张三", "AI部门", "works_in", weight=1.0)
    memory.add_relation("张三", "项目Alpha", "leads", weight=0.9)
    memory.add_relation("张三", "Python", "uses", weight=0.8)
    memory.add_relation("项目Alpha", "AI部门", "belongs_to", weight=1.0)
    print("  已添加 4 条关系")

    # 搜索实体
    entities = memory.search_entities("张三", top_k=3)
    print(f"\n  搜索实体 '张三':")
    for entity, score in entities:
        print(f"    [{entity.entity_type}] {entity.name}: {entity.description} (score={score:.2f})")

    # 查找路径
    path = memory.knowledge_graph.find_path("Python", "AI部门")
    print(f"\n  Python -> AI部门 最短路径: {path}")

    # 从文本构建知识图谱
    text = "张三是一名软件工程师。张三属于AI部门。AI部门包含项目Alpha。张三使用Python。"
    memory.build_knowledge_from_text(text)
    kg_stats = memory.get_knowledge_graph_stats()
    print(f"\n  从文本构建后图谱统计: 实体={kg_stats['entity_count']}, 关系={kg_stats['relation_count']}")

    # ------------------------------------------------------------------
    # 1.5 结构化存储
    # ------------------------------------------------------------------
    sub("1.5 结构化存储 - 偏好/交互日志/事实")

    # 偏好
    memory.store_preference("language", "zh-CN", category="locale")
    memory.store_preference("theme", "dark", category="ui")
    memory.store_preference("response_style", "concise", category="communication")
    print("  已存储 3 条偏好")

    pref = memory.get_preference("theme")
    print(f"  获取偏好 'theme': {pref}")

    # 交互日志
    log_id = memory.log_interaction(role="user", content="请帮我查一下项目进度", topic="project")
    print(f"  记录交互日志: id={log_id}")

    # 事实
    memory.remember_fact("张三有5年Python开发经验", category="personal", source="conversation", confidence=0.95)
    memory.remember_fact("项目Alpha使用微服务架构", category="technical", source="document", confidence=0.9)
    print("  已存储 2 条事实")

    facts = memory.memory_table.get_facts(limit=5)
    print(f"  获取所有事实 ({len(facts)} 条):")
    for f in facts:
        print(f"    - [{f.get('category', '?')}] {f['fact']} (confidence={f['confidence']})")

    # ------------------------------------------------------------------
    # 1.6 对话管理
    # ------------------------------------------------------------------
    sub("1.6 对话管理 - 记住对话/获取历史")

    memory.remember_conversation("你好，我是张三", speaker="user", important=True)
    memory.remember_conversation("你好张三！有什么可以帮你的？", speaker="assistant")
    memory.remember_conversation("我想了解一下项目Alpha的进度", speaker="user", important=True)
    memory.remember_conversation("项目Alpha目前进展顺利，预计按时交付。", speaker="assistant")
    print("  已记录 4 轮对话")

    history = memory.get_conversation_history(n=4)
    print(f"\n  最近 {len(history)} 条对话历史:")
    for h in history:
        role = h.get("role", "?")
        content = h.get("content", "")
        print(f"    {role}: {content}")

    # ------------------------------------------------------------------
    # 1.7 上下文获取 (用于 LLM 提示)
    # ------------------------------------------------------------------
    sub("1.7 上下文获取 - get_relevant_context (模拟 LLM Prompt)")

    context = memory.get_relevant_context("项目Alpha的进度如何？", max_items=5)
    print("  查询: '项目Alpha的进度如何？'")
    print(f"  获取的上下文:\n{context}")

    # ------------------------------------------------------------------
    # 1.8 记忆巩固
    # ------------------------------------------------------------------
    sub("1.8 记忆巩固 - force_consolidate")

    # 先添加一些高重要性的工作记忆
    memory.add_to_working_memory("important1", "系统架构需要重构", importance=0.8, memory_type="goal")
    memory.add_to_working_memory("important2", "客户要求增加新功能", importance=0.9, memory_type="event")
    memory.add_to_working_memory("trivial", "今天天气不错", importance=0.2, memory_type="general")

    stats_before = memory.get_stats()
    print(f"  巩固前 - 工作记忆: {stats_before['short_term']['working_memory_size']}, "
          f"长期记忆: {stats_before['long_term']['total_memories']}")

    result = memory.force_consolidate()
    print(f"  巩固结果: {result}")

    stats_after = memory.get_stats()
    print(f"  巩固后 - 工作记忆: {stats_after['short_term']['working_memory_size']}, "
          f"长期记忆: {stats_after['long_term']['total_memories']}")

    # ------------------------------------------------------------------
    # 1.9 统计信息
    # ------------------------------------------------------------------
    sub("1.9 系统统计 - get_stats")

    stats = memory.get_stats()
    print(f"  会话信息:")
    print(f"    session_id: {stats['session']['session_id']}")
    print(f"    interaction_count: {stats['session']['interaction_count']}")
    print(f"  短期记忆:")
    print(f"    working_memory_size: {stats['short_term']['working_memory_size']}")
    print(f"    history_size: {stats['short_term']['history_size']}")
    print(f"  长期记忆:")
    print(f"    total_memories: {stats['long_term']['total_memories']}")
    print(f"  知识图谱:")
    if "knowledge_graph" in stats:
        kg = stats["knowledge_graph"]
        print(f"    entity_count: {kg['entity_count']}")
        print(f"    relation_count: {kg['relation_count']}")
    print(f"  结构化存储:")
    if "structured_store" in stats:
        print(f"    tables: {stats['structured_store']['tables']}")

    print("\n  Demo 1 完成!")


# =========================================================================
# Demo 2: 可插拔后端演示
# =========================================================================

def demo_pluggable_backends() -> None:
    """演示在不同向量存储后端之间切换"""

    separator("Demo 2: 可插拔后端演示")

    # ------------------------------------------------------------------
    # 2.1 创建三个使用不同后端的 AgentMemory 实例
    # ------------------------------------------------------------------
    sub("2.1 创建 3 个 AgentMemory 实例 (Memory / ChromaDB / FAISS)")

    instances = {}
    labels = ["MemoryVectorStore (内存)", "ChromaDB", "FAISS"]
    configs = [
        AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "dimension": 64},
                vector_store={"backend": "memory"},
            ),
            knowledge_graph={"enabled": False},
            structured_store={"enabled": False},
        ),
        AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "dimension": 64},
                vector_store={"backend": "chroma"},
            ),
            knowledge_graph={"enabled": False},
            structured_store={"enabled": False},
        ),
        AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "fake", "dimension": 64},
                vector_store={"backend": "faiss", "dimension": 64},
            ),
            knowledge_graph={"enabled": False},
            structured_store={"enabled": False},
        ),
    ]

    for label, cfg in zip(labels, configs):
        try:
            mem = AgentMemory(config=cfg)
            backend_name = type(mem.long_term.store).__name__
            instances[label] = mem
            print(f"  [OK] {label} -> {backend_name}")
        except ImportError as e:
            print(f"  [SKIP] {label} -> {e}")
        except Exception as e:
            print(f"  [ERROR] {label} -> {e}")

    if not instances:
        print("  没有可用的后端实例，跳过后续演示。")
        return

    # ------------------------------------------------------------------
    # 2.2 向每个实例添加相同数据
    # ------------------------------------------------------------------
    sub("2.2 向每个实例添加相同数据")

    test_memories = [
        ("机器学习是人工智能的一个分支", "semantic", "knowledge", 0.9),
        ("深度学习使用神经网络处理数据", "semantic", "knowledge", 0.85),
        ("自然语言处理让计算机理解人类语言", "semantic", "knowledge", 0.8),
        ("上周团队完成了模型训练任务", "episodic", "work", 0.7),
    ]

    for label, mem in instances.items():
        print(f"\n  [{label}]")
        for content, mtype, cat, imp in test_memories:
            mid = mem.remember(content, memory_type=mtype, category=cat, importance=imp)
            print(f"    + {content[:30]}... (id={mid})")

    # ------------------------------------------------------------------
    # 2.3 搜索并比较结果
    # ------------------------------------------------------------------
    sub("2.3 搜索并比较结果")

    query = "人工智能和机器学习"
    print(f"  查询: '{query}'\n")

    for label, mem in instances.items():
        results = mem.recall(query, top_k=3)
        print(f"  [{label}] 找到 {len(results)} 条结果:")
        for i, r in enumerate(results, 1):
            print(f"    {i}. [score={r['score']:.4f}] {r['content'][:50]}")
        print()

    # ------------------------------------------------------------------
    # 2.4 统计对比
    # ------------------------------------------------------------------
    sub("2.4 各后端统计对比")

    for label, mem in instances.items():
        stats = mem.get_stats()
        total = stats["long_term"]["total_memories"]
        backend = type(mem.long_term.store).__name__
        print(f"  {label}: {total} 条记忆 (backend={backend})")

    print("\n  Demo 2 完成!")


# =========================================================================
# Demo 3: 独立模块演示
# =========================================================================

def demo_standalone_modules() -> None:
    """演示每个模块可以独立使用"""

    separator("Demo 3: 独立模块演示")

    # ------------------------------------------------------------------
    # 3.1 独立使用 Embedding
    # ------------------------------------------------------------------
    sub("3.1 独立嵌入模块 - EmbeddingFactory + FakeEmbeddingProvider")

    embedder = EmbeddingFactory.create("fake", dimension=64)
    print(f"  嵌入提供者: {type(embedder).__name__}")
    print(f"  向量维度: {embedder.dimension}")

    vec1 = embedder.encode("你好世界")
    vec2 = embedder.encode("Hello World")
    vec3 = embedder.encode("机器学习算法")

    print(f"  '你好世界' 向量前5维: {vec1[:5]}")
    print(f"  'Hello World' 向量前5维: {vec2[:5]}")

    sim_12 = FakeEmbeddingProvider.similarity(vec1, vec2)
    sim_13 = FakeEmbeddingProvider.similarity(vec1, vec3)
    print(f"  相似度('你好世界', 'Hello World'): {sim_12:.4f}")
    print(f"  相似度('你好世界', '机器学习算法'): {sim_13:.4f}")

    # 批量编码
    batch_vecs = embedder.encode_batch(["苹果", "香蕉", "橘子"])
    print(f"  批量编码 3 条文本, 每条维度: {len(batch_vecs[0])}")

    # ------------------------------------------------------------------
    # 3.2 独立使用 VectorStore
    # ------------------------------------------------------------------
    sub("3.2 独立向量存储 - MemoryVectorStore")

    store = MemoryVectorStore()
    print(f"  存储类型: {type(store).__name__}")

    # 添加记录
    records = [
        MemoryRecord(id="r1", content="Python编程语言", embedding=embedder.encode("Python编程语言"), category="tech"),
        MemoryRecord(id="r2", content="Java企业开发", embedding=embedder.encode("Java企业开发"), category="tech"),
        MemoryRecord(id="r3", content="机器学习入门", embedding=embedder.encode("机器学习入门"), category="ai"),
    ]
    for r in records:
        store.add(r)
    print(f"  已添加 {len(records)} 条记录, 总数: {store.count()}")

    # 搜索
    query_vec = embedder.encode("编程语言")
    results = store.search(query_vec, top_k=3)
    print(f"  搜索 '编程语言':")
    for sr in results:
        print(f"    [score={sr.score:.4f}] {sr.record.content} (category={sr.record.category})")

    # 带过滤搜索
    results_filtered = store.search(query_vec, top_k=3, filter={"category": "ai"})
    print(f"  搜索 '编程语言' (filter category=ai):")
    for sr in results_filtered:
        print(f"    [score={sr.score:.4f}] {sr.record.content}")

    # 获取和更新
    rec = store.get("r1")
    print(f"  获取 r1: {rec.content}")
    store.update("r1", importance=0.9)
    print(f"  更新 r1 importance=0.9: {store.get('r1').importance}")

    # ------------------------------------------------------------------
    # 3.3 独立使用 KnowledgeGraph
    # ------------------------------------------------------------------
    sub("3.3 独立知识图谱 - KnowledgeGraph + KnowledgeGraphBuilder")

    kg = KnowledgeGraph()

    # 手动添加
    kg.add_entity(Entity(name="Alice", entity_type="person", description="数据科学家"))
    kg.add_entity(Entity(name="Bob", entity_type="person", description="软件工程师"))
    kg.add_entity(Entity(name="ML项目", entity_type="project", description="机器学习平台"))
    kg.add_relation(Relation(source="Alice", target="ML项目", relation_type="works_on", weight=0.9))
    kg.add_relation(Relation(source="Bob", target="ML项目", relation_type="works_on", weight=0.8))
    kg.add_relation(Relation(source="Alice", target="Bob", relation_type="collaborates_with", weight=0.7))
    print(f"  手动构建图谱: {kg.entity_count()} 实体, {kg.relation_count()} 关系")

    # 搜索
    ents = kg.search_entities("Alice", top_k=3)
    print(f"  搜索 'Alice':")
    for e, s in ents:
        print(f"    [{e.entity_type}] {e.name}: {e.description} (score={s:.2f})")

    # 路径查找
    path = kg.find_path("Bob", "Alice")
    print(f"  Bob -> Alice 路径: {path}")

    # 从文本构建
    text = "Alice是数据科学家。Bob是软件工程师。Alice负责ML项目。Bob参与ML项目。Alice和Bob合作。"
    kg2 = KnowledgeGraphBuilder.build_from_text(text)
    print(f"  从文本构建图谱: {kg2.entity_count()} 实体, {kg2.relation_count()} 关系")

    # 统计
    stats = kg.get_statistics()
    print(f"  图谱统计: density={stats['density']}, connected={stats['is_connected']}")

    # ------------------------------------------------------------------
    # 3.4 独立使用 StructuredStore
    # ------------------------------------------------------------------
    sub("3.4 独立结构化存储 - StructuredStore + MemoryTable")

    ss = StructuredStore(db_path=":memory:")
    mt = MemoryTable(ss)
    mt.init_tables()
    print(f"  初始化 MemoryTable, 表列表: {ss.list_tables()}")

    # 存储偏好
    mt.store_preference("timezone", "Asia/Shanghai", category="locale")
    mt.store_preference("notification", "enabled", category="settings")
    pref = mt.get_preference("timezone")
    print(f"  存储偏好 timezone=Asia/Shanghai: {pref}")

    # 记录交互
    iid = mt.log_interaction("agent-001", "user", "你好，请问今天天气如何？")
    print(f"  记录交互: id={iid}")

    # 存储事实
    mt.store_fact("用户时区为Asia/Shanghai", source="conversation", confidence=0.95, category="user_info")
    mt.store_fact("用户开启了通知", source="system", confidence=1.0, category="settings")
    facts = mt.get_facts(limit=10)
    print(f"  获取事实 ({len(facts)} 条):")
    for f in facts:
        print(f"    - {f['fact']} (confidence={f['confidence']})")

    # 原始 SQL 查询
    result = ss.select("preferences", where="category = ?", params=("locale",))
    print(f"  SQL查询 preferences (category=locale): {result.records}")

    # ------------------------------------------------------------------
    # 3.5 独立使用 ShortTermMemory
    # ------------------------------------------------------------------
    sub("3.5 独立短期记忆 - ShortTermMemory")

    stm = ShortTermMemory(working_memory_capacity=5, history_limit=20)
    print(f"  初始化 ShortTermMemory (capacity=5)")

    stm.add_to_working_memory("task", "完成代码审查", importance=0.8, memory_type="goal")
    stm.add_to_working_memory("info", "会议下午3点开始", importance=0.7, memory_type="event")
    stm.add_to_working_memory("note", "记得提交周报", importance=0.6, memory_type="goal")
    print(f"  添加 3 条工作记忆, 当前容量: {len(stm.working_memory)}")

    # 焦点
    print(f"  当前焦点: {stm.working_memory.get_focus()}")
    stm.working_memory.set_focus("info")
    print(f"  切换焦点到 'info': {stm.working_memory.get_focus()}")

    # 交互历史
    stm.add_interaction("user", "你好")
    stm.add_interaction("assistant", "你好！有什么可以帮你的？")
    stm.add_interaction("user", "今天有什么待办事项？", important=True)
    history = stm.get_recent_history(3)
    print(f"  最近 3 条交互:")
    for h in history:
        print(f"    {h['role']}: {h['content']}")

    # 会话上下文
    stm.set_session_context("user_id", "user_001")
    stm.set_session_context("topic", "task_management")
    ctx = stm.get_session_context("topic")
    print(f"  会话上下文 topic={ctx}")

    # 完整快照
    snapshot = stm.get_full_context()
    print(f"  完整快照 keys: {list(snapshot.keys())}")

    print("\n  Demo 3 完成!")


# =========================================================================
# Demo 4: Sentence Transformers 真实嵌入演示
# =========================================================================

def demo_sentence_transformers() -> None:
    """演示真实嵌入模型的使用 (需要安装 sentence-transformers)"""

    separator("Demo 4: Sentence Transformers 真实嵌入演示")

    try:
        from memory_system import SentenceTransformerProvider

        sub("4.1 创建 SentenceTransformerProvider")

        provider = SentenceTransformerProvider(
            model_name="all-MiniLM-L6-v2",
            device="cpu",
            normalize_embeddings=True,
        )
        print(f"  模型: all-MiniLM-L6-v2")
        print(f"  维度: {provider.dimension}")
        print(f"  设备: cpu")

        # 编码
        sub("4.2 真实语义搜索")

        texts = [
            "Python是一种流行的编程语言",
            "机器学习是人工智能的子领域",
            "今天天气非常好，适合出门散步",
            "深度学习模型需要大量训练数据",
            "我喜欢用Python做数据分析",
        ]

        query = "编程语言和数据分析"
        query_vec = provider.encode(query)
        text_vecs = provider.encode_batch(texts)

        print(f"  查询: '{query}'")
        print(f"  计算与 {len(texts)} 条文本的相似度:\n")

        similarities = []
        for text, vec in zip(texts, text_vecs):
            sim = EmbeddingProvider.similarity(query_vec, vec)
            similarities.append((text, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        for i, (text, sim) in enumerate(similarities, 1):
            print(f"    {i}. [score={sim:.4f}] {text}")

        # 用真实嵌入创建 AgentMemory
        sub("4.3 使用真实嵌入创建 AgentMemory")

        config = AgentMemoryConfig(
            long_term=LongTermMemoryConfig(
                embedding={"provider": "sentence-transformer", "model_name": "all-MiniLM-L6-v2"},
                vector_store={"backend": "memory"},
            ),
            knowledge_graph={"enabled": False},
            structured_store={"enabled": False},
        )
        real_memory = AgentMemory(config=config)
        print(f"  嵌入类型: {type(real_memory.long_term.embedder).__name__}")

        for text in texts:
            real_memory.remember(text, memory_type="semantic", category="demo", importance=0.7)

        results = real_memory.recall("数据分析工具", top_k=3)
        print(f"  搜索 '数据分析工具':")
        for i, r in enumerate(results, 1):
            print(f"    {i}. [score={r['score']:.4f}] {r['content']}")

        print("\n  Demo 4 完成! (使用真实 sentence-transformers 嵌入)")

    except ImportError:
        print("  [INFO] sentence-transformers 未安装，跳过真实嵌入演示。")
        print("  安装方式: pip install sentence-transformers")
        print("  安装后重新运行即可看到真实语义搜索效果。")
        print("\n  Demo 4 跳过。")
    except Exception as e:
        print(f"  [INFO] sentence-transformers 已安装但模型加载失败: {e}")
        print("  这通常是因为模型尚未下载或网络不可用。")
        print("  请在有网络连接的环境下首次运行以自动下载模型。")
        print("  下载后模型会被缓存，之后离线也可使用。")
        print("\n  Demo 4 跳过。")


# =========================================================================
# 主入口
# =========================================================================

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║       Agent 记忆系统 v2.0 - 综合使用示例                        ║")
    print("║       使用 FakeEmbeddingProvider，零外部依赖即可运行             ║")
    print("╚════════════════════════════════════════════════════════════════════╝")

    t0 = time.time()

    demo_all_modules()
    demo_pluggable_backends()
    demo_standalone_modules()
    demo_sentence_transformers()

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"  所有演示完成! 总耗时: {elapsed:.2f}s")
    print(f"{'=' * 70}")
