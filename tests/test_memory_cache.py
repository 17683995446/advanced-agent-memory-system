"""Unit tests for the memory_cache module."""
import pytest
import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.storage.multi_level_memory_cache import (
    CacheLevel,
    EvictionPolicy,
    CacheConfig,
    CacheStats,
    CacheKeyGenerator,
    CacheSerializer,
    MemoryCache,
)


class TestCacheLevel:
    def test_l1_value(self):
        assert CacheLevel.L1_MEMORY.value == "l1_memory"

    def test_l2_value(self):
        assert CacheLevel.L2_REDIS.value == "l2_redis"


class TestEvictionPolicy:
    def test_lru(self):
        assert EvictionPolicy.LRU.value == "lru"

    def test_ttl(self):
        assert EvictionPolicy.TTL.value == "ttl"

    def test_lfu(self):
        assert EvictionPolicy.LFU.value == "lfu"


class TestCacheConfig:
    def test_defaults(self):
        config = CacheConfig()
        assert config.max_size == 1024
        assert config.ttl == 300.0
        assert config.l2_enabled is False
        assert config.l2_ttl == 3600.0
        assert config.key_prefix == "mem:"
        assert config.serializer == "json"
        assert config.enable_stats is True

    def test_custom(self):
        config = CacheConfig(
            max_size=100,
            ttl=60.0,
            l2_enabled=True,
            key_prefix="custom:",
            serializer="pickle",
        )
        assert config.max_size == 100
        assert config.ttl == 60.0
        assert config.l2_enabled is True
        assert config.key_prefix == "custom:"
        assert config.serializer == "pickle"


class TestCacheStats:
    def test_defaults(self):
        stats = CacheStats()
        assert stats.l1_hits == 0
        assert stats.l1_misses == 0
        assert stats.l2_hits == 0
        assert stats.l2_misses == 0

    def test_hit_rate_no_data(self):
        stats = CacheStats()
        assert stats.l1_hit_rate == 0.0
        assert stats.overall_hit_rate == 0.0

    def test_hit_rate_with_data(self):
        stats = CacheStats(l1_hits=8, l1_misses=2, l2_hits=1, l2_misses=1, total_gets=12)
        assert abs(stats.l1_hit_rate - 0.8) < 1e-6
        assert abs(stats.overall_hit_rate - 0.75) < 1e-6

    def test_to_dict(self):
        stats = CacheStats(l1_hits=5, l1_misses=5, total_gets=10)
        d = stats.to_dict()
        assert "l1_hits" in d
        assert "l1_hit_rate" in d
        assert "overall_hit_rate" in d


class TestCacheKeyGenerator:
    def test_generate_with_args(self):
        key = CacheKeyGenerator.generate("prefix", "arg1", "arg2")
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hex digest

    def test_generate_with_kwargs(self):
        key = CacheKeyGenerator.generate("prefix", key1="val1")
        assert isinstance(key, str)
        assert len(key) == 32

    def test_deterministic(self):
        k1 = CacheKeyGenerator.generate("p", "a", "b")
        k2 = CacheKeyGenerator.generate("p", "a", "b")
        assert k1 == k2

    def test_different_args_different_keys(self):
        k1 = CacheKeyGenerator.generate("p", "a")
        k2 = CacheKeyGenerator.generate("p", "b")
        assert k1 != k2

    def test_generate_from_func(self):
        def my_func(x, y):
            pass
        key = CacheKeyGenerator.generate_from_func("prefix", my_func, (1, 2), {})
        assert isinstance(key, str)
        assert len(key) == 32


class TestCacheSerializer:
    def test_json_serialize_deserialize(self):
        data = {"key": "value", "num": 42, "list": [1, 2, 3]}
        serialized = CacheSerializer.serialize(data, "json")
        assert isinstance(serialized, str)
        deserialized = CacheSerializer.deserialize(serialized, "json")
        assert deserialized == data

    def test_str_serialize(self):
        serialized = CacheSerializer.serialize("hello", "str")
        assert serialized == "hello"
        assert CacheSerializer.deserialize(serialized, "str") == "hello"

    def test_pickle_serialize(self):
        data = {"complex": set([1, 2, 3])}
        serialized = CacheSerializer.serialize(data, "pickle")
        assert isinstance(serialized, str)
        deserialized = CacheSerializer.deserialize(serialized, "pickle")
        assert deserialized == data

    def test_unknown_serializer(self):
        with pytest.raises(ValueError):
            CacheSerializer.serialize("test", "unknown")
        with pytest.raises(ValueError):
            CacheSerializer.deserialize("test", "unknown")


class TestMemoryCache:
    def setup_method(self):
        self.cache = MemoryCache(config=CacheConfig(max_size=100, ttl=60.0))

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_default(self):
        assert self.cache.get("nonexistent") is None
        assert self.cache.get("nonexistent", default="default") == "default"

    def test_delete(self):
        self.cache.set("key1", "value1")
        assert self.cache.delete("key1") is True
        assert self.cache.get("key1") is None

    def test_delete_nonexistent(self):
        assert self.cache.delete("nonexistent") is False

    def test_exists(self):
        self.cache.set("key1", "value1")
        assert self.cache.exists("key1") is True
        assert self.cache.exists("nonexistent") is False

    def test_clear(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        self.cache.clear()
        assert self.cache.get("k1") is None
        assert self.cache.get("k2") is None

    def test_get_many(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        self.cache.set("k3", "v3")
        results = self.cache.get_many(["k1", "k2", "k4"])
        assert results == {"k1": "v1", "k2": "v2"}

    def test_set_many(self):
        self.cache.set_many({"k1": "v1", "k2": "v2"})
        assert self.cache.get("k1") == "v1"
        assert self.cache.get("k2") == "v2"

    def test_delete_many(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        count = self.cache.delete_many(["k1", "k2", "k3"])
        assert count == 2

    def test_get_or_set(self):
        call_count = 0
        def factory():
            nonlocal call_count
            call_count += 1
            return "computed"

        # First call: factory is invoked
        result = self.cache.get_or_set("key", factory)
        assert result == "computed"
        assert call_count == 1

        # Second call: cache hit, factory not invoked
        result = self.cache.get_or_set("key", factory)
        assert result == "computed"
        assert call_count == 1

    def test_cached_decorator(self):
        call_count = 0

        @self.cache.cached(ttl=60)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive(5) == 10
        assert call_count == 1
        assert expensive(5) == 10
        assert call_count == 1  # Cached
        assert expensive(6) == 12
        assert call_count == 2  # New arg, not cached

    def test_stats(self):
        self.cache.set("k1", "v1")
        self.cache.get("k1")  # hit
        self.cache.get("nonexistent")  # miss
        stats = self.cache.get_stats()
        assert stats.l1_hits == 1
        assert stats.l1_misses == 1
        assert stats.l1_sets == 1

    def test_reset_stats(self):
        self.cache.set("k1", "v1")
        self.cache.get("k1")
        self.cache.reset_stats()
        stats = self.cache.get_stats()
        assert stats.l1_hits == 0
        assert stats.l1_misses == 0

    def test_size(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        assert self.cache.size() == 2

    def test_keys(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        keys = self.cache.keys()
        assert len(keys) == 2

    def test_complex_value(self):
        data = {"nested": {"key": [1, 2, 3]}, "num": 42}
        self.cache.set("complex", data)
        result = self.cache.get("complex")
        assert result == data

    def test_update_overwrites(self):
        self.cache.set("key", "old")
        self.cache.set("key", "new")
        assert self.cache.get("key") == "new"

    def test_no_ttl_cache(self):
        cache = MemoryCache(config=CacheConfig(max_size=100, ttl=0))
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_l2_backend_mock(self):
        """Test with a mock L2 backend"""
        mock_l2 = type('MockL2', (), {
            'get': lambda self, k: None,
            'set': lambda self, k, v: None,
            'delete': lambda self, k: None,
            'exists': lambda self, k: False,
        })()

        cache = MemoryCache(
            config=CacheConfig(max_size=100, ttl=60.0, l2_enabled=True),
            l2_backend=mock_l2,
        )
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_l2_backend_hit(self):
        """Test L2 cache hit and L1 backfill"""
        class MockL2:
            def __init__(self):
                self.data = {}
            def get(self, k):
                return self.data.get(k)
            def set(self, k, v):
                self.data[k] = v
            def delete(self, k):
                self.data.pop(k, None)
            def exists(self, k):
                return k in self.data

        mock_l2 = MockL2()
        cache = MemoryCache(
            config=CacheConfig(max_size=100, ttl=60.0, l2_enabled=True, serializer="json"),
            l2_backend=mock_l2,
        )

        # Store directly in L2
        mock_l2.data[cache._make_key("l2key")] = '"l2value"'

        # Clear L1 to force L2 lookup
        cache._l1.clear()

        result = cache.get("l2key")
        assert result == "l2value"
        stats = cache.get_stats()
        assert stats.l2_hits == 1

    def test_concurrent_access(self):
        cache = MemoryCache(config=CacheConfig(max_size=1000, ttl=60.0))

        def worker(i):
            cache.set(f"key_{i}", f"value_{i}")
            cache.get(f"key_{i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cache.size() == 100

    def test_chinese_value(self):
        self.cache.set("中文键", "中文值")
        assert self.cache.get("中文键") == "中文值"
