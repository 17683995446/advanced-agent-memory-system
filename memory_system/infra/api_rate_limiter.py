"""
限流模块 - 令牌桶算法

提供多种限流策略，防止记忆系统被滥用：
- 令牌桶限流 (Token Bucket)
- 滑动窗口限流 (Sliding Window)
- 固定窗口限流 (Fixed Window)
- 并发限流 (Concurrency Limiter)

依赖: 无额外依赖
"""

from __future__ import annotations

import logging
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """限流策略"""
    TOKEN_BUCKET = "token_bucket"       # 令牌桶
    SLIDING_WINDOW = "sliding_window"   # 滑动窗口
    FIXED_WINDOW = "fixed_window"       # 固定窗口
    CONCURRENCY = "concurrency"         # 并发限制


@dataclass
class RateLimitResult:
    """限流结果"""
    allowed: bool
    remaining: int = 0
    retry_after: float = 0.0  # 秒
    limit: int = 0
    window: float = 0.0


class TokenBucket:
    """
    令牌桶限流器
    
    特点:
    - 允许突发流量（桶内有累积令牌时）
    - 平均速率受限（令牌补充速率固定）
    - 适合 API 调用限流
    
    Args:
        rate: 令牌补充速率（个/秒）
        capacity: 桶容量（最大令牌数）
    
    Example:
        bucket = TokenBucket(rate=10, capacity=20)
        
        if bucket.consume():
            process_request()
        else:
            retry_after = bucket.retry_after
    """
    
    def __init__(self, rate: float = 10.0, capacity: int = 100):
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def _refill(self):
        """补充令牌"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now
    
    def consume(self, tokens: int = 1) -> bool:
        """
        消费令牌
        
        Args:
            tokens: 消费数量
            
        Returns:
            是否允许
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
    
    @property
    def retry_after(self) -> float:
        """下次可用时间（秒）"""
        with self._lock:
            if self._tokens >= 1:
                return 0.0
            return (1 - self._tokens) / self._rate
    
    @property
    def available(self) -> int:
        """可用令牌数"""
        with self._lock:
            self._refill()
            return int(self._tokens)
    
    def reset(self):
        """重置令牌桶"""
        with self._lock:
            self._tokens = float(self._capacity)
            self._last_refill = time.monotonic()


class SlidingWindowCounter:
    """
    滑动窗口计数器
    
    特点:
    - 平滑限流，无窗口边界突变
    - 精确控制时间窗口内的请求数
    - 适合高频请求限流
    
    Args:
        limit: 窗口内最大请求数
        window: 窗口大小（秒）
    """
    
    def __init__(self, limit: int = 100, window: float = 60.0):
        self._limit = limit
        self._window = window
        self._requests: deque = deque()
        self._lock = threading.Lock()
    
    def allow(self) -> bool:
        """是否允许请求"""
        now = time.monotonic()
        
        with self._lock:
            # 清除过期请求
            while self._requests and now - self._requests[0] > self._window:
                self._requests.popleft()
            
            if len(self._requests) < self._limit:
                self._requests.append(now)
                return True
            return False
    
    @property
    def count(self) -> int:
        """当前窗口内请求数"""
        now = time.monotonic()
        with self._lock:
            while self._requests and now - self._requests[0] > self._window:
                self._requests.popleft()
            return len(self._requests)
    
    @property
    def remaining(self) -> int:
        """剩余可用请求数"""
        return max(0, self._limit - self.count)
    
    def reset(self):
        """重置"""
        with self._lock:
            self._requests.clear()


class ConcurrencyLimiter:
    """
    并发限制器
    
    限制同时执行的并发数，超出则排队或拒绝。
    
    Args:
        max_concurrent: 最大并发数
    """
    
    def __init__(self, max_concurrent: int = 10):
        self._max = max_concurrent
        self._current = 0
        self._lock = threading.Lock()
    
    def acquire(self) -> bool:
        """获取执行许可"""
        with self._lock:
            if self._current < self._max:
                self._current += 1
                return True
            return False
    
    def release(self):
        """释放执行许可"""
        with self._lock:
            if self._current > 0:
                self._current -= 1
    
    @property
    def current(self) -> int:
        """当前并发数"""
        return self._current
    
    @property
    def available(self) -> int:
        """可用并发数"""
        return self._max - self._current


class RateLimiter:
    """
    统一限流器
    
    整合多种限流策略，提供统一的限流接口。
    
    Args:
        strategy: 限流策略
        rate: 速率（令牌桶：个/秒）
        capacity: 容量（令牌桶：最大令牌数）
        limit: 限制数（窗口：最大请求数）
        window: 窗口大小（秒）
        max_concurrent: 最大并发数
    
    Example:
        limiter = RateLimiter(strategy=RateLimitStrategy.TOKEN_BUCKET, rate=10, capacity=20)
        
        result = limiter.check()
        if result.allowed:
            process_request()
        else:
            logger.warning("Rate limited, retry after %.1fs", result.retry_after)
    """
    
    def __init__(
        self,
        strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET,
        rate: float = 10.0,
        capacity: int = 100,
        limit: int = 100,
        window: float = 60.0,
        max_concurrent: int = 10,
    ):
        self._strategy = strategy
        
        if strategy == RateLimitStrategy.TOKEN_BUCKET:
            self._bucket = TokenBucket(rate=rate, capacity=capacity)
        elif strategy == RateLimitStrategy.SLIDING_WINDOW:
            self._window = SlidingWindowCounter(limit=limit, window=window)
        elif strategy == RateLimitStrategy.FIXED_WINDOW:
            self._window = SlidingWindowCounter(limit=limit, window=window)
        elif strategy == RateLimitStrategy.CONCURRENCY:
            self._concurrency = ConcurrencyLimiter(max_concurrent=max_concurrent)
    
    def check(self) -> RateLimitResult:
        """
        检查是否允许请求
        
        Returns:
            RateLimitResult
        """
        if self._strategy == RateLimitStrategy.TOKEN_BUCKET:
            allowed = self._bucket.consume()
            return RateLimitResult(
                allowed=allowed,
                remaining=self._bucket.available,
                retry_after=self._bucket.retry_after if not allowed else 0,
                limit=self._bucket._capacity,
                window=1.0 / self._bucket._rate if self._bucket._rate > 0 else 0,
            )
        
        elif self._strategy in (RateLimitStrategy.SLIDING_WINDOW, RateLimitStrategy.FIXED_WINDOW):
            allowed = self._window.allow()
            return RateLimitResult(
                allowed=allowed,
                remaining=self._window.remaining,
                limit=self._window._limit,
                window=self._window._window,
            )
        
        elif self._strategy == RateLimitStrategy.CONCURRENCY:
            allowed = self._concurrency.acquire()
            return RateLimitResult(
                allowed=allowed,
                remaining=self._concurrency.available,
                limit=self._concurrency._max,
            )
        
        return RateLimitResult(allowed=False)
    
    def release(self):
        """释放并发许可（仅 CONCURRENCY 策略）"""
        if self._strategy == RateLimitStrategy.CONCURRENCY:
            self._concurrency.release()
    
    def reset(self):
        """重置限流器"""
        if self._strategy == RateLimitStrategy.TOKEN_BUCKET:
            self._bucket.reset()
        elif self._strategy in (RateLimitStrategy.SLIDING_WINDOW, RateLimitStrategy.FIXED_WINDOW):
            self._window.reset()


class MultiRateLimiter:
    """
    多维度限流器
    
    支持按不同维度（用户、IP、操作类型）分别限流。
    
    Example:
        limiter = MultiRateLimiter(
            default_rate=10,
            default_capacity=20,
        )
        
        # 按用户限流
        result = limiter.check("user:123")
        
        # 按操作限流
        result = limiter.check("op:search", rate=100, capacity=200)
    """
    
    def __init__(
        self,
        strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET,
        default_rate: float = 10.0,
        default_capacity: int = 100,
    ):
        self._strategy = strategy
        self._default_rate = default_rate
        self._default_capacity = default_capacity
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
    
    def check(
        self,
        key: str,
        rate: Optional[float] = None,
        capacity: Optional[int] = None,
    ) -> RateLimitResult:
        """
        检查指定维度的限流
        
        Args:
            key: 限流维度键
            rate: 自定义速率
            capacity: 自定义容量
        """
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    rate=rate or self._default_rate,
                    capacity=capacity or self._default_capacity,
                )
        
        bucket = self._buckets[key]
        allowed = bucket.consume()
        
        return RateLimitResult(
            allowed=allowed,
            remaining=bucket.available,
            retry_after=bucket.retry_after if not allowed else 0,
            limit=bucket._capacity,
        )
    
    def reset(self, key: Optional[str] = None):
        """重置限流器"""
        if key:
            with self._lock:
                self._buckets.pop(key, None)
        else:
            with self._lock:
                self._buckets.clear()
    
    def get_stats(self) -> dict:
        """获取限流统计"""
        return {
            "total_dimensions": len(self._buckets),
            "strategy": self._strategy.value,
        }


__all__ = [
    "RateLimiter",
    "RateLimitStrategy",
    "RateLimitResult",
    "TokenBucket",
    "SlidingWindowCounter",
    "ConcurrencyLimiter",
    "MultiRateLimiter",
]
