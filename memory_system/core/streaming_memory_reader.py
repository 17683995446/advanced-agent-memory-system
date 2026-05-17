"""
流式记忆模块 - 异步生成器接口

支持流式读取大量记忆，避免一次性加载到内存。
基于 Python async generator 实现。

依赖: 无额外依赖
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class StreamConfig:
    """流式配置"""
    batch_size: int = 10           # 每批数量
    max_items: Optional[int] = None  # 最大返回数量
    buffer_size: int = 100         # 内部缓冲区大小
    prefetch: bool = True          # 预取下一批


@dataclass
class StreamResult:
    """流式结果批次"""
    items: list[dict] = field(default_factory=list)
    batch_index: int = 0
    has_more: bool = True
    total_yielded: int = 0
    query_time_ms: float = 0.0


class MemoryStreamer:
    """
    记忆流式读取器
    
    支持从多种数据源流式读取记忆，避免一次性加载。
    
    Args:
        data_source: 数据源（列表或可调用对象）
        config: 流式配置
    
    Example:
        # 从列表流式读取
        streamer = MemoryStreamer(memories, config=StreamConfig(batch_size=5))
        
        async for batch in streamer.stream():
            for item in batch.items:
                process(item)
        
        # 从回调函数流式读取
        def fetch_batch(offset, limit):
            return db.query(offset=offset, limit=limit)
        
        streamer = MemoryStreamer(fetch_batch, config=StreamConfig(batch_size=10))
        async for batch in streamer.stream():
            print(batch.items)
    """
    
    def __init__(
        self,
        data_source: Any,
        config: Optional[StreamConfig] = None,
    ):
        self._source = data_source
        self._config = config or StreamConfig()
        self._total_yielded = 0
    
    async def stream(self) -> AsyncIterator[StreamResult]:
        """
        异步流式生成器
        
        Yields:
            StreamResult 批次
        """
        start = time.time()
        batch_index = 0
        
        if callable(self._source) and not isinstance(self._source, list):
            # 回调函数模式
            offset = 0
            while True:
                batch_data = await self._fetch_from_callable(offset)
                if not batch_data:
                    break
                
                items = batch_data[:self._config.batch_size]
                self._total_yielded += len(items)
                
                has_more = (
                    len(batch_data) >= self._config.batch_size
                    and (self._config.max_items is None
                         or self._total_yielded < self._config.max_items)
                )
                
                yield StreamResult(
                    items=items,
                    batch_index=batch_index,
                    has_more=has_more,
                    total_yielded=self._total_yielded,
                    query_time_ms=(time.time() - start) * 1000,
                )
                
                batch_index += 1
                offset += self._config.batch_size
                
                if self._config.max_items and self._total_yielded >= self._config.max_items:
                    break
        else:
            # 列表模式
            data = list(self._source)
            total = len(data)
            
            for i in range(0, total, self._config.batch_size):
                batch = data[i:i + self._config.batch_size]
                
                if self._config.max_items:
                    remaining = self._config.max_items - self._total_yielded
                    if remaining <= 0:
                        break
                    batch = batch[:remaining]
                
                self._total_yielded += len(batch)
                
                yield StreamResult(
                    items=batch,
                    batch_index=batch_index,
                    has_more=(i + self._config.batch_size < total),
                    total_yielded=self._total_yielded,
                    query_time_ms=(time.time() - start) * 1000,
                )
                
                batch_index += 1
    
    async def _fetch_from_callable(self, offset: int) -> list:
        """从回调函数获取数据"""
        try:
            result = self._source(offset, self._config.batch_size)
            if asyncio.iscoroutine(result):
                return await result
            return result or []
        except (ValueError, TypeError, RuntimeError, StopIteration) as e:
            logger.error("Failed to fetch data at offset %d: %s", offset, e)
            return []
    
    async def collect_all(self) -> list[dict]:
        """收集所有结果到列表"""
        all_items = []
        async for batch in self.stream():
            all_items.extend(batch.items)
        return all_items
    
    async def count(self) -> int:
        """估算总数"""
        if isinstance(self._source, (list, tuple)):
            return min(len(self._source), self._config.max_items or len(self._source))
        return -1  # 未知


class StreamBuffer:
    """
    流式缓冲区
    
    用于在生产者-消费者模式中缓冲流式数据。
    
    Args:
        max_size: 最大缓冲区大小
    
    Example:
        buffer = StreamBuffer(max_size=100)
        
        # 生产者写入
        buffer.write({"content": "hello"})
        buffer.write({"content": "world"})
        buffer.finish()
        
        # 消费者读取
        async for item in buffer.read_stream():
            print(item)
    """
    
    def __init__(self, max_size: int = 100):
        self._buffer: deque = deque(maxlen=max_size)
        self._finished = False
        self._waiters: list[asyncio.Future] = []
        self._lock = asyncio.Lock()
    
    async def write(self, item: Any):
        """写入数据"""
        async with self._lock:
            self._buffer.append(item)
            # 唤醒等待的消费者
            for future in self._waiters:
                if not future.done():
                    future.set_result(None)
            self._waiters.clear()
    
    async def write_batch(self, items: list):
        """批量写入"""
        async with self._lock:
            self._buffer.extend(items)
            for future in self._waiters:
                if not future.done():
                    future.set_result(None)
            self._waiters.clear()
    
    def finish(self):
        """标记写入完成"""
        self._finished = True
        for future in self._waiters:
            if not future.done():
                future.set_result(None)
        self._waiters.clear()
    
    async def read_stream(self) -> AsyncIterator[Any]:
        """异步读取流"""
        while True:
            async with self._lock:
                if self._buffer:
                    yield self._buffer.popleft()
                    continue
                
                if self._finished:
                    break
                
                # 等待新数据
                future = asyncio.get_event_loop().create_future()
                self._waiters.append(future)
            
            try:
                await asyncio.wait_for(future, timeout=1.0)
            except asyncio.TimeoutError:
                pass  # 重新检查
    
    @property
    def size(self) -> int:
        return len(self._buffer)
    
    @property
    def is_finished(self) -> bool:
        return self._finished
    
    def clear(self):
        self._buffer.clear()


__all__ = [
    "MemoryStreamer",
    "StreamBuffer",
    "StreamConfig",
    "StreamResult",
]
