"""
审计日志模块 - 记忆操作的完整审计追踪

记录所有记忆操作的完整生命周期：
- 操作类型（CRUD + 特殊操作）
- 操作主体（用户/Agent/系统）
- 操作时间戳
- 操作结果（成功/失败）
- 上下文信息

支持输出到：
- 内存缓冲区（实时查询）
- 文件（JSON Lines 格式）
- 标准日志（Python logging）
- syslog（系统日志）

依赖: Python 标准库
"""

from __future__ import annotations

import enum
import json
import logging
import os
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Union


# ---------------------------------------------------------------------------
# Enums and Constants
# ---------------------------------------------------------------------------

class AuditLevel(enum.Enum):
    """审计日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class OperationType(enum.Enum):
    """记忆操作类型"""
    # Storage operations
    MEMORY_ADD = "memory.add"
    MEMORY_UPDATE = "memory.update"
    MEMORY_DELETE = "memory.delete"
    MEMORY_SEARCH = "memory.search"
    MEMORY_RECALL = "memory.recall"
    
    # Knowledge graph operations
    ENTITY_ADD = "entity.add"
    ENTITY_UPDATE = "entity.update"
    ENTITY_DELETE = "entity.delete"
    RELATION_ADD = "relation.add"
    RELATION_DELETE = "relation.delete"
    KG_SEARCH = "knowledge_graph.search"
    
    # System operations
    CONSOLIDATION = "system.consolidation"
    COMPRESSION = "system.compression"
    EXPORT = "system.export"
    IMPORT = "system.import"
    SNAPSHOT = "system.snapshot"
    ROLLBACK = "system.rollback"
    
    # Session operations
    SESSION_CREATE = "session.create"
    SESSION_SWITCH = "session.switch"
    SESSION_CLEAR = "session.clear"
    
    # Configuration
    CONFIG_CHANGE = "config.change"
    PLUGIN_REGISTER = "plugin.register"
    PLUGIN_UNREGISTER = "plugin.unregister"


class ActorType(enum.Enum):
    """操作主体类型"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    PLUGIN = "plugin"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    """审计日志记录
    
    Attributes:
        id: 唯一标识符（UUID）
        timestamp: ISO 格式时间戳
        level: 日志级别
        operation: 操作类型
        actor_type: 操作主体类型
        actor_id: 操作主体标识
        session_id: 会话 ID
        target_id: 目标对象 ID（记忆 ID、实体 ID 等）
        target_type: 目标对象类型
        content: 操作内容摘要
        metadata: 额外元数据
        duration_ms: 操作耗时（毫秒）
        success: 是否成功
        error_message: 错误信息（失败时）
        trace_id: 追踪 ID（用于关联多个操作）
        parent_id: 父操作 ID（用于嵌套操作）
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    level: str = AuditLevel.INFO.value
    operation: str = ""
    actor_type: str = ActorType.SYSTEM.value
    actor_id: str = ""
    session_id: str = ""
    target_id: str = ""
    target_type: str = ""
    content: str = ""
    metadata: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True
    error_message: str = ""
    trace_id: str = ""
    parent_id: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: dict) -> "AuditRecord":
        """从字典创建"""
        return cls(**data)


@dataclass
class AuditStats:
    """审计统计"""
    total_records: int = 0
    by_operation: dict = field(default_factory=dict)
    by_level: dict = field(default_factory=dict)
    by_actor: dict = field(default_factory=dict)
    success_count: int = 0
    failure_count: int = 0
    avg_duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Output Handlers
# ---------------------------------------------------------------------------

class AuditHandler:
    """审计日志处理器基类"""
    
    def emit(self, record: AuditRecord) -> None:
        raise NotImplementedError
    
    def flush(self) -> None:
        pass
    
    def close(self) -> None:
        pass


class MemoryHandler(AuditHandler):
    """内存缓冲区处理器"""
    
    def __init__(self, max_records: int = 10000):
        self._records: list[AuditRecord] = []
        self._max_records = max_records
        self._lock = threading.RLock()
    
    def emit(self, record: AuditRecord) -> None:
        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records.pop(0)
    
    def get_records(
        self,
        limit: int = 100,
        operation: Optional[str] = None,
        actor_id: Optional[str] = None,
        session_id: Optional[str] = None,
        success: Optional[bool] = None,
        since: Optional[float] = None,
    ) -> list[AuditRecord]:
        """查询审计记录"""
        with self._lock:
            results = list(self._records)
        
        if operation:
            results = [r for r in results if r.operation == operation]
        if actor_id:
            results = [r for r in results if r.actor_id == actor_id]
        if session_id:
            results = [r for r in results if r.session_id == session_id]
        if success is not None:
            results = [r for r in results if r.success == success]
        if since:
            results = [r for r in results if float(r.timestamp.replace("Z", "+00:00").replace("+00:00", "")) >= since]
        
        return results[-limit:] if limit else results
    
    def get_stats(self) -> AuditStats:
        """获取统计信息"""
        with self._lock:
            records = list(self._records)
        
        stats = AuditStats(total_records=len(records))
        total_duration = 0.0
        
        for r in records:
            stats.by_operation[r.operation] = stats.by_operation.get(r.operation, 0) + 1
            stats.by_level[r.level] = stats.by_level.get(r.level, 0) + 1
            if r.actor_id:
                stats.by_actor[r.actor_id] = stats.by_actor.get(r.actor_id, 0) + 1
            
            if r.success:
                stats.success_count += 1
            else:
                stats.failure_count += 1
            
            total_duration += r.duration_ms
        
        if records:
            stats.avg_duration_ms = total_duration / len(records)
        
        return stats
    
    def clear(self) -> None:
        """清空缓冲区"""
        with self._lock:
            self._records.clear()


class FileHandler(AuditHandler):
    """文件处理器（JSON Lines 格式）"""
    
    def __init__(
        self,
        path: Union[str, Path],
        max_size_mb: int = 100,
        rotate: bool = True,
        compress: bool = False,
    ):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_size = max_size_mb * 1024 * 1024
        self._enable_rotate = rotate
        self._compress = compress
        self._lock = threading.Lock()
        self._file = None
        self._bytes_written = 0
    
    def _get_file(self) -> Any:
        """获取或创建文件对象"""
        if self._file is None:
            self._file = open(self._path, "a", encoding="utf-8")
            self._bytes_written = self._file.tell()
        return self._file
    
    def _should_rotate(self) -> bool:
        """检查是否需要轮转"""
        return self._enable_rotate and self._bytes_written >= self._max_size
    
    def _rotate(self) -> None:
        """执行文件轮转"""
        if self._file:
            self._file.close()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = self._path.parent / f"{self._path.stem}.{timestamp}{self._path.suffix}"
        self._path.rename(archive_path)
        
        if self._compress:
            import gzip
            import shutil
            gzip_path = Path(str(archive_path) + ".gz")
            with open(archive_path, "rb") as f_in:
                with gzip.open(gzip_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            archive_path.unlink()
        
        self._file = open(self._path, "a", encoding="utf-8")
        self._bytes_written = 0
    
    def emit(self, record: AuditRecord) -> None:
        line = record.to_json() + "\n"
        with self._lock:
            if self._should_rotate():
                self._rotate()
            
            f = self._get_file()
            f.write(line)
            self._bytes_written += len(line.encode("utf-8"))
            f.flush()
    
    def close(self) -> None:
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None


class LoggingHandler(AuditHandler):
    """标准日志处理器（Python logging）"""
    
    def __init__(self, logger_name: str = "audit"):
        self._logger = logging.getLogger(logger_name)
        self._level_map = {
            AuditLevel.DEBUG: logging.DEBUG,
            AuditLevel.INFO: logging.INFO,
            AuditLevel.WARNING: logging.WARNING,
            AuditLevel.ERROR: logging.ERROR,
            AuditLevel.CRITICAL: logging.CRITICAL,
        }
    
    def emit(self, record: AuditRecord) -> None:
        log_level = self._level_map.get(AuditLevel(record.level), logging.INFO)
        msg = f"[{record.operation}] {record.content}"
        if record.actor_id:
            msg = f"{msg} (actor={record.actor_id})"
        if record.target_id:
            msg = f"{msg} (target={record.target_id})"
        if not record.success:
            msg = f"{msg} ERROR: {record.error_message}"
        
        self._logger.log(log_level, msg, extra={"audit_record": record.to_dict()})


class SyslogHandler(AuditHandler):
    """Syslog 处理器"""
    
    def __init__(self, address: Optional[str] = None, facility: int = 16):  # USER
        self._facility = facility
        self._address = address
        self._sock = None
    
    def _connect(self) -> None:
        if self._sock is None:
            import socket
            if isinstance(self._address, str):
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                self._sock.connect(self._address)
            else:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._sock.connect(self._address or ("localhost", 514))
    
    def emit(self, record: AuditRecord) -> None:
        try:
            self._connect()
            msg = f"<{self._facility}>[{record.operation}] {record.content}"
            if self._sock:
                self._sock.send(msg.encode("utf-8"))
        except (OSError, ConnectionError):
            pass  # Syslog failures should not block operations
    
    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    审计日志记录器
    
    Example:
        # 创建审计日志器
        audit = AuditLogger(
            handlers=[
                MemoryHandler(max_records=1000),
                FileHandler("logs/audit.jsonl"),
            ],
        )
        
        # 记录操作
        with audit.log(OperationType.MEMORY_ADD, actor_id="user123", session_id="sess1") as record:
            # 执行实际操作
            memory_id = memory.remember("Important fact")
            record.target_id = memory_id
            record.content = f"Added memory: {memory_id}"
        
        # 查询审计记录
        records = audit.get_records(operation="memory.add", limit=10)
        stats = audit.get_stats()
    """
    
    def __init__(
        self,
        handlers: Optional[list[AuditHandler]] = None,
        default_level: AuditLevel = AuditLevel.INFO,
        session_id: str = "",
    ):
        self._handlers = handlers or [MemoryHandler()]
        self._default_level = default_level
        self._session_id = session_id or str(uuid.uuid4())
        self._trace_stack: list[str] = []
        self._lock = threading.RLock()
    
    @property
    def session_id(self) -> str:
        return self._session_id
    
    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id
    
    def add_handler(self, handler: AuditHandler) -> None:
        with self._lock:
            self._handlers.append(handler)
    
    def remove_handler(self, handler_type: type) -> bool:
        with self._lock:
            for i, h in enumerate(self._handlers):
                if isinstance(h, handler_type):
                    self._handlers.pop(i).close()
                    return True
        return False
    
    def log(
        self,
        operation: OperationType,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: str = "",
        target_id: str = "",
        target_type: str = "",
        level: AuditLevel = AuditLevel.INFO,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> "AuditLogContext":
        """
        创建日志上下文管理器
        
        Example:
            with audit.log(OperationType.MEMORY_ADD, actor_id="user1") as record:
                memory_id = memory.remember("test")
                record.target_id = memory_id
        """
        return AuditLogContext(
            audit_logger=self,
            operation=operation,
            actor_type=actor_type,
            actor_id=actor_id,
            target_id=target_id,
            target_type=target_type,
            level=level,
            session_id=session_id or self._session_id,
            trace_id=trace_id or (self._trace_stack[-1] if self._trace_stack else ""),
            parent_id=parent_id or "",
        )
    
    def log_sync(
        self,
        operation: OperationType,
        content: str,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: str = "",
        target_id: str = "",
        target_type: str = "",
        level: AuditLevel = AuditLevel.INFO,
        success: bool = True,
        error_message: str = "",
        duration_ms: float = 0.0,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> AuditRecord:
        """同步记录一条审计日志"""
        record = AuditRecord(
            operation=operation.value,
            actor_type=actor_type.value,
            actor_id=actor_id,
            target_id=target_id,
            target_type=target_type,
            content=content,
            level=level.value,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata or {},
            session_id=session_id or self._session_id,
        )
        self._emit(record)
        return record
    
    def _emit(self, record: AuditRecord) -> None:
        """向所有处理器发送记录"""
        for handler in self._handlers:
            try:
                handler.emit(record)
            except (ValueError, TypeError, RuntimeError, OSError):
                pass  # Handler errors should not propagate
    
    def get_records(
        self,
        limit: int = 100,
        operation: Optional[str] = None,
        actor_id: Optional[str] = None,
        session_id: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> list[AuditRecord]:
        """查询审计记录"""
        for handler in self._handlers:
            if isinstance(handler, MemoryHandler):
                return handler.get_records(
                    limit=limit,
                    operation=operation,
                    actor_id=actor_id,
                    session_id=session_id,
                    success=success,
                )
        return []
    
    def get_stats(self) -> AuditStats:
        """获取审计统计"""
        for handler in self._handlers:
            if isinstance(handler, MemoryHandler):
                return handler.get_stats()
        return AuditStats()
    
    def export(
        self,
        path: Union[str, Path],
        format: str = "jsonl",
        since: Optional[datetime] = None,
    ) -> int:
        """导出审计记录"""
        records = self.get_records(limit=0)
        if since:
            # Make 'since' timezone-naive for comparison
            if since.tzinfo is not None:
                since = since.replace(tzinfo=None)
            records = [
                r for r in records
                if datetime.fromisoformat(r.timestamp.replace("Z", "+00:00").replace("+00:00", "")) >= since
            ]
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "jsonl":
            with open(path, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(record.to_json() + "\n")
        elif format == "json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return len(records)
    
    def flush(self) -> None:
        """刷新所有处理器"""
        for handler in self._handlers:
            handler.flush()
    
    def close(self) -> None:
        """关闭所有处理器"""
        for handler in self._handlers:
            handler.close()


class AuditLogContext:
    """审计日志上下文管理器"""
    
    def __init__(
        self,
        audit_logger: AuditLogger,
        operation: OperationType,
        actor_type: ActorType,
        actor_id: str,
        target_id: str,
        target_type: str,
        level: AuditLevel,
        session_id: str,
        trace_id: str,
        parent_id: str,
    ):
        self._audit = audit_logger
        self._operation = operation
        self._actor_type = actor_type
        self._actor_id = actor_id
        self._target_id = target_id
        self._target_type = target_type
        self._level = level
        self._session_id = session_id
        self._trace_id = trace_id
        self._parent_id = parent_id
        self._record: Optional[AuditRecord] = None
        self._start_time: float = 0.0
    
    def __enter__(self) -> "AuditRecord":
        self._start_time = time.perf_counter()
        self._record = AuditRecord(
            operation=self._operation.value,
            actor_type=self._actor_type.value,
            actor_id=self._actor_id,
            target_id=self._target_id,
            target_type=self._target_type,
            level=self._level.value,
            session_id=self._session_id,
            trace_id=self._trace_id,
            parent_id=self._parent_id,
        )
        return self._record
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._record:
            self._record.duration_ms = (time.perf_counter() - self._start_time) * 1000
            self._record.success = exc_type is None
            if exc_type:
                self._record.error_message = f"{exc_type.__name__}: {exc_val}"
                self._record.level = AuditLevel.ERROR.value
            self._audit._emit(self._record)
        return False  # Do not suppress exceptions


# ---------------------------------------------------------------------------
# Global Audit Logger
# ---------------------------------------------------------------------------

_global_audit_logger: Optional[AuditLogger] = None
_audit_logger_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志器（线程安全）"""
    global _global_audit_logger
    if _global_audit_logger is None:
        with _audit_logger_lock:
            if _global_audit_logger is None:
                _global_audit_logger = AuditLogger()
    return _global_audit_logger


def reset_audit_logger() -> None:
    """重置全局审计日志器"""
    global _global_audit_logger
    with _audit_logger_lock:
        if _global_audit_logger:
            _global_audit_logger.close()
        _global_audit_logger = None


__all__ = [
    "AuditLevel",
    "OperationType",
    "ActorType",
    "AuditRecord",
    "AuditStats",
    "AuditHandler",
    "MemoryHandler",
    "FileHandler",
    "LoggingHandler",
    "SyslogHandler",
    "AuditLogger",
    "AuditLogContext",
    "get_audit_logger",
    "reset_audit_logger",
]
