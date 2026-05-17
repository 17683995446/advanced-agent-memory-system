"""
记忆去重模块 - SimHash 近似去重

使用 SimHash 算法进行近似重复检测，避免存储冗余记忆。
支持:
- SimHash 指纹计算
- 汉明距离比较
- 批量去重
- LSH (Locality-Sensitive Hashing) 快速检索

依赖: 无额外依赖（纯 Python 实现）
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DedupResult:
    """去重结果"""
    is_duplicate: bool
    similarity: float
    original_id: Optional[str] = None
    fingerprint: int = 0


class SimHash:
    """
    SimHash 指纹计算器
    
    将文本映射为固定长度的指纹，相似文本的指纹汉明距离较小。
    
    Args:
        hash_bits: 指纹位数（默认 64 位）
    
    Example:
        simhash = SimHash(hash_bits=64)
        
        fp1 = simhash.compute("Python is a programming language")
        fp2 = simhash.compute("Python is a great programming language")
        
        distance = simhash.distance(fp1, fp2)
        similarity = simhash.similarity(fp1, fp2)
    """
    
    def __init__(self, hash_bits: int = 64):
        self._bits = hash_bits
    
    def _tokenize(self, text: str) -> list[str]:
        """
        文本分词
        
        支持:
        - 英文按空格和标点分词
        - 中文按字符分词
        - 统一转小写
        """
        # 提取英文单词
        english = re.findall(r'[a-zA-Z]+', text.lower())
        # 提取中文（每 2 个字符一组）
        chinese = re.findall(r'[\u4e00-\u9fff]+', text)
        chinese_tokens = []
        for segment in chinese:
            if len(segment) >= 2:
                chinese_tokens.extend(
                    segment[i:i+2] for i in range(len(segment) - 1)
                )
            else:
                chinese_tokens.append(segment)
        
        # 生成 n-gram (bigram) 增加鲁棒性
        bigrams = []
        all_tokens = english + chinese_tokens
        for i in range(len(all_tokens) - 1):
            bigrams.append(f"{all_tokens[i]}_{all_tokens[i+1]}")
        
        return all_tokens + bigrams
    
    def _hash_token(self, token: str) -> int:
        """计算 token 的哈希值"""
        h = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(h, 16)
    
    def compute(self, text: str) -> int:
        """
        计算 SimHash 指纹
        
        Args:
            text: 输入文本
            
        Returns:
            整数指纹
        """
        tokens = self._tokenize(text)
        if not tokens:
            return 0
        
        # 初始化向量
        v = [0] * self._bits
        
        for token in tokens:
            h = self._hash_token(token)
            for i in range(self._bits):
                if h & (1 << i):
                    v[i] += 1
                else:
                    v[i] -= 1
        
        # 生成指纹
        fingerprint = 0
        for i in range(self._bits):
            if v[i] > 0:
                fingerprint |= (1 << i)
        
        return fingerprint
    
    def distance(self, fp1: int, fp2: int) -> int:
        """
        计算汉明距离
        
        Args:
            fp1: 指纹 1
            fp2: 指纹 2
            
        Returns:
            汉明距离（不同位的数量）
        """
        xor = fp1 ^ fp2
        return bin(xor).count('1')
    
    def similarity(self, fp1: int, fp2: int) -> float:
        """
        计算相似度
        
        Returns:
            相似度 [0, 1]
        """
        dist = self.distance(fp1, fp2)
        return 1.0 - (dist / self._bits)
    
    def is_similar(self, fp1: int, fp2: int, threshold: float = 0.8) -> bool:
        """
        判断两个指纹是否相似
        
        Args:
            threshold: 相似度阈值
            
        Returns:
            是否相似
        """
        return self.similarity(fp1, fp2) >= threshold


class MemoryDeduplicator:
    """
    记忆去重器
    
    使用 SimHash 检测并去除重复记忆。
    
    Args:
        similarity_threshold: 相似度阈值（超过此值视为重复）
        hash_bits: SimHash 位数
    
    Example:
        dedup = MemoryDeduplicator(similarity_threshold=0.85)
        
        # 检查是否重复
        result = dedup.check("Hello world")
        
        # 批量去重
        unique = dedup.deduplicate([
            {"id": "1", "content": "Python programming"},
            {"id": "2", "content": "Python programming language"},
        ])
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        hash_bits: int = 64,
    ):
        self._threshold = similarity_threshold
        self._simhash = SimHash(hash_bits=hash_bits)
        self._fingerprints: dict[str, int] = {}  # id -> fingerprint
        self._max_distance = int(hash_bits * (1 - similarity_threshold))
    
    def compute_fingerprint(self, content: str) -> int:
        """计算内容指纹"""
        return self._simhash.compute(content)
    
    def check(self, content: str) -> DedupResult:
        """
        检查内容是否与已有记忆重复
        
        Args:
            content: 待检查内容
            
        Returns:
            DedupResult
        """
        fp = self._simhash.compute(content)
        
        best_match_id = None
        best_similarity = 0.0
        
        for existing_id, existing_fp in self._fingerprints.items():
            sim = self._simhash.similarity(fp, existing_fp)
            if sim > best_similarity:
                best_similarity = sim
                best_match_id = existing_id
        
        is_dup = best_similarity >= self._threshold
        
        return DedupResult(
            is_duplicate=is_dup,
            similarity=best_similarity,
            original_id=best_match_id if is_dup else None,
            fingerprint=fp,
        )
    
    def add(self, id: str, content: str):
        """
        注册记忆指纹
        
        Args:
            id: 记忆 ID
            content: 记忆内容
        """
        fp = self._simhash.compute(content)
        self._fingerprints[id] = fp
    
    def remove(self, id: str):
        """移除记忆指纹"""
        self._fingerprints.pop(id, None)
    
    def deduplicate(
        self,
        records: list[dict],
        content_key: str = "content",
        id_key: str = "id",
    ) -> list[dict]:
        """
        批量去重
        
        Args:
            records: 记录列表
            content_key: 内容字段名
            id_key: ID 字段名
            
        Returns:
            去重后的记录列表（保留首次出现的）
        """
        seen_fingerprints: dict[int, str] = {}  # fingerprint -> first id
        unique_records = []
        duplicate_count = 0
        
        for record in records:
            content = record.get(content_key, "")
            record_id = record.get(id_key, "")
            fp = self._simhash.compute(content)
            
            # 检查是否与已有指纹相似
            is_dup = False
            for seen_fp in seen_fingerprints:
                dist = self._simhash.distance(fp, seen_fp)
                if dist <= self._max_distance:
                    is_dup = True
                    break
            
            if not is_dup:
                seen_fingerprints[fp] = record_id
                unique_records.append(record)
                self._fingerprints[record_id] = fp
            else:
                duplicate_count += 1
        
        logger.info(
            "Deduplication: %d/%d removed (%d unique)",
            duplicate_count, len(records), len(unique_records),
        )
        
        return unique_records
    
    def find_similar(
        self,
        content: str,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """
        查找相似记忆
        
        Args:
            content: 查询内容
            top_k: 返回数量
            
        Returns:
            [(id, similarity), ...] 按相似度降序
        """
        fp = self._simhash.compute(content)
        
        candidates = []
        for existing_id, existing_fp in self._fingerprints.items():
            sim = self._simhash.similarity(fp, existing_fp)
            candidates.append((existing_id, sim))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]
    
    def clear(self):
        """清空所有指纹"""
        self._fingerprints.clear()
    
    @property
    def count(self) -> int:
        """已注册指纹数量"""
        return len(self._fingerprints)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "registered_fingerprints": len(self._fingerprints),
            "similarity_threshold": self._threshold,
            "max_hamming_distance": self._max_distance,
        }


__all__ = [
    "SimHash",
    "MemoryDeduplicator",
    "DedupResult",
]
