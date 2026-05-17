"""
共享测试 fixtures

提供跨测试文件共享的 fixtures 和 mock 类。
"""

import time
from dataclasses import dataclass, field

import pytest


@dataclass
class MockMemory:
    """模拟记忆记录 - 用于测试"""
    id: str
    content: str
    category: str = "general"
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@pytest.fixture
def sample_memories():
    """提供样本记忆数据"""
    return [
        MockMemory("m1", "Python is a programming language", "tech", 0.9, ["python", "coding"]),
        MockMemory("m2", "Django is a Python web framework", "tech", 0.8, ["python", "web"]),
        MockMemory("m3", "Machine learning is a subset of AI", "ai", 0.85, ["ai", "ml"]),
        MockMemory("m4", "FastAPI is a modern web framework", "tech", 0.75, ["python", "api"]),
        MockMemory("m5", "React is a JavaScript library", "frontend", 0.7, ["javascript", "ui"]),
    ]


class MockMemorySystem:
    """模拟记忆系统 - 用于推理引擎测试"""

    def __init__(self, memories=None):
        self.memories = memories or []
        self.knowledge_graph = None

    def recall(self, query, top_k=10):
        return self.memories[:top_k]


@pytest.fixture
def mock_memory_system(sample_memories):
    """提供模拟记忆系统"""
    return MockMemorySystem(sample_memories)
