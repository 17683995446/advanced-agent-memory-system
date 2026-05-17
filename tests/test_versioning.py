"""Unit tests for the versioning module."""
import pytest
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.infra.memory_version_controller import (
    MemoryVersionControl,
    Snapshot,
    SnapshotTrigger,
)


class TestSnapshot:
    def test_create_default(self):
        snap = Snapshot()
        assert snap.id.startswith("snap_")
        assert snap.trigger == SnapshotTrigger.MANUAL
        assert snap.record_count == 0
    
    def test_create_with_data(self):
        snap = Snapshot(
            name="test",
            trigger=SnapshotTrigger.BEFORE_DELETE,
            data={"records": [{"id": "1"}]},
            record_count=1,
        )
        assert snap.name == "test"
        assert snap.trigger == SnapshotTrigger.BEFORE_DELETE
        assert snap.record_count == 1
    
    def test_to_dict(self):
        snap = Snapshot(name="test", record_count=5)
        d = snap.to_dict()
        assert d["name"] == "test"
        assert d["record_count"] == 5
        assert d["trigger"] == "manual"


class TestSnapshotTrigger:
    def test_values(self):
        assert SnapshotTrigger.MANUAL.value == "manual"
        assert SnapshotTrigger.BEFORE_DELETE.value == "before_delete"
        assert SnapshotTrigger.BEFORE_UPDATE.value == "before_update"


class TestMemoryVersionControl:
    def setup_method(self):
        self.vc = MemoryVersionControl()
    
    def test_create_snapshot(self):
        data = {"records": [{"id": "1", "content": "test"}]}
        snap = self.vc.create_snapshot(data, name="initial")
        assert snap.id in self.vc._snapshots
        assert snap.name == "initial"
        assert snap.record_count == 1
    
    def test_create_snapshot_deep_copy(self):
        data = {"records": [{"id": "1"}]}
        snap = self.vc.create_snapshot(data)
        data["records"][0]["id"] = "modified"
        # Snapshot data should not be affected
        assert self.vc.get_snapshot_data(snap.id)["records"][0]["id"] == "1"
    
    def test_get_snapshot(self):
        snap = self.vc.create_snapshot({"records": []}, name="test")
        retrieved = self.vc.get_snapshot(snap.id)
        assert retrieved is not None
        assert retrieved.name == "test"
    
    def test_get_snapshot_nonexistent(self):
        assert self.vc.get_snapshot("nonexistent") is None
    
    def test_get_snapshot_data(self):
        data = {"records": [{"id": "1"}]}
        snap = self.vc.create_snapshot(data)
        retrieved_data = self.vc.get_snapshot_data(snap.id)
        assert retrieved_data is not None
        assert retrieved_data["records"][0]["id"] == "1"
    
    def test_get_snapshot_data_is_copy(self):
        data = {"records": [{"id": "1"}]}
        snap = self.vc.create_snapshot(data)
        d1 = self.vc.get_snapshot_data(snap.id)
        d2 = self.vc.get_snapshot_data(snap.id)
        d1["records"][0]["id"] = "changed"
        assert d2["records"][0]["id"] == "1"
    
    def test_rollback(self):
        data = {"records": [{"id": "1"}, {"id": "2"}]}
        snap = self.vc.create_snapshot(data, name="backup")
        rolled_back = self.vc.rollback(snap.id)
        assert rolled_back is not None
        assert len(rolled_back["records"]) == 2
    
    def test_rollback_nonexistent(self):
        assert self.vc.rollback("nonexistent") is None
    
    def test_rollback_is_copy(self):
        data = {"records": [{"id": "1"}]}
        snap = self.vc.create_snapshot(data)
        r1 = self.vc.rollback(snap.id)
        r2 = self.vc.rollback(snap.id)
        r1["records"][0]["id"] = "changed"
        assert r2["records"][0]["id"] == "1"
    
    def test_delete_snapshot(self):
        snap = self.vc.create_snapshot({"records": []})
        assert self.vc.delete_snapshot(snap.id) is True
        assert self.vc.get_snapshot(snap.id) is None
    
    def test_delete_nonexistent(self):
        assert self.vc.delete_snapshot("nonexistent") is False
    
    def test_list_history(self):
        self.vc.create_snapshot({"records": []}, name="s1")
        self.vc.create_snapshot({"records": []}, name="s2")
        self.vc.create_snapshot({"records": []}, name="s3")
        history = self.vc.list_history()
        assert len(history) == 3
        # Most recent first
        assert history[0].name == "s3"
    
    def test_list_history_with_limit(self):
        for i in range(5):
            self.vc.create_snapshot({"records": []}, name=f"s{i}")
        history = self.vc.list_history(limit=3)
        assert len(history) == 3
    
    def test_list_history_with_trigger_filter(self):
        self.vc.create_snapshot({"records": []}, trigger=SnapshotTrigger.MANUAL)
        self.vc.create_snapshot({"records": []}, trigger=SnapshotTrigger.BEFORE_DELETE)
        self.vc.create_snapshot({"records": []}, trigger=SnapshotTrigger.MANUAL)
        history = self.vc.list_history(trigger=SnapshotTrigger.MANUAL)
        assert len(history) == 2
    
    def test_auto_snapshot_enabled(self):
        vc = MemoryVersionControl(auto_snapshot_on_delete=True)
        data = {"records": [{"id": "1"}]}
        snap = vc.auto_snapshot(data, SnapshotTrigger.BEFORE_DELETE)
        assert snap is not None
        assert snap.trigger == SnapshotTrigger.BEFORE_DELETE
    
    def test_auto_snapshot_disabled(self):
        vc = MemoryVersionControl(auto_snapshot_on_delete=False)
        snap = vc.auto_snapshot({"records": []}, SnapshotTrigger.BEFORE_DELETE)
        assert snap is None
    
    def test_should_auto_snapshot(self):
        vc = MemoryVersionControl(
            auto_snapshot_on_delete=True,
            auto_snapshot_on_update=True,
        )
        assert vc.should_auto_snapshot(SnapshotTrigger.BEFORE_DELETE) is True
        assert vc.should_auto_snapshot(SnapshotTrigger.BEFORE_UPDATE) is True
        assert vc.should_auto_snapshot(SnapshotTrigger.MANUAL) is False
    
    def test_diff(self):
        s1 = self.vc.create_snapshot(
            {"records": [{"id": "1"}, {"id": "2"}]},
            name="v1",
        )
        s2 = self.vc.create_snapshot(
            {"records": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
            name="v2",
        )
        diff = self.vc.diff(s1.id, s2.id)
        assert diff is not None
        assert diff["record_count_1"] == 2
        assert diff["record_count_2"] == 3
        assert diff["added"] == 1
    
    def test_diff_nonexistent(self):
        s1 = self.vc.create_snapshot({"records": []})
        assert self.vc.diff(s1.id, "nonexistent") is None
    
    def test_max_snapshots_eviction(self):
        vc = MemoryVersionControl(max_snapshots=3)
        vc.create_snapshot({"records": []}, name="s1")
        vc.create_snapshot({"records": []}, name="s2")
        vc.create_snapshot({"records": []}, name="s3")
        vc.create_snapshot({"records": []}, name="s4")
        # s1 should be evicted
        assert not any(s.name == "s1" for s in vc.list_history())
    
    def test_clear(self):
        self.vc.create_snapshot({"records": []})
        self.vc.create_snapshot({"records": []})
        self.vc.clear()
        assert len(self.vc.list_history()) == 0
    
    def test_get_stats(self):
        stats = self.vc.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["max_snapshots"] == 50
    
    def test_count_records_list(self):
        data = [{"id": "1"}, {"id": "2"}]
        snap = self.vc.create_snapshot(data)
        assert snap.record_count == 2
    
    def test_count_records_dict_with_memories(self):
        data = {"memories": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}
        snap = self.vc.create_snapshot(data)
        assert snap.record_count == 3
