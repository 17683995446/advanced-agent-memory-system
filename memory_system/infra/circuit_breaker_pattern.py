"""
断路器模块 - 保护外部依赖的容错机制

基于状态机实现断路器模式，防止级联故障。
支持装饰器、上下文管理器、和手动调用三种使用方式。

状态转换:
  CLOSED → (失败率超阈值) → OPEN
  OPEN → (超时后) → HALF_OPEN
  HALF_OPEN → (探测成功) → CLOSED
  HALF_OPEN → (探测失败) → OPEN

依赖: Python 标准库 (enum, time, threading, dataclasses, functools, logging)
"""

from __future__ import annotations

import enum
import functools
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(enum.Enum):
    """断路器状态"""
    CLOSED = "closed"      # 正常通行
    OPEN = "open"          # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 半开，允许探测


@dataclass
class CircuitBreakerConfig:
    """断路器配置

    Attributes:
        failure_threshold: 触发熔断的连续失败次数
        recovery_timeout: 熔断后等待恢复的时间（秒）
        half_open_max_calls: 半开状态允许的最大探测请求数
        success_threshold: 半开状态下连续成功多少次后恢复关闭
        timeout: 单次请求超时时间（秒），None 表示不限
        expected_exception: 触发失败的异常类型元组
        exclude_exception: 排除的异常类型（不触发失败计数）
    """
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    success_threshold: int = 3
    timeout: Optional[float] = None
    expected_exception: tuple = (Exception,)
    exclude_exception: tuple = ()


@dataclass
class CircuitStats:
    """断路器运行统计"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    last_failure_time: Optional[float] = None
    last_state_change_time: float = field(default_factory=time.time)
    last_error: Optional[str] = None
    half_open_calls: int = 0


class CircuitBreakerError(Exception):
    """断路器打开时抛出的异常"""
    pass


class CircuitBreaker:
    """
    断路器实现

    支持三种使用方式:
    1. 装饰器: @CircuitBreaker(config=config)
    2. 上下文管理器: with breaker.call() as cb: ...
    3. 手动调用: breaker.execute(fn, *args, **kwargs)

    Example:
        breaker = CircuitBreaker("embedding_api", config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=10.0,
        ))

        @breaker
        def call_api():
            ...

        # 或者
        result = breaker.execute(call_api)
    """

    def __init__(self, name: str = "default", config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change_time = time.time()
        self._last_error: Optional[str] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
        self._on_state_change_callbacks: list[Callable[[CircuitState, CircuitState], None]] = []

    @property
    def state(self) -> CircuitState:
        """获取当前状态（线程安全）"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # 检查是否超时恢复
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.recovery_timeout:
                        self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        old_state = self._state
        if old_state == new_state:
            return
        self._state = new_state
        self._last_state_change_time = time.time()

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0

        logger.info(
            "CircuitBreaker '%s': %s → %s",
            self.name, old_state.value, new_state.value,
        )

        for callback in self._on_state_change_callbacks:
            try:
                callback(old_state, new_state)
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("State change callback error: %s", e)

    def _on_success(self):
        """成功回调"""
        with self._lock:
            self._success_count += 1
            self._total_calls += 1

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                # 连续成功重置部分失败计数
                self._failure_count = max(0, self._failure_count - 1)

    def _on_failure(self, error: Exception):
        """失败回调"""
        with self._lock:
            self._failure_count += 1
            self._total_calls += 1
            self._last_failure_time = time.time()
            self._last_error = str(error)

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def _is_expected_exception(self, exc: Exception) -> bool:
        """判断异常是否属于预期异常"""
        if isinstance(exc, self.config.exclude_exception):
            return False
        return isinstance(exc, self.config.expected_exception)

    def execute(self, fn: Callable[..., T], *args, **kwargs) -> T:
        """
        执行函数，受断路器保护

        Args:
            fn: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            CircuitBreakerError: 断路器打开时
            Exception: 原始异常
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"CircuitBreaker '{self.name}' is OPEN. "
                f"Recovery timeout: {self.config.recovery_timeout}s"
            )

        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerError(
                        f"CircuitBreaker '{self.name}' is HALF_OPEN with max probe calls reached"
                    )

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if self._is_expected_exception(e):
                self._on_failure(e)
            raise

    def __call__(self, fn: Callable[..., T]) -> Callable[..., T]:
        """装饰器模式"""
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return self.execute(fn, *args, **kwargs)
        wrapper._circuit_breaker = self
        return wrapper

    def get_stats(self) -> CircuitStats:
        """获取运行统计"""
        with self._lock:
            return CircuitStats(
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                total_calls=self._total_calls,
                last_failure_time=self._last_failure_time,
                last_state_change_time=self._last_state_change_time,
                last_error=self._last_error,
                half_open_calls=self._half_open_calls,
            )

    def reset(self):
        """手动重置断路器"""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._total_calls = 0
            self._last_failure_time = None
            self._last_error = None
            self._half_open_calls = 0

    def force_open(self):
        """手动打开断路器"""
        with self._lock:
            self._last_failure_time = time.time()
            self._transition_to(CircuitState.OPEN)

    def on_state_change(self, callback: Callable[[CircuitState, CircuitState], None]):
        """注册状态变更回调"""
        self._on_state_change_callbacks.append(callback)


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry - 全局断路器注册表
# ---------------------------------------------------------------------------

class CircuitBreakerRegistry:
    """
    断路器注册表

    集中管理多个断路器实例，支持按名称获取。
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def register(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """注册或获取断路器"""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """获取断路器"""
        return self._breakers.get(name)

    def list_all(self) -> dict[str, dict]:
        """列出所有断路器及其状态"""
        return {
            name: breaker.get_stats().__dict__
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """重置所有断路器"""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry
_global_registry: Optional[CircuitBreakerRegistry] = None
_registry_lock = threading.Lock()


def get_circuit_registry() -> CircuitBreakerRegistry:
    """获取全局断路器注册表（线程安全）"""
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = CircuitBreakerRegistry()
    return _global_registry


def reset_circuit_registry():
    """重置全局断路器注册表"""
    global _global_registry
    with _registry_lock:
        _global_registry = None


__all__ = [
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitStats",
    "CircuitBreakerError",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "get_circuit_registry",
    "reset_circuit_registry",
]
