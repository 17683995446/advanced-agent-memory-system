"""
记忆版本控制与审计系统

提供记忆变更追踪、版本历史、审计日志功能。
支持记忆回滚、变更对比、操作审计。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """变更类型枚举"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"
    COMPRESS = "compress"


@dataclass
class MemoryVersion:
    """记忆版本记录"""
    version_id: str
    memory_id: str
    change_type: ChangeType
    timestamp: float
    content_before: Optional[str] = None
    content_after: Optional[str] = None
    metadata_changes: dict[str, Any] = field(default_factory=dict)
    changed_by: str = "system"
    change_reason: Optional[str] = None


@dataclass
class VersionControlConfig:
    """版本控制配置"""
    max_versions_per_memory: int = 10
    keep_forever_versions: int = 3  # 始终保留的最新版本数
    auto_cleanup: bool = True
    audit_all_changes: bool = True


class MemoryVersionControl:
    """
    记忆版本控制系统
    
    提供记忆变更追踪和版本管理：
    1. 版本历史 - 记录每次变更
    2. 变更对比 - 对比不同版本
    3. 回滚功能 - 恢复到历史版本
    4. 审计日志 - 记录所有操作
    
    Example:
        vc = MemoryVersionControl(config=VersionControlConfig())
        vc.record_change(memory_id, ChangeType.UPDATE, before, after)
        history = vc.get_version_history(memory_id)
        vc.rollback_to_version(memory_id, version_id)
    """
    
    def __init__(self, config: Optional[VersionControlConfig] = None):
        self.config = config or VersionControlConfig()
        # memory_id -> list of MemoryVersion
        self._version_history: dict[str, list[MemoryVersion]] = {}
        # audit log
        self._audit_log: list[dict[str, Any]] = []
    
    def record_change(
        self,
        memory_id: str,
        change_type: ChangeType,
        content_before: Optional[str],
        content_after: Optional[str],
        changed_by: str = "system",
        change_reason: Optional[str] = None,
        metadata_changes: Optional[dict[str, Any]] = None,
    ) -> MemoryVersion:
        """
        记录记忆变更
        
        Args:
            memory_id: 记忆ID
            change_type: 变更类型
            content_before: 变更前内容
            content_after: 变更后内容
            changed_by: 变更者
            change_reason: 变更原因
            metadata_changes: 元数据变更
            
        Returns:
            MemoryVersion 创建的版本记录
        """
        version = MemoryVersion(
            version_id=self._generate_version_id(memory_id),
            memory_id=memory_id,
            change_type=change_type,
            timestamp=time.time(),
            content_before=content_before,
            content_after=content_after,
            metadata_changes=metadata_changes or {},
            changed_by=changed_by,
            change_reason=change_reason,
        )
        
        if memory_id not in self._version_history:
            self._version_history[memory_id] = []
        
        self._version_history[memory_id].append(version)
        
        # 清理旧版本
        if self.config.auto_cleanup:
            self._cleanup_old_versions(memory_id)
        
        # 审计日志
        if self.config.audit_all_changes:
            self._audit_log.append({
                "action": change_type.value,
                "timestamp": version.timestamp,
                "memory_id": memory_id,
                "change_type": change_type.value,
                "changed_by": changed_by,
                "version_id": version.version_id,
            })
        
        logger.debug("Recorded %s for memory %s", change_type.value, memory_id)
        return version
    
    def get_version_history(self, memory_id: str) -> list[MemoryVersion]:
        """获取记忆的版本历史"""
        return list(self._version_history.get(memory_id, []))
    
    def get_version(self, memory_id: str, version_id: str) -> Optional[MemoryVersion]:
        """获取特定版本"""
        versions = self._version_history.get(memory_id, [])
        for v in versions:
            if v.version_id == version_id:
                return v
        return None
    
    def get_latest_version(self, memory_id: str) -> Optional[MemoryVersion]:
        """获取最新版本"""
        versions = self._version_history.get(memory_id, [])
        return versions[-1] if versions else None
    
    def rollback_to_version(
        self,
        memory_id: str,
        version_id: str,
        changed_by: str = "system",
    ) -> Optional[str]:
        """
        回滚到指定版本
        
        Returns:
            回滚后的内容，如果版本不存在则返回None
        """
        target_version = self.get_version(memory_id, version_id)
        if not target_version:
            logger.warning("Version %s not found for memory %s", version_id, memory_id)
            return None
        
        # 记录回滚操作
        current = self.get_latest_version(memory_id)
        current_content = current.content_after if current else None
        
        rollback_content = target_version.content_after
        
        self.record_change(
            memory_id=memory_id,
            change_type=ChangeType.UPDATE,
            content_before=current_content,
            content_after=rollback_content,
            changed_by=changed_by,
            change_reason=f"Rollback to version {version_id}",
        )
        
        logger.info("Rolled back memory %s to version %s", memory_id, version_id)
        return rollback_content
    
    def compare_versions(
        self,
        memory_id: str,
        version_id1: str,
        version_id2: str,
    ) -> dict[str, Any]:
        """
        对比两个版本
        
        Returns:
            对比结果字典
        """
        v1 = self.get_version(memory_id, version_id1)
        v2 = self.get_version(memory_id, version_id2)
        
        if not v1 or not v2:
            return {"error": "One or both versions not found"}
        
        return {
            "version1": {
                "id": version_id1,
                "timestamp": v1.timestamp,
                "content": v1.content_after,
            },
            "version2": {
                "id": version_id2,
                "timestamp": v2.timestamp,
                "content": v2.content_after,
            },
            "content_diff": self._compute_diff(v1.content_after, v2.content_after),
            "time_diff_seconds": abs(v2.timestamp - v1.timestamp),
        }
    
    def get_audit_log(
        self,
        memory_id: Optional[str] = None,
        change_type: Optional[ChangeType] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """
        获取审计日志
        
        Args:
            memory_id: 筛选特定记忆
            change_type: 筛选特定变更类型
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            筛选后的审计日志
        """
        results = self._audit_log.copy()
        
        if memory_id:
            results = [r for r in results if r["memory_id"] == memory_id]
        
        if change_type:
            results = [r for r in results if r["change_type"] == change_type.value]
        
        if start_time:
            results = [r for r in results if r["timestamp"] >= start_time]
        
        if end_time:
            results = [r for r in results if r["timestamp"] <= end_time]
        
        return results
    
    def _generate_version_id(self, memory_id: str) -> str:
        """生成版本ID"""
        timestamp = str(time.time())
        return hashlib.md5(f"{memory_id}:{timestamp}".encode()).hexdigest()[:16]
    
    def _cleanup_old_versions(self, memory_id: str) -> None:
        """清理旧版本"""
        versions = self._version_history.get(memory_id, [])
        
        if len(versions) <= self.config.max_versions_per_memory:
            return
        
        # 保留最新的 keep_forever_versions 个，其余的按策略处理
        keep_count = self.config.keep_forever_versions
        to_remove = len(versions) - self.config.max_versions_per_memory
        
        if to_remove > 0:
            # 保留最新的，删除最旧的
            self._version_history[memory_id] = versions[to_remove:]
            logger.debug("Cleaned up %d old versions for memory %s", to_remove, memory_id)
    
    def _compute_diff(self, content1: Optional[str], content2: Optional[str]) -> dict[str, Any]:
        """计算内容差异"""
        c1 = content1 or ""
        c2 = content2 or ""
        
        if c1 == c2:
            return {"type": "identical"}
        
        # 简单的行差异
        lines1 = c1.splitlines()
        lines2 = c2.splitlines()
        
        added = [l for l in lines2 if l not in lines1]
        removed = [l for l in lines1 if l not in lines2]
        
        return {
            "type": "modified",
            "lines_added": len(added),
            "lines_removed": len(removed),
            "added_content": added[:5],  # 最多5行
            "removed_content": removed[:5],
        }
    
    def get_statistics(self) -> dict[str, Any]:
        """获取版本控制统计信息"""
        total_memories = len(self._version_history)
        total_versions = sum(len(v) for v in self._version_history.values())
        avg_versions = total_versions / total_memories if total_memories > 0 else 0
        
        change_type_counts = {}
        for versions in self._version_history.values():
            for v in versions:
                ct = v.change_type.value
                change_type_counts[ct] = change_type_counts.get(ct, 0) + 1
        
        return {
            "total_memories_with_versions": total_memories,
            "total_versions": total_versions,
            "average_versions_per_memory": round(avg_versions, 2),
            "audit_log_entries": len(self._audit_log),
            "change_type_distribution": change_type_counts,
        }


__all__ = [
    "MemoryVersionControl",
    "VersionControlConfig",
    "MemoryVersion",
    "ChangeType",
]