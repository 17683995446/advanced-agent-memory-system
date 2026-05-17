"""Unit tests for the circuit_breaker module."""
import pytest
import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.infra.circuit_breaker_pattern import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitStats,
    CircuitBreakerError,
    CircuitBreaker,
    CircuitBreakerRegistry,
    get_circuit_registry,
    reset_circuit_registry,
)


class TestCircuitState:
    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_all_states(self):
        assert len(CircuitState) == 3


class TestCircuitBreakerConfig:
    def test_defaults(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 3
        assert config.timeout is None
        assert config.expected_exception == (Exception,)
        assert config.exclude_exception == ()

    def test_custom_values(self):
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=10.0,
            half_open_max_calls=2,
            success_threshold=1,
            timeout=5.0,
            expected_exception=(ValueError, KeyError),
            exclude_exception=(TypeError,),
        )
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 10.0
        assert config.half_open_max_calls == 2
        assert config.success_threshold == 1
        assert config.timeout == 5.0
        assert config.expected_exception == (ValueError, KeyError)
        assert config.exclude_exception == (TypeError,)


class TestCircuitBreakerStats:
    def test_defaults(self):
        stats = CircuitStats()
        assert stats.state == CircuitState.CLOSED
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.total_calls == 0
        assert stats.last_failure_time is None
        assert stats.last_error is None
        assert stats.half_open_calls == 0


class TestCircuitBreaker:
    def setup_method(self):
        reset_circuit_registry()

    def test_initial_state_closed(self):
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED

    def test_successful_call(self):
        breaker = CircuitBreaker("test")
        result = breaker.execute(lambda: 42)
        assert result == 42
        stats = breaker.get_stats()
        assert stats.success_count == 1
        assert stats.failure_count == 0
        assert stats.total_calls == 1

    def test_failed_call_increments_failure(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=3))
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        stats = breaker.get_stats()
        assert stats.failure_count == 2

    def test_opens_after_threshold(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert breaker.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert breaker.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerError):
            breaker.execute(lambda: 42)

    def test_half_open_after_timeout(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
        ))
        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert breaker.state == CircuitState.OPEN
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=2,
        ))
        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        breaker.execute(lambda: "ok")
        breaker.execute(lambda: "ok")
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
        ))
        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert breaker.state == CircuitState.OPEN

    def test_exclude_exception_no_count(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1,
            exclude_exception=(TypeError,),
        ))
        with pytest.raises(TypeError):
            breaker.execute(lambda: (_ for _ in ()).throw(TypeError("excluded")))
        # Should NOT open because TypeError is excluded
        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats.failure_count == 0

    def test_decorator_usage(self):
        breaker = CircuitBreaker("decorator_test")

        @breaker
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5
        assert breaker.get_stats().success_count == 1

    def test_decorator_preserves_name(self):
        breaker = CircuitBreaker("name_test")

        @breaker
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_reset(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert breaker.state == CircuitState.OPEN
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats.failure_count == 0

    def test_force_open(self):
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        breaker.force_open()
        assert breaker.state == CircuitState.OPEN

    def test_state_change_callback(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        changes = []
        breaker.on_state_change(lambda old, new: changes.append((old, new)))

        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))

        assert len(changes) == 1
        assert changes[0] == (CircuitState.CLOSED, CircuitState.OPEN)

    def test_get_stats(self):
        breaker = CircuitBreaker("test")
        stats = breaker.get_stats()
        assert isinstance(stats, CircuitStats)
        assert stats.state == CircuitState.CLOSED

    def test_custom_name(self):
        breaker = CircuitBreaker("my_breaker")
        assert breaker.name == "my_breaker"

    def test_success_decrements_failure(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=3))
        # 2 failures
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert breaker.state == CircuitState.CLOSED
        # 1 success should decrement
        breaker.execute(lambda: "ok")
        stats = breaker.get_stats()
        assert stats.failure_count == 1

    def test_concurrent_access(self):
        breaker = CircuitBreaker("concurrent", config=CircuitBreakerConfig(failure_threshold=100))
        results = []

        def worker(val):
            try:
                result = breaker.execute(lambda v=val: v * 2)
                results.append(result)
            except Exception:
                pass

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        assert breaker.get_stats().total_calls == 50

    def test_last_error_recorded(self):
        breaker = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=5))
        with pytest.raises(ValueError):
            breaker.execute(lambda: (_ for _ in ()).throw(ValueError("specific error")))
        assert "specific error" in breaker.get_stats().last_error


class TestCircuitBreakerRegistry:
    def setup_method(self):
        reset_circuit_registry()

    def test_register_and_get(self):
        registry = CircuitBreakerRegistry()
        breaker = registry.register("test", CircuitBreakerConfig(failure_threshold=3))
        assert registry.get("test") is breaker

    def test_register_returns_same_instance(self):
        registry = CircuitBreakerRegistry()
        b1 = registry.register("test")
        b2 = registry.register("test")
        assert b1 is b2

    def test_get_nonexistent(self):
        registry = CircuitBreakerRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all(self):
        registry = CircuitBreakerRegistry()
        registry.register("b1")
        registry.register("b2")
        all_breakers = registry.list_all()
        assert "b1" in all_breakers
        assert "b2" in all_breakers

    def test_reset_all(self):
        registry = CircuitBreakerRegistry()
        b1 = registry.register("b1", CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(ValueError):
            b1.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert b1.state == CircuitState.OPEN
        registry.reset_all()
        assert b1.state == CircuitState.CLOSED


class TestGlobalRegistry:
    def setup_method(self):
        reset_circuit_registry()

    def test_get_singleton(self):
        r1 = get_circuit_registry()
        r2 = get_circuit_registry()
        assert r1 is r2

    def test_reset(self):
        r1 = get_circuit_registry()
        reset_circuit_registry()
        r2 = get_circuit_registry()
        assert r1 is not r2
