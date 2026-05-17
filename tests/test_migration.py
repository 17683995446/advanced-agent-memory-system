"""Unit tests for the migration module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.infra.schema_migration_manager import (
    MigrationManager,
    Migration,
    MigrationRecord,
)


class TestMigration:
    def test_create(self):
        m = Migration(version=1, description="initial")
        assert m.version == 1
        assert m.upgrade is None
        assert m.downgrade is None

    def test_create_with_functions(self):
        m = Migration(
            version=2,
            description="add tags",
            upgrade=lambda v, s: None,
            downgrade=lambda v, s: None,
        )
        assert m.upgrade is not None
        m.upgrade(1, None)  # Should not raise


class TestMigrationRecord:
    def test_create_success(self):
        r = MigrationRecord(version=1, direction="upgrade", success=True)
        assert r.version == 1
        assert r.success is True
        assert r.error == ""

    def test_create_failure(self):
        r = MigrationRecord(version=1, direction="upgrade", success=False, error="timeout")
        assert r.error == "timeout"


class TestMigrationManager:
    def test_create(self):
        manager = MigrationManager(current_version=0)
        assert manager.get_current_version() == 0

    def test_register(self):
        manager = MigrationManager()
        manager.register(Migration(version=1, description="initial"))
        assert 1 in manager.get_available_versions()

    def test_register_multiple(self):
        manager = MigrationManager()
        manager.register(Migration(version=1))
        manager.register(Migration(version=2))
        manager.register(Migration(version=3))
        versions = manager.get_available_versions()
        assert versions == [1, 2, 3]

    def test_upgrade_single(self):
        manager = MigrationManager(current_version=0)
        manager.register(Migration(
            version=1,
            description="v1",
            upgrade=lambda v, s: None,
        ))
        records = manager.upgrade(target_version=1)
        assert len(records) == 1
        assert records[0].success is True
        assert manager.get_current_version() == 1

    def test_upgrade_multiple(self):
        manager = MigrationManager(current_version=0)
        for i in range(1, 4):
            manager.register(Migration(
                version=i,
                description=f"v{i}",
                upgrade=lambda v, s: None,
            ))
        records = manager.upgrade(target_version=3)
        assert len(records) == 3
        assert manager.get_current_version() == 3

    def test_upgrade_to_latest(self):
        manager = MigrationManager(current_version=0)
        manager.register(Migration(version=1, upgrade=lambda v, s: None))
        manager.register(Migration(version=2, upgrade=lambda v, s: None))
        records = manager.upgrade()  # No target = latest
        assert manager.get_current_version() == 2

    def test_upgrade_skip_missing(self):
        manager = MigrationManager(current_version=0)
        manager.register(Migration(version=2, upgrade=lambda v, s: None))
        # v1 not registered, should skip
        records = manager.upgrade(target_version=2)
        assert len(records) == 1
        assert records[0].version == 2

    def test_upgrade_already_at_target(self):
        manager = MigrationManager(current_version=2)
        manager.register(Migration(version=1, upgrade=lambda v, s: None))
        records = manager.upgrade(target_version=2)
        assert len(records) == 0

    def test_upgrade_failure(self):
        manager = MigrationManager(current_version=0)
        manager.register(Migration(
            version=1,
            upgrade=lambda v, s: (_ for _ in ()).throw(RuntimeError("fail")),
        ))
        records = manager.upgrade(target_version=1)
        assert len(records) == 1
        assert records[0].success is False
        assert "fail" in records[0].error
        assert manager.get_current_version() == 0  # Version not bumped

    def test_downgrade(self):
        manager = MigrationManager(current_version=2)
        manager.register(Migration(
            version=2,
            downgrade=lambda v, s: None,
        ))
        manager.register(Migration(
            version=1,
            downgrade=lambda v, s: None,
        ))
        records = manager.downgrade(target_version=0)
        assert len(records) == 2
        assert manager.get_current_version() == 0

    def test_downgrade_no_downgrade_fn(self):
        manager = MigrationManager(current_version=1)
        manager.register(Migration(version=1))  # No downgrade
        records = manager.downgrade(target_version=0)
        assert len(records) == 0

    def test_is_applied(self):
        manager = MigrationManager()
        manager.register(Migration(version=1, upgrade=lambda v, s: None))
        assert not manager.is_applied(1)
        manager.upgrade(target_version=1)
        assert manager.is_applied(1)

    def test_get_pending_upgrades(self):
        manager = MigrationManager(current_version=1)
        manager.register(Migration(version=2, upgrade=lambda v, s: None))
        manager.register(Migration(version=3, upgrade=lambda v, s: None))
        pending = manager.get_pending_upgrades()
        assert pending == [2, 3]

    def test_get_pending_after_upgrade(self):
        manager = MigrationManager(current_version=0)
        manager.register(Migration(version=1, upgrade=lambda v, s: None))
        manager.register(Migration(version=2, upgrade=lambda v, s: None))
        manager.upgrade(target_version=1)
        assert manager.get_pending_upgrades() == [2]

    def test_get_history(self):
        manager = MigrationManager()
        manager.register(Migration(version=1, upgrade=lambda v, s: None))
        manager.upgrade(target_version=1)
        history = manager.get_history()
        assert len(history) == 1
        assert history[0].direction == "upgrade"

    def test_get_stats(self):
        manager = MigrationManager(current_version=1)
        manager.register(Migration(version=2, upgrade=lambda v, s: None))
        manager.register(Migration(version=3, upgrade=lambda v, s: None))
        stats = manager.get_stats()
        assert stats["current_version"] == 1
        assert stats["registered_migrations"] == 2
        assert stats["pending_upgrades"] == 2

    def test_upgrade_with_storage(self):
        storage = {"executed": []}
        def upgrade_fn(v, s):
            s["executed"].append(v)

        manager = MigrationManager(current_version=0, storage=storage)
        manager.register(Migration(version=1, upgrade=upgrade_fn))
        manager.upgrade(target_version=1)

        assert 0 in storage["executed"]  # v=0 passed to upgrade
