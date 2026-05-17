"""
短期记忆模块 - 工作记忆与上下文缓存

短期记忆模拟人类的工作记忆，特点：
- 容量有限（通常4-7个信息块）
- 访问速度快
- 信息会随时间衰减
- 支持优先级排序
"""

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import threading

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """记忆单元"""
    content: str
    memory_type: str = "general"  # general, fact, event, emotion, goal
    importance: float = 0.5  # 0-1
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def priority_score(self) -> float:
        """计算优先级分数（基于重要性和时效性）"""
        age = time.time() - self.timestamp
        recency = 1.0 / (1.0 + age / 3600)  # 1小时内保持较高分数
        access_boost = min(self.access_count * 0.1, 0.3)
        return self.importance * 0.5 + recency * 0.3 + access_boost * 0.2
    
    def touch(self):
        """访问记忆，更新访问计数"""
        self.access_count += 1
        self.last_access = time.time()


class WorkingMemoryBuffer:
    """
    工作记忆缓冲区
    
    模拟人类的认知工作空间，特点：
    - 有限容量（默认7±2个信息块）
    - 支持焦点切换
    - 自动清理低优先级信息
    """
    
    def __init__(self, capacity: int = 7):
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        self.capacity = capacity
        self._buffer: Dict[str, MemoryItem] = {}
        self._focus_stack: List[str] = []  # 焦点栈
        self._lock = threading.RLock()
    
    def add(self, key: str, content: str, **kwargs) -> bool:
        """添加信息到工作记忆"""
        with self._lock:
            if len(self._buffer) >= self.capacity and key not in self._buffer:
                # 需要清理空间
                self._evict_lowest_priority()
            
            item = MemoryItem(content=content, **kwargs)
            self._buffer[key] = item
            logger.debug("Added to working memory: %s", key)
            
            # 新信息获得焦点
            if key in self._focus_stack:
                self._focus_stack.remove(key)
            self._focus_stack.insert(0, key)
            
            return True
    
    def get(self, key: str) -> Optional[MemoryItem]:
        """获取记忆项"""
        with self._lock:
            item = self._buffer.get(key)
            if item:
                item.touch()
            return item
    
    def get_content(self, key: str) -> Optional[str]:
        """获取记忆内容"""
        item = self.get(key)
        return item.content if item else None
    
    def set_focus(self, key: str) -> bool:
        """将指定key设为焦点"""
        with self._lock:
            if key not in self._buffer:
                return False
            if key in self._focus_stack:
                self._focus_stack.remove(key)
            self._focus_stack.insert(0, key)
            return True
    
    def get_focus(self) -> Optional[str]:
        """获取当前焦点"""
        with self._lock:
            return self._focus_stack[0] if self._focus_stack else None
    
    def get_focus_content(self) -> Optional[str]:
        """获取焦点内容"""
        focus_key = self.get_focus()
        if focus_key:
            return self.get_content(focus_key)
        return None
    
    def pop_focus(self) -> Optional[str]:
        """弹出当前焦点，回到上一个焦点"""
        with self._lock:
            if self._focus_stack:
                self._focus_stack.pop(0)
            return self.get_focus()
    
    def remove(self, key: str) -> bool:
        """移除指定记忆"""
        with self._lock:
            if key in self._buffer:
                del self._buffer[key]
                if key in self._focus_stack:
                    self._focus_stack.remove(key)
                logger.debug("Removed from working memory: %s", key)
                return True
            return False
    
    def clear(self):
        """清空工作记忆"""
        with self._lock:
            self._buffer.clear()
            self._focus_stack.clear()
    
    def get_all(self) -> List[Tuple[str, MemoryItem]]:
        """获取所有记忆项，按优先级排序"""
        with self._lock:
            items = [(k, v) for k, v in self._buffer.items()]
            items.sort(key=lambda x: x[1].priority_score, reverse=True)
            return items
    
    def get_context_string(self, max_items: int = 5) -> str:
        """获取上下文字符串，用于LLM提示"""
        items = self.get_all()[:max_items]
        if not items:
            return ""
        
        context_parts = []
        for key, item in items:
            prefix = "【焦点】" if key == self.get_focus() else ""
            context_parts.append(f"{prefix}[{key}] {item.content}")
        
        return "\n".join(context_parts)
    
    def _evict_lowest_priority(self):
        """淘汰优先级最低的记忆"""
        if not self._buffer:
            return
        
        lowest_key = min(self._buffer.keys(), 
                        key=lambda k: self._buffer[k].priority_score)
        logger.debug("Evicted lowest priority: %s", lowest_key)
        self.remove(lowest_key)
    
    def __len__(self) -> int:
        return len(self._buffer)
    
    def __contains__(self, key: str) -> bool:
        return key in self._buffer


class ShortTermMemory:
    """
    短期记忆系统
    
    管理Agent的即时上下文和近期交互历史
    """
    
    def __init__(self, 
                 working_memory_capacity: int = 7,
                 history_limit: int = 50,
                 decay_interval: int = 300):
        """
        Args:
            working_memory_capacity: 工作记忆容量
            history_limit: 历史记录保留数量
            decay_interval: 衰减检查间隔（秒）
        """
        if working_memory_capacity <= 0:
            raise ValueError(f"working_memory_capacity must be positive, got {working_memory_capacity}")
        if history_limit <= 0:
            raise ValueError(f"history_limit must be positive, got {history_limit}")
        self.working_memory = WorkingMemoryBuffer(capacity=working_memory_capacity)
        self.history_limit = history_limit
        self.decay_interval = decay_interval
        
        # 交互历史（时间线）
        self._history: deque = deque(maxlen=history_limit)
        
        # 会话上下文
        self._session_context: Dict[str, Any] = {}
        
        self._lock = threading.RLock()
        self._last_decay_check = time.time()
    
    def add_to_working_memory(self, key: str, content: str, **kwargs) -> bool:
        """添加信息到工作记忆"""
        return self.working_memory.add(key, content, **kwargs)
    
    def get_from_working_memory(self, key: str) -> Optional[MemoryItem]:
        """从工作记忆获取信息"""
        return self.working_memory.get(key)
    
    def add_interaction(self, role: str, content: str, **metadata):
        """添加交互记录到历史"""
        with self._lock:
            interaction = {
                "role": role,  # user, assistant, system
                "content": content,
                "timestamp": time.time(),
                "metadata": metadata
            }
            self._history.append(interaction)
            logger.debug("Interaction recorded: %s -> %s", role, content[:50])
            
            # 同时添加到工作记忆（如果是重要信息）
            if metadata.get("important", False):
                key = f"interaction_{len(self._history)}"
                # 只传递MemoryItem支持的参数
                wm_metadata = {k: v for k, v in metadata.items() 
                              if k in ['memory_type', 'importance']}
                self.working_memory.add(key, content, memory_type="event", **wm_metadata)
    
    def get_recent_history(self, n: int = 10) -> List[Dict]:
        """获取最近n条交互历史"""
        with self._lock:
            return list(self._history)[-n:]
    
    def get_conversation_context(self, max_turns: int = 5) -> str:
        """获取对话上下文，用于LLM"""
        recent = self.get_recent_history(max_turns)
        if not recent:
            return ""
        
        lines = []
        for item in recent:
            role = item["role"]
            content = item["content"]
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)
    
    def set_session_context(self, key: str, value: Any):
        """设置会话上下文"""
        with self._lock:
            self._session_context[key] = value
    
    def get_session_context(self, key: str) -> Optional[Any]:
        """获取会话上下文"""
        with self._lock:
            return self._session_context.get(key)
    
    def clear_session(self):
        """清空会话"""
        with self._lock:
            self._history.clear()
            self._session_context.clear()
            self.working_memory.clear()
    
    def get_full_context(self) -> Dict[str, Any]:
        """获取完整上下文快照"""
        with self._lock:
            return {
                "working_memory": self.working_memory.get_context_string(),
                "recent_history": self.get_recent_history(),
                "session_context": self._session_context.copy(),
                "current_focus": self.working_memory.get_focus()
            }
    
    def check_decay(self):
        """检查并执行记忆衰减"""
        current_time = time.time()
        if current_time - self._last_decay_check < self.decay_interval:
            return
        
        self._last_decay_check = current_time
        
        # 清理过旧的会话上下文
        with self._lock:
            keys_to_remove = []
            for key, value in self._session_context.items():
                if isinstance(value, dict) and "timestamp" in value:
                    if current_time - value["timestamp"] > 3600:  # 1小时过期
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._session_context[key]