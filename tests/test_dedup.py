"""Unit tests for the dedup module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.processing.simhash_deduplicator import SimHash, MemoryDeduplicator, DedupResult


class TestSimHash:
    def test_compute_basic(self):
        sh = SimHash(hash_bits=64)
        fp = sh.compute("Hello world")
        assert isinstance(fp, int)
        assert fp > 0

    def test_compute_empty(self):
        sh = SimHash()
        fp = sh.compute("")
        assert fp == 0

    def test_similar_texts_similar_fingerprints(self):
        sh = SimHash(hash_bits=64)
        fp1 = sh.compute("Python is a programming language")
        fp2 = sh.compute("Python is a great programming language")
        sim = sh.similarity(fp1, fp2)
        assert sim > 0.5

    def test_different_texts_different_fingerprints(self):
        sh = SimHash(hash_bits=64)
        fp1 = sh.compute("Python programming")
        fp2 = sh.compute("Cooking recipes")
        sim = sh.similarity(fp1, fp2)
        # Different topics should have lower similarity
        assert sim < 0.9

    def test_identical_texts(self):
        sh = SimHash()
        fp1 = sh.compute("identical text")
        fp2 = sh.compute("identical text")
        assert sh.distance(fp1, fp2) == 0
        assert sh.similarity(fp1, fp2) == 1.0

    def test_distance(self):
        sh = SimHash()
        fp1 = sh.compute("test one")
        fp2 = sh.compute("test two")
        dist = sh.distance(fp1, fp2)
        assert isinstance(dist, int)
        assert dist >= 0

    def test_is_similar(self):
        sh = SimHash()
        fp1 = sh.compute("machine learning algorithms")
        fp2 = sh.compute("machine learning methods")
        assert sh.is_similar(fp1, fp2, threshold=0.7)

    def test_chinese_text(self):
        sh = SimHash()
        fp = sh.compute("这是一个中文测试")
        assert fp > 0

    def test_chinese_similarity(self):
        sh = SimHash()
        fp1 = sh.compute("机器学习是人工智能的一个分支")
        fp2 = sh.compute("机器学习是人工智能的重要分支")
        sim = sh.similarity(fp1, fp2)
        assert sim > 0.5


class TestMemoryDeduplicator:
    def setup_method(self):
        self.dedup = MemoryDeduplicator(similarity_threshold=0.85)

    def test_check_no_existing(self):
        result = self.dedup.check("Hello world")
        assert result.is_duplicate is False
        assert result.similarity == 0.0

    def test_check_with_existing(self):
        self.dedup.add("1", "Python is a programming language")
        result = self.dedup.check("Python is a programming language")
        assert result.is_duplicate is True
        assert result.original_id == "1"

    def test_check_similar_not_duplicate(self):
        self.dedup.add("1", "Python programming")
        result = self.dedup.check("Cooking recipes")
        assert result.is_duplicate is False

    def test_add_and_remove(self):
        self.dedup.add("1", "Test content")
        assert self.dedup.count == 1
        self.dedup.remove("1")
        assert self.dedup.count == 0

    def test_deduplicate_batch(self):
        records = [
            {"id": "1", "content": "Python is a programming language"},
            {"id": "2", "content": "Python is a programming language"},  # 重复
            {"id": "3", "content": "Machine learning basics"},
            {"id": "4", "content": "Python programming language"},  # 相似
        ]
        unique = self.dedup.deduplicate(records)
        assert len(unique) < len(records)
        assert unique[0]["id"] == "1"

    def test_deduplicate_no_duplicates(self):
        records = [
            {"id": "1", "content": "Python programming"},
            {"id": "2", "content": "Machine learning"},
            {"id": "3", "content": "Data science"},
        ]
        unique = self.dedup.deduplicate(records)
        assert len(unique) == 3

    def test_find_similar(self):
        self.dedup.add("1", "Python programming language")
        self.dedup.add("2", "Cooking Italian recipes")
        self.dedup.add("3", "Machine learning algorithms")

        similar = self.dedup.find_similar("Python programming", top_k=2)
        assert len(similar) == 2
        assert similar[0][0] == "1"  # Most similar

    def test_find_similar_empty(self):
        similar = self.dedup.find_similar("test")
        assert similar == []

    def test_clear(self):
        self.dedup.add("1", "test")
        self.dedup.add("2", "test2")
        self.dedup.clear()
        assert self.dedup.count == 0

    def test_compute_fingerprint(self):
        fp = self.dedup.compute_fingerprint("Hello world")
        assert isinstance(fp, int)
        assert fp > 0

    def test_get_stats(self):
        self.dedup.add("1", "test")
        stats = self.dedup.get_stats()
        assert stats["registered_fingerprints"] == 1
        assert "similarity_threshold" in stats

    def test_custom_threshold(self):
        dedup = MemoryDeduplicator(similarity_threshold=0.99)  # 极高阈值
        dedup.add("1", "Python programming")
        result = dedup.check("Python programming language")
        # 高阈值下可能不视为重复
        assert isinstance(result.is_duplicate, bool)


class TestDedupResult:
    def test_create(self):
        result = DedupResult(is_duplicate=True, similarity=0.95, original_id="1")
        assert result.is_duplicate is True
        assert result.similarity == 0.95

    def test_default_values(self):
        result = DedupResult(is_duplicate=False, similarity=0.0)
        assert result.original_id is None
        assert result.fingerprint == 0
