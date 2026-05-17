"""
S1: 开源工具集成适配器 - 专项测试

测试 ChromaDB、FAISS、NetworkX 适配器。
"""

import pytest

from memory_system.adapters import (
    FAISSAdapter,
    NetworkXAdapter,
)


class TestFAISSAdapter:
    """FAISS 适配器测试"""

    def test_initialization(self):
        """初始化测试"""
        adapter = FAISSAdapter(dimension=128)
        assert adapter._dimension == 128
        assert adapter._index is None  # 延迟初始化

    def test_add_and_search(self):
        """添加和搜索测试"""
        adapter = FAISSAdapter(dimension=4)

        # 添加向量
        ids = ["m1", "m2", "m3"]
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0, 0.0],  # 接近 m1
        ]
        metadatas = [
            {"content": "memory 1"},
            {"content": "memory 2"},
            {"content": "memory 3"},
        ]

        adapter.add(ids, embeddings, metadatas)

        # 搜索
        query = [1.0, 0.0, 0.0, 0.0]  # 应该匹配 m1
        results = adapter.search(query, top_k=2)

        assert len(results) >= 1
        assert results[0]["id"] == "m1"

    def test_metadata_storage(self):
        """元数据存储测试"""
        adapter = FAISSAdapter(dimension=4)

        adapter.add(
            ids=["m1"],
            embeddings=[[1.0, 0.0, 0.0, 0.0]],
            metadatas=[{"content": "test", "category": "test"}],
        )

        assert "m1" in adapter._metadata_store
        assert adapter._metadata_store["m1"]["category"] == "test"


class TestNetworkXAdapter:
    """NetworkX 适配器测试"""

    def test_initialization(self):
        """初始化测试"""
        adapter = NetworkXAdapter()
        assert adapter._graph is None  # 延迟初始化

    def test_add_entities(self):
        """添加实体测试"""
        adapter = NetworkXAdapter()

        adapter.add_entity("Python", "language")
        adapter.add_entity("Django", "framework", {"version": "4.0"})

        adapter._ensure_initialized()
        assert adapter._graph.has_node("Python")
        assert adapter._graph.has_node("Django")

    def test_add_relations(self):
        """添加关系测试"""
        adapter = NetworkXAdapter()

        adapter.add_entity("Python", "language")
        adapter.add_entity("Django", "framework")
        adapter.add_relation("Django", "Python", "uses")

        adapter._ensure_initialized()
        assert adapter._graph.has_edge("Django", "Python")

    def test_find_path(self):
        """路径查找测试"""
        adapter = NetworkXAdapter()

        adapter.add_entity("A", "node")
        adapter.add_entity("B", "node")
        adapter.add_entity("C", "node")
        adapter.add_relation("A", "B", "to")
        adapter.add_relation("B", "C", "to")

        path = adapter.find_path("A", "C")
        assert path == ["A", "B", "C"]

    def test_find_path_no_path(self):
        """无路径测试"""
        adapter = NetworkXAdapter()

        adapter.add_entity("A", "node")
        adapter.add_entity("B", "node")

        path = adapter.find_path("A", "B")
        assert path is None

    def test_get_neighbors(self):
        """邻居获取测试"""
        adapter = NetworkXAdapter()

        adapter.add_entity("A", "node")
        adapter.add_entity("B", "node")
        adapter.add_entity("C", "node")
        adapter.add_relation("A", "B", "to")
        adapter.add_relation("A", "C", "to")

        neighbors = adapter.get_neighbors("A")
        assert set(neighbors) == {"B", "C"}

    def test_entity_types(self):
        """实体类型统计测试"""
        adapter = NetworkXAdapter()

        adapter.add_entity("Python", "language")
        adapter.add_entity("JavaScript", "language")
        adapter.add_entity("Django", "framework")

        types = adapter.get_entity_types()
        assert types["language"] == 2
        assert types["framework"] == 1

    def test_relation_types(self):
        """关系类型统计测试"""
        adapter = NetworkXAdapter()

        adapter.add_entity("A", "node")
        adapter.add_entity("B", "node")
        adapter.add_entity("C", "node")
        adapter.add_relation("A", "B", "uses")
        adapter.add_relation("B", "C", "uses")
        adapter.add_relation("A", "C", "depends")

        types = adapter.get_relation_types()
        assert types["uses"] == 2
        assert types["depends"] == 1


class TestLangChainCompatible:
    """LangChain 兼容接口测试"""

    def test_interface_exists(self):
        """接口存在测试"""
        from memory_system.adapters import LangChainCompatible

        # 检查接口方法
        assert hasattr(LangChainCompatible, "load_memory_variables")
        assert hasattr(LangChainCompatible, "save_context")
        assert hasattr(LangChainCompatible, "clear")
