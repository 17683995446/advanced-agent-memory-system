"""Unit tests for the metrics module."""
import pytest
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.observability.prometheus_metrics_collector import MemoryMetrics, timed, get_metrics, reset_metrics


class TestMemoryMetrics:
    """Test MemoryMetrics class"""
    
    _counter = 0  # 类级别的计数器，用于生成唯一命名空间
    
    def setup_method(self):
        """Reset metrics before each test"""
        reset_metrics()
        TestMemoryMetrics._counter += 1
    
    def _get_unique_namespace(self, base="test"):
        """生成唯一的命名空间，避免指标重复注册"""
        return f"{base}_{TestMemoryMetrics._counter}_{id(self)}"
    
    def test_metrics_initialization(self):
        """Test metrics can be initialized"""
        metrics = MemoryMetrics(namespace=self._get_unique_namespace("test_memory"))
        assert metrics.namespace.startswith("test_memory")
    
    def test_get_metrics_singleton(self):
        """Test get_metrics returns singleton"""
        ns = self._get_unique_namespace("singleton")
        m1 = get_metrics(ns)
        m2 = get_metrics(ns)
        assert m1 is m2
    
    def test_embed_requests_counter(self):
        """Test embed requests counter"""
        metrics = MemoryMetrics(self._get_unique_namespace("embed"))
        metrics.embed_requests.labels(provider="fake").inc()
        # Should not raise
    
    def test_embed_duration_histogram(self):
        """Test embed duration histogram"""
        metrics = MemoryMetrics(self._get_unique_namespace("embed_dur"))
        with metrics.time_embed(provider="fake"):
            time.sleep(0.001)
        # Should not raise
    
    def test_record_embed_error(self):
        """Test record embed error"""
        metrics = MemoryMetrics(self._get_unique_namespace("embed_err"))
        metrics.record_embed_error("fake", "timeout")
        # Should not raise
    
    def test_vector_search_timing(self):
        """Test vector search timing"""
        metrics = MemoryMetrics(self._get_unique_namespace("vec_search"))
        with metrics.time_vector_search(backend="memory"):
            time.sleep(0.001)
        # Should not raise
    
    def test_memory_operations_counter(self):
        """Test memory operations counter"""
        metrics = MemoryMetrics(self._get_unique_namespace("mem_ops"))
        metrics.record_memory_operation("remember", "long_term")
        # Should not raise
    
    def test_memory_size_gauge(self):
        """Test memory size gauge"""
        metrics = MemoryMetrics(self._get_unique_namespace("mem_size"))
        metrics.set_memory_size("long_term", 100)
        # Should not raise
    
    def test_cache_hit_miss_counters(self):
        """Test cache hit/miss counters"""
        metrics = MemoryMetrics(self._get_unique_namespace("cache"))
        metrics.record_cache_hit("embed")
        metrics.record_cache_miss("embed")
        # Should not raise
    
    def test_kg_size_gauges(self):
        """Test knowledge graph size gauges"""
        metrics = MemoryMetrics(self._get_unique_namespace("kg"))
        metrics.set_kg_size(entities=10, relations=20)
        # Should not raise
    
    def test_get_prometheus_metrics(self):
        """Test getting prometheus metrics"""
        metrics = MemoryMetrics(self._get_unique_namespace("prom"))
        data = metrics.get_prometheus_metrics()
        assert isinstance(data, bytes)
    
    def test_get_content_type(self):
        """Test getting content type"""
        metrics = MemoryMetrics(self._get_unique_namespace("content"))
        ct = metrics.get_content_type()
        assert isinstance(ct, str)
        assert "text/plain" in ct


class TestTimedDecorator:
    """Test timed decorator"""
    
    def test_timed_decorator(self):
        """Test timed decorator measures execution time"""
        metrics = MemoryMetrics(f"timed_decorator_{id(self)}")
        
        @timed(metrics.embed_duration, provider="fake")
        def slow_function():
            time.sleep(0.01)
            return "result"
        
        result = slow_function()
        assert result == "result"
