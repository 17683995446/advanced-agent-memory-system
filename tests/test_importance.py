"""Unit tests for the importance scoring module."""
import pytest
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.memory_importance_scorer import ImportanceScorer, ImportanceScore, ScoringStrategy


class TestImportanceScorer:
    def setup_method(self):
        self.scorer = ImportanceScorer()

    def test_default_strategy(self):
        assert self.scorer._strategy == ScoringStrategy.HYBRID

    def test_score_returns_importance_score(self):
        score = self.scorer.score(content="Hello world")
        assert isinstance(score, ImportanceScore)
        assert 0.0 <= score.score <= 1.0

    def test_score_empty_content(self):
        scorer = ImportanceScorer(strategy=ScoringStrategy.TFIDF)
        score = scorer.score(content="")
        assert score.score == 0.0

    def test_score_recent_content(self):
        score = self.scorer.score(content="test", created_at=time.time())
        assert score.score > 0

    def test_score_old_content(self):
        score = self.scorer.score(content="test", created_at=time.time() - 1e9)
        assert score.score < 0.5

    def test_score_with_access_count(self):
        score_low = self.scorer.score(content="test", access_count=0)
        score_high = self.scorer.score(content="test", access_count=50)
        assert score_high.score > score_low.score

    def test_score_with_metadata_factor(self):
        score_normal = self.scorer.score(content="test")
        score_boosted = self.scorer.score(content="test", metadata={"importance_factor": 2.0})
        assert score_boosted.score >= score_normal.score

    def test_score_tfidf_strategy(self):
        scorer = ImportanceScorer(strategy=ScoringStrategy.TFIDF)
        score = scorer.score(content="Python programming language")
        assert "tfidf" in score.components

    def test_score_recency_strategy(self):
        scorer = ImportanceScorer(strategy=ScoringStrategy.RECENCY)
        score = scorer.score(content="test", created_at=time.time())
        assert "recency" in score.components
        assert score.score > 0.9

    def test_score_access_strategy(self):
        scorer = ImportanceScorer(strategy=ScoringStrategy.ACCESS)
        score = scorer.score(content="test", access_count=10)
        assert "access" in score.components

    def test_score_chinese_content(self):
        score = self.scorer.score(content="这是一个中文测试")
        assert score.score >= 0.0

    def test_score_batch(self):
        records = [
            {"content": "Python programming", "access_count": 10, "timestamp": time.time()},
            {"content": "Hello world", "access_count": 0, "timestamp": time.time() - 1000},
        ]
        scores = self.scorer.score_batch(records)
        assert len(scores) == 2
        assert all(isinstance(s, ImportanceScore) for s in scores)

    def test_rank(self):
        records = [
            {"content": "important topic", "access_count": 100, "timestamp": time.time()},
            {"content": "random note", "access_count": 1, "timestamp": time.time() - 1e7},
        ]
        ranked = self.scorer.rank(records, top_k=1)
        assert len(ranked) == 1
        assert ranked[0][0]["content"] == "important topic"

    def test_rank_all(self):
        records = [{"content": f"item {i}", "access_count": i} for i in range(5)]
        ranked = self.scorer.rank(records)
        assert len(ranked) == 5
        # First should have highest access count
        assert ranked[0][0]["access_count"] == 4

    def test_custom_weights(self):
        scorer = ImportanceScorer(weights={"recency": 1.0, "access": 0.0, "tfidf": 0.0})
        score = scorer.score(content="test", created_at=time.time(), access_count=100)
        assert "recency" in score.components

    def test_custom_half_life(self):
        scorer = ImportanceScorer(recency_half_life=60.0)  # 1 minute
        score = scorer.score(content="test", created_at=time.time() - 300)
        assert score.score < 0.5


class TestImportanceScore:
    def test_to_dict(self):
        score = ImportanceScore(score=0.75, components={"tfidf": 0.5, "recency": 0.8})
        d = score.to_dict()
        assert d["score"] == 0.75
        assert d["components"]["tfidf"] == 0.5

    def test_default_components(self):
        score = ImportanceScore(score=0.5)
        assert score.components == {}
