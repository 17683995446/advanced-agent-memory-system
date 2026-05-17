"""
工具函数模块

提供跨模块共享的工具函数和常量。
"""

from memory_system.utils.similarity import calculate_similarity, jaccard_similarity
from memory_system.utils.text_processing import extract_keywords, tokenize, normalize_text
from memory_system.utils.constants import (
    CompressionConstants,
    ConflictConstants,
    TimeConstants,
    InferenceConstants,
)

__all__ = [
    # 相似度计算
    "calculate_similarity",
    "jaccard_similarity",
    # 文本处理
    "extract_keywords",
    "tokenize",
    "normalize_text",
    # 常量
    "CompressionConstants",
    "ConflictConstants",
    "TimeConstants",
    "InferenceConstants",
]
