"""
记忆压缩模块 - 长文本摘要与重要性筛选

支持:
- LLM 摘要压缩 (可配置摘要器)
- 重要性阈值筛选
- 时间窗口压缩
- 批量压缩

依赖: 无额外依赖 (摘要器可插拔)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """压缩策略"""
    IMPORTANCE = "importance"       # 按重要性筛选
    RECENCY = "recency"             # 按时间筛选
    HYBRID = "hybrid"               # 混合策略
    SUMMARY = "summary"             # LLM 摘要


@dataclass
class CompressionResult:
    """压缩结果"""
    original_count: int
    compressed_count: int
    removed_ids: list[str] = field(default_factory=list)
    summary: Optional[str] = None


class MemoryCompressor:
    """
    记忆压缩器
    
    通过摘要或筛选减少记忆数量，保留关键信息。
    
    Args:
        strategy: 压缩策略
        importance_threshold: 重要性阈值 (低于此值可压缩)
        max_age_seconds: 最大保留时间 (超过此时间可压缩)
        summarizer: 可选的摘要函数 (text -> summary)
    
    Example:
        compressor = MemoryCompressor(
            strategy=CompressionStrategy.IMPORTANCE,
            importance_threshold=0.3,
        )
        
        result = compressor.compress(memories)
        print(f"Compressed {result.original_count} -> {result.compressed_count}")
    """
    
    def __init__(
        self,
        strategy: CompressionStrategy = CompressionStrategy.IMPORTANCE,
        importance_threshold: float = 0.3,
        max_age_seconds: float = 7 * 24 * 3600,  # 7 天
        summarizer: Optional[Callable[[str], str]] = None,
    ):
        self._strategy = strategy
        self._importance_threshold = importance_threshold
        self._max_age = max_age_seconds
        self._summarizer = summarizer
    
    def compress(
        self,
        memories: list[dict],
        content_key: str = "content",
        importance_key: str = "importance",
        timestamp_key: str = "timestamp",
        id_key: str = "id",
    ) -> CompressionResult:
        """
        压缩记忆列表
        
        Args:
            memories: 记忆列表
            content_key: 内容字段名
            importance_key: 重要性字段名
            timestamp_key: 时间戳字段名
            id_key: ID 字段名
            
        Returns:
            CompressionResult
        """
        original_count = len(memories)
        now = time.time()
        keep = []
        removed_ids = []
        
        for mem in memories:
            should_keep = self._should_keep(
                mem, now, importance_key, timestamp_key
            )
            if should_keep:
                keep.append(mem)
            else:
                removed_ids.append(mem.get(id_key, ""))
        
        return CompressionResult(
            original_count=original_count,
            compressed_count=len(keep),
            removed_ids=removed_ids,
        )
    
    def _should_keep(
        self,
        mem: dict,
        now: float,
        importance_key: str,
        timestamp_key: str,
    ) -> bool:
        """判断是否保留"""
        importance = mem.get(importance_key, 0.5)
        timestamp = mem.get(timestamp_key, now)
        age = now - timestamp
        
        if self._strategy == CompressionStrategy.IMPORTANCE:
            return importance >= self._importance_threshold
        
        elif self._strategy == CompressionStrategy.RECENCY:
            return age <= self._max_age
        
        elif self._strategy == CompressionStrategy.HYBRID:
            # 重要性高 或 时间新 则保留
            if importance >= self._importance_threshold:
                return True
            if age <= self._max_age:
                return True
            return False
        
        return True
    
    def summarize(self, texts: list[str]) -> Optional[str]:
        """
        摘要多个文本
        
        Args:
            texts: 文本列表
            
        Returns:
            摘要文本
        """
        if self._summarizer is None:
            # 简单拼接摘要
            total_len = sum(len(t) for t in texts)
            return f"[{len(texts)} memories, {total_len} chars total]"
        
        combined = "\n---\n".join(texts)
        return self._summarizer(combined)
    
    def compress_with_summary(
        self,
        memories: list[dict],
        content_key: str = "content",
    ) -> tuple[list[dict], CompressionResult]:
        """
        压缩并生成摘要
        
        Returns:
            (保留的记忆列表, 压缩结果)
        """
        result = self.compress(memories)
        
        # 生成摘要
        if result.removed_ids and self._summarizer:
            removed_contents = [
                m.get(content_key, "")
                for m in memories
                if m.get("id") in result.removed_ids
            ]
            result.summary = self.summarize(removed_contents)
        
        keep = [m for m in memories if m.get("id") not in result.removed_ids]
        return keep, result
    
    def get_stats(self) -> dict:
        """获取压缩器统计"""
        return {
            "strategy": self._strategy.value,
            "importance_threshold": self._importance_threshold,
            "max_age_seconds": self._max_age,
            "has_summarizer": self._summarizer is not None,
        }


def simple_summarizer(text: str, max_length: int = 200) -> str:
    """简单摘要器 - 截断"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


__all__ = [
    "MemoryCompressor",
    "CompressionStrategy",
    "CompressionResult",
    "simple_summarizer",
]
