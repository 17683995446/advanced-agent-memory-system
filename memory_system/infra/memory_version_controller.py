"""
记忆版本控制模块 - Snapshot 与 Rollback

支持:
- 记忆快照 (Snapshot)
- 版本回滚 (Rollback)
- 版本历史查询
- 自动快照策略

依赖: 无额外依赖
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SnapshotTrigger(Enum):
    """快照触发方式"""
    MANUAL = "manual"           # 手动触发
    BEFORE_DELETE = "before_delete"  # 删除前自动
    BEFORE_UPDATE = "before_update"  # 更新前自动
    SCHEDULED = "scheduled"     # 定时触发
    SIZE_THRESHOLD = "size_threshold"  # 数量阈值


@dataclass
class Snapshot:
    """
    记忆快照
    
    Attributes:
        id: 快照唯一标识
        name: 快照名称
        trigger: 触发方式
        data: 快照数据 (深拷贝)
        record_count: 记录数量
        created_at: 创建时间
        metadata: 快照元数据
    """
    id: str = field(default_factory=lambda: f"snap_{int(time.time()*1000)}")
    name: str = ""
    trigger: SnapshotTrigger = SnapshotTrigger.MANUAL
    data: dict = field(default_factory=dict)
    record_count: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "trigger": self.trigger.value,
            "record_count": self.record_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class MemoryVersionControl:
    """
    记忆版本控制器
    
    管理记忆数据的版本历史，支持快照和回滚。
    
    Args:
        max_snapshots: 最大保留快照数
        auto_snapshot_on_delete: 删除前自动快照
        auto_snapshot_on_update: 更新前自动快照
    
    Example:
        vc = MemoryVersionControl(max_snapshots=10)
        
        # 创建快照
        vc.create_snapshot(
            name="before-cleanup",
            data={"records": [...]},
            trigger=SnapshotTrigger.MANUAL,
        )
        
        # 回滚
        vc.rollback("snap_xxx")
        
        # 查看历史
        history = vc.list_history()
    """
    
    def __init__(
        self,
        max_snapshots: int = 50,
        auto_snapshot_on_delete: bool = True,
        auto_snapshot_on_update: bool = False,
    ):
        self._snapshots: dict[str, Snapshot] = {}
        self._max_snapshots = max_snapshots
        self._auto_delete = auto_snapshot_on_delete
        self._auto_update = auto_snapshot_on_update
        self._snapshot_counter = 0
    
    def create_snapshot(
        self,
        data: dict,
        name: Optional[str] = None,
        trigger: SnapshotTrigger = SnapshotTrigger.MANUAL,
        metadata: Optional[dict] = None,
    ) -> Snapshot:
        """
        创建快照
        
        Args:
            data: 要快照的数据 (会被深拷贝)
            name: 快照名称
            trigger: 触发方式
            metadata: 元数据
            
        Returns:
            创建的快照
        """
        self._snapshot_counter += 1
        
        snapshot = Snapshot(
            id=f"snap_{int(time.time()*1000)}_{self._snapshot_counter}",
            name=name or f"snapshot_{self._snapshot_counter}",
            trigger=trigger,
            data=copy.deepcopy(data),
            record_count=self._count_records(data),
            metadata=metadata or {},
        )
        
        self._snapshots[snapshot.id] = snapshot
        
        # 淘汰旧快照
        self._evict_old()
        
        logger.info(
            "Snapshot created: %s (%d records, trigger=%s)",
            snapshot.id, snapshot.record_count, trigger.value,
        )
        
        return snapshot
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """获取快照"""
        return self._snapshots.get(snapshot_id)
    
    def get_snapshot_data(self, snapshot_id: str) -> Optional[dict]:
        """获取快照数据"""
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot:
            return copy.deepcopy(snapshot.data)
        return None
    
    def rollback(self, snapshot_id: str) -> Optional[dict]:
        """
        回滚到指定快照
        
        Args:
            snapshot_id: 快照 ID
            
        Returns:
            快照数据的深拷贝，或 None
        """
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            logger.warning("Snapshot not found: %s", snapshot_id)
            return None
        
        logger.info(
            "Rollback to snapshot: %s (%s, %d records)",
            snapshot_id, snapshot.name, snapshot.record_count,
        )
        
        return copy.deepcopy(snapshot.data)
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照"""
        if snapshot_id in self._snapshots:
            del self._snapshots[snapshot_id]
            logger.info("Snapshot deleted: %s", snapshot_id)
            return True
        return False
    
    def list_history(
        self,
        limit: Optional[int] = None,
        trigger: Optional[SnapshotTrigger] = None,
    ) -> list[Snapshot]:
        """
        列出快照历史
        
        Args:
            limit: 返回数量
            trigger: 按触发方式过滤
        """
        snapshots = sorted(
            self._snapshots.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        
        if trigger:
            snapshots = [s for s in snapshots if s.trigger == trigger]
        
        if limit:
            snapshots = snapshots[:limit]
        
        return snapshots
    
    def should_auto_snapshot(self, trigger: SnapshotTrigger) -> bool:
        """是否应自动创建快照"""
        if trigger == SnapshotTrigger.BEFORE_DELETE:
            return self._auto_delete
        elif trigger == SnapshotTrigger.BEFORE_UPDATE:
            return self._auto_update
        return False
    
    def auto_snapshot(
        self,
        data: dict,
        trigger: SnapshotTrigger,
    ) -> Optional[Snapshot]:
        """自动快照（如果启用）"""
        if not self.should_auto_snapshot(trigger):
            return None
        return self.create_snapshot(
            data=data,
            trigger=trigger,
            metadata={"auto": True},
        )
    
    def diff(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str,
    ) -> Optional[dict]:
        """
        比较两个快照的差异
        
        Returns:
            {"added": int, "removed": int, "changed": int, "snapshot_1": ..., "snapshot_2": ...}
        """
        s1 = self._snapshots.get(snapshot_id_1)
        s2 = self._snapshots.get(snapshot_id_2)
        
        if s1 is None or s2 is None:
            return None
        
        count1 = s1.record_count
        count2 = s2.record_count
        
        added = max(0, count2 - count1)
        removed = max(0, count1 - count2)
        changed = min(count1, count2)
        
        return {
            "snapshot_1": s1.to_dict(),
            "snapshot_2": s2.to_dict(),
            "record_count_1": count1,
            "record_count_2": count2,
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    
    def clear(self):
        """清空所有快照"""
        self._snapshots.clear()
        logger.info("All snapshots cleared")
    
    def _count_records(self, data: dict) -> int:
        """计算记录数量"""
        if isinstance(data, dict):
            if "records" in data:
                return len(data["records"])
            if "memories" in data:
                return len(data["memories"])
        elif isinstance(data, list):
            return len(data)
        return 0
    
    def _evict_old(self):
        """淘汰旧快照"""
        if len(self._snapshots) <= self._max_snapshots:
            return
        
        sorted_snaps = sorted(
            self._snapshots.items(),
            key=lambda x: x[1].created_at,
        )
        
        to_remove = len(self._snapshots) - self._max_snapshots
        for i in range(to_remove):
            sid, _ = sorted_snaps[i]
            del self._snapshots[sid]
            logger.debug("Evicted old snapshot: %s", sid)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_snapshots": len(self._snapshots),
            "max_snapshots": self._max_snapshots,
            "auto_snapshot_on_delete": self._auto_delete,
            "auto_snapshot_on_update": self._auto_update,
        }


__all__ = [
    "MemoryVersionControl",
    "Snapshot",
    "SnapshotTrigger",
]
