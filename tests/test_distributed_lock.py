"""Unit tests for the distributed lock module."""
import pytest
import time
import os
import tempfile
import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))

from memory_system.infra.distributed_lock_manager import (
    FileLock,
    DistributedLockManager,
    LockInfo,
)


class TestFileLock:
    def test_acquire_and_release(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock = FileLock(lock_dir=tmpdir)
            acquired = lock.acquire("test_lock", timeout=1.0)
            assert acquired is True
            lock.release()
    
    def test_context_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock = FileLock(lock_dir=tmpdir)
            with lock.lock("test_lock"):
                pass  # 锁在上下文中持有
    
    def test_reentrant_same_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock = FileLock(lock_dir=tmpdir)
            acquired1 = lock.acquire("r1", timeout=1.0)
            assert acquired1 is True
            lock.release()
            # 重新获取应该成功
            acquired2 = lock.acquire("r1", timeout=1.0)
            assert acquired2 is True
            lock.release()
    
    def test_different_locks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock1 = FileLock(lock_dir=tmpdir)
            lock2 = FileLock(lock_dir=tmpdir)
            
            a1 = lock1.acquire("lock_a", timeout=1.0)
            a2 = lock2.acquire("lock_b", timeout=1.0)
            
            assert a1 is True
            assert a2 is True
            
            lock1.release()
            lock2.release()


class TestDistributedLockManager:
    def test_file_lock_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DistributedLockManager(lock_dir=tmpdir)
            assert manager.get_type() == "file"
    
    def test_context_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DistributedLockManager(lock_dir=tmpdir)
            with manager.lock("resource"):
                pass
    
    def test_redis_unavailable_fallback(self):
        # 无 Redis 时应回退到文件锁
        manager = DistributedLockManager()
        assert manager.get_type() == "file"


class TestLockInfo:
    def test_create(self):
        info = LockInfo(
            name="test",
            holder="holder1",
            acquired_at=time.time(),
            ttl=30.0,
        )
        assert info.name == "test"
        assert info.ttl == 30.0


import fakeredis
from unittest.mock import patch, MagicMock

# Check if fakeredis supports eval command (Lua scripting)
_fakeredis_supports_eval = True
try:
    _fr = fakeredis.FakeRedis()
    _fr.eval("return 1", 0)
    _fr.close()
except Exception:
    _fakeredis_supports_eval = False


@pytest.mark.skipif(
    not _fakeredis_supports_eval,
    reason="fakeredis version does not support EVAL (Lua scripting)",
)
class TestRedisDistributedLock:
    """Redis distributed lock tests using fakeredis"""
    
    def setup_method(self):
        self.fake_redis = fakeredis.FakeRedis()
        from memory_system.infra.distributed_lock_manager import RedisDistributedLock
        self.lock = RedisDistributedLock(self.fake_redis, default_ttl=5.0)
    
    def test_acquire_success(self):
        acquired = self.lock.acquire("test_lock")
        assert acquired is True
    
    def test_acquire_already_locked(self):
        self.lock.acquire("test_lock")
        # Same holder can re-acquire? No, different holder
        from memory_system.infra.distributed_lock_manager import RedisDistributedLock
        lock2 = RedisDistributedLock(self.fake_redis, default_ttl=5.0)
        acquired = lock2.acquire("test_lock")
        assert acquired is False
    
    def test_release_success(self):
        self.lock.acquire("test_lock")
        released = self.lock.release("test_lock")
        assert released is True
    
    def test_release_not_owner(self):
        self.lock.acquire("test_lock")
        from memory_system.infra.distributed_lock_manager import RedisDistributedLock
        lock2 = RedisDistributedLock(self.fake_redis, default_ttl=5.0)
        released = lock2.release("test_lock")
        assert released is False
    
    def test_is_locked(self):
        assert self.lock.is_locked("test_lock") is False
        self.lock.acquire("test_lock")
        assert self.lock.is_locked("test_lock") is True
        self.lock.release("test_lock")
        assert self.lock.is_locked("test_lock") is False
    
    def test_extend_success(self):
        self.lock.acquire("test_lock")
        extended = self.lock.extend("test_lock", ttl=10.0)
        assert extended is True
    
    def test_extend_not_owner(self):
        self.lock.acquire("test_lock")
        from memory_system.infra.distributed_lock_manager import RedisDistributedLock
        lock2 = RedisDistributedLock(self.fake_redis, default_ttl=5.0)
        extended = lock2.extend("test_lock", ttl=10.0)
        assert extended is False
    
    def test_context_manager(self):
        with self.lock.lock("ctx_lock", timeout=1.0):
            assert self.lock.is_locked("ctx_lock") is True
        # After context exit, lock should be released
        assert self.lock.is_locked("ctx_lock") is False
    
    def test_context_manager_timeout(self):
        self.lock.acquire("busy_lock")
        from memory_system.infra.distributed_lock_manager import RedisDistributedLock
        lock2 = RedisDistributedLock(self.fake_redis, default_ttl=5.0)
        with pytest.raises(TimeoutError):
            with lock2.lock("busy_lock", timeout=0.1):
                pass
    
    def test_acquire_with_custom_ttl(self):
        acquired = self.lock.acquire("ttl_lock", ttl=1)
        assert acquired is True
        # Key should exist with TTL
        assert self.fake_redis.ttl("lock:ttl_lock") > 0
    
    def test_release_nonexistent(self):
        released = self.lock.release("nonexistent")
        assert released is False
    
    def test_extend_nonexistent(self):
        extended = self.lock.extend("nonexistent", ttl=10)
        assert extended is False


@pytest.mark.skipif(
    not _fakeredis_supports_eval,
    reason="fakeredis version does not support EVAL (Lua scripting)",
)
class TestDistributedLockManagerRedis:
    """Test DistributedLockManager with Redis"""
    
    def test_redis_mode(self):
        fake_redis = fakeredis.FakeRedis()
        from memory_system.infra.distributed_lock_manager import DistributedLockManager
        manager = DistributedLockManager(redis_client=fake_redis)
        assert manager.get_type() == "redis"
    
    def test_redis_context_manager(self):
        fake_redis = fakeredis.FakeRedis()
        from memory_system.infra.distributed_lock_manager import DistributedLockManager
        manager = DistributedLockManager(redis_client=fake_redis)
        with manager.lock("resource"):
            assert fake_redis.exists("lock:resource") == 1
        assert fake_redis.exists("lock:resource") == 0
