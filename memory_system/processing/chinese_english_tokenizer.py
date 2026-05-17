"""
文本分词模块

提供统一的文本分词接口，支持中文和英文。
使用 jieba 进行中文分词，英文按空格分词。
jieba 不可用时自动回退到简单分词。
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

# 尝试导入 jieba
try:
    import jieba
    _jieba_available = True
    logger.debug("jieba 分词库已加载")
except ImportError:
    _jieba_available = False
    logger.debug("jieba 未安装，使用简单分词回退")


def tokenize(text: str, language: str = "auto") -> List[str]:
    """
    对文本进行分词

    Args:
        text: 待分词文本
        language: 语言 ("auto", "chinese", "english")

    Returns:
        分词结果列表（已去重、去停用词）
    """
    if not text or not text.strip():
        return []

    if language == "auto":
        language = _detect_language(text)

    if language == "chinese":
        tokens = _tokenize_chinese(text)
    else:
        tokens = _tokenize_english(text)

    return tokens


def tokenize_for_search(text: str) -> List[str]:
    """
    为搜索目的进行分词（更激进的分词策略）

    Returns:
        分词结果列表（小写、去重、去停用词、去短词）
    """
    tokens = tokenize(text)
    # 过滤短词（单字）和停用词
    return [t.lower() for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def _detect_language(text: str) -> str:
    """检测文本语言"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.strip())
    if total_chars == 0:
        return "english"
    ratio = chinese_chars / total_chars
    return "chinese" if ratio > 0.3 else "english"


def _tokenize_chinese(text: str) -> List[str]:
    """中文分词"""
    if _jieba_available:
        words = jieba.lcut(text)
    else:
        # 回退：按字符切分（每2个字符一组）
        words = [text[i:i+2] for i in range(len(text)-1)] if len(text) > 1 else [text]

    # 去停用词和单字符
    return [w.strip() for w in words if w.strip() and len(w.strip()) > 1 and w.strip() not in _STOPWORDS]


def _tokenize_english(text: str) -> List[str]:
    """英文分词"""
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


# 中文停用词（精简版）
_STOPWORDS = {
    # 中文
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "她",
    "他", "它", "们", "个", "中", "为", "与", "对", "等", "被",
    "从", "把", "让", "用", "能", "可以", "这个", "那个", "什么",
    "怎么", "如何", "为什么", "吗", "呢", "吧", "啊", "哦",
    # 英文
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again",
    "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "because",
    "but", "and", "or", "if", "while", "about", "up", "it",
    "its", "i", "me", "my", "we", "our", "you", "your", "he",
    "him", "his", "she", "her", "they", "them", "their",
    "this", "that", "these", "those", "am",
}


__all__ = ["tokenize", "tokenize_for_search", "_detect_language"]
