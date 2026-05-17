"""
记忆重要性评分模块

使用多种算法计算记忆的重要性分数，用于：
- 记忆淘汰决策
- 检索结果排序
- 记忆整合优先级

算法:
- TF-IDF 重要性: 基于内容关键词频率
- 时间衰减: 越新的记忆越重要
- 访问频率: 被访问越多越重要
- 混合评分: 加权组合以上因素
"""

from __future__ import annotations

import math
import re
import time
import logging
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ScoringStrategy(Enum):
    """评分策略"""
    TFIDF = "tfidf"           # 基于关键词频率
    RECENCY = "recency"       # 基于时间衰减
    ACCESS = "access"         # 基于访问频率
    HYBRID = "hybrid"         # 混合评分（默认）


@dataclass
class ImportanceScore:
    """重要性评分结果"""
    score: float
    components: dict = None  # 各维度分值明细
    
    def __post_init__(self):
        if self.components is None:
            self.components = {}
    
    def to_dict(self) -> dict:
        return {"score": self.score, "components": self.components}


class ImportanceScorer:
    """
    记忆重要性评分器
    
    支持多种评分策略，可灵活配置权重。
    
    Args:
        strategy: 评分策略
        recency_half_life: 时间衰减半衰期（秒），默认 7 天
        tfidf_corpus_size: TF-IDF 语料库大小估计
        weights: 混合评分权重 {"recency": 0.3, "access": 0.2, "tfidf": 0.5}
    
    Example:
        scorer = ImportanceScorer(strategy=ScoringStrategy.HYBRID)
        
        score = scorer.score(
            content="Python is a programming language",
            access_count=10,
            created_at=time.time() - 3600,  # 1 小时前
        )
        print(f"Importance: {score.score:.3f}")
    """
    
    def __init__(
        self,
        strategy: ScoringStrategy = ScoringStrategy.HYBRID,
        recency_half_life: float = 604800.0,  # 7 天
        tfidf_corpus_size: int = 1000,
        weights: Optional[dict] = None,
    ):
        self._strategy = strategy
        self._half_life = recency_half_life
        self._corpus_size = tfidf_corpus_size
        self._weights = weights or {
            "recency": 0.3,
            "access": 0.2,
            "tfidf": 0.5,
        }
        
        # 内置 IDF 语料（常见英文停用词 + 中文常见词）
        self._idf_corpus: Counter = Counter()
        self._total_docs = 0
    
    def add_to_corpus(self, documents: list[str]):
        """
        添加文档到 IDF 语料库
        
        Args:
            documents: 文档列表
        """
        for doc in documents:
            words = set(self._tokenize(doc))
            self._idf_corpus.update(words)
            self._total_docs += 1
    
    def _tokenize(self, text: str) -> list[str]:
        """分词（优先使用chinese_english_tokenizer，回退到内置实现）"""
        try:
            from memory_system.processing.chinese_english_tokenizer import tokenize
            return tokenize(text)
        except ImportError:
            import re
            english_words = re.findall(r'[a-zA-Z]+', text.lower())
            chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
            chinese_words = [text[i:i+2] for i in range(0, len(chinese_chars) - 1, 2)] if chinese_chars else []
            return english_words + chinese_words
    
    def _compute_tfidf(self, content: str) -> float:
        """
        计算 TF-IDF 重要性分数
        
        Returns:
            归一化到 [0, 1] 的分数
        """
        words = self._tokenize(content)
        if not words:
            return 0.0
        
        # TF: 词频
        word_counts = Counter(words)
        total_words = len(words)
        tf_scores = {w: c / total_words for w, c in word_counts.items()}
        
        # IDF: 逆文档频率
        idf_sum = 0.0
        for word in word_counts:
            if self._total_docs > 0:
                doc_freq = self._idf_corpus.get(word, 1)
                idf = math.log((self._total_docs + 1) / (doc_freq + 1)) + 1
            else:
                idf = 1.0
            idf_sum += tf_scores[word] * idf
        
        # 归一化
        max_possible = len(word_counts) * 2.0  # 理论最大值
        return min(idf_sum / max_possible, 1.0) if max_possible > 0 else 0.0
    
    def _compute_recency(self, created_at: float, now: Optional[float] = None) -> float:
        """
        计算时间衰减分数
        
        使用指数衰减: score = 2^(-age/half_life)
        
        Returns:
            归一化到 [0, 1] 的分数
        """
        now = now or time.time()
        age = now - created_at
        
        if age <= 0:
            return 1.0
        
        decay = math.pow(2, -age / self._half_life)
        return max(0.0, min(1.0, decay))
    
    def _compute_access(self, access_count: int) -> float:
        """
        计算访问频率分数
        
        使用对数缩放: score = log(1 + count) / log(1 + max_expected)
        
        Returns:
            归一化到 [0, 1] 的分数
        """
        if access_count <= 0:
            return 0.0
        
        # 假设最大期望访问次数为 100
        max_expected = 100
        score = math.log(1 + access_count) / math.log(1 + max_expected)
        return max(0.0, min(1.0, score))
    
    def score(
        self,
        content: str,
        access_count: int = 0,
        created_at: Optional[float] = None,
        metadata: Optional[dict] = None,
        now: Optional[float] = None,
    ) -> ImportanceScore:
        """
        计算记忆重要性分数
        
        Args:
            content: 记忆内容
            access_count: 访问次数
            created_at: 创建时间戳
            metadata: 元数据（可包含自定义重要性因子）
            now: 当前时间戳
            
        Returns:
            ImportanceScore 对象
        """
        created_at = created_at or time.time()
        now = now or time.time()
        metadata = metadata or {}
        
        if self._strategy == ScoringStrategy.TFIDF:
            tfidf = self._compute_tfidf(content)
            return ImportanceScore(score=tfidf, components={"tfidf": tfidf})
        
        elif self._strategy == ScoringStrategy.RECENCY:
            recency = self._compute_recency(created_at, now)
            return ImportanceScore(score=recency, components={"recency": recency})
        
        elif self._strategy == ScoringStrategy.ACCESS:
            access = self._compute_access(access_count)
            return ImportanceScore(score=access, components={"access": access})
        
        else:  # HYBRID
            tfidf = self._compute_tfidf(content)
            recency = self._compute_recency(created_at, now)
            access = self._compute_access(access_count)
            
            # 加权组合
            w = self._weights
            final_score = (
                w.get("tfidf", 0.5) * tfidf +
                w.get("recency", 0.3) * recency +
                w.get("access", 0.2) * access
            )
            
            # 元数据中的重要性因子
            meta_factor = metadata.get("importance_factor", 1.0)
            final_score *= meta_factor
            
            final_score = max(0.0, min(1.0, final_score))
            
            return ImportanceScore(
                score=final_score,
                components={
                    "tfidf": tfidf,
                    "recency": recency,
                    "access": access,
                    "meta_factor": meta_factor,
                },
            )
    
    def score_batch(
        self,
        records: list[dict],
    ) -> list[ImportanceScore]:
        """
        批量计算重要性分数
        
        Args:
            records: 记录列表，每个记录需包含 content, access_count, timestamp
            
        Returns:
            ImportanceScore 列表
        """
        # 先构建 IDF 语料
        self.add_to_corpus([r.get("content", "") for r in records])
        
        return [
            self.score(
                content=r.get("content", ""),
                access_count=r.get("access_count", 0),
                created_at=r.get("timestamp", r.get("created_at")),
                metadata=r.get("metadata", {}),
            )
            for r in records
        ]
    
    def rank(
        self,
        records: list[dict],
        top_k: Optional[int] = None,
    ) -> list[tuple[dict, ImportanceScore]]:
        """
        按重要性排序记录
        
        Args:
            records: 记录列表
            top_k: 返回前 k 个，None 表示返回全部
            
        Returns:
            (record, score) 元组列表，按分数降序
        """
        scored = list(zip(records, self.score_batch(records)))
        scored.sort(key=lambda x: x[1].score, reverse=True)
        
        if top_k is not None:
            scored = scored[:top_k]
        
        return scored


__all__ = [
    "ImportanceScorer",
    "ImportanceScore",
    "ScoringStrategy",
]
