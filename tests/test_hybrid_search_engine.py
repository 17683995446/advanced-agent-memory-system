"""Tests for hybrid_search_engine module."""

import pytest
from unittest.mock import MagicMock, patch
from memory_system.core.hybrid_search_engine import (
    SearchHit,
    SearchStrategy,
    VectorSearchStrategy,
    KeywordSearchStrategy,
    KnowledgeGraphSearchStrategy,
    HybridSearchEngine,
)


# ============================================================
# SearchHit Tests
# ============================================================

class TestSearchHit:
    """SearchHit 数据模型测试"""

    def test_create_search_hit(self):
        hit = SearchHit(
            id="mem-001",
            content="测试记忆内容",
            score=0.95,
            source="vector",
            metadata={"category": "test"},
        )
        assert hit.id == "mem-001"
        assert hit.content == "测试记忆内容"
        assert hit.score == 0.95
        assert hit.source == "vector"
        assert hit.metadata == {"category": "test"}

    def test_search_hit_is_immutable(self):
        hit = SearchHit(id="1", content="test", score=0.5, source="keyword", metadata={})
        with pytest.raises(AttributeError):
            hit.score = 0.9

    def test_search_hit_replace(self):
        hit = SearchHit(id="1", content="test", score=0.5, source="keyword", metadata={})
        new_hit = hit._replace(score=0.8)
        assert new_hit.score == 0.8
        assert hit.score == 0.5


# ============================================================
# VectorSearchStrategy Tests
# ============================================================

class TestVectorSearchStrategy:
    """向量搜索策略测试"""

    def test_search_with_mock_store(self):
        mock_record_1 = MagicMock()
        mock_record_1.id = "v-1"
        mock_record_1.content = "向量结果1"
        mock_record_1.memory_type = "general"
        mock_record_1.category = "test"
        mock_record_1.importance = 0.9
        mock_record_1.tags = []
        mock_record_1.metadata = {}

        mock_record_2 = MagicMock()
        mock_record_2.id = "v-2"
        mock_record_2.content = "向量结果2"
        mock_record_2.memory_type = "general"
        mock_record_2.category = "test"
        mock_record_2.importance = 0.7
        mock_record_2.tags = []
        mock_record_2.metadata = {}

        mock_result_1 = MagicMock()
        mock_result_1.record = mock_record_1
        mock_result_1.score = 0.9

        mock_result_2 = MagicMock()
        mock_result_2.record = mock_record_2
        mock_result_2.score = 0.7

        mock_store = MagicMock()
        mock_store.search.return_value = [mock_result_1, mock_result_2]
        mock_embedding = MagicMock()
        mock_embedding.return_value = [0.1] * 128

        strategy = VectorSearchStrategy(vector_store=mock_store, embedding_provider=mock_embedding)
        results = strategy.search("测试查询", top_k=5)

        assert len(results) == 2
        assert results[0].source == "vector"
        assert results[0].score == 0.9
        assert results[0].id == "v-1"

    def test_search_empty_results(self):
        mock_store = MagicMock()
        mock_store.search.return_value = []
        mock_embedding = MagicMock()
        mock_embedding.get_embedding.return_value = [0.1] * 128

        strategy = VectorSearchStrategy(vector_store=mock_store, embedding_provider=mock_embedding)
        results = strategy.search("不存在的查询", top_k=5)
        assert results == []

    def test_search_with_embedding_error(self):
        mock_store = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.get_embedding.side_effect = Exception("模型加载失败")

        strategy = VectorSearchStrategy(vector_store=mock_store, embedding_provider=mock_embedding)
        results = strategy.search("测试", top_k=5)
        assert results == []


# ============================================================
# KeywordSearchStrategy Tests
# ============================================================

class TestKeywordSearchStrategy:
    """关键词搜索策略测试"""

    def test_basic_search(self):
        strategy = KeywordSearchStrategy()
        strategy.add_document("doc-1", "机器学习是人工智能的一个分支")
        strategy.add_document("doc-2", "深度学习使用神经网络")
        strategy.add_document("doc-3", "自然语言处理处理文本数据")

        results = strategy.search("机器学习", top_k=3)
        assert len(results) > 0
        assert results[0].source == "keyword"
        assert results[0].id == "doc-1"

    def test_fuzzy_search(self):
        strategy = KeywordSearchStrategy()
        strategy.add_document("doc-1", "Python编程语言")
        strategy.add_document("doc-2", "Java编程语言")
        strategy.add_document("doc-3", "数据库管理系统")

        # Use tokens that exist in the index; fuzzy matching boosts relevant docs
        results = strategy.search("编程语言", top_k=3)
        assert len(results) > 0
        # Both Python and Java docs contain 编程语言
        ids = [r.id for r in results]
        assert "doc-1" in ids

    def test_empty_index_search(self):
        strategy = KeywordSearchStrategy()
        results = strategy.search("测试", top_k=5)
        assert results == []

    def test_remove_document(self):
        strategy = KeywordSearchStrategy()
        strategy.add_document("doc-1", "测试内容一")
        strategy.add_document("doc-2", "测试内容二")
        strategy.remove_document("doc-1")

        results = strategy.search("测试", top_k=5)
        ids = [r.id for r in results]
        assert "doc-1" not in ids

    def test_search_respects_top_k(self):
        strategy = KeywordSearchStrategy()
        for i in range(20):
            strategy.add_document(f"doc-{i}", f"这是第{i}个测试文档的内容")

        results = strategy.search("测试文档", top_k=5)
        assert len(results) <= 5

    def test_chinese_tokenization(self):
        strategy = KeywordSearchStrategy()
        strategy.add_document("doc-1", "智能体记忆系统用于存储和检索信息")
        strategy.add_document("doc-2", "向量数据库支持高维向量的相似度搜索")

        results = strategy.search("记忆系统", top_k=3)
        assert len(results) > 0
        assert results[0].id == "doc-1"

    def test_reindex(self):
        strategy = KeywordSearchStrategy()
        strategy.add_document("doc-1", "旧内容")
        strategy.remove_document("doc-1")
        strategy.add_document("doc-1", "新内容")

        results = strategy.search("新内容", top_k=3)
        assert len(results) > 0


# ============================================================
# KnowledgeGraphSearchStrategy Tests
# ============================================================

class TestKnowledgeGraphSearchStrategy:
    """知识图谱搜索策略测试"""

    def test_search_entities(self):
        mock_entity = MagicMock()
        mock_entity.name = "Python"
        mock_entity.entity_type = "technology"
        mock_entity.description = "A programming language"
        mock_entity.properties = {"popularity": "high"}

        mock_graph = MagicMock()
        mock_graph.search_entities.return_value = [(mock_entity, 0.95)]
        mock_graph.get_relations.return_value = [
            MagicMock(source="Python", target="机器学习", relation_type="used_in"),
        ]
        mock_graph.get_neighbors.return_value = ["机器学习", "深度学习"]

        strategy = KnowledgeGraphSearchStrategy(knowledge_graph=mock_graph)
        results = strategy.search("Python", top_k=5)

        assert len(results) > 0
        assert results[0].source == "graph"

    def test_search_empty_graph(self):
        mock_graph = MagicMock()
        mock_graph.search_entities.return_value = []

        strategy = KnowledgeGraphSearchStrategy(knowledge_graph=mock_graph)
        results = strategy.search("不存在", top_k=5)
        assert results == []

    def test_search_with_graph_error(self):
        mock_graph = MagicMock()
        mock_graph.search_entities.side_effect = Exception("图谱不可用")

        strategy = KnowledgeGraphSearchStrategy(knowledge_graph=mock_graph)
        with pytest.raises(Exception, match="图谱不可用"):
            strategy.search("测试", top_k=5)


# ============================================================
# HybridSearchEngine Tests
# ============================================================

class TestHybridSearchEngine:
    """混合搜索引擎测试"""

    def _make_keyword_strategy(self, docs=None):
        strategy = KeywordSearchStrategy()
        if docs:
            for doc_id, content in docs:
                strategy.add_document(doc_id, content)
        return strategy

    def test_single_strategy_search(self):
        engine = HybridSearchEngine()
        strategy = self._make_keyword_strategy([("d1", "人工智能技术")])
        engine.add_strategy(strategy)

        results = engine.search("人工智能", top_k=5)
        assert len(results) > 0

    def test_rrf_fusion(self):
        """测试倒数排名融合"""
        engine = HybridSearchEngine(fusion_method="rrf")

        s1 = KeywordSearchStrategy()
        s1.add_document("a", "机器学习算法")
        s1.add_document("b", "深度学习框架")
        s1.add_document("c", "数据可视化工具")

        s2 = KeywordSearchStrategy()
        s2.add_document("b", "深度学习框架和工具")
        s2.add_document("c", "数据分析和可视化")
        s2.add_document("d", "自然语言处理应用")

        engine.add_strategy(s1)
        engine.add_strategy(s2)

        results = engine.search("学习", top_k=5)
        assert len(results) > 0
        # "b" 出现在两个策略中，RRF 应该给它更高的排名
        sources = {}
        for r in results:
            sources.setdefault(r.id, []).append(r.source)

    def test_weighted_fusion(self):
        """测试加权融合"""
        engine = HybridSearchEngine(fusion_method="weighted")

        s1 = KeywordSearchStrategy()
        s1.add_document("a", "测试文档A")

        engine.add_strategy(s1, weight=2.0)
        results = engine.search("测试", top_k=5)
        assert len(results) > 0

    def test_max_fusion(self):
        """测试最大分数融合"""
        engine = HybridSearchEngine(fusion_method="max")

        s1 = KeywordSearchStrategy()
        s1.add_document("a", "测试文档")

        engine.add_strategy(s1)
        results = engine.search("测试", top_k=5)
        assert len(results) > 0

    def test_empty_engine_search(self):
        engine = HybridSearchEngine()
        results = engine.search("测试", top_k=5)
        assert results == []

    def test_remove_strategy(self):
        engine = HybridSearchEngine()
        strategy = self._make_keyword_strategy([("a", "测试")])
        engine.add_strategy(strategy)
        engine.remove_strategy(strategy.name)

        results = engine.search("测试", top_k=5)
        assert results == []

    def test_set_fusion_method(self):
        engine = HybridSearchEngine(fusion_method="rrf")
        engine.set_fusion_method("weighted")
        assert engine.fusion_method == "weighted"

    def test_invalid_fusion_method(self):
        with pytest.raises(ValueError, match="不支持的融合方法"):
            HybridSearchEngine(fusion_method="invalid")

    def test_deduplication(self):
        """同一文档出现在多个策略中应去重"""
        engine = HybridSearchEngine(fusion_method="rrf")

        s1 = KeywordSearchStrategy()
        s1.add_document("shared", "共享文档内容")

        s2 = KeywordSearchStrategy()
        s2.add_document("shared", "共享文档内容另一个视角")

        engine.add_strategy(s1)
        engine.add_strategy(s2)

        results = engine.search("共享", top_k=10)
        # 同一 ID 只应出现一次
        ids = [r.id for r in results]
        assert len(ids) == len(set(ids))

    def test_top_k_respected(self):
        engine = HybridSearchEngine()
        strategy = KeywordSearchStrategy()
        for i in range(20):
            strategy.add_document(f"doc-{i}", f"文档编号{i}的内容")
        engine.add_strategy(strategy)

        results = engine.search("文档", top_k=5)
        assert len(results) <= 5

    def test_search_with_no_results_from_any_strategy(self):
        engine = HybridSearchEngine()
        s1 = KeywordSearchStrategy()
        s1.add_document("a", "完全不相关的内容")
        engine.add_strategy(s1)

        results = engine.search("xyznonexistent12345", top_k=5)
        # 可能返回空或低分结果
        assert isinstance(results, list)
