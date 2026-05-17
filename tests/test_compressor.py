"""Unit tests for the compressor module."""
import pytest
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.processing.memory_content_compressor import (
    MemoryCompressor,
    CompressionStrategy,
    CompressionResult,
    simple_summarizer,
)


class TestCompressionStrategy:
    def test_values(self):
        assert CompressionStrategy.IMPORTANCE.value == "importance"
        assert CompressionStrategy.RECENCY.value == "recency"
        assert CompressionStrategy.HYBRID.value == "hybrid"


class TestCompressionResult:
    def test_create(self):
        result = CompressionResult(original_count=10, compressed_count=5)
        assert result.original_count == 10
        assert result.compressed_count == 5
        assert result.removed_ids == []
    
    def test_with_summary(self):
        result = CompressionResult(
            original_count=5,
            compressed_count=2,
            removed_ids=["a", "b", "c"],
            summary="Summary text",
        )
        assert result.summary == "Summary text"


class TestMemoryCompressor:
    def setup_method(self):
        self.compressor = MemoryCompressor()
    
    def test_create_default(self):
        assert self.compressor._strategy == CompressionStrategy.IMPORTANCE
    
    def test_compress_by_importance(self):
        memories = [
            {"id": "1", "content": "a", "importance": 0.8},
            {"id": "2", "content": "b", "importance": 0.2},
            {"id": "3", "content": "c", "importance": 0.5},
        ]
        result = self.compressor.compress(memories)
        assert result.original_count == 3
        assert result.compressed_count == 2  # 0.8 and 0.5 kept
        assert "2" in result.removed_ids
    
    def test_compress_by_recency(self):
        compressor = MemoryCompressor(strategy=CompressionStrategy.RECENCY, max_age_seconds=100)
        now = time.time()
        memories = [
            {"id": "1", "content": "old", "timestamp": now - 200},
            {"id": "2", "content": "new", "timestamp": now - 50},
        ]
        result = compressor.compress(memories)
        assert result.compressed_count == 1
        assert "2" not in result.removed_ids
    
    def test_compress_by_hybrid(self):
        compressor = MemoryCompressor(
            strategy=CompressionStrategy.HYBRID,
            importance_threshold=0.7,
            max_age_seconds=100,
        )
        now = time.time()
        memories = [
            {"id": "1", "importance": 0.9, "timestamp": now - 1000},  # 高重要性，保留
            {"id": "2", "importance": 0.3, "timestamp": now - 50},   # 新，保留
            {"id": "3", "importance": 0.3, "timestamp": now - 1000}, # 低且旧，移除
        ]
        result = compressor.compress(memories)
        assert result.compressed_count == 2
    
    def test_compress_empty(self):
        result = self.compressor.compress([])
        assert result.original_count == 0
        assert result.compressed_count == 0
    
    def test_summarize_without_summarizer(self):
        compressor = MemoryCompressor()
        summary = compressor.summarize(["a", "b", "c"])
        assert "3 memories" in summary
    
    def test_summarize_with_summarizer(self):
        def my_summarizer(text):
            return "CUSTOM: " + text[:10]
        compressor = MemoryCompressor(summarizer=my_summarizer)
        summary = compressor.summarize(["hello world"])
        assert summary.startswith("CUSTOM:")
    
    def test_compress_with_summary(self):
        def summarizer(text):
            return "Summary"
        compressor = MemoryCompressor(summarizer=summarizer)
        memories = [
            {"id": "1", "content": "keep", "importance": 0.8},
            {"id": "2", "content": "remove", "importance": 0.1},
        ]
        keep, result = compressor.compress_with_summary(memories)
        assert len(keep) == 1
        assert result.summary == "Summary"
    
    def test_get_stats(self):
        compressor = MemoryCompressor(
            strategy=CompressionStrategy.HYBRID,
            importance_threshold=0.4,
        )
        stats = compressor.get_stats()
        assert stats["strategy"] == "hybrid"
        assert stats["importance_threshold"] == 0.4


class TestSimpleSummarizer:
    def test_short_text(self):
        result = simple_summarizer("short", max_length=100)
        assert result == "short"
    
    def test_long_text(self):
        text = "a" * 300
        result = simple_summarizer(text, max_length=100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")
