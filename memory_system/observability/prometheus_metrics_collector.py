"""
可观测性模块 - 指标收集

使用 prometheus_client 收集关键性能指标。
"""

import time
import functools
import threading
from typing import Callable, Optional
import logging

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    _prometheus_available = True
except ImportError:
    _prometheus_available = False
    # Create dummy classes if prometheus_client not installed
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def time(self): return _DummyTimer()
        def labels(self, *args, **kwargs): return self
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Info:
        def __init__(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
    def generate_latest(*args): return b""
    CONTENT_TYPE_LATEST = "text/plain"
    
    class _DummyTimer:
        def __enter__(self): return self
        def __exit__(self, *args): pass


logger = logging.getLogger(__name__)


class MemoryMetrics:
    """
    记忆系统指标收集器
    
    收集以下指标：
    - 嵌入请求数量和延迟
    - 向量搜索数量和延迟
    - 记忆存储/检索操作计数
    - 缓存命中率
    - 错误率
    - 内存使用量
    """
    
    def __init__(self, namespace: str = "agent_memory"):
        """
        Args:
            namespace: 指标命名空间前缀
        """
        self.namespace = namespace
        
        # 嵌入指标
        self.embed_requests = Counter(
            f"{namespace}_embed_requests_total",
            "Total number of embedding requests",
            ["provider"]
        )
        self.embed_duration = Histogram(
            f"{namespace}_embed_duration_seconds",
            "Embedding request duration in seconds",
            ["provider"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )
        self.embed_errors = Counter(
            f"{namespace}_embed_errors_total",
            "Total number of embedding errors",
            ["provider", "error_type"]
        )
        
        # 向量存储指标
        self.vector_search_requests = Counter(
            f"{namespace}_vector_search_requests_total",
            "Total number of vector search requests",
            ["backend"]
        )
        self.vector_search_duration = Histogram(
            f"{namespace}_vector_search_duration_seconds",
            "Vector search duration in seconds",
            ["backend"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        )
        self.vector_store_operations = Counter(
            f"{namespace}_vector_store_operations_total",
            "Total number of vector store operations",
            ["backend", "operation"]
        )
        
        # 记忆操作指标
        self.memory_operations = Counter(
            f"{namespace}_memory_operations_total",
            "Total number of memory operations",
            ["operation", "memory_type"]
        )
        self.memory_size = Gauge(
            f"{namespace}_memory_size",
            "Current number of memories",
            ["memory_type"]
        )
        
        # 缓存指标
        self.cache_hits = Counter(
            f"{namespace}_cache_hits_total",
            "Total number of cache hits",
            ["cache_name"]
        )
        self.cache_misses = Counter(
            f"{namespace}_cache_misses_total",
            "Total number of cache misses",
            ["cache_name"]
        )
        
        # 知识图谱指标
        self.kg_entities = Gauge(
            f"{namespace}_kg_entities",
            "Number of entities in knowledge graph"
        )
        self.kg_relations = Gauge(
            f"{namespace}_kg_relations",
            "Number of relations in knowledge graph"
        )
        
        # 系统信息
        self.system_info = Info(
            f"{namespace}_system_info",
            "System information"
        )
        self.system_info.info({"version": "2.1.0"})
        
        logger.info("MemoryMetrics initialized (prometheus_available=%s)", _prometheus_available)
    
    def time_embed(self, provider: str):
        """嵌入计时器上下文管理器"""
        self.embed_requests.labels(provider=provider).inc()
        return self.embed_duration.labels(provider=provider).time()
    
    def record_embed_error(self, provider: str, error_type: str):
        """记录嵌入错误"""
        self.embed_errors.labels(provider=provider, error_type=error_type).inc()
    
    def time_vector_search(self, backend: str):
        """向量搜索计时器上下文管理器"""
        self.vector_search_requests.labels(backend=backend).inc()
        return self.vector_search_duration.labels(backend=backend).time()
    
    def record_vector_store_operation(self, backend: str, operation: str):
        """记录向量存储操作"""
        self.vector_store_operations.labels(backend=backend, operation=operation).inc()
    
    def record_memory_operation(self, operation: str, memory_type: str):
        """记录记忆操作"""
        self.memory_operations.labels(operation=operation, memory_type=memory_type).inc()
    
    def set_memory_size(self, memory_type: str, size: int):
        """设置记忆大小"""
        self.memory_size.labels(memory_type=memory_type).set(size)
    
    def record_cache_hit(self, cache_name: str):
        """记录缓存命中"""
        self.cache_hits.labels(cache_name=cache_name).inc()
    
    def record_cache_miss(self, cache_name: str):
        """记录缓存未命中"""
        self.cache_misses.labels(cache_name=cache_name).inc()
    
    def set_kg_size(self, entities: int, relations: int):
        """设置知识图谱大小"""
        self.kg_entities.set(entities)
        self.kg_relations.set(relations)
    
    def get_prometheus_metrics(self) -> bytes:
        """获取 Prometheus 格式的指标数据"""
        return generate_latest()
    
    def get_content_type(self) -> str:
        """获取指标内容类型"""
        return CONTENT_TYPE_LATEST


class timed:
    """
    方法执行时间装饰器
    
    用法:
        @timed(metrics.embed_duration, provider="fake")
        def encode(self, text: str) -> list[float]:
            ...
    """
    
    def __init__(self, histogram, **labels):
        self.histogram = histogram
        self.labels = labels
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                self.histogram.labels(**self.labels).observe(duration)
        return wrapper


# 全局指标实例（单例模式）
_metrics_instance: Optional[MemoryMetrics] = None
_metrics_lock = threading.Lock()


def get_metrics(namespace: str = "agent_memory") -> MemoryMetrics:
    """获取全局指标实例（线程安全）"""
    global _metrics_instance
    if _metrics_instance is None:
        with _metrics_lock:
            if _metrics_instance is None:
                _metrics_instance = MemoryMetrics(namespace)
    return _metrics_instance


def reset_metrics():
    """重置全局指标实例（主要用于测试）"""
    global _metrics_instance
    with _metrics_lock:
        _metrics_instance = None


__all__ = [
    "MemoryMetrics",
    "timed",
    "get_metrics",
    "reset_metrics",
]
