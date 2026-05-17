"""
相似度计算工具

提供统一的相似度计算函数。
"""

from typing import Optional


def jaccard_similarity(set1: set, set2: set) -> float:
    """
    计算Jaccard相似度
    
    J(A, B) = |A ∩ B| / |A ∪ B|
    
    Args:
        set1: 第一个集合
        set2: 第二个集合
        
    Returns:
        0.0 到 1.0 之间的相似度值
    """
    if not set1 and not set2:
        return 1.0  # 两个空集视为完全相似
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def calculate_similarity(
    content1: str,
    content2: str,
    tokenizer: Optional[callable] = None,
) -> float:
    """
    计算两段内容的相似度
    
    默认使用Jaccard相似度基于词集合计算。
    
    Args:
        content1: 第一段内容
        content2: 第二段内容
        tokenizer: 可选的分词函数，默认按空格分词
        
    Returns:
        0.0 到 1.0 之间的相似度值
    """
    if not content1 or not content2:
        return 0.0
    
    if content1 == content2:
        return 1.0
    
    # 默认分词：按空格分割并转为小写
    if tokenizer is None:
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
    else:
        words1 = set(tokenizer(content1))
        words2 = set(tokenizer(content2))
    
    return jaccard_similarity(words1, words2)


def calculate_content_hash(content: str, length: int = 16) -> str:
    """
    计算内容的MD5哈希
    
    Args:
        content: 要哈希的内容
        length: 返回哈希的长度，默认16字符
        
    Returns:
        十六进制哈希字符串
    """
    import hashlib
    full_hash = hashlib.md5(content.encode()).hexdigest()
    return full_hash[:length]
