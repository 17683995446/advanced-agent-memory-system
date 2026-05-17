"""
文本处理工具

提供统一的文本处理函数。
"""

import re
from typing import Optional


# 英文停用词列表
ENGLISH_STOPWORDS = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was",
    "one", "our", "out", "day", "get", "has", "him", "his", "how", "its", "may", "new",
    "now", "old", "see", "two", "who", "boy", "did", "she", "use", "her", "way", "many",
    "oil", "sit", "set", "run", "eat", "far", "sea", "eye", "ago", "off", "too", "any",
    "say", "man", "try", "ask", "end", "why", "let", "put", "say", "she", "try", "way",
    "own", "say", "too", "old", "tell", "very", "when", "much", "would", "there", "their",
    "what", "said", "each", "which", "will", "about", "could", "other", "after", "first",
    "never", "these", "think", "where", "being", "every", "great", "might", "shall",
    "still", "those", "while", "this", "that", "with", "have", "from", "they", "been",
    "were", "said", "time", "than", "them", "into", "just", "like", "over", "also",
    "back", "only", "know", "take", "year", "good", "some", "come", "make", "well",
    "work", "life", "even", "more", "want", "here", "look", "down", "most", "long",
    "last", "find", "give", "does", "made", "part", "such", "keep", "call", "came",
    "need", "feel", "seem", "turn", "hand", "high", "sure", "upon", "head", "help",
    "home", "side", "move", "both", "five", "once", "same", "must", "name", "left",
    "each", "done", "open", "case", "show", "live", "play", "went", "told", "seen",
    "hear", "talk", "soon", "read", "stop", "face", "fact", "land", "line", "kind",
    "next", "word",
})


def normalize_text(text: str) -> str:
    """
    标准化文本
    
    - 去除多余空白
    - 转为小写
    - 去除首尾空格
    
    Args:
        text: 原始文本
        
    Returns:
        标准化后的文本
    """
    if not text:
        return ""
    return " ".join(text.lower().split())


def tokenize(text: str, include_chinese: bool = True) -> set[str]:
    """
    文本分词
    
    提取英文单词和连续中文字符。
    
    Args:
        text: 要分词的文本
        include_chinese: 是否包含中文分词
        
    Returns:
        词集合
    """
    if not text:
        return set()
    
    words = []
    
    # 提取英文单词
    english_words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    words.extend(english_words)
    
    # 提取中文（如果启用）
    if include_chinese:
        chinese_words = re.findall(r"[\u4e00-\u9fa5]{2,}", text)
        words.extend(chinese_words)
    
    return set(words)


def extract_keywords(
    text: str,
    min_length: int = 3,
    remove_stopwords: bool = True,
    max_keywords: Optional[int] = None,
) -> list[str]:
    """
    提取关键词
    
    从文本中提取有意义的关键词。
    
    Args:
        text: 原始文本
        min_length: 最小词长度
        remove_stopwords: 是否移除停用词
        max_keywords: 最大返回关键词数量
        
    Returns:
        关键词列表
    """
    if not text:
        return []
    
    # 提取英文单词
    words = re.findall(rf"\b[a-zA-Z]{{{min_length},}}\b", text.lower())
    
    # 过滤停用词
    if remove_stopwords:
        words = [w for w in words if w not in ENGLISH_STOPWORDS]
    
    # 去重并保持顺序
    seen = set()
    unique_words = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique_words.append(w)
    
    # 限制数量
    if max_keywords:
        unique_words = unique_words[:max_keywords]
    
    return unique_words


def extract_entities(text: str, max_entities: int = 10) -> list[str]:
    """
    从文本中提取实体
    
    简单实体提取：大写单词或中文字符。
    
    Args:
        text: 原始文本
        max_entities: 最大实体数量
        
    Returns:
        实体列表
    """
    if not text:
        return []
    
    entities = []
    
    # 英文实体（大写开头的单词）
    english_entities = re.findall(r"\b[A-Z][a-zA-Z]*\b", text)
    entities.extend(english_entities)
    
    # 中文实体（2-4字词组）
    chinese_entities = re.findall(r"[\u4e00-\u9fa5]{2,4}", text)
    entities.extend(chinese_entities)
    
    # 去重并限制
    return list(dict.fromkeys(entities))[:max_entities]


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本到指定长度
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后添加的后缀
        
    Returns:
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def count_words(text: str) -> int:
    """
    统计词数
    
    Args:
        text: 文本内容
        
    Returns:
        词数
    """
    if not text:
        return 0
    return len(text.split())
