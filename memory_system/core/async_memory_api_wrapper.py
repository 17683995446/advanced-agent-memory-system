"""
异步 API 模块

为核心记忆系统提供异步接口，支持 async/await 模式。
使用 asyncio 和线程池实现非阻塞操作。
"""

import asyncio
import functools
from typing import Optional, List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor
import logging

from memory_system.core.agent_memory_manager import AgentMemory, AgentMemoryConfig
from memory_system.core.long_term_persistent_memory import LongTermMemory
from memory_system.processing.knowledge_graph_engine import KnowledgeGraph
from memory_system.storage.structured_sqlite_store import StructuredStore

logger = logging.getLogger(__name__)


class AsyncAgentMemory:
    """
    AgentMemory 的异步包装器
    
    将所有同步操作委托给线程池执行，实现非阻塞 API。
    """
    
    def __init__(
        self,
        config: Optional[AgentMemoryConfig] = None,
        max_workers: int = 4,
        **kwargs
    ):
        """
        Args:
            config: AgentMemory 配置
            max_workers: 线程池最大工作线程数
            **kwargs: 传递给 AgentMemory 的参数
        """
        self._loop = asyncio.get_running_loop()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._memory = AgentMemory(config, **kwargs)
        logger.info("AsyncAgentMemory initialized with %d workers", max_workers)
    
    async def _run_in_executor(self, func: Callable, *args, **kwargs):
        """在线程池中执行同步函数"""
        return await self._loop.run_in_executor(
            self._executor,
            functools.partial(func, *args, **kwargs)
        )
    
    # ========== 记忆存储 ==========
    
    async def add_to_working_memory(self, key: str, content: str, **kwargs) -> bool:
        """异步添加信息到工作记忆"""
        return await self._run_in_executor(
            self._memory.add_to_working_memory, key, content, **kwargs
        )
    
    async def remember(self, content: str, **kwargs) -> str:
        """异步存储长期记忆"""
        return await self._run_in_executor(
            self._memory.remember, content, **kwargs
        )
    
    async def remember_fact(self, fact: str, **kwargs) -> str:
        """异步记住事实"""
        return await self._run_in_executor(
            self._memory.remember_fact, fact, **kwargs
        )
    
    async def remember_conversation(self, content: str, **kwargs) -> Optional[str]:
        """异步记录对话"""
        return await self._run_in_executor(
            self._memory.remember_conversation, content, **kwargs
        )
    
    # ========== 记忆检索 ==========
    
    async def recall(self, query: str, **kwargs) -> List[Any]:
        """异步回忆信息"""
        return await self._run_in_executor(
            self._memory.recall, query, **kwargs
        )
    
    async def get_relevant_context(self, query: str, **kwargs) -> str:
        """异步获取相关上下文"""
        return await self._run_in_executor(
            self._memory.get_relevant_context, query, **kwargs
        )
    
    # ========== 知识图谱 ==========
    
    async def add_entity(self, name: str, **kwargs) -> str:
        """异步添加实体"""
        return await self._run_in_executor(
            self._memory.add_entity, name, **kwargs
        )
    
    async def add_relation(self, source: str, target: str, **kwargs) -> str:
        """异步添加关系"""
        return await self._run_in_executor(
            self._memory.add_relation, source, target, **kwargs
        )
    
    async def search_entities(self, query: str, **kwargs) -> List[Any]:
        """异步搜索实体"""
        return await self._run_in_executor(
            self._memory.search_entities, query, **kwargs
        )
    
    # ========== 结构化存储 ==========
    
    async def store_preference(self, key: str, value: str, **kwargs) -> str:
        """异步存储偏好"""
        return await self._run_in_executor(
            self._memory.store_preference, key, value, **kwargs
        )
    
    async def get_preference(self, key: str, raw: bool = False) -> Optional[Dict]:
        """异步获取偏好"""
        return await self._run_in_executor(
            self._memory.get_preference, key, raw=raw
        )
    
    # ========== 会话管理 ==========
    
    async def add_interaction(self, role: str, content: str, **kwargs):
        """异步添加交互"""
        return await self._run_in_executor(
            self._memory.add_interaction, role, content, **kwargs
        )
    
    async def get_conversation_history(self, n: int = 10) -> List[Dict]:
        """异步获取对话历史"""
        return await self._run_in_executor(
            self._memory.get_conversation_history, n
        )
    
    async def clear_session(self):
        """异步清空会话"""
        return await self._run_in_executor(
            self._memory.clear_session
        )
    
    # ========== 其他 ==========
    
    async def consolidate(self, auto: bool = True) -> Dict[str, Any]:
        """异步记忆巩固"""
        return await self._run_in_executor(
            self._memory.consolidate, auto
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """异步获取统计"""
        return await self._run_in_executor(
            self._memory.get_stats
        )
    
    async def save(self, directory: str = "."):
        """异步保存"""
        return await self._run_in_executor(
            self._memory.save, directory=directory
        )
    
    async def close(self):
        """异步关闭"""
        return await self._run_in_executor(
            self._memory.close
        )

    # ==================== 知识图谱接口（补充） ====================

    async def find_related(self, entity_name: str, top_k: int = 5) -> list:
        """异步查找相关实体"""
        return await self._run_in_executor(
            self._memory.find_related, entity_name, top_k=top_k
        )

    async def get_entity(self, name: str):
        """异步获取实体"""
        return await self._run_in_executor(
            self._memory.get_entity, name
        )

    async def build_knowledge_from_text(self, text: str):
        """异步从文本构建知识图谱"""
        return await self._run_in_executor(
            self._memory.build_knowledge_from_text, text
        )

    async def get_knowledge_graph_stats(self) -> dict:
        """异步获取知识图谱统计"""
        return await self._run_in_executor(
            self._memory.get_knowledge_graph_stats
        )

    async def get_all_entities(self) -> list:
        """异步获取所有实体"""
        return await self._run_in_executor(
            self._memory.get_all_entities
        )

    async def get_entity_relationships(
        self, entity_name: str = None, direction: str = "both"
    ) -> list:
        """异步获取实体关系"""
        return await self._run_in_executor(
            self._memory.get_entity_relationships,
            entity_name, direction=direction,
        )

    async def delete_entity(self, name: str) -> bool:
        """异步删除实体"""
        return await self._run_in_executor(
            self._memory.delete_entity, name
        )

    async def find_path(self, source: str, target: str):
        """异步查找最短路径"""
        return await self._run_in_executor(
            self._memory.find_path, source, target
        )

    async def get_neighbors(self, entity_name: str, max_depth: int = 1) -> list:
        """异步获取邻居实体"""
        return await self._run_in_executor(
            self._memory.get_neighbors, entity_name, max_depth=max_depth
        )

    async def get_most_connected_entities(self, top_k: int = 10) -> list:
        """异步获取最连接实体"""
        return await self._run_in_executor(
            self._memory.get_most_connected_entities, top_k=top_k
        )

    async def get_entity_types(self) -> list:
        """异步获取实体类型"""
        return await self._run_in_executor(
            self._memory.get_entity_types
        )

    async def get_relation_types(self) -> list:
        """异步获取关系类型"""
        return await self._run_in_executor(
            self._memory.get_relation_types
        )

    # ==================== 结构化存储接口（补充） ====================

    async def set_preference(self, key: str, value, category: str = "general") -> str:
        """异步设置偏好"""
        return await self._run_in_executor(
            self._memory.set_preference, key, value, category=category
        )

    async def log_interaction(self, role: str, content: str, **metadata) -> str:
        """异步记录交互"""
        return await self._run_in_executor(
            self._memory.log_interaction, role, content, **metadata
        )

    async def get_interaction_history(self, limit: int = 50) -> list:
        """异步获取交互历史"""
        return await self._run_in_executor(
            self._memory.get_interaction_history, limit=limit
        )

    # ==================== 检索接口（补充） ====================

    async def recall_for_prompt(
        self, query: str, max_short_term: int = 3, max_long_term: int = 3
    ) -> str:
        """异步回忆并格式化为提示文本"""
        return await self._run_in_executor(
            self._memory.recall_for_prompt,
            query, max_short_term=max_short_term, max_long_term=max_long_term,
        )

    # ==================== 会话管理接口（补充） ====================

    async def get_conversation_context(self, max_turns: int = 5) -> str:
        """异步获取对话上下文"""
        return await self._run_in_executor(
            self._memory.get_conversation_context, max_turns=max_turns
        )

    async def set_session_context(self, key: str, value):
        """异步设置会话上下文"""
        return await self._run_in_executor(
            self._memory.set_session_context, key, value
        )

    async def get_session_context(self, key: str):
        """异步获取会话上下文"""
        return await self._run_in_executor(
            self._memory.get_session_context, key
        )

    # ==================== 记忆巩固（补充） ====================

    async def force_consolidate(self) -> dict:
        """异步强制执行记忆巩固"""
        return await self._run_in_executor(
            self._memory.force_consolidate
        )

    # ==================== 统计监控（补充） ====================

    async def get_working_memory_snapshot(self) -> dict:
        """异步获取工作记忆快照"""
        return await self._run_in_executor(
            self._memory.get_working_memory_snapshot
        )

    # ==================== 长期记忆 CRUD ====================

    async def get_memory(self, memory_id: str):
        """异步获取指定记忆"""
        return await self._run_in_executor(
            self._memory.get_memory, memory_id
        )

    async def update_memory(self, memory_id: str, **kwargs) -> bool:
        """异步更新记忆"""
        return await self._run_in_executor(
            self._memory.update_memory, memory_id, **kwargs
        )

    async def delete_memory(self, memory_id: str) -> bool:
        """异步删除记忆"""
        return await self._run_in_executor(
            self._memory.delete_memory, memory_id
        )

    async def forget_memory(self, memory_id: str) -> bool:
        """异步遗忘记忆"""
        return await self._run_in_executor(
            self._memory.forget_memory, memory_id
        )

    async def get_memories_by_category(self, category: str) -> list:
        """异步按类别获取记忆"""
        return await self._run_in_executor(
            self._memory.get_memories_by_category, category
        )

    async def get_memories_by_tag(self, tag: str) -> list:
        """异步按标签获取记忆"""
        return await self._run_in_executor(
            self._memory.get_memories_by_tag, tag
        )

    async def get_all_memories(self, limit: int = 100) -> list:
        """异步获取所有记忆"""
        return await self._run_in_executor(
            self._memory.get_all_memories, limit=limit
        )

    async def count_memories(self) -> int:
        """异步获取记忆总数"""
        return await self._run_in_executor(
            self._memory.count_memories
        )

    # ==================== 工作记忆焦点管理 ====================

    async def set_focus(self, key: str) -> bool:
        """异步设置焦点"""
        return await self._run_in_executor(
            self._memory.set_focus, key
        )

    async def get_focus(self):
        """异步获取焦点键"""
        return await self._run_in_executor(
            self._memory.get_focus
        )

    async def get_focus_content(self):
        """异步获取焦点内容"""
        return await self._run_in_executor(
            self._memory.get_focus_content
        )

    async def pop_focus(self):
        """异步弹出焦点"""
        return await self._run_in_executor(
            self._memory.pop_focus
        )

    # ==================== 事实查询 ====================

    async def get_facts(self, category: str = None, limit: int = 50) -> list:
        """异步获取事实"""
        return await self._run_in_executor(
            self._memory.get_facts, category=category, limit=limit
        )
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.save()
        await self.close()
        self._executor.shutdown(wait=True)


__all__ = ["AsyncAgentMemory"]
