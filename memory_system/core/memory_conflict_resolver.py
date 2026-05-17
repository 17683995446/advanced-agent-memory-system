"""
记忆冲突检测与解决机制

自动检测矛盾记忆、提供解决策略、维护记忆一致性。
支持多种冲突类型：事实矛盾、时间冲突、来源冲突。
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


class ConflictType(Enum):
    """冲突类型枚举"""
    FACTUAL = "factual"          # 事实矛盾
    TEMPORAL = "temporal"        # 时间冲突
    SOURCE = "source"            # 来源冲突
    SEMANTIC = "semantic"        # 语义矛盾


class ResolutionStrategy(Enum):
    """解决策略枚举"""
    KEEP_NEWER = "newer"         # 保留较新的
    KEEP_OLDER = "older"         # 保留较旧的
    KEEP_HIGHER_IMPORTANCE = "importance"  # 保留重要性高的
    MERGE = "merge"              # 合并
    MANUAL = "manual"            # 手动解决
    DELETE_BOTH = "delete_both"  # 删除两者


@dataclass
class ConflictConfig:
    """冲突检测配置"""
    # 检测阈值
    similarity_threshold: float = 0.7      # 相似度阈值（可能是冲突）
    contradiction_threshold: float = 0.8   # 矛盾度阈值（确认冲突）
    
    # 自动解决
    auto_resolve: bool = False             # 是否自动解决
    default_strategy: ResolutionStrategy = ResolutionStrategy.KEEP_NEWER
    
    # 回调
    on_conflict_detected: Optional[Callable[["Conflict"], None]] = None
    on_conflict_resolved: Optional[Callable[["Conflict", ResolutionStrategy], None]] = None


@dataclass
class Conflict:
    """冲突记录"""
    conflict_id: str
    conflict_type: ConflictType
    memory_ids: list[str]                  # 冲突的记忆ID列表
    description: str                       # 冲突描述
    detected_at: float                     # 检测时间
    resolved: bool = False
    resolution_strategy: Optional[ResolutionStrategy] = None
    resolution_result: Optional[str] = None


@dataclass
class ConflictResult:
    """冲突检测结果"""
    conflicts_found: list[Conflict] = field(default_factory=list)
    auto_resolved: list[Conflict] = field(default_factory=list)
    manual_review: list[Conflict] = field(default_factory=list)
    duration_ms: float = 0.0


class MemoryConflictResolver:
    """
    记忆冲突解决器
    
    提供智能冲突检测和解决功能：
    1. 事实矛盾检测 - 识别相互矛盾的事实陈述
    2. 时间冲突检测 - 识别时间线不一致
    3. 来源冲突检测 - 识别来源矛盾
    4. 语义矛盾检测 - 识别语义相似但结论相反的内容
    
    Example:
        resolver = MemoryConflictResolver(config=ConflictConfig())
        result = resolver.detect_conflicts(memory_list)
        resolver.resolve_conflict(result.conflicts_found[0], ResolutionStrategy.KEEP_NEWER)
    """
    
    def __init__(self, config: Optional[ConflictConfig] = None):
        self.config = config or ConflictConfig()
        self._conflict_history: list[Conflict] = []
        self._resolution_history: list[tuple[Conflict, ResolutionStrategy]] = []
    
    def detect_conflicts(
        self,
        memories: list[Any],
        conflict_types: Optional[list[ConflictType]] = None,
    ) -> ConflictResult:
        """
        检测记忆冲突
        
        Args:
            memories: 记忆记录列表
            conflict_types: 要检测的冲突类型，None表示全部
            
        Returns:
            ConflictResult 冲突检测结果
        """
        start_time = time.time()
        
        if len(memories) < 2:
            return ConflictResult()
        
        conflict_types = conflict_types or list(ConflictType)
        result = ConflictResult()
        
        # 检测各类冲突
        if ConflictType.FACTUAL in conflict_types:
            factual_conflicts = self._detect_factual_conflicts(memories)
            result.conflicts_found.extend(factual_conflicts)
        
        if ConflictType.TEMPORAL in conflict_types:
            temporal_conflicts = self._detect_temporal_conflicts(memories)
            result.conflicts_found.extend(temporal_conflicts)
        
        if ConflictType.SOURCE in conflict_types:
            source_conflicts = self._detect_source_conflicts(memories)
            result.conflicts_found.extend(source_conflicts)
        
        if ConflictType.SEMANTIC in conflict_types:
            semantic_conflicts = self._detect_semantic_conflicts(memories)
            result.conflicts_found.extend(semantic_conflicts)
        
        # 去重（同一对记忆可能有多种冲突）
        result.conflicts_found = self._deduplicate_conflicts(result.conflicts_found)
        
        # 自动解决
        if self.config.auto_resolve:
            for conflict in result.conflicts_found:
                if self._can_auto_resolve(conflict):
                    self.resolve_conflict(conflict, self.config.default_strategy)
                    result.auto_resolved.append(conflict)
                else:
                    result.manual_review.append(conflict)
        else:
            result.manual_review = result.conflicts_found.copy()
        
        result.duration_ms = (time.time() - start_time) * 1000

        # 记录到历史
        self._conflict_history.extend(result.conflicts_found)

        # 触发回调
        for conflict in result.conflicts_found:
            if self.config.on_conflict_detected:
                self.config.on_conflict_detected(conflict)

        logger.info("Conflict detection complete: found=%d, auto_resolved=%d, manual=%d",
                   len(result.conflicts_found), len(result.auto_resolved), len(result.manual_review))

        return result
    
    def _detect_factual_conflicts(self, memories: list[Any]) -> list[Conflict]:
        """检测事实矛盾"""
        conflicts = []
        
        # 基于关键词的冲突检测
        for i, mem1 in enumerate(memories):
            content1 = getattr(mem1, 'content', str(mem1)).lower()
            id1 = getattr(mem1, 'id', str(i))
            
            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                content2 = getattr(mem2, 'content', str(mem2)).lower()
                id2 = getattr(mem2, 'id', str(j))
                
                # 检查是否包含矛盾关键词
                contradiction_score = self._calculate_contradiction(content1, content2)
                
                if contradiction_score >= self.config.contradiction_threshold:
                    conflict = Conflict(
                        conflict_id=f"fact_{id1}_{id2}",
                        conflict_type=ConflictType.FACTUAL,
                        memory_ids=[id1, id2],
                        description=f"事实矛盾: '{content1[:50]}...' vs '{content2[:50]}...'",
                        detected_at=time.time(),
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _detect_temporal_conflicts(self, memories: list[Any]) -> list[Conflict]:
        """检测时间冲突"""
        conflicts = []
        
        # 提取时间信息并检查冲突
        for i, mem1 in enumerate(memories):
            content1 = getattr(mem1, 'content', str(mem1))
            id1 = getattr(mem1, 'id', str(i))
            ts1 = getattr(mem1, 'timestamp', 0)
            
            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                content2 = getattr(mem2, 'content', str(mem2))
                id2 = getattr(mem2, 'id', str(j))
                ts2 = getattr(mem2, 'timestamp', 0)
                
                # 检查时间线矛盾（例如同一事件不同时间）
                if self._has_temporal_contradiction(content1, content2, ts1, ts2):
                    conflict = Conflict(
                        conflict_id=f"temp_{id1}_{id2}",
                        conflict_type=ConflictType.TEMPORAL,
                        memory_ids=[id1, id2],
                        description=f"时间冲突: 时间戳 {ts1} vs {ts2}",
                        detected_at=time.time(),
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _detect_source_conflicts(self, memories: list[Any]) -> list[Conflict]:
        """检测来源冲突"""
        conflicts = []
        
        for i, mem1 in enumerate(memories):
            content1 = getattr(mem1, 'content', str(mem1))
            id1 = getattr(mem1, 'id', str(i))
            source1 = getattr(mem1, 'source', 'unknown')
            
            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                content2 = getattr(mem2, 'content', str(mem2))
                id2 = getattr(mem2, 'id', str(j))
                source2 = getattr(mem2, 'source', 'unknown')
                
                # 内容相似但来源不同
                sim = self._calculate_similarity(content1, content2)
                if sim >= self.config.similarity_threshold and source1 != source2:
                    conflict = Conflict(
                        conflict_id=f"src_{id1}_{id2}",
                        conflict_type=ConflictType.SOURCE,
                        memory_ids=[id1, id2],
                        description=f"来源冲突: '{source1}' vs '{source2}'",
                        detected_at=time.time(),
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _detect_semantic_conflicts(self, memories: list[Any]) -> list[Conflict]:
        """检测语义矛盾"""
        conflicts = []
        
        # 检测语义相似但结论相反的内容
        negation_words = ['不', '没', '无', '非', 'not', 'no', 'never', "don't", "doesn't"]
        
        for i, mem1 in enumerate(memories):
            content1 = getattr(mem1, 'content', str(mem1)).lower()
            id1 = getattr(mem1, 'id', str(i))
            
            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                content2 = getattr(mem2, 'content', str(mem2)).lower()
                id2 = getattr(mem2, 'id', str(j))
                
                # 检查是否一个包含否定词而另一个不包含
                has_neg1 = any(w in content1 for w in negation_words)
                has_neg2 = any(w in content2 for w in negation_words)
                
                # 语义相似但否定状态不同
                sim = self._calculate_similarity(content1, content2)
                if sim >= self.config.similarity_threshold and has_neg1 != has_neg2:
                    conflict = Conflict(
                        conflict_id=f"sem_{id1}_{id2}",
                        conflict_type=ConflictType.SEMANTIC,
                        memory_ids=[id1, id2],
                        description=f"语义矛盾: 否定状态不同",
                        detected_at=time.time(),
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _calculate_contradiction(self, content1: str, content2: str) -> float:
        """计算两个内容的矛盾度"""
        # 矛盾关键词对
        contradiction_pairs = [
            ('是', '不是'), ('有', '没有'), ('可以', '不可以'),
            ('true', 'false'), ('yes', 'no'), ('can', 'cannot'),
            ('支持', '不支持'), ('启用', '禁用'), ('开启', '关闭'),
        ]
        
        score = 0.0
        for pos, neg in contradiction_pairs:
            if (pos in content1 and neg in content2) or (neg in content1 and pos in content2):
                score += 0.25
        
        return min(score, 1.0)
    
    def _has_temporal_contradiction(self, content1: str, content2: str, ts1: float, ts2: float) -> bool:
        """检查是否有时间矛盾"""
        # 提取时间相关关键词
        time_keywords = ['今天', '昨天', '明天', '现在', '之前', '之后', 'today', 'yesterday', 'tomorrow']
        
        has_time1 = any(kw in content1 for kw in time_keywords)
        has_time2 = any(kw in content2 for kw in time_keywords)
        
        # 如果都包含时间信息但时间戳相差很大
        if has_time1 and has_time2 and abs(ts1 - ts2) > 86400:  # 超过1天
            return True
        
        return False
    
    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """计算内容相似度（简单版本）"""
        words1 = set(re.findall(r'\b\w{2,}\b', content1.lower()))
        words2 = set(re.findall(r'\b\w{2,}\b', content2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _deduplicate_conflicts(self, conflicts: list[Conflict]) -> list[Conflict]:
        """去重冲突（基于记忆ID组合）"""
        seen = set()
        unique = []
        
        for conflict in conflicts:
            key = tuple(sorted(conflict.memory_ids))
            if key not in seen:
                seen.add(key)
                unique.append(conflict)
        
        return unique
    
    def _can_auto_resolve(self, conflict: Conflict) -> bool:
        """判断是否可以自动解决"""
        # 事实矛盾和时间冲突通常需要人工判断
        if conflict.conflict_type in [ConflictType.FACTUAL, ConflictType.TEMPORAL]:
            return False
        return True
    
    def resolve_conflict(
        self,
        conflict: Conflict,
        strategy: ResolutionStrategy,
        memories: Optional[list[Any]] = None,
    ) -> Optional[str]:
        """
        解决冲突
        
        Args:
            conflict: 要解决的冲突
            strategy: 解决策略
            memories: 完整的记忆列表（用于查找记忆详情）
            
        Returns:
            解决结果的描述
        """
        if conflict.resolved:
            return conflict.resolution_result
        
        result = None
        
        if strategy == ResolutionStrategy.KEEP_NEWER:
            result = self._resolve_keep_newer(conflict, memories)
        elif strategy == ResolutionStrategy.KEEP_OLDER:
            result = self._resolve_keep_older(conflict, memories)
        elif strategy == ResolutionStrategy.KEEP_HIGHER_IMPORTANCE:
            result = self._resolve_keep_importance(conflict, memories)
        elif strategy == ResolutionStrategy.MERGE:
            result = self._resolve_merge(conflict, memories)
        elif strategy == ResolutionStrategy.DELETE_BOTH:
            result = "Both memories marked for deletion"
        elif strategy == ResolutionStrategy.MANUAL:
            result = "Pending manual review"
        
        conflict.resolved = True
        conflict.resolution_strategy = strategy
        conflict.resolution_result = result
        
        self._resolution_history.append((conflict, strategy))
        
        if self.config.on_conflict_resolved:
            self.config.on_conflict_resolved(conflict, strategy)
        
        return result
    
    def _resolve_keep_newer(self, conflict: Conflict, memories: Optional[list[Any]]) -> str:
        """保留较新的记忆"""
        if not memories:
            return "Keep newer (no memory details available)"
        
        mem_dict = {getattr(m, 'id', str(i)): m for i, m in enumerate(memories)}
        
        newest_id = None
        newest_time = 0
        for mem_id in conflict.memory_ids:
            mem = mem_dict.get(mem_id)
            if mem:
                ts = getattr(mem, 'timestamp', 0)
                if ts > newest_time:
                    newest_time = ts
                    newest_id = mem_id
        
        return f"Keep memory {newest_id} (newest)" if newest_id else "Keep newer"
    
    def _resolve_keep_older(self, conflict: Conflict, memories: Optional[list[Any]]) -> str:
        """保留较旧的记忆"""
        if not memories:
            return "Keep older (no memory details available)"
        
        mem_dict = {getattr(m, 'id', str(i)): m for i, m in enumerate(memories)}
        
        oldest_id = None
        oldest_time = float('inf')
        for mem_id in conflict.memory_ids:
            mem = mem_dict.get(mem_id)
            if mem:
                ts = getattr(mem, 'timestamp', float('inf'))
                if ts < oldest_time:
                    oldest_time = ts
                    oldest_id = mem_id
        
        return f"Keep memory {oldest_id} (oldest)" if oldest_id else "Keep older"
    
    def _resolve_keep_importance(self, conflict: Conflict, memories: Optional[list[Any]]) -> str:
        """保留重要性高的记忆"""
        if not memories:
            return "Keep higher importance (no memory details available)"
        
        mem_dict = {getattr(m, 'id', str(i)): m for i, m in enumerate(memories)}
        
        best_id = None
        best_importance = -1
        for mem_id in conflict.memory_ids:
            mem = mem_dict.get(mem_id)
            if mem:
                imp = getattr(mem, 'importance', 0.5)
                if imp > best_importance:
                    best_importance = imp
                    best_id = mem_id
        
        return f"Keep memory {best_id} (importance={best_importance:.2f})" if best_id else "Keep higher importance"
    
    def _resolve_merge(self, conflict: Conflict, memories: Optional[list[Any]]) -> str:
        """合并记忆"""
        return f"Merge memories {conflict.memory_ids}"
    
    def get_statistics(self) -> dict[str, Any]:
        """获取冲突解决器统计信息"""
        return {
            "total_conflicts_detected": len(self._conflict_history),
            "total_resolved": len(self._resolution_history),
            "by_type": {
                ct.value: sum(1 for c in self._conflict_history if c.conflict_type == ct)
                for ct in ConflictType
            },
            "by_strategy": {
                rs.value: sum(1 for _, rs in self._resolution_history if rs == rs)
                for rs in ResolutionStrategy
            },
        }


__all__ = [
    "MemoryConflictResolver",
    "ConflictConfig",
    "Conflict",
    "ConflictResult",
    "ConflictType",
    "ResolutionStrategy",
]