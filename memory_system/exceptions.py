"""
Agent Memory System - 统一异常体系

所有模块的异常都应继承自 MemoryError 基类，
便于调用方统一捕获和处理。
"""


class MemoryError(Exception):
    """记忆系统基础异常"""
    pass


class EmbeddingError(MemoryError):
    """嵌入模型相关异常"""
    pass


class EmbeddingModelNotFoundError(EmbeddingError):
    """嵌入模型未找到"""
    pass


class EmbeddingDimensionError(EmbeddingError):
    """嵌入维度不匹配"""
    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        super().__init__(f"维度不匹配: 期望 {expected}, 实际 {actual}")


class VectorStoreError(MemoryError):
    """向量存储相关异常"""
    pass


class VectorStoreConnectionError(VectorStoreError):
    """向量存储连接失败"""
    pass


class MemoryNotFoundError(VectorStoreError):
    """记忆未找到"""
    def __init__(self, memory_id: str):
        self.memory_id = memory_id
        super().__init__(f"记忆未找到: {memory_id}")


class KnowledgeGraphError(MemoryError):
    """知识图谱相关异常"""
    pass


class EntityNotFoundError(KnowledgeGraphError):
    """实体未找到"""
    def __init__(self, entity_name: str):
        self.entity_name = entity_name
        super().__init__(f"实体未找到: {entity_name}")


class StructuredStoreError(MemoryError):
    """结构化存储相关异常"""
    pass


class TableNotFoundError(StructuredStoreError):
    """表未找到"""
    def __init__(self, table_name: str):
        self.table_name = table_name
        super().__init__(f"表未找到: {table_name}")


class ConfigurationError(MemoryError):
    """配置错误"""
    pass


class ConsolidationError(MemoryError):
    """记忆巩固异常"""
    pass
