"""
系统监控模块 - 实时监控与告警

基于 psutil 实现系统级监控：
- CPU 使用率、负载
- 内存使用率
- 磁盘使用率、IO
- 网络 IO
- 进程监控
- 自定义指标收集
- 告警规则引擎
- 多通道通知（日志/邮件/Webhook）

依赖: psutil>=5.9.0
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union

# Try to import psutil
try:
    import psutil
    _psutil_available = True
except ImportError:
    _psutil_available = False
    psutil = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MetricType(Enum):
    """指标类型"""
    CPU_PERCENT = "cpu_percent"
    CPU_COUNT = "cpu_count"
    CPU_FREQ = "cpu_freq"
    MEMORY_PERCENT = "memory_percent"
    MEMORY_USED = "memory_used"
    MEMORY_AVAILABLE = "memory_available"
    DISK_PERCENT = "disk_percent"
    DISK_USED = "disk_used"
    DISK_FREE = "disk_free"
    DISK_READ_BYTES = "disk_read_bytes"
    DISK_WRITE_BYTES = "disk_write_bytes"
    NET_SENT_BYTES = "net_sent_bytes"
    NET_RECV_BYTES = "net_recv_bytes"
    NET_SENT_PACKETS = "net_sent_packets"
    NET_RECV_PACKETS = "net_recv_packets"
    LOAD_AVG_1 = "load_avg_1"
    LOAD_AVG_5 = "load_avg_5"
    LOAD_AVG_15 = "load_avg_15"
    PROCESS_COUNT = "process_count"
    THREAD_COUNT = "thread_count"


class AlertSeverity(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertOperator(Enum):
    """告警比较运算符"""
    GT = ">"      # 大于
    GTE = ">="    # 大于等于
    LT = "<"      # 小于
    LTE = "<="    # 小于等于
    EQ = "=="     # 等于
    NEQ = "!="    # 不等于


class NotificationChannel(Enum):
    """通知渠道"""
    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SystemMetrics:
    """系统指标快照"""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # CPU
    cpu_percent: float = 0.0
    cpu_count_logical: int = 0
    cpu_count_physical: int = 0
    cpu_freq_current: float = 0.0
    cpu_freq_min: float = 0.0
    cpu_freq_max: float = 0.0
    
    # Memory (MB)
    memory_total: int = 0
    memory_available: int = 0
    memory_used: int = 0
    memory_percent: float = 0.0
    
    # Disk
    disk_total: int = 0
    disk_used: int = 0
    disk_free: int = 0
    disk_percent: float = 0.0
    
    # Network
    net_bytes_sent: int = 0
    net_bytes_recv: int = 0
    net_packets_sent: int = 0
    net_packets_recv: int = 0
    
    # Load
    load_avg_1: float = 0.0
    load_avg_5: float = 0.0
    load_avg_15: float = 0.0
    
    # Process
    process_count: int = 0
    thread_count: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric: MetricType
    operator: AlertOperator
    threshold: float
    severity: AlertSeverity
    duration_sec: int = 0  # 持续多少秒才触发
    enabled: bool = True
    cooldown_sec: int = 300  # 冷却时间
    description: str = ""
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "metric": self.metric.value,
            "operator": self.operator.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "duration_sec": self.duration_sec,
            "enabled": self.enabled,
            "cooldown_sec": self.cooldown_sec,
            "description": self.description,
        }


@dataclass
class AlertEvent:
    """告警事件"""
    rule_name: str
    severity: str
    metric: str
    current_value: float
    threshold: float
    operator: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NotificationConfig:
    """通知配置"""
    channel: NotificationChannel
    enabled: bool = True
    config: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Metric Collectors
# ---------------------------------------------------------------------------

class MetricCollector:
    """指标收集器基类"""
    
    def collect(self) -> dict[str, Any]:
        raise NotImplementedError


class SystemMetricCollector(MetricCollector):
    """系统指标收集器"""
    
    def __init__(self):
        if not _psutil_available:
            raise ImportError("psutil is required. Install: pip install psutil")
        self._last_disk_io = None
        self._last_net_io = None
        self._last_time = None
    
    def collect(self) -> SystemMetrics:
        """收集系统指标"""
        metrics = SystemMetrics()
        
        # CPU
        metrics.cpu_percent = psutil.cpu_percent(interval=0.1)
        metrics.cpu_count_logical = psutil.cpu_count(logical=True) or 0
        metrics.cpu_count_physical = psutil.cpu_count(logical=False) or 0
        
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            metrics.cpu_freq_current = cpu_freq.current
            metrics.cpu_freq_min = cpu_freq.min or 0
            metrics.cpu_freq_max = cpu_freq.max or 0
        
        # Memory
        mem = psutil.virtual_memory()
        metrics.memory_total = mem.total // (1024 * 1024)  # MB
        metrics.memory_available = mem.available // (1024 * 1024)
        metrics.memory_used = mem.used // (1024 * 1024)
        metrics.memory_percent = mem.percent
        
        # Disk
        disk = psutil.disk_usage("/")
        metrics.disk_total = disk.total // (1024 * 1024 * 1024)  # GB
        metrics.disk_used = disk.used // (1024 * 1024 * 1024)
        metrics.disk_free = disk.free // (1024 * 1024 * 1024)
        metrics.disk_percent = disk.percent
        
        # Network
        net_io = psutil.net_io_counters()
        metrics.net_bytes_sent = net_io.bytes_sent
        metrics.net_bytes_recv = net_io.bytes_recv
        metrics.net_packets_sent = net_io.packets_sent
        metrics.net_packets_recv = net_io.packets_recv
        
        # Load average
        try:
            load1, load5, load15 = psutil.getloadavg()
            metrics.load_avg_1 = load1
            metrics.load_avg_5 = load5
            metrics.load_avg_15 = load15
        except AttributeError:
            pass  # Windows doesn't have loadavg
        
        # Process count
        metrics.process_count = len(psutil.pids())
        metrics.thread_count = sum(p.num_threads() for p in psutil.process_iter(["num_threads"]))
        
        return metrics


class ProcessMetricCollector(MetricCollector):
    """进程指标收集器"""
    
    def __init__(self, pid: Optional[int] = None):
        if not _psutil_available:
            raise ImportError("psutil is required")
        self.pid = pid or os.getpid()
    
    def collect(self) -> dict[str, Any]:
        """收集指定进程指标"""
        try:
            proc = psutil.Process(self.pid)
            with proc.oneshot():
                return {
                    "pid": self.pid,
                    "name": proc.name(),
                    "cpu_percent": proc.cpu_percent(),
                    "memory_percent": proc.memory_percent(),
                    "memory_rss_mb": proc.memory_info().rss // (1024 * 1024),
                    "num_threads": proc.num_threads(),
                    "num_fds": proc.num_fds() if hasattr(proc, "num_fds") else 0,
                    "status": proc.status(),
                    "create_time": proc.create_time(),
                }
        except psutil.NoSuchProcess:
            return {"error": "Process not found"}


# ---------------------------------------------------------------------------
# Notification Handlers
# ---------------------------------------------------------------------------

class NotificationHandler:
    """通知处理器基类"""
    
    def send(self, alert: AlertEvent) -> bool:
        raise NotImplementedError


class LogNotificationHandler(NotificationHandler):
    """日志通知处理器"""
    
    def __init__(self, logger_name: str = "monitoring.alerts"):
        self._logger = logging.getLogger(logger_name)
    
    def send(self, alert: AlertEvent) -> bool:
        msg = f"[{alert.severity.upper()}] {alert.rule_name}: {alert.message}"
        if alert.severity == AlertSeverity.CRITICAL.value:
            self._logger.critical(msg)
        elif alert.severity == AlertSeverity.WARNING.value:
            self._logger.warning(msg)
        else:
            self._logger.info(msg)
        return True


class WebhookNotificationHandler(NotificationHandler):
    """Webhook 通知处理器"""
    
    def __init__(self, webhook_url: str, headers: Optional[dict] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}
    
    def send(self, alert: AlertEvent) -> bool:
        try:
            import urllib.request
            import urllib.error
            
            data = json.dumps(alert.to_dict()).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers=self.headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as e:
            logger.error("Webhook notification failed: %s", e)
            return False


# ---------------------------------------------------------------------------
# Alert Engine
# ---------------------------------------------------------------------------

class AlertEngine:
    """
    告警引擎
    
    基于规则的告警判断和通知发送。
    """
    
    def __init__(self):
        self._rules: list[AlertRule] = []
        self._handlers: list[NotificationHandler] = []
        self._alert_history: list[AlertEvent] = []
        self._last_alert_time: dict[str, float] = {}
        self._rule_violation_start: dict[str, float] = {}
        self._lock = threading.RLock()
        self._max_history = 1000
    
    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        with self._lock:
            self._rules.append(rule)
    
    def remove_rule(self, rule_name: str) -> bool:
        """删除告警规则"""
        with self._lock:
            for i, rule in enumerate(self._rules):
                if rule.name == rule_name:
                    self._rules.pop(i)
                    return True
        return False
    
    def add_handler(self, handler: NotificationHandler) -> None:
        """添加通知处理器"""
        with self._lock:
            self._handlers.append(handler)
    
    def evaluate(self, metrics: SystemMetrics) -> list[AlertEvent]:
        """
        评估指标并触发告警
        
        Returns:
            list[AlertEvent]: 触发的告警事件列表
        """
        triggered = []
        current_time = time.time()
        metrics_dict = metrics.to_dict()
        
        with self._lock:
            for rule in self._rules:
                if not rule.enabled:
                    continue
                
                # Get metric value
                metric_value = metrics_dict.get(rule.metric.value)
                if metric_value is None:
                    continue
                
                # Check condition
                condition_met = self._check_condition(
                    metric_value, rule.operator, rule.threshold
                )
                
                if condition_met:
                    # Check duration
                    if rule.duration_sec > 0:
                        start_time = self._rule_violation_start.get(rule.name)
                        if start_time is None:
                            self._rule_violation_start[rule.name] = current_time
                            continue
                        elif current_time - start_time < rule.duration_sec:
                            continue
                    
                    # Check cooldown
                    last_alert = self._last_alert_time.get(rule.name, 0)
                    if current_time - last_alert < rule.cooldown_sec:
                        continue
                    
                    # Create alert
                    alert = AlertEvent(
                        rule_name=rule.name,
                        severity=rule.severity.value,
                        metric=rule.metric.value,
                        current_value=float(metric_value),
                        threshold=rule.threshold,
                        operator=rule.operator.value,
                        message=f"{rule.metric.value} is {metric_value} {rule.operator.value} {rule.threshold}",
                    )
                    
                    triggered.append(alert)
                    self._alert_history.append(alert)
                    self._last_alert_time[rule.name] = current_time
                    
                    # Send notifications
                    for handler in self._handlers:
                        try:
                            handler.send(alert)
                        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
                            logger.error("Notification failed: %s", e)
                    
                    # Trim history
                    if len(self._alert_history) > self._max_history:
                        self._alert_history = self._alert_history[-self._max_history:]
                else:
                    # Reset violation timer
                    self._rule_violation_start.pop(rule.name, None)
        
        return triggered
    
    def _check_condition(self, value: float, operator: AlertOperator, threshold: float) -> bool:
        """检查条件是否满足"""
        if operator == AlertOperator.GT:
            return value > threshold
        elif operator == AlertOperator.GTE:
            return value >= threshold
        elif operator == AlertOperator.LT:
            return value < threshold
        elif operator == AlertOperator.LTE:
            return value <= threshold
        elif operator == AlertOperator.EQ:
            return value == threshold
        elif operator == AlertOperator.NEQ:
            return value != threshold
        return False
    
    def get_alert_history(
        self,
        severity: Optional[AlertSeverity] = None,
        limit: int = 100,
    ) -> list[AlertEvent]:
        """获取告警历史"""
        with self._lock:
            history = list(self._alert_history)
        
        if severity:
            history = [a for a in history if a.severity == severity.value]
        
        return history[-limit:]


# ---------------------------------------------------------------------------
# Monitoring Service
# ---------------------------------------------------------------------------

class MonitoringService:
    """
    监控服务
    
    后台收集指标并评估告警。
    
    Example:
        # 创建监控服务
        monitor = MonitoringService(interval_sec=30)
        
        # 添加告警规则
        monitor.add_alert_rule(AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_sec=60,
        ))
        
        # 启动监控
        monitor.start()
        
        # 获取最新指标
        metrics = monitor.get_latest_metrics()
        
        # 停止监控
        monitor.stop()
    """
    
    def __init__(
        self,
        interval_sec: float = 30.0,
        metrics_dir: Optional[Union[str, Path]] = None,
    ):
        if not _psutil_available:
            raise ImportError("psutil is required. Install: pip install psutil")
        
        self.interval_sec = interval_sec
        self.metrics_dir = Path(metrics_dir) if metrics_dir else None
        if self.metrics_dir:
            self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        self._collector = SystemMetricCollector()
        self._alert_engine = AlertEngine()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._latest_metrics: Optional[SystemMetrics] = None
        self._metrics_history: list[SystemMetrics] = []
        self._max_history = 10000
    
    def add_alert_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        self._alert_engine.add_rule(rule)
    
    def remove_alert_rule(self, rule_name: str) -> bool:
        """删除告警规则"""
        return self._alert_engine.remove_rule(rule_name)
    
    def add_notification_handler(self, handler: NotificationHandler) -> None:
        """添加通知处理器"""
        self._alert_engine.add_handler(handler)
    
    def start(self) -> None:
        """启动监控服务"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Monitoring service started (interval=%ss)", self.interval_sec)
    
    def stop(self) -> None:
        """停止监控服务"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Monitoring service stopped")
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                # Collect metrics
                metrics = self._collector.collect()
                
                with self._lock:
                    self._latest_metrics = metrics
                    self._metrics_history.append(metrics)
                    
                    # Trim history
                    if len(self._metrics_history) > self._max_history:
                        self._metrics_history = self._metrics_history[-self._max_history:]
                
                # Save to file if configured
                if self.metrics_dir:
                    self._save_metrics(metrics)
                
                # Evaluate alerts
                self._alert_engine.evaluate(metrics)
                
            except (ValueError, TypeError, RuntimeError, OSError) as e:
                logger.error("Monitoring loop error: %s", e)
            
            # Sleep
            time.sleep(self.interval_sec)
    
    def _save_metrics(self, metrics: SystemMetrics) -> None:
        """保存指标到文件"""
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        file_path = self.metrics_dir / f"metrics_{date_str}.jsonl"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(metrics.to_json() + "\n")
    
    def get_latest_metrics(self) -> Optional[SystemMetrics]:
        """获取最新指标"""
        with self._lock:
            return self._latest_metrics
    
    def get_metrics_history(
        self,
        duration_sec: Optional[float] = None,
        limit: int = 100,
    ) -> list[SystemMetrics]:
        """获取指标历史"""
        with self._lock:
            history = list(self._metrics_history)
        
        if duration_sec:
            cutoff = time.time() - duration_sec
            history = [
                m for m in history
                if datetime.fromisoformat(m.timestamp.replace("Z", "+00:00")).timestamp() > cutoff
            ]
        
        return history[-limit:]
    
    def get_alert_history(self, **kwargs) -> list[AlertEvent]:
        """获取告警历史"""
        return self._alert_engine.get_alert_history(**kwargs)
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running


__all__ = [
    "MetricType",
    "AlertSeverity",
    "AlertOperator",
    "NotificationChannel",
    "SystemMetrics",
    "AlertRule",
    "AlertEvent",
    "NotificationConfig",
    "MetricCollector",
    "SystemMetricCollector",
    "ProcessMetricCollector",
    "NotificationHandler",
    "LogNotificationHandler",
    "WebhookNotificationHandler",
    "AlertEngine",
    "MonitoringService",
]
