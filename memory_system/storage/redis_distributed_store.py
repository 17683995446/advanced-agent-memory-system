"""
Redis 向量存储后端 - 分布式缓存与向量存储

使用 Redis 提供:
1. 向量存储后端 (实现 VectorStoreBackend 接口)
2. 分布式缓存层
3. 高性能键值存储

依赖: redis>=5.0.0
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Optional

import numpy as np

try:
    import redis
    from redis.commands.search.field import VectorField, TextField, NumericField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    _redis_available = True
except ImportError:
    _redis_available = False
    redis = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Redis 向量存储后端
# ---------------------------------------------------------------------------

class RedisVectorStore:
    """
    Redis 向量存储后端
    
    实现 VectorStoreBackend 接口，支持:
    - 向量存储与检索
    - 元数据过滤
    - TTL 过期
    - 分布式部署
    
    Args:
        host: Redis 主机地址
        port: Redis 端口
        db: Redis 数据库编号
        password: Redis 密码
        prefix: 键前缀
        dimension: 向量维度
        ttl: 记录过期时间（秒），None 表示永不过期
    
    Example:
        store = RedisVectorStore(host="localhost", port=6379, dimension=768)
        store.add(record)
        results = store.search(query_embedding, top_k=5)
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "agent_memory:",
        dimension: int = 384,
        ttl: Optional[int] = None,
    ):
        if not _redis_available:
            raise ImportError(
                "redis is required for RedisVectorStore. "
                "Install it with: pip install redis"
            )
        
        self._prefix = prefix
        self._dimension = dimension
        self._ttl = ttl
        
        # 连接 Redis
        self._client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False  # 使用 bytes 以支持向量存储
        )
        
        # 测试连接
        try:
            self._client.ping()
            logger.info("RedisVectorStore connected to %s:%s", host, port)
        except redis.ConnectionError as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise
        
        # 记录计数器
        self._counter_key = f"{prefix}counter"
    
    def _make_key(self, id: str) -> str:
        """生成 Redis 键"""
        return f"{self._prefix}record:{id}"
    
    def _serialize_record(self, record: dict) -> bytes:
        """序列化记录为 JSON bytes"""
        # 将向量单独处理
        data = record.copy()
        if "embedding" in data and data["embedding"] is not None:
            data["embedding"] = list(data["embedding"])
        return json.dumps(data).encode("utf-8")
    
    def _deserialize_record(self, data: bytes) -> dict:
        """反序列化记录"""
        return json.loads(data.decode("utf-8"))
    
    # ------------------------------------------------------------------
    # VectorStoreBackend 接口实现
    # ------------------------------------------------------------------
    
    def add(self, record: dict) -> str:
        """
        添加记录
        
        Args:
            record: 记录字典，包含 id, content, embedding 等字段
            
        Returns:
            记录 ID
        """
        if "id" not in record or record["id"] is None:
            record["id"] = str(uuid.uuid4())
        
        record_id = record["id"]
        key = self._make_key(record_id)
        
        # 设置时间戳
        if "timestamp" not in record:
            record["timestamp"] = time.time()
        if "access_count" not in record:
            record["access_count"] = 0
        if "last_access" not in record:
            record["last_access"] = time.time()
        
        # 存储记录
        serialized = self._serialize_record(record)
        if self._ttl:
            self._client.setex(key, self._ttl, serialized)
        else:
            self._client.set(key, serialized)
        
        # 更新计数器
        self._client.incr(self._counter_key)
        
        logger.debug("Added record %s to Redis", record_id)
        return record_id
    
    def add_batch(self, records: list[dict]) -> list[str]:
        """批量添加记录"""
        ids = []
        pipe = self._client.pipeline()
        
        for record in records:
            if "id" not in record or record["id"] is None:
                record["id"] = str(uuid.uuid4())
            
            record_id = record["id"]
            key = self._make_key(record_id)
            
            if "timestamp" not in record:
                record["timestamp"] = time.time()
            if "access_count" not in record:
                record["access_count"] = 0
            if "last_access" not in record:
                record["last_access"] = time.time()
            
            serialized = self._serialize_record(record)
            
            if self._ttl:
                pipe.setex(key, self._ttl, serialized)
            else:
                pipe.set(key, serialized)
            
            ids.append(record_id)
        
        pipe.incrby(self._counter_key, len(records))
        pipe.execute()
        
        logger.debug("Added %d records to Redis", len(records))
        return ids
    
    def get(self, id: str) -> Optional[dict]:
        """根据 ID 获取记录"""
        key = self._make_key(id)
        data = self._client.get(key)
        
        if data is None:
            return None
        
        record = self._deserialize_record(data)
        
        # 更新访问计数
        record["access_count"] = record.get("access_count", 0) + 1
        record["last_access"] = time.time()
        self._client.set(key, self._serialize_record(record))
        
        return record
    
    def delete(self, id: str) -> bool:
        """删除记录"""
        key = self._make_key(id)
        result = self._client.delete(key)
        
        if result:
            self._client.decr(self._counter_key)
            logger.debug("Deleted record %s from Redis", id)
            return True
        return False
    
    def update(self, id: str, **kwargs) -> bool:
        """更新记录"""
        record = self.get(id)
        if record is None:
            return False
        
        # 更新字段
        for key, value in kwargs.items():
            record[key] = value
        
        record["last_access"] = time.time()
        
        key = self._make_key(id)
        serialized = self._serialize_record(record)
        
        if self._ttl:
            self._client.setex(key, self._ttl, serialized)
        else:
            self._client.set(key, serialized)
        
        return True
    
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter: Optional[dict] = None,
    ) -> list[tuple[dict, float]]:
        """
        向量相似度搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            filter: 过滤条件
            
        Returns:
            (record, score) 元组列表
        """
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm
        
        # 获取所有记录键
        pattern = f"{self._prefix}record:*"
        keys = list(self._client.scan_iter(match=pattern))
        
        candidates = []
        
        for key in keys:
            data = self._client.get(key)
            if data is None:
                continue
            
            record = self._deserialize_record(data)
            
            # 应用过滤条件
            if filter and not self._matches_filter(record, filter):
                continue
            
            # 计算相似度
            embedding = record.get("embedding")
            if embedding is None:
                continue
            
            vec = np.array(embedding, dtype=np.float32)
            vec_norm = np.linalg.norm(vec)
            if vec_norm > 0:
                vec = vec / vec_norm
            
            score = float(np.dot(query_vec, vec))
            candidates.append((record, score))
        
        # 按相似度排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[:top_k]
    
    def _matches_filter(self, record: dict, filter: dict) -> bool:
        """检查记录是否匹配过滤条件"""
        for key, value in filter.items():
            if key == "category":
                if record.get("category") != value:
                    return False
            elif key == "memory_type":
                if record.get("memory_type") != value:
                    return False
            elif key == "tags":
                record_tags = set(record.get("tags", []))
                if isinstance(value, list):
                    if not any(t in record_tags for t in value):
                        return False
                elif value not in record_tags:
                    return False
            elif key == "min_importance":
                if record.get("importance", 0) < value:
                    return False
            else:
                if record.get(key) != value:
                    return False
        return True
    
    def count(self) -> int:
        """统计记录数量"""
        count = self._client.get(self._counter_key)
        return int(count) if count else 0
    
    def clear(self):
        """清空所有记录"""
        pattern = f"{self._prefix}record:*"
        keys = list(self._client.scan_iter(match=pattern))
        if keys:
            self._client.delete(*keys)
        self._client.set(self._counter_key, 0)
        logger.info("Cleared all records from Redis")
    
    def close(self):
        """关闭连接"""
        self._client.close()


# ---------------------------------------------------------------------------
# Redis 缓存层
# ---------------------------------------------------------------------------

class RedisCache:
    """
    Redis 缓存层
    
    提供高性能缓存功能，支持 TTL 和 LRU 淘汰。
    
    Args:
        host: Redis 主机
        port: Redis 端口
        db: 数据库编号
        prefix: 键前缀
        default_ttl: 默认过期时间（秒）
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        prefix: str = "cache:",
        default_ttl: int = 3600,
    ):
        if not _redis_available:
            raise ImportError("redis is required for RedisCache")
        
        self._prefix = prefix
        self._default_ttl = default_ttl
        
        self._client = redis.Redis(
            host=host, port=port, db=db, decode_responses=True
        )
    
    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        full_key = self._make_key(key)
        value = self._client.get(full_key)
        if value is not None:
            return json.loads(value)
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        full_key = self._make_key(key)
        serialized = json.dumps(value)
        ttl = ttl or self._default_ttl
        self._client.setex(full_key, ttl, serialized)
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        full_key = self._make_key(key)
        return bool(self._client.delete(full_key))
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        full_key = self._make_key(key)
        return bool(self._client.exists(full_key))
    
    def clear(self):
        """清空缓存"""
        pattern = f"{self._prefix}*"
        keys = list(self._client.scan_iter(match=pattern))
        if keys:
            self._client.delete(*keys)


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

def create_redis_store(
    host: str = "localhost",
    port: int = 6379,
    dimension: int = 384,
    **kwargs
) -> RedisVectorStore:
    """创建 Redis 向量存储实例"""
    return RedisVectorStore(host=host, port=port, dimension=dimension, **kwargs)


def create_redis_cache(
    host: str = "localhost",
    port: int = 6379,
    **kwargs
) -> RedisCache:
    """创建 Redis 缓存实例"""
    return RedisCache(host=host, port=port, **kwargs)


__all__ = [
    "RedisVectorStore",
    "RedisCache",
    "create_redis_store",
    "create_redis_cache",
]
