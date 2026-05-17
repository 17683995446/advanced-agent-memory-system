"""
智能记忆压缩与摘要系统

自动检测冗余记忆、生成摘要、压缩存储，优化长期记忆的存储效率。
支持多种压缩策略：摘要生成、相似合并、过期清理。
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """压缩策略枚举"""
    SUMMARIZE = "summarize"      # 生成摘要
    MERGE_SIMILAR = "merge"      # 合并相似记忆
    REMOVE_DUPLICATES = "dedup"  # 去重
    EXPIRE_OLD = "expire"        # 过期清理


@dataclass
class CompressionConfig:
    """压缩配置"""
    # 触发阈值
    min_memories_to_compress: int = 100      # 最少记忆数才触发压缩
    similarity_threshold: float = 0.85       # 相似度阈值
    
    # 摘要配置
    max_summary_length: int = 200            # 摘要最大长度
    min_content_length_to_summarize: int = 500  # 超过此长度才摘要
    
    # 过期配置
    max_age_days: int = 90                   # 最大保留天数
    low_importance_decay_days: int = 30      # 低重要性记忆衰减天数
    
    # 自动压缩
    auto_compress: bool = False              # 是否自动压缩
    compress_interval_hours: int = 24        # 自动压缩间隔
    
    # 回调
    on_compress_callback: Optional[Callable[[list[str]], None]] = None


@dataclass
class CompressionResult:
    """压缩结果"""
    compressed_count: int = 0
    removed_count: int = 0
    merged_groups: list[list[str]] = field(default_factory=list)
    summaries_generated: list[tuple[str, str]] = field(default_factory=list)  # (original_id, summary)
    saved_bytes_estimate: int = 0
    duration_ms: float = 0.0


class MemoryCompressionEngine:
    """
    记忆压缩引擎
    
    提供智能记忆压缩功能：
    1. 摘要生成 - 将长内容压缩为关键信息
    2. 相似合并 - 合并高度相似的记忆
    3. 去重清理 - 移除重复和过期记忆
    
    Example:
        engine = MemoryCompressionEngine(config=CompressionConfig())
        result = engine.compress_memories(memory_list)
    """
    
    def __init__(self, config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()
        self._compression_history: list[CompressionResult] = []
        self._last_compress_time: Optional[float] = None
    
    def compress_memories(
        self,
        memories: list[Any],
        strategies: Optional[list[CompressionStrategy]] = None,
    ) -> CompressionResult:
        """
        执行记忆压缩
        
        Args:
            memories: 记忆记录列表
            strategies: 要应用的压缩策略，None表示全部
            
        Returns:
            CompressionResult 压缩结果统计
        """
        start_time = time.time()
        
        if not memories:
            return CompressionResult()
        
        if len(memories) < self.config.min_memories_to_compress:
            logger.info("Memory count %d below threshold %d, skipping compression",
                       len(memories), self.config.min_memories_to_compress)
            return CompressionResult()
        
        strategies = strategies or list(CompressionStrategy)
        result = CompressionResult()
        
        working_memories = list(memories)
        
        # 按顺序应用各策略
        if CompressionStrategy.EXPIRE_OLD in strategies:
            expired, working_memories = self._remove_expired(working_memories)
            result.removed_count += len(expired)
        
        if CompressionStrategy.REMOVE_DUPLICATES in strategies:
            duplicates, working_memories = self._remove_duplicates(working_memories)
            result.removed_count += len(duplicates)
        
        if CompressionStrategy.MERGE_SIMILAR in strategies:
            merged, working_memories = self._merge_similar(working_memories)
            result.merged_groups.extend(merged)
            result.compressed_count += len(merged)
        
        if CompressionStrategy.SUMMARIZE in strategies:
            summaries, working_memories = self._generate_summaries(working_memories)
            result.summaries_generated.extend(summaries)
            result.compressed_count += len(summaries)
        
        result.duration_ms = (time.time() - start_time) * 1000
        result.saved_bytes_estimate = self._estimate_savings(memories, working_memories)
        
        self._compression_history.append(result)
        self._last_compress_time = time.time()
        
        if self.config.on_compress_callback:
            self.config.on_compress_callback([m.id for m in working_memories if hasattr(m, 'id')])
        
        logger.info("Compression complete: removed=%d, merged=%d, summarized=%d, saved=%d bytes",
                   result.removed_count, len(result.merged_groups),
                   len(result.summaries_generated), result.saved_bytes_estimate)
        
        return result
    
    def _remove_expired(self, memories: list[Any]) -> tuple[list[Any], list[Any]]:
        """移除过期记忆"""
        expired = []
        kept = []
        
        now = time.time()
        max_age_seconds = self.config.max_age_days * 24 * 3600
        decay_seconds = self.config.low_importance_decay_days * 24 * 3600
        
        for memory in memories:
            # 获取记忆的时间戳和重要性
            timestamp = getattr(memory, 'timestamp', now)
            importance = getattr(memory, 'importance', 0.5)
            
            age = now - timestamp
            
            # 高重要性记忆可以保留更久，低重要性更快过期
            if importance >= 0.7:
                effective_max_age = max_age_seconds * 2  # 高重要性：2倍保留期
            elif importance < 0.3:
                effective_max_age = decay_seconds  # 低重要性：短保留期
            else:
                effective_max_age = max_age_seconds  # 普通：标准保留期
            
            if age > effective_max_age:
                expired.append(memory)
            else:
                kept.append(memory)
        
        return expired, kept
    
    def _remove_duplicates(self, memories: list[Any]) -> tuple[list[Any], list[Any]]:
        """移除重复记忆（基于内容哈希）"""
        seen_hashes: set[str] = set()
        duplicates = []
        kept = []
        
        for memory in memories:
            content = getattr(memory, 'content', str(memory))
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            if content_hash in seen_hashes:
                duplicates.append(memory)
            else:
                seen_hashes.add(content_hash)
                kept.append(memory)
        
        return duplicates, kept
    
    def _merge_similar(self, memories: list[Any]) -> tuple[list[list[str]], list[Any]]:
        """合并相似记忆"""
        if len(memories) < 2:
            return [], memories
        
        merged_groups: list[list[str]] = []
        merged_ids: set[str] = set()
        kept = []
        
        # 简单的基于标签和类别的相似度计算
        for i, mem1 in enumerate(memories):
            mem1_id = getattr(mem1, 'id', str(i))
            if mem1_id in merged_ids:
                continue
            
            similar_group = [mem1_id]
            tags1 = set(getattr(mem1, 'tags', []))
            cat1 = getattr(mem1, 'category', '')
            
            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                mem2_id = getattr(mem2, 'id', str(j))
                if mem2_id in merged_ids:
                    continue
                
                tags2 = set(getattr(mem2, 'tags', []))
                cat2 = getattr(mem2, 'category', '')
                
                # 计算相似度
                similarity = self._calculate_similarity(tags1, cat1, tags2, cat2)
                
                if similarity >= self.config.similarity_threshold:
                    similar_group.append(mem2_id)
                    merged_ids.add(mem2_id)
            
            if len(similar_group) > 1:
                merged_groups.append(similar_group)
                merged_ids.add(mem1_id)
            else:
                kept.append(mem1)
        
        # 添加未被合并的记忆
        for mem in memories:
            mem_id = getattr(mem, 'id', None)
            if mem_id and mem_id not in merged_ids:
                kept.append(mem)
        
        return merged_groups, kept
    
    def _calculate_similarity(
        self,
        tags1: set[str],
        cat1: str,
        tags2: set[str],
        cat2: str,
    ) -> float:
        """计算两个记忆的相似度"""
        # 类别相同贡献0.5
        cat_sim = 0.5 if cat1 == cat2 else 0.0
        
        # 标签Jaccard相似度贡献0.5
        if tags1 or tags2:
            intersection = len(tags1 & tags2)
            union = len(tags1 | tags2)
            tag_sim = (intersection / union) * 0.5 if union > 0 else 0.0
        else:
            tag_sim = 0.0
        
        return cat_sim + tag_sim
    
    def _generate_summaries(self, memories: list[Any]) -> tuple[list[tuple[str, str]], list[Any]]:
        """为长记忆生成摘要"""
        summaries = []
        processed = []
        
        for memory in memories:
            content = getattr(memory, 'content', str(memory))
            mem_id = getattr(memory, 'id', str(id(memory)))
            
            if len(content) > self.config.min_content_length_to_summarize:
                summary = self._create_summary(content)
                summaries.append((mem_id, summary))
                # 创建压缩后的记忆对象（简化版）
                processed.append(memory)
            else:
                processed.append(memory)
        
        return summaries, processed
    
    def _create_summary(self, content: str) -> str:
        """
        创建内容摘要
        
        使用简单的提取式摘要：
        1. 提取关键句子（包含关键词）
        2. 限制总长度
        """
        # 分句
        sentences = re.split(r'[。！？.!?]', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if not sentences:
            return content[:self.config.max_summary_length] + "..."
        
        # 简单的关键词提取（频率最高的词）
        words = re.findall(r'\b\w{2,}\b', content.lower())
        word_freq = {}
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1
        
        # 按词频排序取前10个关键词
        keywords = set(sorted(word_freq.keys(), key=lambda x: word_freq[x], reverse=True)[:10])
        
        # 选择包含最多关键词的句子
        scored_sentences = []
        for sent in sentences[:5]:  # 只看前5句
            score = sum(1 for kw in keywords if kw in sent.lower())
            scored_sentences.append((score, sent))
        
        scored_sentences.sort(reverse=True)
        
        # 组合摘要
        summary_parts = []
        total_len = 0
        for score, sent in scored_sentences:
            if total_len + len(sent) > self.config.max_summary_length:
                break
            summary_parts.append(sent)
            total_len += len(sent)
        
        summary = "。".join(summary_parts)
        if len(summary) < 20 and sentences:
            summary = sentences[0][:self.config.max_summary_length]
        
        return summary + "..." if len(content) > self.config.max_summary_length else summary
    
    def _estimate_savings(self, original: list[Any], compressed: list[Any]) -> int:
        """估算节省的字节数"""
        original_size = sum(len(getattr(m, 'content', str(m))) for m in original)
        compressed_size = sum(len(getattr(m, 'content', str(m))) for m in compressed)
        return max(0, original_size - compressed_size)
    
    def should_compress(self, memory_count: int) -> bool:
        """判断是否应该执行压缩"""
        if memory_count < self.config.min_memories_to_compress:
            return False
        
        if not self.config.auto_compress:
            return False
        
        if self._last_compress_time is None:
            return True
        
        hours_since_last = (time.time() - self._last_compress_time) / 3600
        return hours_since_last >= self.config.compress_interval_hours
    
    def get_statistics(self) -> dict[str, Any]:
        """获取压缩引擎统计信息"""
        if not self._compression_history:
            return {
                "total_compressions": 0,
                "total_removed": 0,
                "total_saved_bytes": 0,
            }
        
        return {
            "total_compressions": len(self._compression_history),
            "total_removed": sum(r.removed_count for r in self._compression_history),
            "total_merged": sum(len(r.merged_groups) for r in self._compression_history),
            "total_summarized": sum(len(r.summaries_generated) for r in self._compression_history),
            "total_saved_bytes": sum(r.saved_bytes_estimate for r in self._compression_history),
            "avg_duration_ms": sum(r.duration_ms for r in self._compression_history) / len(self._compression_history),
            "last_compress_time": self._last_compress_time,
        }


__all__ = [
    "MemoryCompressionEngine",
    "CompressionConfig",
    "CompressionResult",
    "CompressionStrategy",
]