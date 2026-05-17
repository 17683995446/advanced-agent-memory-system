"""
会话管理器 - 多会话上下文隔离

管理多个独立会话的上下文，支持：
- 会话创建、切换、销毁
- 会话级上下文存储
- 会话超时自动清理
- 会话统计

依赖: 无额外依赖
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """
    会话上下文
    
    Attributes:
        session_id: 会话唯一标识
        user_id: 用户标识
        metadata: 会话级元数据
        working_memory: 工作记忆内容列表
        variables: 会话变量
        created_at: 创建时间
        last_active: 最后活跃时间
        message_count: 消息计数
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    working_memory: list[dict] = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0
    
    @property
    def age_seconds(self) -> float:
        """会话年龄（秒）"""
        return time.time() - self.created_at
    
    @property
    def idle_seconds(self) -> float:
        """空闲时间（秒）"""
        return time.time() - self.last_active
    
    def touch(self):
        """更新最后活跃时间"""
        self.last_active = time.time()
    
    def add_message(self, role: str, content: str, metadata: Optional[dict] = None):
        """
        添加消息到工作记忆
        
        Args:
            role: 角色 ("user" / "assistant" / "system")
            content: 消息内容
            metadata: 消息元数据
        """
        self.working_memory.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })
        self.message_count += 1
        self.touch()
    
    def get_recent_messages(self, n: int = 10) -> list[dict]:
        """获取最近 n 条消息"""
        return self.working_memory[-n:]
    
    def set_variable(self, key: str, value: Any):
        """设置会话变量"""
        self.variables[key] = value
        self.touch()
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取会话变量"""
        return self.variables.get(key, default)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "working_memory": self.working_memory,
            "variables": self.variables,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "message_count": self.message_count,
        }


class SessionManager:
    """
    会话管理器
    
    管理多个独立会话，支持会话创建、切换、销毁和超时清理。
    
    Args:
        max_sessions: 最大会话数
        session_timeout: 会话超时时间（秒），0 表示不超时
        max_working_memory: 每个会话最大工作记忆条数
    
    Example:
        sm = SessionManager(max_sessions=100, session_timeout=3600)
        
        # 创建会话
        ctx = sm.create_session(user_id="user1")
        
        # 添加消息
        ctx.add_message("user", "Hello")
        ctx.add_message("assistant", "Hi there!")
        
        # 切换会话
        sm.switch_session(ctx.session_id)
        
        # 获取当前会话
        current = sm.get_current_session()
    """
    
    def __init__(
        self,
        max_sessions: int = 1000,
        session_timeout: float = 0,
        max_working_memory: int = 50,
    ):
        self._sessions: dict[str, SessionContext] = {}
        self._current_session_id: Optional[str] = None
        self._max_sessions = max_sessions
        self._session_timeout = session_timeout
        self._max_working_memory = max_working_memory
    
    def create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> SessionContext:
        """
        创建新会话
        
        Args:
            session_id: 可选的自定义会话 ID
            user_id: 用户标识
            metadata: 会话元数据
            
        Returns:
            新创建的会话上下文
        """
        # 检查容量
        if len(self._sessions) >= self._max_sessions:
            self._evict_oldest()
        
        ctx = SessionContext(
            session_id=session_id or str(uuid.uuid4()),
            user_id=user_id,
            metadata=metadata or {},
        )
        
        self._sessions[ctx.session_id] = ctx
        self._current_session_id = ctx.session_id
        
        logger.info("Session created: %s (user=%s)", ctx.session_id, user_id)
        return ctx
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """获取指定会话"""
        ctx = self._sessions.get(session_id)
        if ctx is not None:
            # 检查超时
            if self._session_timeout > 0 and ctx.idle_seconds > self._session_timeout:
                self.destroy_session(session_id)
                return None
            ctx.touch()
        return ctx
    
    def get_current_session(self) -> Optional[SessionContext]:
        """获取当前活跃会话"""
        if self._current_session_id is None:
            return None
        return self.get_session(self._current_session_id)
    
    def switch_session(self, session_id: str) -> bool:
        """
        切换当前会话
        
        Returns:
            是否切换成功
        """
        if session_id in self._sessions:
            self._current_session_id = session_id
            self._sessions[session_id].touch()
            logger.debug("Switched to session: %s", session_id)
            return True
        return False
    
    def destroy_session(self, session_id: str) -> bool:
        """
        销毁会话
        
        Returns:
            是否销毁成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._current_session_id == session_id:
                self._current_session_id = None
            logger.info("Session destroyed: %s", session_id)
            return True
        return False
    
    def list_sessions(
        self,
        user_id: Optional[str] = None,
        active_only: bool = False,
    ) -> list[SessionContext]:
        """
        列出会话
        
        Args:
            user_id: 按用户过滤
            active_only: 仅返回活跃会话（未超时）
        """
        sessions = list(self._sessions.values())
        
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        
        if active_only and self._session_timeout > 0:
            sessions = [s for s in sessions if s.idle_seconds <= self._session_timeout]
        
        return sessions
    
    def cleanup_expired(self) -> int:
        """
        清理过期会话
        
        Returns:
            清理的会话数量
        """
        if self._session_timeout <= 0:
            return 0
        
        expired = [
            sid for sid, ctx in self._sessions.items()
            if ctx.idle_seconds > self._session_timeout
        ]
        
        for sid in expired:
            self.destroy_session(sid)
        
        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))
        
        return len(expired)
    
    def _evict_oldest(self):
        """淘汰最旧的会话"""
        if not self._sessions:
            return
        
        oldest = min(self._sessions.items(), key=lambda x: x[1].last_active)
        self.destroy_session(oldest[0])
        logger.info("Evicted oldest session: %s", oldest[0])
    
    def get_stats(self) -> dict:
        """获取会话统计"""
        return {
            "total_sessions": len(self._sessions),
            "max_sessions": self._max_sessions,
            "current_session": self._current_session_id,
            "timeout": self._session_timeout,
        }
    
    def get_all_user_ids(self) -> list[str]:
        """获取所有用户 ID"""
        return list(set(
            ctx.user_id for ctx in self._sessions.values()
            if ctx.user_id is not None
        ))


__all__ = [
    "SessionManager",
    "SessionContext",
]
