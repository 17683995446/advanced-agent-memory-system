"""
记忆迁移工具 - Schema 版本管理

支持:
- Schema 版本号管理
- 迁移脚本注册与执行
- 向前/向后迁移
- 迁移历史记录

依赖: 无额外依赖 (轻量级，不依赖 Alembic)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """
    迁移定义
    
    Args:
        version: 目标版本号
        description: 迁移描述
        upgrade: 升级函数 (current_version, storage) -> None
        downgrade: 降级函数 (current_version, storage) -> None
    """
    version: int
    description: str = ""
    upgrade: Optional[Callable] = None
    downgrade: Optional[Callable] = None


@dataclass
class MigrationRecord:
    """迁移执行记录"""
    version: int
    direction: str  # "upgrade" or "downgrade"
    applied_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""


class MigrationManager:
    """
    记忆迁移管理器
    
    轻量级迁移工具，管理 schema 版本变更。
    
    Args:
        current_version: 当前版本号
        storage: 存储后端引用（传递给迁移函数）
    
    Example:
        manager = MigrationManager(current_version=1)
        
        # 注册迁移
        manager.register(Migration(
            version=2,
            description="Add tags field",
            upgrade=lambda v, s: s.execute("ALTER TABLE ..."),
            downgrade=lambda v, s: s.execute("ALTER TABLE ..."),
        ))
        
        # 执行迁移
        manager.upgrade(target_version=2)
        
        # 查看历史
        history = manager.get_history()
    """
    
    def __init__(
        self,
        current_version: int = 0,
        storage: Any = None,
    ):
        self._current_version = current_version
        self._storage = storage
        self._migrations: dict[int, Migration] = {}
        self._history: list[MigrationRecord] = []
        self._applied_versions: set[int] = set()
    
    def register(self, migration: Migration):
        """
        注册迁移
        
        Args:
            migration: 迁移定义
        """
        self._migrations[migration.version] = migration
        logger.info(
            "Migration registered: v%d - %s",
            migration.version, migration.description,
        )
    
    def upgrade(self, target_version: Optional[int] = None) -> list[MigrationRecord]:
        """
        执行升级迁移
        
        Args:
            target_version: 目标版本，None 表示升级到最新
            
        Returns:
            执行的迁移记录列表
        """
        if target_version is None:
            target_version = max(self._migrations.keys()) if self._migrations else self._current_version
        
        records = []
        
        for version in range(self._current_version + 1, target_version + 1):
            migration = self._migrations.get(version)
            if migration is None:
                logger.warning("Migration v%d not found, skipping", version)
                continue
            
            record = self._execute_migration(migration, "upgrade")
            records.append(record)
            
            if record.success:
                self._current_version = version
                self._applied_versions.add(version)
        
        return records
    
    def downgrade(self, target_version: int) -> list[MigrationRecord]:
        """
        执行降级迁移
        
        Args:
            target_version: 目标版本
            
        Returns:
            执行的迁移记录列表
        """
        records = []
        
        for version in range(self._current_version, target_version, -1):
            migration = self._migrations.get(version)
            if migration is None or migration.downgrade is None:
                logger.warning("Downgrade for v%d not available", version)
                continue
            
            record = self._execute_migration(migration, "downgrade")
            records.append(record)
            
            if record.success:
                self._current_version = version - 1
                self._applied_versions.discard(version)
        
        return records
    
    def _execute_migration(self, migration: Migration, direction: str) -> MigrationRecord:
        """执行单个迁移"""
        start = time.time()
        
        try:
            func = migration.upgrade if direction == "upgrade" else migration.downgrade
            if func is not None:
                func(self._current_version, self._storage)
            
            duration = (time.time() - start) * 1000
            
            record = MigrationRecord(
                version=migration.version,
                direction=direction,
                duration_ms=duration,
                success=True,
            )
            
            logger.info(
                "Migration %s v%d succeeded (%.1fms): %s",
                direction, migration.version, duration, migration.description,
            )
            
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            duration = (time.time() - start) * 1000
            
            record = MigrationRecord(
                version=migration.version,
                direction=direction,
                duration_ms=duration,
                success=False,
                error=str(e),
            )
            
            logger.error(
                "Migration %s v%d failed: %s",
                direction, migration.version, e,
            )
        
        self._history.append(record)
        return record
    
    def get_current_version(self) -> int:
        """获取当前版本"""
        return self._current_version
    
    def get_available_versions(self) -> list[int]:
        """获取所有已注册的迁移版本"""
        return sorted(self._migrations.keys())
    
    def get_pending_upgrades(self) -> list[int]:
        """获取待执行的升级"""
        return [
            v for v in sorted(self._migrations.keys())
            if v > self._current_version
        ]
    
    def get_history(self) -> list[MigrationRecord]:
        """获取迁移历史"""
        return list(self._history)
    
    def is_applied(self, version: int) -> bool:
        """检查迁移是否已执行"""
        return version in self._applied_versions
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "current_version": self._current_version,
            "registered_migrations": len(self._migrations),
            "applied_versions": len(self._applied_versions),
            "pending_upgrades": len(self.get_pending_upgrades()),
            "total_history": len(self._history),
            "failed_migrations": sum(1 for h in self._history if not h.success),
        }


__all__ = [
    "MigrationManager",
    "Migration",
    "MigrationRecord",
]
