"""
存储事件总线 - 模块间数据同步

使用 Blinker 实现发布-订阅模式的事件总线，支持:
- 存储操作事件通知
- 模块间数据同步
- 事件过滤和路由

依赖: blinker>=1.7.0 (零依赖纯 Python 库)
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from blinker import Signal, Namespace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 事件类型定义
# ---------------------------------------------------------------------------

class StorageEventType(Enum):
    """存储事件类型"""
    # 记忆操作
    MEMORY_ADD = "memory_add"
    MEMORY_UPDATE = "memory_update"
    MEMORY_DELETE = "memory_delete"
    MEMORY_ACCESS = "memory_access"
    
    # 向量存储操作
    VECTOR_ADD = "vector_add"
    VECTOR_SEARCH = "vector_search"
    VECTOR_DELETE = "vector_delete"
    
    # 知识图谱操作
    ENTITY_ADD = "entity_add"
    ENTITY_DELETE = "entity_delete"
    RELATION_ADD = "relation_add"
    RELATION_DELETE = "relation_delete"
    
    # 结构化存储操作
    RECORD_INSERT = "record_insert"
    RECORD_UPDATE = "record_update"
    RECORD_DELETE = "record_delete"
    
    # 系统事件
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    SYNC_START = "sync_start"
    SYNC_COMPLETE = "sync_complete"
    SYNC_ERROR = "sync_error"


class StorageSource(Enum):
    """存储来源"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    VECTOR_STORE = "vector_store"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    STRUCTURED_STORE = "structured_store"
    CACHE = "cache"
    EXTERNAL = "external"


# ---------------------------------------------------------------------------
# 事件数据结构
# ---------------------------------------------------------------------------

@dataclass
class StorageEvent:
    """
    存储事件
    
    Attributes:
        event_id: 事件唯一标识
        event_type: 事件类型
        source: 事件来源
        data: 事件数据
        metadata: 事件元数据
        timestamp: 事件时间戳
        correlation_id: 关联 ID（用于追踪相关事件）
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: StorageEventType = StorageEventType.MEMORY_ADD
    source: StorageSource = StorageSource.LONG_TERM
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "data": self.data,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "StorageEvent":
        """从字典创建"""
        return cls(
            event_id=data["event_id"],
            event_type=StorageEventType(data["event_type"]),
            source=StorageSource(data["source"]),
            data=data["data"],
            metadata=data.get("metadata", {}),
            timestamp=data["timestamp"],
            correlation_id=data.get("correlation_id"),
        )


# ---------------------------------------------------------------------------
# 事件总线
# ---------------------------------------------------------------------------

class EventBus:
    """
    存储事件总线
    
    基于 Blinker Signal 实现的发布-订阅事件系统。
    
    Features:
    - 类型安全的事件发布
    - 支持事件过滤
    - 支持同步和异步处理
    - 事件历史记录
    - 调试和监控支持
    
    Example:
        bus = EventBus()
        
        # 订阅事件
        @bus.on(StorageEventType.MEMORY_ADD)
        def handle_memory_add(event):
            print(f"New memory: {event.data}")
        
        # 发布事件
        bus.emit(StorageEventType.MEMORY_ADD, data={"content": "Hello"})
    """
    
    def __init__(self, history_size: int = 1000):
        """
        Args:
            history_size: 事件历史记录大小
        """
        self._namespace = Namespace()
        self._history: list[StorageEvent] = []
        self._history_size = history_size
        self._subscribers: dict[str, list[Callable]] = {}
        
        # 为每种事件类型创建 Signal
        self._signals: dict[StorageEventType, Signal] = {}
        for event_type in StorageEventType:
            self._signals[event_type] = self._namespace.signal(event_type.value)
        
        logger.info("EventBus initialized with history_size=%d", history_size)
    
    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    
    def emit(
        self,
        event_type: StorageEventType,
        source: StorageSource = StorageSource.LONG_TERM,
        data: Optional[dict] = None,
        metadata: Optional[dict] = None,
        correlation_id: Optional[str] = None,
    ) -> StorageEvent:
        """
        发布事件
        
        Args:
            event_type: 事件类型
            source: 事件来源
            data: 事件数据
            metadata: 事件元数据
            correlation_id: 关联 ID
            
        Returns:
            创建的事件对象
        """
        event = StorageEvent(
            event_type=event_type,
            source=source,
            data=data or {},
            metadata=metadata or {},
            correlation_id=correlation_id,
        )
        
        # 添加到历史记录
        self._add_to_history(event)
        
        # 发送信号
        signal = self._signals[event_type]
        signal.send(event)
        
        logger.debug(
            "Event emitted: %s from %s (id=%s)",
            event_type.value, source.value, event.event_id
        )
        
        return event
    
    def on(
        self,
        event_type: StorageEventType,
        *,
        source_filter: Optional[StorageSource] = None,
    ) -> Callable:
        """
        订阅事件装饰器
        
        Args:
            event_type: 要订阅的事件类型
            source_filter: 可选的来源过滤器
            
        Returns:
            装饰器函数
            
        Example:
            @bus.on(StorageEventType.MEMORY_ADD)
            def handler(event):
                print(event)
            
            @bus.on(StorageEventType.MEMORY_ADD, source_filter=StorageSource.LONG_TERM)
            def handler_long_term_only(event):
                print(event)
        """
        def decorator(func: Callable) -> Callable:
            signal = self._signals[event_type]
            
            if source_filter:
                # 带过滤器的处理函数
                def filtered_handler(event: StorageEvent):
                    if event.source == source_filter:
                        return func(event)
                
                signal.connect(filtered_handler)
                self._track_subscriber(event_type, filtered_handler)
            else:
                signal.connect(func)
                self._track_subscriber(event_type, func)
            
            logger.debug(
                "Subscriber registered for %s%s",
                event_type.value,
                f" (source={source_filter.value})" if source_filter else ""
            )
            
            return func
        
        return decorator
    
    def subscribe(
        self,
        event_type: StorageEventType,
        handler: Callable,
        *,
        source_filter: Optional[StorageSource] = None,
    ):
        """
        编程式订阅事件
        
        Args:
            event_type: 事件类型
            handler: 处理函数
            source_filter: 可选的来源过滤器
        """
        decorator = self.on(event_type, source_filter=source_filter)
        decorator(handler)
    
    def unsubscribe(
        self,
        event_type: StorageEventType,
        handler: Callable,
    ):
        """取消订阅"""
        signal = self._signals[event_type]
        signal.disconnect(handler)
        logger.debug("Unsubscribed handler from %s", event_type.value)
    
    # ------------------------------------------------------------------
    # 批量订阅
    # ------------------------------------------------------------------
    
    def on_multiple(
        self,
        event_types: list[StorageEventType],
    ) -> Callable:
        """
        订阅多种事件类型
        
        Example:
            @bus.on_multiple([StorageEventType.MEMORY_ADD, StorageEventType.MEMORY_UPDATE])
            def handler(event):
                print(f"Memory changed: {event.event_type}")
        """
        def decorator(func: Callable) -> Callable:
            for event_type in event_types:
                self.on(event_type)(func)
            return func
        return decorator
    
    # ------------------------------------------------------------------
    # 历史记录
    # ------------------------------------------------------------------
    
    def _add_to_history(self, event: StorageEvent):
        """添加事件到历史记录"""
        self._history.append(event)
        if len(self._history) > self._history_size:
            self._history.pop(0)
    
    def get_history(
        self,
        event_type: Optional[StorageEventType] = None,
        source: Optional[StorageSource] = None,
        limit: int = 100,
    ) -> list[StorageEvent]:
        """
        获取事件历史
        
        Args:
            event_type: 可选的事件类型过滤
            source: 可选的来源过滤
            limit: 返回数量限制
            
        Returns:
            事件列表
        """
        events = self._history.copy()
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if source:
            events = [e for e in events if e.source == source]
        
        return events[-limit:]
    
    def clear_history(self):
        """清空历史记录"""
        self._history.clear()
    
    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    
    def _track_subscriber(self, event_type: StorageEventType, handler: Callable):
        """追踪订阅者"""
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(handler)
    
    def get_subscribers(self, event_type: StorageEventType) -> list[Callable]:
        """获取事件类型的订阅者"""
        return self._subscribers.get(event_type.value, [])
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "history_size": len(self._history),
            "max_history_size": self._history_size,
            "subscriber_count": sum(len(v) for v in self._subscribers.values()),
            "event_types": {
                k: len(v) for k, v in self._subscribers.items()
            },
        }


# ---------------------------------------------------------------------------
# 全局事件总线实例
# ---------------------------------------------------------------------------

_global_bus: Optional[EventBus] = None
_global_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """获取全局事件总线实例（线程安全）"""
    global _global_bus
    if _global_bus is None:
        with _global_bus_lock:
            if _global_bus is None:
                _global_bus = EventBus()
    return _global_bus


def reset_event_bus():
    """重置全局事件总线（主要用于测试）"""
    global _global_bus
    with _global_bus_lock:
        _global_bus = None


# ---------------------------------------------------------------------------
# 便捷装饰器
# ---------------------------------------------------------------------------

def on_memory_add(func: Callable) -> Callable:
    """订阅记忆添加事件"""
    return get_event_bus().on(StorageEventType.MEMORY_ADD)(func)


def on_memory_update(func: Callable) -> Callable:
    """订阅记忆更新事件"""
    return get_event_bus().on(StorageEventType.MEMORY_UPDATE)(func)


def on_memory_delete(func: Callable) -> Callable:
    """订阅记忆删除事件"""
    return get_event_bus().on(StorageEventType.MEMORY_DELETE)(func)


def on_vector_add(func: Callable) -> Callable:
    """订阅向量添加事件"""
    return get_event_bus().on(StorageEventType.VECTOR_ADD)(func)


def on_entity_add(func: Callable) -> Callable:
    """订阅实体添加事件"""
    return get_event_bus().on(StorageEventType.ENTITY_ADD)(func)


__all__ = [
    "EventBus",
    "StorageEvent",
    "StorageEventType",
    "StorageSource",
    "get_event_bus",
    "reset_event_bus",
    "on_memory_add",
    "on_memory_update",
    "on_memory_delete",
    "on_vector_add",
    "on_entity_add",
]
