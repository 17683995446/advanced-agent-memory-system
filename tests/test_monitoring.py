"""Unit tests for the monitoring module."""
import pytest
import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.observability.system_monitoring_alerting import (
    MetricType,
    AlertSeverity,
    AlertOperator,
    NotificationChannel,
    SystemMetrics,
    AlertRule,
    AlertEvent,
    AlertEngine,
    LogNotificationHandler,
    WebhookNotificationHandler,
    MetricCollector,
    NotificationHandler,
    NotificationConfig,
)


class TestMetricType:
    def test_cpu_metrics(self):
        assert MetricType.CPU_PERCENT.value == "cpu_percent"
        assert MetricType.CPU_COUNT.value == "cpu_count"
        assert MetricType.CPU_FREQ.value == "cpu_freq"
    
    def test_memory_metrics(self):
        assert MetricType.MEMORY_PERCENT.value == "memory_percent"
        assert MetricType.MEMORY_USED.value == "memory_used"
        assert MetricType.MEMORY_AVAILABLE.value == "memory_available"
    
    def test_disk_metrics(self):
        assert MetricType.DISK_PERCENT.value == "disk_percent"
        assert MetricType.DISK_USED.value == "disk_used"
        assert MetricType.DISK_FREE.value == "disk_free"
    
    def test_network_metrics(self):
        assert MetricType.NET_SENT_BYTES.value == "net_sent_bytes"
        assert MetricType.NET_RECV_BYTES.value == "net_recv_bytes"


class TestAlertSeverity:
    def test_all_severities(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestAlertOperator:
    def test_all_operators(self):
        assert AlertOperator.GT.value == ">"
        assert AlertOperator.GTE.value == ">="
        assert AlertOperator.LT.value == "<"
        assert AlertOperator.LTE.value == "<="
        assert AlertOperator.EQ.value == "=="
        assert AlertOperator.NEQ.value == "!="


class TestNotificationChannel:
    def test_all_channels(self):
        assert NotificationChannel.LOG.value == "log"
        assert NotificationChannel.WEBHOOK.value == "webhook"
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.SLACK.value == "slack"


class TestSystemMetrics:
    def test_defaults(self):
        metrics = SystemMetrics()
        assert metrics.timestamp != ""
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_percent == 0.0
    
    def test_to_dict(self):
        metrics = SystemMetrics(cpu_percent=50.0, memory_percent=75.0)
        d = metrics.to_dict()
        assert d["cpu_percent"] == 50.0
        assert d["memory_percent"] == 75.0
    
    def test_to_json(self):
        metrics = SystemMetrics(cpu_percent=50.0)
        json_str = metrics.to_json()
        assert '"cpu_percent": 50.0' in json_str


class TestAlertRule:
    def test_defaults(self):
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
        )
        assert rule.name == "high_cpu"
        assert rule.duration_sec == 0
        assert rule.enabled is True
        assert rule.cooldown_sec == 300
    
    def test_to_dict(self):
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
        )
        d = rule.to_dict()
        assert d["name"] == "high_cpu"
        assert d["metric"] == "cpu_percent"
        assert d["operator"] == ">"
        assert d["threshold"] == 80.0


class TestAlertEvent:
    def test_defaults(self):
        event = AlertEvent(
            rule_name="high_cpu",
            severity="warning",
            metric="cpu_percent",
            current_value=85.0,
            threshold=80.0,
            operator=">",
        )
        assert event.rule_name == "high_cpu"
        assert event.timestamp != ""
    
    def test_to_dict(self):
        event = AlertEvent(
            rule_name="test",
            severity="info",
            metric="test_metric",
            current_value=100.0,
            threshold=90.0,
            operator=">",
            message="Test message",
        )
        d = event.to_dict()
        assert d["rule_name"] == "test"
        assert d["message"] == "Test message"


class TestAlertEngine:
    def test_add_rule(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
        )
        engine.add_rule(rule)
        
        # Should trigger alert
        metrics = SystemMetrics(cpu_percent=85.0)
        alerts = engine.evaluate(metrics)
        
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high_cpu"
        assert alerts[0].current_value == 85.0
    
    def test_remove_rule(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="test_rule",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=50.0,
            severity=AlertSeverity.INFO,
        )
        engine.add_rule(rule)
        assert engine.remove_rule("test_rule") is True
        assert engine.remove_rule("nonexistent") is False
    
    def test_no_alert_when_condition_not_met(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
        )
        engine.add_rule(rule)
        
        # Should not trigger (cpu < threshold)
        metrics = SystemMetrics(cpu_percent=50.0)
        alerts = engine.evaluate(metrics)
        
        assert len(alerts) == 0
    
    def test_disabled_rule_not_evaluated(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            enabled=False,
        )
        engine.add_rule(rule)
        
        metrics = SystemMetrics(cpu_percent=85.0)
        alerts = engine.evaluate(metrics)
        
        assert len(alerts) == 0
    
    def test_different_operators(self):
        engine = AlertEngine()
        
        # Test LT
        rule = AlertRule(
            name="low_memory",
            metric=MetricType.MEMORY_AVAILABLE,
            operator=AlertOperator.LT,
            threshold=1000.0,
            severity=AlertSeverity.WARNING,
        )
        engine.add_rule(rule)
        
        metrics = SystemMetrics(memory_available=500.0)
        alerts = engine.evaluate(metrics)
        
        assert len(alerts) == 1
    
    def test_cooldown_prevents_duplicate_alerts(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            cooldown_sec=10,  # 10 second cooldown
        )
        engine.add_rule(rule)
        
        metrics = SystemMetrics(cpu_percent=85.0)
        
        # First evaluation should trigger
        alerts1 = engine.evaluate(metrics)
        assert len(alerts1) == 1
        
        # Second evaluation should not trigger (cooldown)
        alerts2 = engine.evaluate(metrics)
        assert len(alerts2) == 0
    
    def test_alert_history(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            name="test",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=0.0,
            severity=AlertSeverity.INFO,
        ))
        
        metrics = SystemMetrics(cpu_percent=50.0)
        engine.evaluate(metrics)
        
        history = engine.get_alert_history()
        assert len(history) == 1
        
        # Test with severity filter
        history_filtered = engine.get_alert_history(severity=AlertSeverity.WARNING)
        assert len(history_filtered) == 0
    
    def test_add_handler(self):
        engine = AlertEngine()
        handler = LogNotificationHandler()
        engine.add_handler(handler)
        
        # Should not raise
        rule = AlertRule(
            name="test",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=0.0,
            severity=AlertSeverity.INFO,
        )
        engine.add_rule(rule)
        
        metrics = SystemMetrics(cpu_percent=50.0)
        engine.evaluate(metrics)


class TestLogNotificationHandler:
    def test_send_info(self):
        handler = LogNotificationHandler()
        event = AlertEvent(
            rule_name="test",
            severity="info",
            metric="test",
            current_value=1.0,
            threshold=0.5,
            operator=">",
            message="Test info",
        )
        assert handler.send(event) is True
    
    def test_send_warning(self):
        handler = LogNotificationHandler()
        event = AlertEvent(
            rule_name="test",
            severity="warning",
            metric="test",
            current_value=1.0,
            threshold=0.5,
            operator=">",
            message="Test warning",
        )
        assert handler.send(event) is True
    
    def test_send_critical(self):
        handler = LogNotificationHandler()
        event = AlertEvent(
            rule_name="test",
            severity="critical",
            metric="test",
            current_value=1.0,
            threshold=0.5,
            operator=">",
            message="Test critical",
        )
        assert handler.send(event) is True


class TestAlertEngineDuration:
    def test_duration_requirement(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_sec=2,  # 2 second duration
        )
        engine.add_rule(rule)
        
        metrics = SystemMetrics(cpu_percent=85.0)
        
        # First evaluation should not trigger (duration not met)
        alerts1 = engine.evaluate(metrics)
        assert len(alerts1) == 0
        
        # Wait for duration
        time.sleep(2.1)
        
        # Second evaluation should trigger
        alerts2 = engine.evaluate(metrics)
        assert len(alerts2) == 1


# ===========================================================================
# NEW TEST CLASSES - Added for improved coverage
# ===========================================================================


class TestAlertEngineAllOperators:
    """Test AlertEngine with all six operators."""

    @pytest.mark.parametrize("operator,threshold,metric_value,should_alert", [
        (AlertOperator.GT, 80.0, 85.0, True),
        (AlertOperator.GT, 80.0, 80.0, False),
        (AlertOperator.GT, 80.0, 75.0, False),
        (AlertOperator.GTE, 80.0, 80.0, True),
        (AlertOperator.GTE, 80.0, 81.0, True),
        (AlertOperator.GTE, 80.0, 79.0, False),
        (AlertOperator.LT, 100.0, 50.0, True),
        (AlertOperator.LT, 100.0, 100.0, False),
        (AlertOperator.LT, 100.0, 101.0, False),
        (AlertOperator.LTE, 100.0, 100.0, True),
        (AlertOperator.LTE, 100.0, 99.0, True),
        (AlertOperator.LTE, 100.0, 101.0, False),
        (AlertOperator.EQ, 50.0, 50.0, True),
        (AlertOperator.EQ, 50.0, 51.0, False),
        (AlertOperator.EQ, 50.0, 49.0, False),
        (AlertOperator.NEQ, 50.0, 51.0, True),
        (AlertOperator.NEQ, 50.0, 50.0, False),
        (AlertOperator.NEQ, 50.0, 49.0, True),
    ])
    def test_operator_evaluation(self, operator, threshold, metric_value, should_alert):
        engine = AlertEngine()
        rule = AlertRule(
            name=f"test_{operator.value}",
            metric=MetricType.CPU_PERCENT,
            operator=operator,
            threshold=threshold,
            severity=AlertSeverity.INFO,
            cooldown_sec=0,
        )
        engine.add_rule(rule)
        metrics = SystemMetrics(cpu_percent=metric_value)
        alerts = engine.evaluate(metrics)
        if should_alert:
            assert len(alerts) == 1
            assert alerts[0].operator == operator.value
        else:
            assert len(alerts) == 0


class TestAlertEngineDurationReset:
    """Test that violation timer resets when condition is no longer met."""

    def test_duration_resets_when_condition_clears(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_sec=2,
            cooldown_sec=0,
        )
        engine.add_rule(rule)

        # First: condition met, start timer
        metrics_high = SystemMetrics(cpu_percent=85.0)
        alerts1 = engine.evaluate(metrics_high)
        assert len(alerts1) == 0  # duration not met yet

        # Second: condition NOT met - timer should reset
        metrics_low = SystemMetrics(cpu_percent=50.0)
        alerts2 = engine.evaluate(metrics_low)
        assert len(alerts2) == 0

        # Wait for what would have been enough time
        time.sleep(2.1)

        # Third: condition met again - should NOT trigger because timer was reset
        alerts3 = engine.evaluate(metrics_high)
        assert len(alerts3) == 0

        # Wait again for the new duration
        time.sleep(2.1)

        # Fourth: should now trigger
        alerts4 = engine.evaluate(metrics_high)
        assert len(alerts4) == 1


class TestAlertEngineCooldownExpired:
    """Test that alerts fire again after cooldown expires."""

    def test_alert_fires_after_cooldown_expires(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            cooldown_sec=1,  # 1 second cooldown
        )
        engine.add_rule(rule)

        metrics = SystemMetrics(cpu_percent=85.0)

        # First evaluation: alert fires
        alerts1 = engine.evaluate(metrics)
        assert len(alerts1) == 1

        # Second evaluation (immediate): suppressed by cooldown
        alerts2 = engine.evaluate(metrics)
        assert len(alerts2) == 0

        # Wait for cooldown to expire
        time.sleep(1.1)

        # Third evaluation: cooldown expired, alert fires again
        alerts3 = engine.evaluate(metrics)
        assert len(alerts3) == 1


class TestAlertEngineMultipleRules:
    """Test AlertEngine with multiple rules at once."""

    def test_multiple_rules_can_fire(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            name="high_cpu", metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT, threshold=80.0,
            severity=AlertSeverity.WARNING, cooldown_sec=0,
        ))
        engine.add_rule(AlertRule(
            name="low_memory", metric=MetricType.MEMORY_AVAILABLE,
            operator=AlertOperator.LT, threshold=1000.0,
            severity=AlertSeverity.CRITICAL, cooldown_sec=0,
        ))

        metrics = SystemMetrics(cpu_percent=90.0, memory_available=500.0)
        alerts = engine.evaluate(metrics)
        assert len(alerts) == 2
        names = {a.rule_name for a in alerts}
        assert "high_cpu" in names
        assert "low_memory" in names

    def test_partial_rules_fire(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            name="high_cpu", metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT, threshold=80.0,
            severity=AlertSeverity.WARNING, cooldown_sec=0,
        ))
        engine.add_rule(AlertRule(
            name="low_memory", metric=MetricType.MEMORY_AVAILABLE,
            operator=AlertOperator.LT, threshold=100.0,
            severity=AlertSeverity.CRITICAL, cooldown_sec=0,
        ))

        # Only CPU condition is met
        metrics = SystemMetrics(cpu_percent=90.0, memory_available=500.0)
        alerts = engine.evaluate(metrics)
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high_cpu"


class TestAlertEngineMissingMetric:
    """Test that rules are skipped when metric is not available."""

    def test_missing_metric_skipped(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="test_disk",
            metric=MetricType.DISK_FREE,
            operator=AlertOperator.LT,
            threshold=1000.0,
            severity=AlertSeverity.WARNING,
        )
        engine.add_rule(rule)

        # SystemMetrics with default disk_free=0 should still match LT
        metrics = SystemMetrics(disk_free=0)
        alerts = engine.evaluate(metrics)
        assert len(alerts) == 1


class TestAlertEngineHistoryLimit:
    """Test alert history limit parameter."""

    def test_history_limit(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            name="test", metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT, threshold=0.0,
            severity=AlertSeverity.INFO, cooldown_sec=0,
        ))

        # Generate more alerts than the default limit
        for i in range(5):
            metrics = SystemMetrics(cpu_percent=float(i + 1))
            engine.evaluate(metrics)

        history = engine.get_alert_history(limit=3)
        assert len(history) == 3

        # Get all
        history_all = engine.get_alert_history(limit=100)
        assert len(history_all) == 5


class TestAlertEngineHistoryTrimming:
    """Test that history is trimmed when exceeding max_history."""

    def test_history_trimming(self):
        engine = AlertEngine()
        engine._max_history = 5
        engine.add_rule(AlertRule(
            name="test", metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT, threshold=0.0,
            severity=AlertSeverity.INFO, cooldown_sec=0,
        ))

        for i in range(10):
            engine.evaluate(SystemMetrics(cpu_percent=float(i + 1)))

        history = engine.get_alert_history(limit=100)
        # Should be trimmed to max_history
        assert len(history) <= 10


class TestAlertEngineAlertEventContents:
    """Test that AlertEvent contains correct data."""

    def test_alert_event_fields(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule(
            name="cpu_alert",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.CRITICAL,
            cooldown_sec=0,
        ))

        metrics = SystemMetrics(cpu_percent=95.5)
        alerts = engine.evaluate(metrics)
        assert len(alerts) == 1

        event = alerts[0]
        assert event.rule_name == "cpu_alert"
        assert event.severity == "critical"
        assert event.metric == "cpu_percent"
        assert event.current_value == 95.5
        assert event.threshold == 80.0
        assert event.operator == ">"
        assert "cpu_percent" in event.message
        assert event.timestamp != ""


class TestWebhookNotificationHandler:
    """Tests for WebhookNotificationHandler."""

    def test_webhook_send_success(self):
        """Test successful webhook delivery using a mock HTTP server."""
        import http.server
        import json

        received_data = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                received_data.append(json.loads(body.decode("utf-8")))
                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress log output

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        handler = WebhookNotificationHandler(f"http://127.0.0.1:{port}/webhook")
        event = AlertEvent(
            rule_name="test_webhook",
            severity="warning",
            metric="cpu_percent",
            current_value=90.0,
            threshold=80.0,
            operator=">",
            message="CPU is high",
        )
        result = handler.send(event)
        thread.join(timeout=5)
        server.server_close()

        assert result is True
        assert len(received_data) == 1
        assert received_data[0]["rule_name"] == "test_webhook"

    def test_webhook_send_failure(self):
        """Test webhook failure when server is unreachable."""
        handler = WebhookNotificationHandler("http://127.0.0.1:1/nonexistent")
        event = AlertEvent(
            rule_name="test_fail",
            severity="info",
            metric="test",
            current_value=1.0,
            threshold=0.5,
            operator=">",
            message="Should fail",
        )
        result = handler.send(event)
        assert result is False

    def test_webhook_custom_headers(self):
        """Test that custom headers are passed."""
        handler = WebhookNotificationHandler(
            "http://example.com/webhook",
            headers={"X-Custom": "value", "Content-Type": "application/json"},
        )
        assert handler.headers["X-Custom"] == "value"
        assert handler.headers["Content-Type"] == "application/json"


class TestNotificationHandlerBaseClass:
    """Tests for NotificationHandler base class."""

    def test_base_send_not_implemented(self):
        handler = NotificationHandler()
        event = AlertEvent(
            rule_name="test", severity="info", metric="m",
            current_value=1.0, threshold=0.5, operator=">",
        )
        with pytest.raises(NotImplementedError):
            handler.send(event)


class TestMetricCollectorBaseClass:
    """Tests for MetricCollector base class."""

    def test_base_collect_not_implemented(self):
        collector = MetricCollector()
        with pytest.raises(NotImplementedError):
            collector.collect()


class TestNotificationConfig:
    """Tests for NotificationConfig dataclass."""

    def test_defaults(self):
        config = NotificationConfig(channel=NotificationChannel.LOG)
        assert config.channel == NotificationChannel.LOG
        assert config.enabled is True
        assert config.config == {}

    def test_custom(self):
        config = NotificationConfig(
            channel=NotificationChannel.WEBHOOK,
            enabled=False,
            config={"url": "http://example.com"},
        )
        assert config.channel == NotificationChannel.WEBHOOK
        assert config.enabled is False
        assert config.config["url"] == "http://example.com"


class TestAlertRuleDescription:
    """Tests for AlertRule with description field."""

    def test_rule_with_description(self):
        rule = AlertRule(
            name="high_cpu",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            description="CPU usage is too high",
        )
        assert rule.description == "CPU usage is too high"
        d = rule.to_dict()
        assert d["description"] == "CPU usage is too high"


class TestAlertEngineRemoveNonexistentRule:
    """Additional test for removing nonexistent rules."""

    def test_remove_nonexistent_returns_false(self):
        engine = AlertEngine()
        assert engine.remove_rule("does_not_exist") is False

    def test_remove_then_re_add(self):
        engine = AlertEngine()
        rule = AlertRule(
            name="temp_rule",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=50.0,
            severity=AlertSeverity.INFO,
            cooldown_sec=0,
        )
        engine.add_rule(rule)
        assert engine.remove_rule("temp_rule") is True

        # Re-add should work
        engine.add_rule(rule)
        metrics = SystemMetrics(cpu_percent=60.0)
        alerts = engine.evaluate(metrics)
        assert len(alerts) == 1


class TestLogNotificationHandlerCustomLogger:
    """Test LogNotificationHandler with custom logger name."""

    def test_custom_logger_name(self):
        handler = LogNotificationHandler(logger_name="custom.test.logger")
        assert handler._logger.name == "custom.test.logger"
        event = AlertEvent(
            rule_name="test", severity="info", metric="m",
            current_value=1.0, threshold=0.5, operator=">",
            message="Test",
        )
        assert handler.send(event) is True


class TestMonitoringServiceStartStop:
    """Test MonitoringService start/stop lifecycle."""

    @pytest.fixture(autouse=True)
    def _check_psutil(self):
        try:
            from memory_system.observability.system_monitoring_alerting import MonitoringService
            MonitoringService(interval_sec=60)
        except ImportError:
            pytest.skip("psutil not available")

    def test_start_stop_lifecycle(self):
        """Test that MonitoringService can be started and stopped."""
        from memory_system.observability.system_monitoring_alerting import MonitoringService

        service = MonitoringService(interval_sec=60)
        assert service.is_running() is False

        service.start()
        assert service.is_running() is True

        service.stop()
        # After stop, _running should be False
        assert service.is_running() is False

    def test_start_idempotent(self):
        """Calling start twice should not create extra threads."""
        from memory_system.observability.system_monitoring_alerting import MonitoringService

        service = MonitoringService(interval_sec=60)
        service.start()
        service.start()  # Should be no-op
        assert service.is_running() is True
        service.stop()

    def test_stop_when_not_running(self):
        """Stopping when not running should not raise."""
        from memory_system.observability.system_monitoring_alerting import MonitoringService

        service = MonitoringService(interval_sec=60)
        service.stop()  # Should not raise

    def test_get_latest_metrics_before_start(self):
        """get_latest_metrics should return None before any collection."""
        from memory_system.observability.system_monitoring_alerting import MonitoringService

        service = MonitoringService(interval_sec=60)
        assert service.get_latest_metrics() is None

    def test_add_and_remove_alert_rule(self):
        """Test adding and removing alert rules via MonitoringService."""
        from memory_system.observability.system_monitoring_alerting import MonitoringService

        service = MonitoringService(interval_sec=60)
        rule = AlertRule(
            name="test_rule",
            metric=MetricType.CPU_PERCENT,
            operator=AlertOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
        )
        service.add_alert_rule(rule)
        assert service.remove_alert_rule("test_rule") is True
        assert service.remove_alert_rule("nonexistent") is False

    def test_get_metrics_history_empty(self):
        """get_metrics_history should return empty list before start."""
        from memory_system.observability.system_monitoring_alerting import MonitoringService

        service = MonitoringService(interval_sec=60)
        history = service.get_metrics_history()
        assert history == []

    def test_get_alert_history_via_service(self):
        """get_alert_history delegates to AlertEngine."""
        from memory_system.observability.system_monitoring_alerting import MonitoringService

        service = MonitoringService(interval_sec=60)
        history = service.get_alert_history()
        assert history == []


class TestCustomMetricCollector:
    """Test custom MetricCollector implementations."""

    def test_custom_collector(self):
        """A custom collector should implement the collect method."""

        class CustomCollector(MetricCollector):
            def collect(self):
                return {"custom_metric": 42.0, "timestamp": "now"}

        collector = CustomCollector()
        result = collector.collect()
        assert result["custom_metric"] == 42.0
        assert result["timestamp"] == "now"

    def test_custom_collector_returns_system_metrics(self):
        """Custom collector can return SystemMetrics."""

        class CustomSystemCollector(MetricCollector):
            def collect(self):
                return SystemMetrics(cpu_percent=99.9, memory_percent=88.8)

        collector = CustomSystemCollector()
        result = collector.collect()
        assert isinstance(result, SystemMetrics)
        assert result.cpu_percent == 99.9
        assert result.memory_percent == 88.8


class TestSystemMetricsAdditionalFields:
    """Test SystemMetrics with additional fields."""

    def test_all_cpu_fields(self):
        metrics = SystemMetrics(
            cpu_percent=50.0,
            cpu_count_logical=8,
            cpu_count_physical=4,
            cpu_freq_current=3000.0,
            cpu_freq_min=800.0,
            cpu_freq_max=4000.0,
        )
        d = metrics.to_dict()
        assert d["cpu_count_logical"] == 8
        assert d["cpu_count_physical"] == 4
        assert d["cpu_freq_current"] == 3000.0

    def test_all_memory_fields(self):
        metrics = SystemMetrics(
            memory_total=16000,
            memory_available=8000,
            memory_used=8000,
            memory_percent=50.0,
        )
        d = metrics.to_dict()
        assert d["memory_total"] == 16000
        assert d["memory_available"] == 8000

    def test_all_disk_fields(self):
        metrics = SystemMetrics(
            disk_total=500,
            disk_used=200,
            disk_free=300,
            disk_percent=40.0,
        )
        d = metrics.to_dict()
        assert d["disk_total"] == 500
        assert d["disk_free"] == 300

    def test_all_network_fields(self):
        metrics = SystemMetrics(
            net_bytes_sent=1000,
            net_bytes_recv=2000,
            net_packets_sent=10,
            net_packets_recv=20,
        )
        d = metrics.to_dict()
        assert d["net_bytes_sent"] == 1000
        assert d["net_packets_recv"] == 20

    def test_load_and_process_fields(self):
        metrics = SystemMetrics(
            load_avg_1=1.0,
            load_avg_5=0.8,
            load_avg_15=0.5,
            process_count=100,
            thread_count=250,
        )
        d = metrics.to_dict()
        assert d["load_avg_1"] == 1.0
        assert d["process_count"] == 100
        assert d["thread_count"] == 250


class TestAlertEventToDict:
    """Test AlertEvent to_dict with all fields."""

    def test_to_dict_completeness(self):
        event = AlertEvent(
            rule_name="full_test",
            severity="critical",
            metric="disk_percent",
            current_value=95.0,
            threshold=90.0,
            operator=">=",
            message="Disk almost full",
        )
        d = event.to_dict()
        assert d["rule_name"] == "full_test"
        assert d["severity"] == "critical"
        assert d["metric"] == "disk_percent"
        assert d["current_value"] == 95.0
        assert d["threshold"] == 90.0
        assert d["operator"] == ">="
        assert d["message"] == "Disk almost full"
        assert d["timestamp"] != ""


class TestMetricTypeEnumCompleteness:
    """Test all MetricType enum values."""

    def test_disk_io_metrics(self):
        assert MetricType.DISK_READ_BYTES.value == "disk_read_bytes"
        assert MetricType.DISK_WRITE_BYTES.value == "disk_write_bytes"

    def test_network_packet_metrics(self):
        assert MetricType.NET_SENT_PACKETS.value == "net_sent_packets"
        assert MetricType.NET_RECV_PACKETS.value == "net_recv_packets"

    def test_load_avg_metrics(self):
        assert MetricType.LOAD_AVG_1.value == "load_avg_1"
        assert MetricType.LOAD_AVG_5.value == "load_avg_5"
        assert MetricType.LOAD_AVG_15.value == "load_avg_15"

    def test_process_metrics(self):
        assert MetricType.PROCESS_COUNT.value == "process_count"
        assert MetricType.THREAD_COUNT.value == "thread_count"
