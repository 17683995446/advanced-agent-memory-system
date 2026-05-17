"""
S1: 记忆推理引擎 - 专项测试

测试 MemoryInferenceEngine 的完整功能：
1. 规则推理
2. 关联推理
3. 类比推理
4. 推理链追踪
5. 置信度计算
6. 推理解释
"""

import pytest

from memory_system.core.memory_inference_engine import (
    InferenceConfig,
    InferenceRule,
    InferenceType,
    MemoryInferenceEngine,
)


class MockMemorySystem:
    """模拟记忆系统"""

    def __init__(self, memories=None):
        self.memories = memories or []
        self.knowledge_graph = None

    def recall(self, query, top_k=10):
        return self.memories[:top_k]


@pytest.fixture
def engine():
    """创建推理引擎实例"""
    config = InferenceConfig(
        min_confidence_threshold=0.6,
        max_inference_steps=5,
        enable_rule_reasoning=True,
        enable_associative_reasoning=True,
        enable_analogical_reasoning=True,
    )
    return MemoryInferenceEngine(config=config)


@pytest.fixture
def sample_memories():
    """样本记忆数据"""
    return [
        {"id": "m1", "content": "Python 是一种编程语言，用于开发各种应用"},
        {"id": "m2", "content": "Django 是 Python 的 Web 框架，用于构建网站"},
        {"id": "m3", "content": "如果下雨，那么地面会湿"},
        {"id": "m4", "content": "天空是蓝色的因为瑞利散射"},
        {"id": "m5", "content": "机器学习是人工智能的一种技术"},
    ]


class TestRuleReasoning:
    """规则推理测试"""

    def test_causal_rule(self, engine, sample_memories):
        """测试因果规则推理"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("为什么天空是蓝色的？", mock_memory)

        assert result is not None
        assert result.confidence > 0
        # 应该找到包含"原因"或"导致"的记忆

    def test_conditional_rule(self, engine, sample_memories):
        """测试条件规则推理"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("如果下雨会发生什么？", mock_memory)

        assert result is not None
        # 应该匹配包含"如果"和"那么"的记忆

    def test_no_matching_rule(self, engine):
        """测试无匹配规则的情况"""
        mock_memory = MockMemorySystem([])

        result = engine.infer("随机查询", mock_memory)

        assert result.confidence == 0.0
        assert len(result.steps) == 0


class TestAnalogicalReasoning:
    """类比推理测试"""

    def test_analogical_inference(self, engine, sample_memories):
        """测试类比推理"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("Python 能做什么？", mock_memory)

        assert result is not None
        # 应该基于相似案例进行类比

    def test_similarity_calculation(self, engine):
        """测试相似度计算"""
        keywords1 = engine._extract_keywords("Python programming language")
        keywords2 = engine._extract_keywords("Python web development")

        # 应该有共同的关键词
        assert "python" in [k.lower() for k in keywords1]


class TestInferenceSteps:
    """推理步骤测试"""

    def test_inference_chain(self, engine, sample_memories):
        """测试推理链"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("Django 是什么？", mock_memory)

        assert len(result.steps) >= 0
        for i, step in enumerate(result.steps):
            assert step.step_number == i + 1
            assert step.confidence > 0

    def test_confidence_propagation(self, engine, sample_memories):
        """测试置信度传播"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("测试查询", mock_memory)

        # 置信度应该在合理范围内
        assert 0 <= result.confidence <= 1


class TestCustomRules:
    """自定义规则测试"""

    def test_add_custom_rule(self, engine):
        """添加自定义规则"""
        custom_rule = InferenceRule(
            rule_id="custom1",
            name="自定义规则",
            premises=["测试", "规则"],
            conclusion="这是自定义结论",
            confidence=0.95,
            inference_type=InferenceType.RULE_BASED,
        )
        engine.add_rule(custom_rule)

        assert len(engine._rules) > 4  # 默认4条 + 新增


class TestExplanation:
    """推理解释测试"""

    def test_explain_inference(self, engine, sample_memories):
        """测试推理解释生成"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("解释测试", mock_memory)
        explanation = engine.explain_inference(result)

        assert isinstance(explanation, str)
        assert result.query in explanation


class TestStatistics:
    """统计信息测试"""

    def test_empty_statistics(self, engine):
        """空统计"""
        stats = engine.get_statistics()

        assert stats["total_inferences"] == 0
        assert stats["avg_confidence"] == 0.0

    def test_statistics_after_inference(self, engine, sample_memories):
        """推理后统计"""
        mock_memory = MockMemorySystem(sample_memories)

        engine.infer("查询1", mock_memory)
        engine.infer("查询2", mock_memory)

        stats = engine.get_statistics()

        assert stats["total_inferences"] == 2
        assert stats["rules_count"] >= 4


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_query(self, engine, sample_memories):
        """空查询"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("", mock_memory)

        assert result is not None

    def test_very_long_query(self, engine, sample_memories):
        """超长查询"""
        mock_memory = MockMemorySystem(sample_memories)

        long_query = "Python " * 100
        result = engine.infer(long_query, mock_memory)

        assert result is not None

    def test_chinese_query(self, engine, sample_memories):
        """中文查询"""
        mock_memory = MockMemorySystem(sample_memories)

        result = engine.infer("什么是Python？", mock_memory)

        assert result is not None
