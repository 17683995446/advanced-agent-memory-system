"""
遥测模块 - OpenTelemetry 分布式追踪与指标

基于 OpenTelemetry 实现完整的可观测性：
- 分布式追踪（Trace）：记录操作链路
- 指标收集（Metrics）：Prometheus 格式输出
- 结构化日志（Log）：关联追踪上下文

自动为所有记忆操作创建 span，支持：
- 自动传播 Trace Context
- 自定义属性和事件
- 错误记录和状态标记
- 采样策略

依赖: opentelemetry-api, opentelemetry-sdk (可选，有 graceful fallback)
"""

from __future__ import annotations

import functools
import logging
import time
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
_otel_available = False
_otel_api = None
_otel_sdk = None

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider, SpanProcessor, SimpleSpanProcessor
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import Status, StatusCode, SpanKind
    from opentelemetry.trace.propagation import set_span_in_context
    from opentelemetry.context import Context
    _otel_available = True
    _otel_api = type('OtelAPI', (), {
        'trace': trace,
        'metrics': metrics,
        'Status': Status,
        'StatusCode': StatusCode,
        'SpanKind': SpanKind,
        'set_span_in_context': set_span_in_context,
        'Context': Context,
    })()
except ImportError:
    _otel_available = False


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SpanKind(Enum):
    """Span 类型"""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(Enum):
    """Span 状态"""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TelemetryConfig:
    """遥测配置
    
    Attributes:
        service_name: 服务名称
        service_version: 服务版本
        enabled: 是否启用遥测
        trace_enabled: 是否启用追踪
        metrics_enabled: 是否启用指标
        exporter: 导出器类型 ("console", "otlp", "none")
        otlp_endpoint: OTLP 接收端点
        sample_rate: 采样率 (0.0-1.0)
        trace_id_ratio: Trace ID 采样比例
        max_span_attributes: 最大 span 属性数
        attribute_max_length: 属性值最大长度
    """
    service_name: str = "agent-memory"
    service_version: str = "1.0.0"
    enabled: bool = True
    trace_enabled: bool = True
    metrics_enabled: bool = True
    exporter: str = "console"  # console, otlp, none
    otlp_endpoint: Optional[str] = None
    sample_rate: float = 1.0
    trace_id_ratio: float = 1.0
    max_span_attributes: int = 128
    attribute_max_length: int = 1024


# ---------------------------------------------------------------------------
# Span Context
# ---------------------------------------------------------------------------

@dataclass
class SpanContext:
    """Span 上下文"""
    trace_id: str = ""
    span_id: str = ""
    is_remote: bool = False
    is_valid: bool = False


@dataclass
class Span:
    """Span 记录
    
    当 OpenTelemetry 不可用时的内存实现。
    """
    name: str
    span_id: str = field(default_factory=lambda: format(uuid.uuid4().fields[0] % (2**64), "016x"))
    trace_id: str = field(default_factory=lambda: format(uuid.uuid4().fields[0] % (2**64), "016x") + format(uuid.uuid4().fields[1] % (2**64), "016x"))
    parent_id: str = ""
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    attributes: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    status: SpanStatus = SpanStatus.UNSET
    kind: SpanKind = SpanKind.INTERNAL
    service_name: str = ""

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = str(value)[:1024] if isinstance(value, str) else value

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.perf_counter(),
            "attributes": attributes or {},
        })

    def set_status(self, status: SpanStatus, message: str = "") -> None:
        self.status = status

    def end(self) -> None:
        self.end_time = time.perf_counter()

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.perf_counter()
        return (end - self.start_time) * 1000

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "start_time_ms": self.start_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status.value,
            "kind": self.kind.value,
        }


# ---------------------------------------------------------------------------
# Telemetry Manager
# ---------------------------------------------------------------------------

class TelemetryManager:
    """
    遥测管理器
    
    提供统一的追踪和指标接口，自动管理 OpenTelemetry 生命周期。
    
    Example:
        # 初始化
        telemetry = TelemetryManager(config=TelemetryConfig(
            service_name="agent-memory",
            exporter="console",
        ))
        
        # 创建 span
        with telemetry.start_span("memory.remember") as span:
            span.set_attribute("memory.category", "fact")
            memory_id = memory.remember("Important fact")
            span.set_attribute("memory.id", memory_id)
        
        # 装饰器
        @telemetry.trace()
        def remember_fact(fact):
            ...
        
        # 指标
        telemetry.increment_counter("memory.operations", {"operation": "add"})
        
        # 关闭
        telemetry.shutdown()
    """
    
    def __init__(self, config: Optional[TelemetryConfig] = None):
        self.config = config or TelemetryConfig()
        self._lock = threading.RLock()
        self._tracer: Optional[Any] = None
        self._meter: Optional[Any] = None
        self._counters: dict = {}
        self._histograms: dict = {}
        self._gauges: dict = {}
        self._spans: list = []
        self._enabled = self.config.enabled and _otel_available
        
        if self._enabled:
            self._setup_otel()
        else:
            logger.info("OpenTelemetry not available, using in-memory telemetry")
    
    def _setup_otel(self) -> None:
        """初始化 OpenTelemetry"""
        if not _otel_available:
            return
        
        try:
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource
            
            resource = Resource.create({
                "service.name": self.config.service_name,
                "service.version": self.config.service_version,
            })
            
            provider = TracerProvider(resource=resource)
            
            # Set span processor
            if self.config.exporter == "console":
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter
                provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            elif self.config.exporter == "otlp" and self.config.otlp_endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    provider.add_span_processor(BatchSpanProcessor(
                        OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
                    ))
                except ImportError:
                    logger.warning("OTLP exporter not available")
            
            self._tracer = trace.get_tracer(self.config.service_name)
            
            # Setup metrics
            if self.config.metrics_enabled:
                try:
                    from opentelemetry.sdk.metrics import MeterProvider
                    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
                    
                    reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
                    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
                    self._meter = metrics.get_meter(self.config.service_name)
                except ImportError:
                    logger.warning("Metrics not available")
            
            logger.info("OpenTelemetry initialized (service=%s)", self.config.service_name)
        except (ImportError, ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.error("Failed to initialize OpenTelemetry: %s", e)
            self._enabled = False
    
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: Optional[Span] = None,
        attributes: Optional[dict] = None,
    ) -> Span:
        """开始一个 span"""
        parent_id = parent.span_id if parent else ""
        
        if self._enabled and self._tracer:
            otel_kind = _otel_api.SpanKind.INTERNAL
            if kind == SpanKind.SERVER:
                otel_kind = _otel_api.SpanKind.SERVER
            elif kind == SpanKind.CLIENT:
                otel_kind = _otel_api.SpanKind.CLIENT
            
            ctx = None
            if parent and hasattr(parent, '_otel_span'):
                ctx = _otel_api.set_span_in_context(parent._otel_span)
            
            otel_span = self._tracer.start_span(
                name,
                kind=otel_kind,
                context=ctx,
            )
            
            if attributes:
                for k, v in attributes.items():
                    otel_span.set_attribute(k, str(v)[:self.config.attribute_max_length])
            
            span = Span(name=name, kind=kind, parent_id=parent_id)
            span._otel_span = otel_span
            span._otel_context = ctx
        else:
            span = Span(name=name, kind=kind, parent_id=parent_id)
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
        
        with self._lock:
            self._spans.append(span)
        
        return span
    
    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK) -> None:
        """结束一个 span"""
        span.set_status(status)
        span.end()
        
        if self._enabled and hasattr(span, '_otel_span'):
            try:
                if status == SpanStatus.ERROR:
                    span._otel_span.set_status(_otel_api.Status(_otel_api.StatusCode.ERROR))
                elif status == SpanStatus.OK:
                    span._otel_span.set_status(_otel_api.Status(_otel_api.StatusCode.OK))
                span._otel_span.end()
            except (AttributeError, ValueError, RuntimeError):
                pass

    def trace(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict] = None,
    ) -> Callable:
        """追踪装饰器"""
        def decorator(fn: Callable) -> Callable:
            span_name = name or f"{fn.__module__}.{fn.__qualname__}"
            
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                span = self.start_span(span_name, kind=kind, attributes=attributes)
                try:
                    result = fn(*args, **kwargs)
                    self.end_span(span, SpanStatus.OK)
                    return result
                except Exception as e:
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e)[:1024])
                    span.add_event("exception", {"exception.type": type(e).__name__})
                    self.end_span(span, SpanStatus.ERROR)
                    raise
            
            return wrapper
        return decorator
    
    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        attributes: Optional[dict] = None,
    ) -> None:
        """递增计数器"""
        key = (name, tuple(sorted((attributes or {}).items())))
        with self._lock:
            if key not in self._counters:
                self._counters[key] = 0.0
            self._counters[key] += value
    
    def record_histogram(
        self,
        name: str,
        value: float,
        attributes: Optional[dict] = None,
    ) -> None:
        """记录直方图值"""
        key = (name, tuple(sorted((attributes or {}).items())))
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
    
    def set_gauge(
        self,
        name: str,
        value: float,
        attributes: Optional[dict] = None,
    ) -> None:
        """设置 gauge 值"""
        key = (name, tuple(sorted((attributes or {}).items())))
        with self._lock:
            self._gauges[key] = value
    
    def get_current_span(self) -> Optional[Span]:
        """获取当前 span"""
        if self._enabled and _otel_available:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span and span.is_recording():
                return span
        return None
    
    def get_metrics_summary(self) -> dict:
        """获取指标摘要"""
        with self._lock:
            return {
                "counters": {str(k): v for k, v in self._counters.items()},
                "histograms": {
                    str(k): {
                        "count": len(v),
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                        "avg": sum(v) / len(v) if v else 0,
                    }
                    for k, v in self._histograms.items()
                },
                "gauges": {str(k): v for k, v in self._gauges.items()},
                "spans_count": len(self._spans),
            }
    
    def get_traces(self, limit: int = 100) -> list[dict]:
        """获取最近的 traces"""
        with self._lock:
            spans = sorted(self._spans, key=lambda s: s.start_time, reverse=True)[:limit]
            return [s.to_dict() for s in spans]
    
    def shutdown(self, timeout: float = 5.0) -> None:
        """关闭遥测"""
        with self._lock:
            self._spans.clear()
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()
        logger.info("Telemetry shutdown complete")


# ---------------------------------------------------------------------------
# Span Context Manager
# ---------------------------------------------------------------------------

class SpanContextManager:
    """Span 上下文管理器"""
    
    def __init__(
        self,
        telemetry: TelemetryManager,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict] = None,
    ):
        self._telemetry = telemetry
        self._name = name
        self._kind = kind
        self._attributes = attributes
        self._span: Optional[Span] = None
    
    def __enter__(self) -> Span:
        self._span = self._telemetry.start_span(
            self._name,
            kind=self._kind,
            attributes=self._attributes,
        )
        return self._span
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._span:
            if exc_type:
                self._span.set_attribute("error.type", type(exc_val).__name__)
                self._span.set_attribute("error.message", str(exc_val)[:1024])
                self._telemetry.end_span(self._span, SpanStatus.ERROR)
            else:
                self._telemetry.end_span(self._span, SpanStatus.OK)
        return False


# ---------------------------------------------------------------------------
# Global Telemetry
# ---------------------------------------------------------------------------

_global_telemetry: Optional[TelemetryManager] = None
_telemetry_lock = threading.Lock()


def get_telemetry() -> TelemetryManager:
    """获取全局遥测管理器（线程安全）"""
    global _global_telemetry
    if _global_telemetry is None:
        with _telemetry_lock:
            if _global_telemetry is None:
                _global_telemetry = TelemetryManager()
    return _global_telemetry


def reset_telemetry() -> None:
    """重置全局遥测管理器"""
    global _global_telemetry
    with _telemetry_lock:
        if _global_telemetry:
            _global_telemetry.shutdown()
        _global_telemetry = None


__all__ = [
    "TelemetryConfig",
    "SpanKind",
    "SpanStatus",
    "SpanContext",
    "Span",
    "TelemetryManager",
    "SpanContextManager",
    "get_telemetry",
    "reset_telemetry",
]
