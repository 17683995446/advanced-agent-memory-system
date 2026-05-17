"""
多级缓存模块 - L1 内存 + L2 可选后端

基于 cachetools 实现高性能多级缓存，支持:
- L1: 内存缓存 (TTLCache / LRUCache)
- L2: 可选 Redis 后端 (通过 RedisCache 适配)
- 自动降级: L2 不可用时自动回退到 L1
- 统计: 命中率、淘汰数等
- 序列化: 支持 JSON 序列化复杂对象

依赖: cachetools>=5.0.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Try to import cachetools
try:
    from cachetools import TTLCache, LRUCache, cached
    _cachetools_available = True
except ImportError:
    _cachetools_available = False
    TTLCache = None
    LRUCache = None


class CacheLevel(Enum):
    """缓存级别"""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"


class EvictionPolicy(Enum):
    """淘汰策略"""
    LRU = "lru"
    TTL = "ttl"
    LFU = "lfu"


@dataclass
class CacheConfig:
    """缓存配置

    Attributes:
        max_size: L1 最大缓存条目数
        ttl: L1 缓存过期时间（秒），0 表示永不过期
        l2_enabled: 是否启用 L2 缓存
        l2_ttl: L2 缓存过期时间（秒）
        key_prefix: 缓存键前缀
        serializer: 序列化方式 ("json", "pickle", "str")
        enable_stats: 是否启用统计
    """
    max_size: int = 1024
    ttl: float = 300.0  # 5 minutes
    l2_enabled: bool = False
    l2_ttl: float = 3600.0  # 1 hour
    key_prefix: str = "mem:"
    serializer: str = "json"
    enable_stats: bool = True


@dataclass
class CacheStats:
    """缓存统计"""
    l1_hits: int = 0
    l1_misses: int = 0
    l2_hits: int = 0
    l2_misses: int = 0
    l1_sets: int = 0
    l1_deletes: int = 0
    l1_evictions: int = 0
    total_sets: int = 0
    total_gets: int = 0

    @property
    def l1_hit_rate(self) -> float:
        total = self.l1_hits + self.l1_misses
        return self.l1_hits / total if total > 0 else 0.0

    @property
    def overall_hit_rate(self) -> float:
        total = self.total_gets
        if total == 0:
            return 0.0
        hits = self.l1_hits + self.l2_hits
        return hits / total

    def to_dict(self) -> dict:
        return {
            "l1_hits": self.l1_hits,
            "l1_misses": self.l1_misses,
            "l2_hits": self.l2_hits,
            "l2_misses": self.l2_misses,
            "l1_hit_rate": round(self.l1_hit_rate, 4),
            "overall_hit_rate": round(self.overall_hit_rate, 4),
            "total_sets": self.total_sets,
            "total_gets": self.total_gets,
            "l1_evictions": self.l1_evictions,
        }


class CacheKeyGenerator:
    """缓存键生成器"""

    @staticmethod
    def generate(prefix: str, *args, **kwargs) -> str:
        """生成缓存键"""
        raw = prefix + ":" + ":".join(str(a) for a in args)
        if kwargs:
            raw += ":" + json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_from_func(prefix: str, fn: Callable, args: tuple, kwargs: dict) -> str:
        """从函数调用生成缓存键"""
        raw = f"{prefix}:{fn.__module__}.{fn.__qualname__}"
        raw += ":" + ":".join(str(a) for a in args)
        if kwargs:
            raw += ":" + json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()


class CacheSerializer:
    """缓存序列化器"""

    @staticmethod
    def serialize(value: Any, method: str = "json") -> str:
        """序列化值"""
        if method == "json":
            return json.dumps(value, default=str, ensure_ascii=False)
        elif method == "pickle":
            return pickle.dumps(value).hex()
        elif method == "str":
            return str(value)
        else:
            raise ValueError(f"Unknown serializer: {method}")

    @staticmethod
    def deserialize(data: str, method: str = "json") -> Any:
        """反序列化值"""
        if method == "json":
            return json.loads(data)
        elif method == "pickle":
            return pickle.loads(bytes.fromhex(data))
        elif method == "str":
            return data
        else:
            raise ValueError(f"Unknown serializer: {method}")


class MemoryCache:
    """
    多级缓存

    L1: 基于 cachetools TTLCache 的内存缓存
    L2: 可选的外部缓存后端（Redis 等）

    Example:
        cache = MemoryCache(config=CacheConfig(max_size=100, ttl=60))

        # 基本操作
        cache.set("key", "value")
        value = cache.get("key")
        cache.delete("key")

        # 装饰器
        @cache.cached(ttl=120)
        def expensive_function(x):
            return x * x

        # 批量操作
        cache.set_many({"k1": "v1", "k2": "v2"})
        results = cache.get_many(["k1", "k2"])
    """

    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        l2_backend: Optional[Any] = None,
    ):
        if not _cachetools_available:
            raise ImportError(
                "cachetools is required for MemoryCache. "
                "Install it with: pip install cachetools"
            )

        self.config = config or CacheConfig()
        self._l2_backend = l2_backend
        self._stats = CacheStats()
        self._lock = threading.RLock()
        self._key_prefix = self.config.key_prefix

        # Initialize L1 cache
        if self.config.ttl > 0:
            self._l1 = TTLCache(
                maxsize=self.config.max_size,
                ttl=self.config.ttl,
            )
        else:
            self._l1 = LRUCache(maxsize=self.config.max_size)

        self._serializer = CacheSerializer()
        self._key_gen = CacheKeyGenerator()

        logger.info(
            "MemoryCache initialized (max_size=%d, ttl=%.1fs, l2=%s)",
            self.config.max_size,
            self.config.ttl,
            "enabled" if self._l2_backend else "disabled",
        )

    def _make_key(self, key: str) -> str:
        """添加前缀"""
        return f"{self._key_prefix}{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存值

        查找顺序: L1 → L2 → default
        """
        full_key = self._make_key(key)
        self._stats.total_gets += 1

        # Try L1
        try:
            value = self._l1.get(full_key)
            if value is not None:
                self._stats.l1_hits += 1
                return value
        except (KeyError, TypeError):
            pass
        self._stats.l1_misses += 1

        # Try L2
        if self._l2_backend is not None:
            try:
                if hasattr(self._l2_backend, 'get'):
                    data = self._l2_backend.get(full_key)
                    if data is not None:
                        self._stats.l2_hits += 1
                        # Backfill L1
                        if isinstance(data, str):
                            value = self._serializer.deserialize(data, self.config.serializer)
                        else:
                            value = data
                        self._l1[full_key] = value
                        return value
                self._stats.l2_misses += 1
            except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as e:
                logger.warning("L2 cache get error: %s", e)
                self._stats.l2_misses += 1

        return default

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        设置缓存值

        同时写入 L1 和 L2。
        """
        full_key = self._make_key(key)
        self._stats.total_sets += 1
        self._stats.l1_sets += 1

        # Write L1
        self._l1[full_key] = value

        # Write L2
        if self._l2_backend is not None:
            try:
                if hasattr(self._l2_backend, 'set'):
                    serialized = self._serializer.serialize(value, self.config.serializer)
                    l2_ttl = ttl or self.config.l2_ttl
                    if hasattr(self._l2_backend, 'setex'):
                        self._l2_backend.setex(full_key, int(l2_ttl), serialized)
                    else:
                        self._l2_backend.set(full_key, serialized)
            except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as e:
                logger.warning("L2 cache set error: %s", e)

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        full_key = self._make_key(key)
        self._stats.l1_deletes += 1

        deleted = False
        try:
            del self._l1[full_key]
            deleted = True
        except KeyError:
            pass

        if self._l2_backend is not None:
            try:
                if hasattr(self._l2_backend, 'delete'):
                    self._l2_backend.delete(full_key)
            except (ConnectionError, TimeoutError, OSError, ValueError) as e:
                logger.warning("L2 cache delete error: %s", e)

        return deleted

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """批量获取"""
        results = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                results[key] = value
        return results

    def set_many(self, mapping: dict[str, Any], ttl: Optional[float] = None):
        """批量设置"""
        for key, value in mapping.items():
            self.set(key, value, ttl=ttl)

    def delete_many(self, keys: list[str]) -> int:
        """批量删除"""
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        full_key = self._make_key(key)
        if full_key in self._l1:
            return True
        if self._l2_backend is not None:
            try:
                if hasattr(self._l2_backend, 'exists'):
                    return bool(self._l2_backend.exists(full_key))
            except (ConnectionError, TimeoutError, OSError):
                pass
        return False

    def clear(self):
        """清空所有缓存"""
        self._l1.clear()
        if self._l2_backend is not None:
            try:
                if hasattr(self._l2_backend, 'flushdb') or hasattr(self._l2_backend, 'flush'):
                    flush_fn = getattr(self._l2_backend, 'flushdb', getattr(self._l2_backend, 'flush', None))
                    if flush_fn:
                        flush_fn()
            except (ConnectionError, TimeoutError, OSError, ValueError) as e:
                logger.warning("L2 cache clear error: %s", e)

    def get_or_set(self, key: str, factory: Callable[[], T], ttl: Optional[float] = None) -> T:
        """获取或设置（缓存穿透保护）"""
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def cached(self, ttl: Optional[float] = None, key_prefix: Optional[str] = None):
        """缓存装饰器"""
        def decorator(fn):
            _prefix = key_prefix or f"fn:{fn.__qualname__}"

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                cache_key = self._key_gen.generate_from_func(
                    self._key_prefix + _prefix, fn, args, kwargs
                )
                return self.get_or_set(cache_key, lambda: fn(*args, **kwargs), ttl=ttl)
            return wrapper
        return decorator

    def get_stats(self) -> CacheStats:
        """获取缓存统计"""
        return self._stats

    def reset_stats(self):
        """重置统计"""
        self._stats = CacheStats()

    def size(self) -> int:
        """返回 L1 缓存大小"""
        return len(self._l1)

    def keys(self) -> list[str]:
        """返回 L1 缓存所有键"""
        return list(self._l1.keys())


# Need functools for the decorator
import functools

__all__ = [
    "CacheLevel",
    "EvictionPolicy",
    "CacheConfig",
    "CacheStats",
    "CacheKeyGenerator",
    "CacheSerializer",
    "MemoryCache",
]
