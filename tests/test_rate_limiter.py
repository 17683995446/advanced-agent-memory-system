"""Unit tests for the rate limiter module."""
import pytest
import time
import threading
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.infra.api_rate_limiter import (
    RateLimiter,
    RateLimitStrategy,
    RateLimitResult,
    TokenBucket,
    SlidingWindowCounter,
    ConcurrencyLimiter,
    MultiRateLimiter,
)


class TestTokenBucket:
    def test_create(self):
        bucket = TokenBucket(rate=10, capacity=20)
        assert bucket.available == 20

    def test_consume_success(self):
        bucket = TokenBucket(rate=10, capacity=5)
        assert bucket.consume(1) is True
        assert bucket.available == 4

    def test_consume_multiple(self):
        bucket = TokenBucket(rate=10, capacity=5)
        assert bucket.consume(3) is True
        assert bucket.available == 2

    def test_consume_exceeds_capacity(self):
        bucket = TokenBucket(rate=10, capacity=5)
        assert bucket.consume(6) is False
        assert bucket.available == 5  # 未消费

    def test_consume_until_empty(self):
        bucket = TokenBucket(rate=10, capacity=3)
        bucket.consume(1)
        bucket.consume(1)
        bucket.consume(1)
        assert bucket.consume(1) is False

    def test_refill_over_time(self):
        bucket = TokenBucket(rate=1000, capacity=10)  # 高速率便于测试
        bucket.consume(10)  # 耗尽
        assert bucket.available == 0
        time.sleep(0.02)  # 等待补充
        assert bucket.available > 0

    def test_retry_after(self):
        bucket = TokenBucket(rate=10, capacity=5)
        bucket.consume(5)
        result = bucket.consume(1)
        assert result is False
        assert bucket.retry_after > 0

    def test_retry_after_when_available(self):
        bucket = TokenBucket(rate=10, capacity=5)
        assert bucket.retry_after == 0.0

    def test_reset(self):
        bucket = TokenBucket(rate=10, capacity=5)
        bucket.consume(5)
        bucket.reset()
        assert bucket.available == 5


class TestSlidingWindowCounter:
    def test_allow_within_limit(self):
        sw = SlidingWindowCounter(limit=5, window=60)
        for _ in range(5):
            assert sw.allow() is True

    def test_deny_over_limit(self):
        sw = SlidingWindowCounter(limit=3, window=60)
        sw.allow()
        sw.allow()
        sw.allow()
        assert sw.allow() is False

    def test_count(self):
        sw = SlidingWindowCounter(limit=10, window=60)
        sw.allow()
        sw.allow()
        assert sw.count == 2

    def test_remaining(self):
        sw = SlidingWindowCounter(limit=5, window=60)
        sw.allow()
        assert sw.remaining == 4

    def test_window_expires(self):
        sw = SlidingWindowCounter(limit=3, window=0.1)
        sw.allow()
        sw.allow()
        sw.allow()
        assert sw.allow() is False
        time.sleep(0.15)
        assert sw.allow() is True

    def test_reset(self):
        sw = SlidingWindowCounter(limit=3, window=60)
        sw.allow()
        sw.allow()
        sw.reset()
        assert sw.count == 0


class TestConcurrencyLimiter:
    def test_acquire_within_limit(self):
        cl = ConcurrencyLimiter(max_concurrent=3)
        assert cl.acquire() is True
        assert cl.current == 1

    def test_deny_over_limit(self):
        cl = ConcurrencyLimiter(max_concurrent=2)
        cl.acquire()
        cl.acquire()
        assert cl.acquire() is False

    def test_release(self):
        cl = ConcurrencyLimiter(max_concurrent=2)
        cl.acquire()
        cl.acquire()
        cl.release()
        assert cl.current == 1
        assert cl.acquire() is True

    def test_available(self):
        cl = ConcurrencyLimiter(max_concurrent=5)
        cl.acquire()
        assert cl.available == 4


class TestRateLimiter:
    def test_token_bucket_strategy(self):
        rl = RateLimiter(strategy=RateLimitStrategy.TOKEN_BUCKET, rate=10, capacity=5)
        result = rl.check()
        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert result.remaining >= 0

    def test_sliding_window_strategy(self):
        rl = RateLimiter(strategy=RateLimitStrategy.SLIDING_WINDOW, limit=3, window=60)
        rl.check()
        rl.check()
        rl.check()
        result = rl.check()
        assert result.allowed is False

    def test_fixed_window_strategy(self):
        rl = RateLimiter(strategy=RateLimitStrategy.FIXED_WINDOW, limit=3, window=60)
        for _ in range(3):
            assert rl.check().allowed is True
        assert rl.check().allowed is False

    def test_concurrency_strategy(self):
        rl = RateLimiter(strategy=RateLimitStrategy.CONCURRENCY, max_concurrent=2)
        assert rl.check().allowed is True
        assert rl.check().allowed is True
        assert rl.check().allowed is False
        rl.release()
        assert rl.check().allowed is True

    def test_rate_limit_result_fields(self):
        rl = RateLimiter(strategy=RateLimitStrategy.TOKEN_BUCKET, rate=10, capacity=5)
        result = rl.check()
        assert hasattr(result, 'allowed')
        assert hasattr(result, 'remaining')
        assert hasattr(result, 'retry_after')
        assert hasattr(result, 'limit')

    def test_reset(self):
        rl = RateLimiter(strategy=RateLimitStrategy.TOKEN_BUCKET, rate=10, capacity=3)
        rl.check()
        rl.check()
        rl.check()
        assert rl.check().allowed is False
        rl.reset()
        assert rl.check().allowed is True


class TestMultiRateLimiter:
    def test_check_different_keys(self):
        ml = MultiRateLimiter(default_rate=10, default_capacity=5)
        r1 = ml.check("user:1")
        r2 = ml.check("user:2")
        assert r1.allowed is True
        assert r2.allowed is True

    def test_rate_limit_per_key(self):
        ml = MultiRateLimiter(default_rate=10, default_capacity=2)
        ml.check("key1")
        ml.check("key1")
        result = ml.check("key1")
        assert result.allowed is False
        # Different key should be allowed
        assert ml.check("key2").allowed is True

    def test_custom_rate_per_key(self):
        ml = MultiRateLimiter(default_rate=1, default_capacity=1)
        ml.check("key1")
        assert ml.check("key1").allowed is False
        # Custom rate
        result = ml.check("key1_custom", rate=100, capacity=100)
        assert result.allowed is True

    def test_reset_key(self):
        ml = MultiRateLimiter(default_rate=10, default_capacity=2)
        ml.check("key1")
        ml.check("key1")
        ml.reset("key1")
        assert ml.check("key1").allowed is True

    def test_reset_all(self):
        ml = MultiRateLimiter(default_rate=10, default_capacity=2)
        ml.check("a")
        ml.check("b")
        ml.reset()
        assert ml.get_stats()["total_dimensions"] == 0

    def test_get_stats(self):
        ml = MultiRateLimiter()
        ml.check("a")
        ml.check("b")
        stats = ml.get_stats()
        assert stats["total_dimensions"] == 2
