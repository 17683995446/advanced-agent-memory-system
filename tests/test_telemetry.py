"""Unit tests for the telemetry module."""
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.observability.opentelemetry_tracing import (
    TelemetryConfig,
    SpanKind,
    SpanStatus,
    Span,
    TelemetryManager,
    SpanContextManager,
    get_telemetry,
    reset_telemetry,
)


class TestSpanKind:
    def test_all_kinds(self):
        assert SpanKind.INTERNAL.value == "internal"
        assert SpanKind.SERVER.value == "server"
        assert SpanKind.CLIENT.value == "client"
        assert SpanKind.PRODUCER.value == "producer"
        assert SpanKind.CONSUMER.value == "consumer"


class TestSpanStatus:
    def test_all_statuses(self):
        assert SpanStatus.UNSET.value == "unset"
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"


class TestSpan:
    def test_defaults(self):
        span = Span(name="test_span")
        assert span.name == "test_span"
        assert span.span_id != ""
        assert span.trace_id != ""
        assert span.status == SpanStatus.UNSET
        assert span.attributes == {}
        assert span.events == []
    
    def test_set_attribute(self):
        span = Span(name="test")
        span.set_attribute("key1", "value1")
        span.set_attribute("key2", 42)
        assert span.attributes["key1"] == "value1"
        assert span.attributes["key2"] == 42
    
    def test_add_event(self):
        span = Span(name="test")
        span.add_event("custom_event", {"info": "test"})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "custom_event"
        assert "timestamp" in span.events[0]
    
    def test_set_status(self):
        span = Span(name="test")
        span.set_status(SpanStatus.OK)
        assert span.status == SpanStatus.OK
    
    def test_end(self):
        span = Span(name="test")
        time.sleep(0.01)
        span.end()
        assert span.end_time is not None
        assert span.duration_ms >= 10
    
    def test_to_dict(self):
        span = Span(name="test", kind=SpanKind.INTERNAL)
        span.set_attribute("key", "value")
        span.add_event("event1")
        span.set_status(SpanStatus.OK)
        span.end()
        
        d = span.to_dict()
        assert d["name"] == "test"
        assert d["attributes"]["key"] == "value"
        assert len(d["events"]) == 1
        assert d["status"] == "ok"
        assert "duration_ms" in d


class TestTelemetryConfig:
    def test_defaults(self):
        config = TelemetryConfig()
        assert config.service_name == "agent-memory"
        assert config.enabled is True
        assert config.trace_enabled is True
        assert config.metrics_enabled is True
        assert config.exporter == "console"
    
    def test_custom(self):
        config = TelemetryConfig(
            service_name="test-service",
            service_version="2.0.0",
            exporter="otlp",
            otlp_endpoint="http://localhost:4317",
            sample_rate=0.5,
        )
        assert config.service_name == "test-service"
        assert config.service_version == "2.0.0"
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.sample_rate == 0.5


class TestTelemetryManager:
    def setup_method(self):
        reset_telemetry()
    
    def teardown_method(self):
        reset_telemetry()
    
    def test_disabled_telemetry(self):
        config = TelemetryConfig(enabled=False)
        tm = TelemetryManager(config)
        assert tm._enabled is False
    
    def test_start_span(self):
        tm = TelemetryManager()
        span = tm.start_span("test_span")
        assert span is not None
        assert span.name == "test_span"
    
    def test_end_span(self):
        tm = TelemetryManager()
        span = tm.start_span("test_span")
        tm.end_span(span, SpanStatus.OK)
        assert span.status == SpanStatus.OK
        assert span.end_time is not None
    
    def test_span_with_attributes(self):
        tm = TelemetryManager()
        span = tm.start_span("test", attributes={"key": "value", "num": 42})
        assert span.attributes["key"] == "value"
        assert span.attributes["num"] == 42
    
    def test_span_context_manager(self):
        tm = TelemetryManager()
        with SpanContextManager(tm, "test_span") as span:
            span.set_attribute("in_context", True)
        assert span.duration_ms > 0
    
    def test_trace_decorator(self):
        tm = TelemetryManager()
        
        @tm.trace()
        def my_function(x, y):
            return x + y
        
        result = my_function(2, 3)
        assert result == 5
        
        spans = tm.get_traces()
        assert len(spans) >= 1
        span_names = [s["name"] for s in spans]
        assert any("my_function" in name for name in span_names)
    
    def test_trace_decorator_with_exception(self):
        tm = TelemetryManager()
        
        @tm.trace()
        def failing_function():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        spans = tm.get_traces()
        error_spans = [s for s in spans if s["status"] == "error"]
        assert len(error_spans) >= 1
    
    def test_increment_counter(self):
        tm = TelemetryManager()
        tm.increment_counter("operations", value=1.0)
        tm.increment_counter("operations", value=2.0)
        tm.increment_counter("bytes", value=100.0)
        
        summary = tm.get_metrics_summary()
        assert "operations" in str(summary["counters"])
    
    def test_record_histogram(self):
        tm = TelemetryManager()
        tm.record_histogram("latency", 50.0)
        tm.record_histogram("latency", 100.0)
        tm.record_histogram("latency", 150.0)
        
        summary = tm.get_metrics_summary()
        hist_data = summary["histograms"]
        assert len(hist_data) > 0
    
    def test_set_gauge(self):
        tm = TelemetryManager()
        tm.set_gauge("cpu_percent", 45.5)
        tm.set_gauge("memory_mb", 1024.0)
        
        summary = tm.get_metrics_summary()
        assert "cpu_percent" in str(summary["gauges"])
    
    def test_get_traces(self):
        tm = TelemetryManager()
        for i in range(5):
            span = tm.start_span(f"span_{i}")
            tm.end_span(span)
        
        traces = tm.get_traces(limit=3)
        assert len(traces) == 3
    
    def test_get_current_span(self):
        tm = TelemetryManager()
        span = tm.get_current_span()
        # Returns None in in-memory mode without active context
        assert span is None
    
    def test_metrics_summary(self):
        tm = TelemetryManager()
        tm.increment_counter("test_counter", 5.0)
        tm.record_histogram("test_histogram", 42.0)
        tm.set_gauge("test_gauge", 100.0)
        
        summary = tm.get_metrics_summary()
        assert "counters" in summary
        assert "histograms" in summary
        assert "gauges" in summary
        assert "spans_count" in summary


class TestGlobalTelemetry:
    def setup_method(self):
        reset_telemetry()
    
    def teardown_method(self):
        reset_telemetry()
    
    def test_singleton(self):
        t1 = get_telemetry()
        t2 = get_telemetry()
        assert t1 is t2
    
    def test_reset(self):
        t1 = get_telemetry()
        reset_telemetry()
        t2 = get_telemetry()
        assert t1 is not t2
    
    def test_shutdown(self):
        tm = get_telemetry()
        tm.shutdown()
        # Should not raise


class TestTelemetryAdvanced:
    """Advanced tests for TelemetryManager."""
    
    def test_span_with_parent(self):
        """Test span with parent."""
        tm = TelemetryManager()
        parent = tm.start_span("parent")
        child = tm.start_span("child", parent=parent)
        
        assert child.parent_id == parent.span_id
    
    def test_span_error_status(self):
        """Test span error status."""
        tm = TelemetryManager()
        span = tm.start_span("test")
        tm.end_span(span, SpanStatus.ERROR)
        
        assert span.status == SpanStatus.ERROR
    
    def test_trace_decorator_preserves_return_value(self):
        """Test trace decorator preserves return value."""
        tm = TelemetryManager()
        
        @tm.trace()
        def add(a, b):
            return a + b
        
        result = add(3, 4)
        assert result == 7
    
    def test_trace_decorator_with_custom_name(self):
        """Test trace decorator with custom span name."""
        tm = TelemetryManager()
        
        @tm.trace(name="custom.span.name")
        def my_func():
            return 42
        
        my_func()
        
        spans = tm.get_traces()
        names = [s["name"] for s in spans]
        assert "custom.span.name" in names
    
    def test_trace_decorator_with_attributes(self):
        """Test trace decorator with custom attributes."""
        tm = TelemetryManager()
        
        @tm.trace(attributes={"env": "test", "version": "1.0"})
        def my_func():
            return "ok"
        
        my_func()
        
        spans = tm.get_traces()
        for s in spans:
            if "my_func" in s["name"]:
                assert s["attributes"].get("env") == "test"
    
    def test_span_kind_server(self):
        """Test span with SERVER kind."""
        tm = TelemetryManager()
        span = tm.start_span("http_handler", kind=SpanKind.SERVER)
        tm.end_span(span)
        
        assert span.kind == SpanKind.SERVER
    
    def test_span_kind_client(self):
        """Test span with CLIENT kind."""
        tm = TelemetryManager()
        span = tm.start_span("redis_call", kind=SpanKind.CLIENT)
        tm.end_span(span)
        
        assert span.kind == SpanKind.CLIENT
    
    def test_record_histogram_multiple_values(self):
        """Test recording multiple histogram values."""
        tm = TelemetryManager()
        for i in range(1, 101):
            tm.record_histogram("request_size", float(i))
        
        summary = tm.get_metrics_summary()
        hist = summary["histograms"]
        # Find the request_size histogram
        for key, data in hist.items():
            if "request_size" in str(key):
                assert data["count"] == 100
                break
    
    def test_metrics_with_attributes(self):
        """Test metrics with attribute labels."""
        tm = TelemetryManager()
        tm.increment_counter("requests", value=1, attributes={"method": "GET", "path": "/api"})
        tm.increment_counter("requests", value=1, attributes={"method": "POST", "path": "/api"})
        
        summary = tm.get_metrics_summary()
        assert len(summary["counters"]) >= 1
