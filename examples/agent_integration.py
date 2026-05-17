"""
Agent 集成示例 - v2.0 记忆系统

展示如何将 v2.0 记忆系统集成到真实的 AI Agent 中。
包含多轮对话演示和记忆持久化演示。
"""

import sys
import os
import re
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system import (
    AgentMemory,
    AgentMemoryConfig,
    LongTermMemoryConfig,
)


class SmartAgent:
    """
    智能Agent - 集成 v2.0 记忆系统

    演示如何在实际 AI Agent 中使用记忆系统的完整功能：
    - 短期工作记忆（上下文缓存）
    - 长期向量记忆（语义检索）
    - 知识图谱（实体关系）
    - 结构化存储（SQLite 持久化）
    - 记忆巩固（短期 -> 长期自动迁移）
    """

    def __init__(self, name: str = "SmartAgent"):
        """
        初始化 SmartAgent，创建完整的记忆系统。

        使用 FakeEmbedding（无需模型依赖）+ 内存向量存储 + 知识图谱 + SQLite。
        """
        self.name = name

        # 构建记忆系统配置
        config = AgentMemoryConfig(
            short_term={
                "working_memory_capacity": 7,
                "history_limit": 50,
            },
            long_term=LongTermMemoryConfig(
                embedding={
                    "provider": "fake",
                    "fake_dimension": 128,
                },
                vector_store={
                    "backend": "memory",
                },
            ),
            knowledge_graph={"enabled": True},
            structured_store={
                "db_path": ":memory:",
                "enabled": True,
            },
            consolidation_threshold=0.6,
            auto_consolidate=True,
            default_top_k=5,
        )

        self.memory = AgentMemory(config=config)

        # 系统提示词模板
        self.system_prompt = (
            f"你是 {self.name}，一个有帮助的AI助手。\n"
            f"你会利用记忆系统中的上下文来回答用户的问题。\n"
            f"请用中文回答，保持友好、专业的态度。"
        )

    def chat(self, user_message: str) -> str:
        """
        处理一轮对话。

        流程：
        1. 通过 remember_conversation 记录用户消息
        2. 通过 get_relevant_context 获取相关记忆上下文
        3. 构建包含系统指令 + 记忆上下文 + 用户消息的提示词
        4. 生成模拟回复（基于规则，无实际 LLM 调用）
        5. 通过 remember_conversation 记录助手回复
        6. 返回回复

        Args:
            user_message: 用户输入的消息

        Returns:
            助手的回复文本
        """
        # 1. 记录用户消息（标记重要性）
        is_important = self._is_important(user_message)
        self.memory.remember_conversation(
            content=user_message,
            speaker="user",
            important=is_important,
        )

        # 2. 获取相关记忆上下文
        context = self.memory.get_relevant_context(
            query=user_message,
            max_items=5,
        )

        # 3. 构建提示词
        prompt = self._build_prompt(user_message, context)

        # 4. 生成模拟回复
        response = self._simulate_llm(prompt, user_message)

        # 5. 记录助手回复
        self.memory.remember_conversation(
            content=response,
            speaker="assistant",
            important=False,
        )

        # 6. 执行记忆巩固（将重要短期记忆迁移到长期记忆）
        self.memory.consolidate(auto=True)

        return response

    def _is_important(self, message: str) -> bool:
        """
        启发式判断消息是否重要。

        重要性判断规则：
        - 包含自我介绍关键词（名字、叫、是...身份）
        - 包含偏好表达（喜欢、讨厌、爱好）
        - 包含显式记忆请求（记住、别忘了、重要）
        - 包含事实性陈述（由...创建、发明于、成立于）
        - 包含个人信息（电话、地址、邮箱）

        Args:
            message: 待判断的消息文本

        Returns:
            是否标记为重要
        """
        important_patterns = [
            # 自我介绍（排除疑问句）
            r"(?:我叫|我的名字是)(?!什么|谁)",
            r"我是.*?(?:工程师|医生|老师|学生|经理)",
            # 偏好表达
            r"我喜欢|我讨厌|我爱好|我擅长|我常用",
            # 显式记忆请求
            r"记住|别忘了|请记住|重要|关键",
            # 事实性陈述
            r"由.*?创建|发明于|成立于|诞生于",
            # 个人信息
            r"电话|地址|邮箱|生日",
        ]
        for pattern in important_patterns:
            if re.search(pattern, message):
                return True
        return False

    def _build_prompt(self, user_message: str, context: str) -> str:
        """
        构建完整的提示词。

        将系统指令、记忆上下文和用户消息组合成完整的提示词。

        Args:
            user_message: 用户消息
            context: 记忆系统提供的上下文

        Returns:
            完整的提示词文本
        """
        parts = [
            f"【系统指令】\n{self.system_prompt}",
        ]
        if context:
            parts.append(f"【记忆上下文】\n{context}")
        else:
            parts.append("【记忆上下文】\n（无相关记忆）")
        parts.append(f"【用户消息】\n{user_message}")
        return "\n\n".join(parts)

    def _simulate_llm(self, prompt: str, user_message: str) -> str:
        """
        模拟 LLM 响应（基于规则，无实际 LLM 调用）。

        响应策略：
        1. 如果用户分享个人信息，提取并记住为事实，同时更新知识图谱
        2. 如果用户询问已记住的信息，从记忆中检索并回答
        3. 如果用户询问实体相关信息，搜索知识图谱
        4. 如果用户要求记住某事，显式存储并确认
        5. 否则返回通用回复

        Args:
            prompt: 完整提示词（包含上下文）
            user_message: 原始用户消息

        Returns:
            模拟的回复文本
        """
        # --- 策略1：用户分享个人信息（自我介绍、偏好等）---
        # 排除疑问句（如 "你还记得我叫什么名字吗？"）
        is_question = bool(re.search(r"[？?]|什么|谁|吗|呢", user_message))

        if not is_question:
            # 提取名字
            name_match = re.search(r"我叫(\S+?)[，,。.！! ]", user_message)
            if not name_match:
                name_match = re.search(r"我叫(\S+)", user_message)

            if name_match:
                user_name = name_match.group(1)
                # 提取职业（避免重复匹配 "是" 和 "一名"）
                job_match = re.search(r"一名(.+)", user_message)
                if not job_match:
                    job_match = re.search(r"是(.+)", user_message)
                job = job_match.group(1).strip() if job_match else ""

                # 记住为事实
                fact_content = f"用户名字叫{user_name}"
                if job:
                    fact_content += f"，{job}"
                self.memory.remember_fact(
                    fact=fact_content,
                    category="personal",
                    source="user",
                    confidence=0.95,
                )

                # 添加到知识图谱
                self.memory.add_entity(
                    name=user_name,
                    entity_type="person",
                    description=f"用户，{job}" if job else "用户",
                )

                # 提取并记录偏好
                pref_match = re.search(r"喜欢(.*?)[。.！! ]", user_message)
                if pref_match:
                    preference = pref_match.group(1)
                    self.memory.remember_fact(
                        fact=f"{user_name}喜欢{preference}",
                        category="preference",
                        source="user",
                        confidence=0.9,
                    )
                    # 添加实体和关系到知识图谱
                    self.memory.add_entity(
                        name=preference,
                        entity_type="interest",
                        description=f"{user_name}的兴趣",
                    )
                    self.memory.add_relation(
                        source=user_name,
                        target=preference,
                        relation_type="likes",
                        weight=0.9,
                    )

                response = f"你好{user_name}！很高兴认识你。"
                if job:
                    response += f"知道你是一名{job}，很棒！"
                response += "我会记住你的信息的。有什么我可以帮助你的吗？"
                return response

            # 检测偏好分享（非自我介绍的情况）
            # 匹配 "我喜欢XXX" 后面可能跟任何字符或直接结束
            pref_match = re.search(r"我喜欢(.*?)(?:[。.！!？? ]|$)", user_message)
            if pref_match:
                preference = pref_match.group(1).strip()
                if not preference:
                    # 尝试更宽松的匹配
                    pref_match2 = re.search(r"我喜欢(\S+)", user_message)
                    if pref_match2:
                        preference = pref_match2.group(1)
                if preference:
                    # 尝试从记忆中找到用户名
                    name_results = self.memory.recall("用户名字叫", top_k=3)
                    user_name = "你"
                    for r in name_results:
                        name_m = re.search(r"用户名字叫(\S+?)[，,。]", r["content"])
                        if name_m:
                            user_name = name_m.group(1)
                            break

                    self.memory.remember_fact(
                        fact=f"{user_name}喜欢{preference}",
                        category="preference",
                        source="user",
                        confidence=0.9,
                    )
                    self.memory.add_entity(
                        name=preference,
                        entity_type="interest",
                        description=f"{user_name}的兴趣",
                    )
                    self.memory.add_relation(
                        source=user_name,
                        target=preference,
                        relation_type="likes",
                        weight=0.9,
                    )
                    return f"好的，我记住了{user_name}喜欢{preference}。这会帮助我更好地为你服务！"

        # --- 策略2：用户要求记住某事 ---
        remember_match = re.search(r"帮我记住[：:](.*)", user_message)
        if remember_match:
            fact_text = remember_match.group(1).strip()
            self.memory.remember_fact(
                fact=fact_text,
                category="knowledge",
                source="user",
                confidence=0.95,
            )
            # 尝试从文本中提取实体和关系，构建知识图谱
            self.memory.build_knowledge_from_text(fact_text)
            return f"好的，我已经记住了：{fact_text}。以后你可以随时问我关于这件事的信息。"

        # --- 策略3：用户询问已记住的信息 ---
        if re.search(r"记得|记得吗|记得我|我叫什么|我的名字", user_message):
            # 从记忆中检索用户名（使用更精确的查询）
            name_results = self.memory.recall("用户名字叫", top_k=10)
            for r in name_results:
                content = r["content"]
                # 只匹配实际存储的事实（以"用户名字叫"开头），排除对话记录
                if content.startswith("用户名字叫"):
                    name_m = re.search(r"用户名字叫(\S+?)[，,。]", content)
                    if name_m:
                        user_name = name_m.group(1)
                        # 获取更多关于该用户的信息
                        user_info_results = self.memory.recall(user_name, top_k=5)
                        extra_info = ""
                        for info in user_info_results:
                            if "喜欢" in info["content"] and user_name in info["content"]:
                                extra_info = f" 我还知道{info['content']}。"
                                break
                        return f"当然记得！你叫{user_name}。{extra_info}有什么我可以帮你的吗？"

            # 备选：从结构化存储中查找事实
            try:
                facts = self.memory.memory_table.get_facts(limit=20)
                for fact in facts:
                    content = fact.get("fact", "") if isinstance(fact, dict) else str(fact)
                    if "名字叫" in content or "叫" in content:
                        name_m = re.search(r"名字叫(\S+?)[，,。]", content)
                        if name_m:
                            user_name = name_m.group(1)
                            return f"当然记得！你叫{user_name}。有什么我可以帮你的吗？"
            except Exception:
                pass

            return "抱歉，我暂时没有找到关于你名字的记忆。能再告诉我一次吗？"

        # --- 策略4：用户询问实体/事实信息 ---
        if re.search(r"创始人|创建|发明|是谁|什么关系", user_message):
            # 先从长期记忆检索（优先查找语义记忆/事实）
            recall_results = self.memory.recall(user_message, top_k=5)
            # 过滤：优先选择语义记忆和事实类别，排除对话记录和用户个人信息
            fact_results = [
                r for r in recall_results
                if r.get("memory_type") == "semantic"
                and r.get("category") in ("knowledge",)
            ]
            best_results = fact_results if fact_results else recall_results
            if best_results:
                best = best_results[0]
                return f"根据我的记忆：{best['content']}（相关度：{best['score']:.2f}）"

            # 备选：从结构化存储中查找知识类事实
            try:
                facts = self.memory.memory_table.get_facts(category="knowledge", limit=10)
                for fact in facts:
                    content = fact.get("fact", "") if isinstance(fact, dict) else str(fact)
                    # 简单关键词匹配
                    query_terms = set(user_message)
                    if len(query_terms & set(content)) > 2:
                        return f"根据我的记忆：{content}"
            except Exception:
                pass

            # 再从知识图谱搜索
            try:
                # 提取查询中的关键实体名
                entity_results = self.memory.search_entities(user_message, top_k=5)
                if entity_results:
                    entity_name = entity_results[0][0].name
                    entity_desc = entity_results[0][0].description
                    # 查找相关实体
                    related = self.memory.find_related(entity_name, top_k=5)
                    if related:
                        relation_info = []
                        for rel_result in related:
                            for rel in rel_result.relations:
                                relation_info.append(
                                    f"{rel.source} --[{rel.relation_type}]--> {rel.target}"
                                )
                        return (
                            f"关于「{entity_name}」{entity_desc}，"
                            f"我找到了以下关系：{'；'.join(relation_info)}"
                        )
                    return f"我在知识图谱中找到了「{entity_name}」{entity_desc}，但暂无更多关联信息。"
            except Exception:
                pass

            return "抱歉，我在记忆中没有找到相关的信息。你能告诉我更多吗？"

        # --- 策略5：用户询问两个实体之间的关系 ---
        relation_match = re.search(r"(\S+?)和(\S+?)有什么关系", user_message)
        if relation_match:
            entity_a = relation_match.group(1)
            entity_b = relation_match.group(2)

            # 查找实体A的相关实体
            try:
                related_a = self.memory.find_related(entity_a, top_k=10)
                for rel_result in related_a:
                    for rel in rel_result.relations:
                        # 检查是否与实体B有关
                        if entity_b in (rel.source, rel.target):
                            return (
                                f"根据我的知识图谱，{rel.source} "
                                f"与 {rel.target} 之间存在 "
                                f"「{rel.relation_type}」的关系。"
                            )
            except Exception:
                pass

            # 尝试从长期记忆中查找
            recall_results = self.memory.recall(
                f"{entity_a} {entity_b}", top_k=5
            )
            if recall_results:
                return f"根据我的记忆：{recall_results[0]['content']}"

            # 检查两个实体是否都存在于知识图谱中
            try:
                ent_a = self.memory.get_entity(entity_a)
                ent_b = self.memory.get_entity(entity_b)
                if ent_a and ent_b:
                    return (
                        f"我在知识图谱中找到了「{entity_a}」和「{entity_b}」两个实体，"
                        f"但它们之间暂无直接关系。"
                    )
                elif ent_a:
                    return f"我找到了「{entity_a}」，但没有找到「{entity_b}」。"
                elif ent_b:
                    return f"我找到了「{entity_b}」，但没有找到「{entity_a}」。"
            except Exception:
                pass

            return f"抱歉，我没有找到「{entity_a}」和「{entity_b}」之间的关系信息。"

        # --- 策略6：通用回复 ---
        recall_results = self.memory.recall(user_message, top_k=3)
        if recall_results:
            best = recall_results[0]
            return (
                f"关于你说的「{user_message}」，"
                f"我找到了相关记忆：{best['content']}。"
                f"如果你有更具体的问题，请告诉我。"
            )
        return (
            f"我理解你说的「{user_message}」。"
            f"目前我还没有相关的记忆，能否告诉我更多信息？"
        )

    def show_status(self):
        """打印记忆系统的完整统计信息。"""
        stats = self.memory.get_stats()

        print(f"\n{'=' * 60}")
        print(f"  {self.name} - 记忆系统状态")
        print(f"{'=' * 60}")

        # 会话信息
        session = stats.get("session", {})
        print(f"\n  [会话信息]")
        print(f"    会话ID: {session.get('session_id', 'N/A')}")
        print(f"    交互次数: {session.get('interaction_count', 0)}")

        # 短期记忆
        st = stats.get("short_term", {})
        print(f"\n  [短期记忆]")
        print(f"    工作记忆条目: {st.get('working_memory_size', 0)}")
        print(f"    对话历史条目: {st.get('history_size', 0)}")
        print(f"    会话上下文键: {st.get('session_context_keys', 0)}")

        # 长期记忆
        lt = stats.get("long_term", {})
        print(f"\n  [长期记忆]")
        print(f"    总记忆数: {lt.get('total_memories', 0)}")
        if lt.get("categories"):
            print(f"    类别: {', '.join(lt['categories'])}")

        # 知识图谱
        kg = stats.get("knowledge_graph", {})
        if kg and kg.get("entity_count") is not None:
            print(f"\n  [知识图谱]")
            print(f"    实体数: {kg.get('entity_count', 0)}")
            print(f"    关系数: {kg.get('relation_count', 0)}")
            if kg.get("entity_types"):
                print(f"    实体类型: {', '.join(kg['entity_types'])}")
            if kg.get("relation_types"):
                print(f"    关系类型: {', '.join(kg['relation_types'])}")
        else:
            print(f"\n  [知识图谱] 未启用")

        # 结构化存储
        ss = stats.get("structured_store", {})
        if ss and ss.get("tables"):
            print(f"\n  [结构化存储]")
            print(f"    数据表: {', '.join(ss['tables'])}")
        else:
            print(f"\n  [结构化存储] 未启用")

        print(f"\n{'=' * 60}")


def demo_smart_agent():
    """
    演示 SmartAgent 的多轮对话能力。

    对话流程：
    - 回合1：用户自我介绍（名字 + 职业）
    - 回合2：用户分享偏好（编程语言）
    - 回合3：用户要求记住一个事实
    - 回合4：用户测试 Agent 是否记住了名字
    - 回合5：用户询问事实信息（Python创始人）
    - 回合6：用户询问两个实体之间的关系
    """
    print("=" * 60)
    print("  SmartAgent 多轮对话演示")
    print("  集成 v2.0 记忆系统（FakeEmbedding + Memory + KG + SQLite）")
    print("=" * 60)

    # 创建 Agent
    agent = SmartAgent(name="小智")

    # 多轮对话
    conversation = [
        "你好，我叫张三，是一名软件工程师",
        "我喜欢用Python编程",
        "帮我记住：Python由Guido创建",
        "你还记得我叫什么名字吗？",
        "Python的创始人是誰？",
        "张三和Python有什么关系？",
    ]

    print("\n--- 开始对话 ---\n")

    for i, user_msg in enumerate(conversation, 1):
        print(f"[回合 {i}]")
        print(f"  用户: {user_msg}")

        response = agent.chat(user_msg)

        print(f"  小智: {response}")
        print()

    # 显示最终记忆状态
    agent.show_status()

    print("\n  演示完成！")


def demo_persistence():
    """
    演示记忆持久化能力。

    流程：
    1. 创建 Agent（使用 ChromaDB 后端 + 文件 SQLite）
    2. 存储一些记忆
    3. 保存记忆
    4. 创建新的 Agent 实例（使用相同路径）
    5. 验证记忆是否在新实例中持久化
    """
    print("\n\n")
    print("=" * 60)
    print("  记忆持久化演示")
    print("  使用 ChromaDB 后端 + 文件 SQLite")
    print("=" * 60)

    # 创建临时目录用于持久化存储
    persist_dir = tempfile.mkdtemp(prefix="agent_memory_persist_")
    db_path = os.path.join(persist_dir, "agent_store.db")

    print(f"\n  持久化目录: {persist_dir}")
    print(f"  SQLite路径: {db_path}")

    # ========== 阶段1：创建 Agent 并存储记忆 ==========
    print("\n  --- 阶段1: 创建 Agent 并存储记忆 ---")

    config1 = AgentMemoryConfig(
        short_term={
            "working_memory_capacity": 7,
            "history_limit": 50,
        },
        long_term=LongTermMemoryConfig(
            embedding={
                "provider": "fake",
                "fake_dimension": 128,
            },
            vector_store={
                "backend": "chromadb",
                "persist_directory": persist_dir,
                "collection_name": "agent_memory",
            },
        ),
        knowledge_graph={"enabled": True},
        structured_store={
            "db_path": db_path,
            "enabled": True,
        },
        consolidation_threshold=0.5,
        auto_consolidate=True,
    )

    agent1 = SmartAgent(name="持久化助手")
    agent1.memory = AgentMemory(config=config1)

    # 存储一些记忆
    print("  存储记忆中...")

    agent1.memory.remember_fact(
        fact="用户王五是一名数据科学家",
        category="personal",
        source="user",
        confidence=0.95,
    )
    print("    - 已存储: 用户王五是一名数据科学家")

    agent1.memory.remember_fact(
        fact="王五喜欢使用R语言进行数据分析",
        category="preference",
        source="user",
        confidence=0.9,
    )
    print("    - 已存储: 王五喜欢使用R语言进行数据分析")

    agent1.memory.remember(
        content="R语言由Ross Ihaka和Robert Gentleman开发",
        memory_type="semantic",
        category="knowledge",
        importance=0.85,
    )
    print("    - 已存储: R语言由Ross Ihaka和Robert Gentleman开发")

    # 添加知识图谱实体
    agent1.memory.add_entity(
        name="王五",
        entity_type="person",
        description="数据科学家",
    )
    agent1.memory.add_entity(
        name="R语言",
        entity_type="technology",
        description="统计分析编程语言",
    )
    agent1.memory.add_relation(
        source="王五",
        target="R语言",
        relation_type="uses",
        weight=0.9,
    )
    print("    - 已添加知识图谱: 王五 --[uses]--> R语言")

    # 保存
    agent1.memory.save()
    print("  记忆已保存到磁盘。")

    # 显示阶段1统计
    stats1 = agent1.memory.get_stats()
    lt1 = stats1.get("long_term", {})
    kg1 = stats1.get("knowledge_graph", {})
    print(f"  长期记忆数: {lt1.get('total_memories', 0)}")
    print(f"  知识图谱实体数: {kg1.get('entity_count', 0)}")
    print(f"  知识图谱关系数: {kg1.get('relation_count', 0)}")

    # ========== 阶段2：创建新 Agent 实例，验证持久化 ==========
    print("\n  --- 阶段2: 创建新 Agent 实例，验证记忆持久化 ---")

    # 使用相同的持久化路径创建新实例
    config2 = AgentMemoryConfig(
        short_term={
            "working_memory_capacity": 7,
            "history_limit": 50,
        },
        long_term=LongTermMemoryConfig(
            embedding={
                "provider": "fake",
                "fake_dimension": 128,
            },
            vector_store={
                "backend": "chromadb",
                "persist_directory": persist_dir,
                "collection_name": "agent_memory",
            },
        ),
        knowledge_graph={"enabled": True},
        structured_store={
            "db_path": db_path,
            "enabled": True,
        },
        consolidation_threshold=0.5,
        auto_consolidate=True,
    )

    agent2 = SmartAgent(name="持久化助手")
    agent2.memory = AgentMemory(config=config2)

    # 验证记忆是否持久化
    stats2 = agent2.memory.get_stats()
    lt2 = stats2.get("long_term", {})
    kg2 = stats2.get("knowledge_graph", {})

    print(f"  新实例长期记忆数: {lt2.get('total_memories', 0)}")
    print(f"  新实例知识图谱实体数: {kg2.get('entity_count', 0)}")
    print(f"  新实例知识图谱关系数: {kg2.get('relation_count', 0)}")

    # 尝试检索之前存储的记忆
    print("\n  验证记忆检索:")
    recall_results = agent2.memory.recall("王五", top_k=3)
    if recall_results:
        print("    检索 '王五' 的结果:")
        for r in recall_results:
            print(f"      - {r['content']} (相关度: {r['score']:.2f})")
    else:
        print("    未检索到关于 '王五' 的记忆")

    # 验证知识图谱
    try:
        entity = agent2.memory.get_entity("王五")
        if entity:
            print(f"\n    知识图谱实体 '王五': type={entity.entity_type}, desc={entity.description}")
            related = agent2.memory.find_related("王五", top_k=5)
            if related:
                for rel_result in related:
                    for rel in rel_result.relations:
                        print(
                            f"    关系: {rel.source} --[{rel.relation_type}]--> {rel.target}"
                        )
        else:
            print("\n    知识图谱中未找到 '王五' 实体")
    except Exception as e:
        print(f"\n    知识图谱查询异常: {e}")

    # 验证结构化存储
    try:
        interactions = agent2.memory.get_interaction_history(limit=10)
        print(f"\n    结构化存储交互记录数: {len(interactions)}")
    except Exception:
        print("\n    结构化存储: 新实例无交互历史（符合预期）")

    # 持久化验证结论
    lt_count = lt2.get("total_memories", 0)
    kg_entity_count = kg2.get("entity_count", 0)

    print(f"\n  --- 持久化验证结论 ---")
    if lt_count > 0:
        print(f"  [成功] ChromaDB 长期记忆已持久化 ({lt_count} 条)")
    else:
        print(f"  [注意] ChromaDB 长期记忆未检测到持久化数据")

    if kg_entity_count > 0:
        print(f"  [成功] 知识图谱已持久化 ({kg_entity_count} 个实体)")
    else:
        print(f"  [注意] 知识图谱未检测到持久化数据（知识图谱需手动 load_from_json）")

    print(f"\n  持久化演示完成！临时目录: {persist_dir}")

    # 清理临时目录
    try:
        import shutil
        shutil.rmtree(persist_dir, ignore_errors=True)
        print(f"  已清理临时目录。")
    except Exception:
        pass


if __name__ == "__main__":
    demo_smart_agent()
    demo_persistence()
