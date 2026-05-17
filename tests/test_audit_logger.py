"""Unit tests for the audit_logger module."""
import pytest
import sys
import os
import time
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.observability.operation_audit_logger import (
    AuditLevel,
    OperationType,
    ActorType,
    AuditRecord,
    AuditStats,
    AuditHandler,
    MemoryHandler,
    FileHandler,
    LoggingHandler,
    AuditLogger,
    AuditLogContext,
    get_audit_logger,
    reset_audit_logger,
)
from datetime import datetime


class TestAuditLevel:
    def test_all_levels(self):
        assert AuditLevel.DEBUG.value == "debug"
        assert AuditLevel.INFO.value == "info"
        assert AuditLevel.WARNING.value == "warning"
        assert AuditLevel.ERROR.value == "error"
        assert AuditLevel.CRITICAL.value == "critical"


class TestOperationType:
    def test_storage_operations(self):
        assert OperationType.MEMORY_ADD.value == "memory.add"
        assert OperationType.MEMORY_UPDATE.value == "memory.update"
        assert OperationType.MEMORY_DELETE.value == "memory.delete"
        assert OperationType.MEMORY_SEARCH.value == "memory.search"
    
    def test_entity_operations(self):
        assert OperationType.ENTITY_ADD.value == "entity.add"
        assert OperationType.ENTITY_UPDATE.value == "entity.update"
        assert OperationType.ENTITY_DELETE.value == "entity.delete"


class TestActorType:
    def test_all_actors(self):
        assert ActorType.USER.value == "user"
        assert ActorType.AGENT.value == "agent"
        assert ActorType.SYSTEM.value == "system"
        assert ActorType.PLUGIN.value == "plugin"


class TestAuditRecord:
    def test_defaults(self):
        record = AuditRecord()
        assert record.id != ""
        assert record.timestamp != ""
        assert record.success is True
        assert record.metadata == {}
    
    def test_to_dict(self):
        record = AuditRecord(
            operation="memory.add",
            actor_id="user1",
            content="Added memory",
            success=True,
        )
        d = record.to_dict()
        assert d["operation"] == "memory.add"
        assert d["actor_id"] == "user1"
        assert d["success"] is True
    
    def test_to_json(self):
        record = AuditRecord(operation="memory.add", content="test")
        json_str = record.to_json()
        assert '"operation": "memory.add"' in json_str
    
    def test_from_dict(self):
        data = {
            "operation": "memory.add",
            "actor_id": "user1",
            "content": "test",
        }
        record = AuditRecord.from_dict(data)
        assert record.operation == "memory.add"
        assert record.actor_id == "user1"


class TestMemoryHandler:
    def test_emit_and_get(self):
        handler = MemoryHandler(max_records=100)
        record = AuditRecord(operation="memory.add", content="test")
        handler.emit(record)
        
        records = handler.get_records()
        assert len(records) == 1
        assert records[0].operation == "memory.add"
    
    def test_get_records_with_filter(self):
        handler = MemoryHandler()
        handler.emit(AuditRecord(operation="memory.add", actor_id="user1"))
        handler.emit(AuditRecord(operation="memory.add", actor_id="user2"))
        handler.emit(AuditRecord(operation="memory.delete", actor_id="user1"))
        
        # Filter by operation
        records = handler.get_records(operation="memory.add")
        assert len(records) == 2
        
        # Filter by actor_id
        records = handler.get_records(actor_id="user1")
        assert len(records) == 2
        
        # Filter by both
        records = handler.get_records(operation="memory.delete", actor_id="user1")
        assert len(records) == 1
    
    def test_get_records_limit(self):
        handler = MemoryHandler()
        for i in range(50):
            handler.emit(AuditRecord(operation=f"op.{i}"))
        
        records = handler.get_records(limit=10)
        assert len(records) == 10
    
    def test_get_stats(self):
        handler = MemoryHandler()
        handler.emit(AuditRecord(operation="memory.add", success=True))
        handler.emit(AuditRecord(operation="memory.add", success=True))
        handler.emit(AuditRecord(operation="memory.delete", success=False))
        
        stats = handler.get_stats()
        assert stats.total_records == 3
        assert stats.by_operation["memory.add"] == 2
        assert stats.by_operation["memory.delete"] == 1
        assert stats.success_count == 2
        assert stats.failure_count == 1
    
    def test_max_records_eviction(self):
        handler = MemoryHandler(max_records=5)
        for i in range(10):
            handler.emit(AuditRecord(operation=f"op.{i}"))
        
        records = handler.get_records(limit=0)
        assert len(records) == 5  # Oldest records evicted
    
    def test_clear(self):
        handler = MemoryHandler()
        handler.emit(AuditRecord())
        handler.clear()
        assert len(handler.get_records()) == 0


class TestFileHandler:
    def test_emit_to_file(self, tmp_path):
        log_file = tmp_path / "audit.jsonl"
        handler = FileHandler(log_file, rotate=False)
        handler.emit(AuditRecord(operation="memory.add", content="test"))
        handler.close()
        
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        assert '"operation": "memory.add"' in lines[0]


class TestLoggingHandler:
    def test_emit_no_error(self):
        handler = LoggingHandler(logger_name="test.audit")
        handler.emit(AuditRecord(operation="memory.add", content="test"))


class TestAuditLogger:
    def setup_method(self):
        reset_audit_logger()
    
    def teardown_method(self):
        reset_audit_logger()
    
    def test_basic_logging(self):
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        
        audit.log_sync(
            operation=OperationType.MEMORY_ADD,
            content="Added a memory",
            actor_id="user1",
            success=True,
        )
        
        records = audit.get_records()
        assert len(records) == 1
        assert records[0].operation == "memory.add"
        assert records[0].actor_id == "user1"
    
    def test_context_manager_success(self):
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        
        with audit.log(OperationType.MEMORY_ADD, actor_id="user1") as record:
            record.content = "Adding memory"
        
        records = audit.get_records()
        assert len(records) == 1
        assert records[0].success is True
        assert records[0].duration_ms > 0
    
    def test_context_manager_exception(self):
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        
        try:
            with audit.log(OperationType.MEMORY_ADD) as record:
                record.content = "Will fail"
                raise ValueError("test error")
        except ValueError:
            pass
        
        records = audit.get_records()
        assert len(records) == 1
        assert records[0].success is False
        assert "ValueError" in records[0].error_message
    
    def test_get_stats(self):
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        audit.log_sync(OperationType.MEMORY_ADD, "test", success=True)
        audit.log_sync(OperationType.MEMORY_DELETE, "test", success=False)
        
        stats = audit.get_stats()
        assert stats.total_records == 2
        assert stats.success_count == 1
        assert stats.failure_count == 1
    
    def test_export_jsonl(self, tmp_path):
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        audit.log_sync(OperationType.MEMORY_ADD, "test1")
        audit.log_sync(OperationType.MEMORY_ADD, "test2")
        
        export_file = tmp_path / "export.jsonl"
        count = audit.export(export_file, format="jsonl")
        assert count == 2
        assert export_file.exists()
    
    def test_export_json(self, tmp_path):
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        audit.log_sync(OperationType.MEMORY_ADD, "test")
        
        export_file = tmp_path / "export.json"
        count = audit.export(export_file, format="json")
        assert count == 1
        assert export_file.exists()
    
    def test_add_remove_handler(self):
        handler1 = MemoryHandler()
        handler2 = MemoryHandler()
        audit = AuditLogger(handlers=[handler1])
        audit.add_handler(handler2)
        
        assert len(audit._handlers) == 2
        audit.remove_handler(MemoryHandler)
        assert len(audit._handlers) == 1


class TestGlobalAuditLogger:
    def setup_method(self):
        reset_audit_logger()
    
    def teardown_method(self):
        reset_audit_logger()
    
    def test_singleton(self):
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2
    
    def test_reset(self):
        logger1 = get_audit_logger()
        reset_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is not logger2


class TestAuditLoggerAdvanced:
    """Advanced tests for AuditLogger."""
    
    def test_trace_context(self):
        """Test trace context in audit records."""
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        
        trace_id = "trace-123"
        
        with audit.log(
            OperationType.MEMORY_ADD,
            actor_id="user1",
            trace_id=trace_id,
        ) as record:
            record.content = "Test trace"
        
        records = audit.get_records()
        assert records[0].trace_id == trace_id
    
    def test_nested_operation(self):
        """Test nested operations with parent_id."""
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        
        with audit.log(OperationType.MEMORY_ADD) as parent_record:
            parent_record.target_id = "parent-id"
            
            with audit.log(OperationType.MEMORY_SEARCH, parent_id=parent_record.id) as child_record:
                child_record.content = "Child operation"
        
        records = audit.get_records()
        parent = next(r for r in records if r.target_id == "parent-id")
        child = next(r for r in records if r.parent_id == parent.id)
        assert child is not None
    
    def test_session_management(self):
        """Test session ID management."""
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler], session_id="session-abc")
        
        audit.log_sync(OperationType.MEMORY_ADD, "test1")
        
        records = audit.get_records()
        assert records[0].session_id == "session-abc"
        
        audit.set_session_id("session-xyz")
        audit.log_sync(OperationType.MEMORY_ADD, "test2")
        
        records = audit.get_records(session_id="session-xyz")
        assert len(records) == 1
    
    def test_export_with_since_filter(self, tmp_path):
        """Test export with time filter."""
        import time
        from datetime import datetime, timezone
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        audit.log_sync(OperationType.MEMORY_ADD, "old record")
        
        # Wait a bit
        time.sleep(0.1)
        since = datetime.now(timezone.utc)
        
        audit.log_sync(OperationType.MEMORY_ADD, "new record")
        
        # Only export records since 'since'
        export_file = tmp_path / "filtered.json"
        count = audit.export(export_file, since=since)
        
        assert count == 1
        content = export_file.read_text()
        assert "new record" in content
    
    def test_multiple_handlers(self):
        """Test multiple handlers receive records."""
        handler1 = MemoryHandler()
        handler2 = MemoryHandler()
        audit = AuditLogger(handlers=[handler1, handler2])
        
        audit.log_sync(OperationType.MEMORY_ADD, "test")
        
        assert len(handler1.get_records()) == 1
        assert len(handler2.get_records()) == 1
    
    def test_close_all_handlers(self):
        """Test closing all handlers."""
        handler = MemoryHandler()
        audit = AuditLogger(handlers=[handler])
        audit.close()  # Should not raise
