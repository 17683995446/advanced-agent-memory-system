"""
分布式锁模块 - Redis 锁与文件锁

支持:
- Redis 分布式锁 (跨进程/跨机器)
- 文件锁 (单机多进程)
- 上下文管理器接口
- 自动过期

依赖: redis (可选)
"""

from __future__ import annotations

import fcntl
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis
    _redis_available = True
except ImportError:
    _redis_available = False
    redis = None


@dataclass
class LockInfo:
    """锁信息"""
    name: str
    holder: str
    acquired_at: float
    ttl: float


class FileLock:
    """
    文件锁 (单机多进程)
    
    使用 fcntl.flock 实现进程间互斥。
    
    Args:
        lock_dir: 锁文件目录
        timeout: 获取锁超时时间（秒）
    
    Example:
        lock = FileLock("/tmp/locks")
        
        with lock.acquire("my_resource"):
            # 临界区
            pass
    """
    
    def __init__(self, lock_dir: str = "/tmp", timeout: float = 10.0):
        self._lock_dir = lock_dir
        self._timeout = timeout
        self._fd: Optional[int] = None
        self._lock_path: Optional[str] = None
    
    def _get_lock_path(self, name: str) -> str:
        return os.path.join(self._lock_dir, f".lock_{name}")
    
    def acquire(self, name: str, timeout: Optional[float] = None) -> bool:
        """
        获取锁
        
        Args:
            name: 锁名称
            timeout: 超时时间
            
        Returns:
            是否成功获取
        """
        timeout = timeout or self._timeout
        self._lock_path = self._get_lock_path(name)
        
        start = time.monotonic()
        while True:
            try:
                self._fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR)
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, OSError):
                if self._fd is not None:
                    os.close(self._fd)
                    self._fd = None
                if time.monotonic() - start >= timeout:
                    return False
                time.sleep(0.1)
    
    def release(self):
        """释放锁"""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except (OSError, RuntimeError):
                pass
            finally:
                self._fd = None

            # 清理锁文件
            if self._lock_path and os.path.exists(self._lock_path):
                try:
                    os.unlink(self._lock_path)
                except (OSError, RuntimeError):
                    pass
    
    @contextmanager
    def lock(self, name: str, timeout: Optional[float] = None):
        """上下文管理器"""
        acquired = self.acquire(name, timeout)
        if not acquired:
            raise TimeoutError(f"Failed to acquire lock: {name}")
        try:
            yield
        finally:
            self.release()


class RedisDistributedLock:
    """
    Redis 分布式锁
    
    使用 SET NX EX 实现跨进程/跨机器互斥。
    
    Args:
        client: Redis 客户端
        key_prefix: 锁键前缀
        default_ttl: 默认过期时间（秒）
    
    Example:
        lock = RedisDistributedLock(redis_client)
        
        with lock.lock("my_resource"):
            # 临界区
            pass
    """
    
    def __init__(
        self,
        client: Any,
        key_prefix: str = "lock:",
        default_ttl: float = 30.0,
    ):
        self._client = client
        self._prefix = key_prefix
        self._default_ttl = default_ttl
        self._holder = str(uuid.uuid4())
    
    def _make_key(self, name: str) -> str:
        return f"{self._prefix}{name}"
    
    def acquire(self, name: str, ttl: Optional[float] = None) -> bool:
        """
        获取锁
        
        Args:
            name: 锁名称
            ttl: 过期时间
            
        Returns:
            是否成功获取
        """
        key = self._make_key(name)
        ttl = int(ttl or self._default_ttl)
        
        # SET key value NX EX ttl
        result = self._client.set(key, self._holder, nx=True, ex=ttl)
        return result is not None or result is True
    
    def release(self, name: str) -> bool:
        """
        释放锁
        
        使用 Lua 脚本确保只有持有者能释放。
        回退到 GET + DEL 非原子操作（当 eval 不可用时）。
        """
        key = self._make_key(name)
        
        # Lua 脚本: 只有值匹配时才删除
        lua = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            result = self._client.eval(lua, 1, key, self._holder)
            return bool(result)
        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError):
            # 回退: 非原子 GET + DEL
            try:
                value = self._client.get(key)
                if value is None:
                    return False
                actual = value.decode() if isinstance(value, bytes) else value
                if actual == self._holder:
                    return bool(self._client.delete(key))
                return False
            except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError):
                return False
    
    def extend(self, name: str, ttl: float) -> bool:
        """
        延长锁的过期时间
        """
        key = self._make_key(name)
        
        # 只有持有者能延长
        lua = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("EXPIRE", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        try:
            result = self._client.eval(lua, 1, key, self._holder, int(ttl))
            return bool(result)
        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError):
            # 回退: 非原子 GET + EXPIRE
            try:
                value = self._client.get(key)
                if value is None:
                    return False
                actual = value.decode() if isinstance(value, bytes) else value
                if actual == self._holder:
                    return bool(self._client.expire(key, int(ttl)))
                return False
            except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError):
                return False
    
    def is_locked(self, name: str) -> bool:
        """检查锁是否被持有"""
        key = self._make_key(name)
        return bool(self._client.exists(key))
    
    @contextmanager
    def lock(self, name: str, ttl: Optional[float] = None, timeout: float = 10.0):
        """上下文管理器"""
        start = time.monotonic()
        while not self.acquire(name, ttl):
            if time.monotonic() - start >= timeout:
                raise TimeoutError(f"Failed to acquire lock: {name}")
            time.sleep(0.1)
        
        try:
            yield
        finally:
            self.release(name)


class DistributedLockManager:
    """
    分布式锁管理器
    
    统一接口，自动选择 Redis 或文件锁。
    
    Example:
        # 使用 Redis
        manager = DistributedLockManager(redis_client=client)
        
        # 使用文件锁
        manager = DistributedLockManager(lock_dir="/tmp/locks")
        
        with manager.lock("resource"):
            pass
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        lock_dir: str = "/tmp",
        default_ttl: float = 30.0,
    ):
        if redis_client is not None and _redis_available:
            self._lock = RedisDistributedLock(redis_client, default_ttl=default_ttl)
            self._type = "redis"
        else:
            self._lock = FileLock(lock_dir=lock_dir)
            self._type = "file"
        
        logger.info("DistributedLockManager initialized with %s lock", self._type)
    
    @contextmanager
    def lock(self, name: str, ttl: Optional[float] = None, timeout: float = 10.0):
        """获取锁的上下文管理器"""
        if self._type == "redis":
            with self._lock.lock(name, ttl=ttl, timeout=timeout):
                yield
        else:
            with self._lock.lock(name, timeout=timeout):
                yield
    
    def get_type(self) -> str:
        """获取锁类型"""
        return self._type


__all__ = [
    "FileLock",
    "RedisDistributedLock",
    "DistributedLockManager",
    "LockInfo",
]
