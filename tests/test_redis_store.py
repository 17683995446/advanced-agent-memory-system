"""
Redis 向量存储与缓存测试 - 使用 fakeredis 模拟 Redis

覆盖:
- RedisVectorStore: add, add_batch, get, delete, update, search, count, clear, _matches_filter
- RedisCache: get, set, delete, exists, clear
- create_redis_store, create_redis_cache 工厂函数
- 边界情况：空数据、不存在的 key、TTL
"""

from __future__ import annotations

import json
import sys
import time
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# 修复 redis_store 模块：确保 redis 可用
#
# redis_store.py 在导入时尝试 from redis.commands.search.indexDefinition import ...，
# 如果失败则将 redis 设为 None。我们需要在导入 redis_store 之前确保
# redis 模块能正常加载。
# ---------------------------------------------------------------------------
import importlib
import redis as _real_redis

# 确保 redis.commands.search.indexDefinition 可导入
# 如果不存在，创建一个假的模块来避免 ImportError
if not hasattr(sys.modules, "redis.commands.search.indexDefinition"):
    mod = type(sys)("redis.commands.search.indexDefinition")
    mod.IndexDefinition = MagicMock
    mod.IndexType = MagicMock
    sys.modules["redis.commands.search.indexDefinition"] = mod

if not hasattr(sys.modules, "redis.commands.search.field"):
    mod2 = type(sys)("redis.commands.search.field")
    mod2.VectorField = MagicMock
    mod2.TextField = MagicMock
    mod2.NumericField = MagicMock
    sys.modules["redis.commands.search.field"] = mod2

# 现在重新加载 redis_store 模块
import memory_system.storage.redis_distributed_store as _rs_mod
importlib.reload(_rs_mod)

from memory_system.storage.redis_distributed_store import (
    RedisVectorStore,
    RedisCache,
    create_redis_store,
    create_redis_cache,
)

import fakeredis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_fake_redis(decode_responses=False):
    """创建一个 fakeredis 实例。"""
    return fakeredis.FakeRedis(decode_responses=decode_responses)


@pytest.fixture()
def fake_redis_server():
    """每个测试一个独立的 fakeredis 实例（不跨测试共享）。"""
    return _make_fake_redis(decode_responses=False)


@pytest.fixture()
def fake_redis_str():
    """decode_responses=True 的 fakeredis 实例，用于 RedisCache。"""
    return _make_fake_redis(decode_responses=True)


@pytest.fixture()
def vector_store(fake_redis_server):
    """
    创建 RedisVectorStore，用 mock 替换 redis.Redis 返回 fakeredis 实例。
    """
    with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_server):
        store = RedisVectorStore(
            host="localhost",
            port=6379,
            db=0,
            prefix="test_mem:",
            dimension=4,
            ttl=None,
        )
    yield store
    store.close()


@pytest.fixture()
def vector_store_with_ttl(fake_redis_server):
    """带 TTL 的 RedisVectorStore。"""
    with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_server):
        store = RedisVectorStore(
            host="localhost",
            port=6379,
            db=0,
            prefix="test_ttl:",
            dimension=4,
            ttl=2,
        )
    yield store
    store.close()


@pytest.fixture()
def redis_cache(fake_redis_str):
    """创建 RedisCache，用 mock 替换 redis.Redis。"""
    with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_str):
        cache = RedisCache(
            host="localhost",
            port=6379,
            db=0,
            prefix="test_cache:",
            default_ttl=60,
        )
    yield cache


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

_UNSET = object()

def _make_record(content="hello", embedding=_UNSET, **kwargs):
    """构造一个测试记录。"""
    if embedding is _UNSET:
        embedding = [0.1, 0.2, 0.3, 0.4]
    record = {
        "content": content,
        "embedding": embedding,
    }
    record.update(kwargs)
    return record


# ===========================================================================
# RedisVectorStore 测试
# ===========================================================================

class TestRedisVectorStoreAdd:
    """测试 add 方法。"""

    def test_add_generates_id(self, vector_store):
        record = _make_record()
        record_id = vector_store.add(record)
        assert record_id is not None
        assert isinstance(record_id, str)

    def test_add_preserves_given_id(self, vector_store):
        record = _make_record(id="my-id")
        record_id = vector_store.add(record)
        assert record_id == "my-id"

    def test_add_sets_timestamp_and_access_count(self, vector_store):
        record = _make_record()
        vector_store.add(record)
        result = vector_store.get(record["id"])
        assert "timestamp" in result
        assert "access_count" in result
        assert result["access_count"] >= 1  # get 会递增

    def test_add_increments_counter(self, vector_store):
        assert vector_store.count() == 0
        vector_store.add(_make_record())
        assert vector_store.count() == 1
        vector_store.add(_make_record())
        assert vector_store.count() == 2

    def test_add_with_ttl(self, vector_store_with_ttl):
        record = _make_record(id="ttl-record")
        vector_store_with_ttl.add(record)
        result = vector_store_with_ttl.get(record["id"])
        assert result is not None
        assert result["content"] == "hello"


class TestRedisVectorStoreAddBatch:
    """测试 add_batch 方法。"""

    def test_add_batch(self, vector_store):
        records = [_make_record(content=f"item-{i}") for i in range(5)]
        ids = vector_store.add_batch(records)
        assert len(ids) == 5
        assert vector_store.count() == 5

    def test_add_batch_generates_ids(self, vector_store):
        records = [_make_record() for _ in range(3)]
        ids = vector_store.add_batch(records)
        for rid in ids:
            assert rid is not None

    def test_add_batch_preserves_ids(self, vector_store):
        records = [_make_record(id=f"batch-{i}") for i in range(3)]
        ids = vector_store.add_batch(records)
        assert ids == ["batch-0", "batch-1", "batch-2"]

    def test_add_batch_empty(self, vector_store):
        ids = vector_store.add_batch([])
        assert ids == []
        assert vector_store.count() == 0


class TestRedisVectorStoreGet:
    """测试 get 方法。"""

    def test_get_existing(self, vector_store):
        record = _make_record(content="hello world")
        rid = vector_store.add(record)
        result = vector_store.get(rid)
        assert result is not None
        assert result["content"] == "hello world"
        assert result["id"] == rid

    def test_get_nonexistent(self, vector_store):
        result = vector_store.get("nonexistent-id")
        assert result is None

    def test_get_increments_access_count(self, vector_store):
        record = _make_record()
        rid = vector_store.add(record)
        vector_store.get(rid)
        vector_store.get(rid)
        result = vector_store.get(rid)
        # add 时 access_count=0，每次 get +1，所以第 3 次 get 后应为 3
        assert result["access_count"] == 3

    def test_get_updates_last_access(self, vector_store):
        record = _make_record()
        rid = vector_store.add(record)
        first = vector_store.get(rid)
        time.sleep(0.01)
        second = vector_store.get(rid)
        assert second["last_access"] >= first["last_access"]


class TestRedisVectorStoreDelete:
    """测试 delete 方法。"""

    def test_delete_existing(self, vector_store):
        record = _make_record()
        rid = vector_store.add(record)
        assert vector_store.count() == 1
        result = vector_store.delete(rid)
        assert result is True
        assert vector_store.count() == 0
        assert vector_store.get(rid) is None

    def test_delete_nonexistent(self, vector_store):
        result = vector_store.delete("nonexistent-id")
        assert result is False

    def test_delete_decrements_counter(self, vector_store):
        vector_store.add(_make_record())
        vector_store.add(_make_record())
        assert vector_store.count() == 2
        rid = vector_store.add(_make_record())
        assert vector_store.count() == 3
        vector_store.delete(rid)
        assert vector_store.count() == 2


class TestRedisVectorStoreUpdate:
    """测试 update 方法。"""

    def test_update_existing(self, vector_store):
        record = _make_record(content="original")
        rid = vector_store.add(record)
        result = vector_store.update(rid, content="updated")
        assert result is True
        fetched = vector_store.get(rid)
        assert fetched["content"] == "updated"

    def test_update_nonexistent(self, vector_store):
        result = vector_store.update("nonexistent-id", content="new")
        assert result is False

    def test_update_preserves_other_fields(self, vector_store):
        record = _make_record(content="hello", category="test")
        rid = vector_store.add(record)
        vector_store.update(rid, content="world")
        fetched = vector_store.get(rid)
        assert fetched["category"] == "test"
        assert fetched["content"] == "world"

    def test_update_adds_new_field(self, vector_store):
        record = _make_record()
        rid = vector_store.add(record)
        vector_store.update(rid, extra_field=42)
        fetched = vector_store.get(rid)
        assert fetched["extra_field"] == 42


class TestRedisVectorStoreSearch:
    """测试 search 方法。"""

    def _add_search_records(self, store):
        """添加用于搜索测试的记录。"""
        records = [
            _make_record(id="s1", content="cat", embedding=[1.0, 0.0, 0.0, 0.0], category="animal"),
            _make_record(id="s2", content="dog", embedding=[0.0, 1.0, 0.0, 0.0], category="animal"),
            _make_record(id="s3", content="car", embedding=[0.0, 0.0, 1.0, 0.0], category="vehicle"),
        ]
        store.add_batch(records)

    def test_search_returns_sorted_by_similarity(self, vector_store):
        self._add_search_records(vector_store)
        # 查询向量接近 s1
        results = vector_store.search([0.9, 0.1, 0.0, 0.0], top_k=3)
        assert len(results) <= 3
        assert len(results) > 0
        # 第一个结果应该是 s1（最相似）
        assert results[0][0]["id"] == "s1"
        # 分数递减
        scores = [r[1] for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_search_with_top_k(self, vector_store):
        self._add_search_records(vector_store)
        results = vector_store.search([0.5, 0.5, 0.0, 0.0], top_k=2)
        assert len(results) <= 2

    def test_search_with_filter_category(self, vector_store):
        self._add_search_records(vector_store)
        results = vector_store.search(
            [0.5, 0.5, 0.0, 0.0], top_k=10, filter={"category": "animal"}
        )
        for record, _ in results:
            assert record["category"] == "animal"

    def test_search_with_filter_memory_type(self, vector_store):
        vector_store.add(_make_record(id="mt1", content="episodic", embedding=[1, 0, 0, 0], memory_type="episodic"))
        vector_store.add(_make_record(id="mt2", content="semantic", embedding=[0, 1, 0, 0], memory_type="semantic"))
        results = vector_store.search(
            [1, 0, 0, 0], top_k=10, filter={"memory_type": "semantic"}
        )
        for record, _ in results:
            assert record["memory_type"] == "semantic"

    def test_search_with_filter_tags(self, vector_store):
        vector_store.add(_make_record(id="t1", content="tagged", embedding=[1, 0, 0, 0], tags=["python", "redis"]))
        vector_store.add(_make_record(id="t2", content="other", embedding=[0, 1, 0, 0], tags=["java"]))
        results = vector_store.search(
            [0.5, 0.5, 0, 0], top_k=10, filter={"tags": "python"}
        )
        ids = [r[0]["id"] for r in results]
        assert "t1" in ids
        assert "t2" not in ids

    def test_search_with_filter_tags_list(self, vector_store):
        vector_store.add(_make_record(id="t1", content="a", embedding=[1, 0, 0, 0], tags=["python", "redis"]))
        vector_store.add(_make_record(id="t2", content="b", embedding=[0, 1, 0, 0], tags=["java", "go"]))
        # 匹配任一 tag
        results = vector_store.search(
            [0.5, 0.5, 0, 0], top_k=10, filter={"tags": ["go", "redis"]}
        )
        ids = [r[0]["id"] for r in results]
        assert "t1" in ids
        assert "t2" in ids

    def test_search_with_filter_min_importance(self, vector_store):
        vector_store.add(_make_record(id="i1", content="low", embedding=[1, 0, 0, 0], importance=2))
        vector_store.add(_make_record(id="i2", content="high", embedding=[0, 1, 0, 0], importance=8))
        results = vector_store.search(
            [0.5, 0.5, 0, 0], top_k=10, filter={"min_importance": 5}
        )
        for record, _ in results:
            assert record.get("importance", 0) >= 5

    def test_search_no_results(self, vector_store):
        results = vector_store.search([1, 0, 0, 0], top_k=5)
        assert results == []

    def test_search_no_embedding_in_record(self, vector_store):
        """没有 embedding 字段的记录应被跳过。"""
        record = {"id": "no-emb", "content": "no embedding"}
        vector_store.add(record)
        results = vector_store.search([1, 0, 0, 0], top_k=5)
        assert results == []


class TestRedisVectorStoreCount:
    """测试 count 方法。"""

    def test_count_empty(self, vector_store):
        assert vector_store.count() == 0

    def test_count_after_add(self, vector_store):
        vector_store.add(_make_record())
        assert vector_store.count() == 1

    def test_count_after_add_batch(self, vector_store):
        vector_store.add_batch([_make_record() for _ in range(5)])
        assert vector_store.count() == 5

    def test_count_after_delete(self, vector_store):
        rid = vector_store.add(_make_record())
        assert vector_store.count() == 1
        vector_store.delete(rid)
        assert vector_store.count() == 0


class TestRedisVectorStoreClear:
    """测试 clear 方法。"""

    def test_clear(self, vector_store):
        vector_store.add_batch([_make_record(content=f"item-{i}") for i in range(5)])
        assert vector_store.count() == 5
        vector_store.clear()
        assert vector_store.count() == 0
        # 确认记录确实被删除
        assert vector_store.get("item-0") is None

    def test_clear_empty(self, vector_store):
        vector_store.clear()  # 不应报错
        assert vector_store.count() == 0


class TestRedisVectorStoreMatchesFilter:
    """测试 _matches_filter 方法。"""

    def test_matches_no_filter(self, vector_store):
        record = _make_record()
        assert vector_store._matches_filter(record, {}) is True

    def test_matches_category(self, vector_store):
        record = _make_record(category="animal")
        assert vector_store._matches_filter(record, {"category": "animal"}) is True
        assert vector_store._matches_filter(record, {"category": "vehicle"}) is False

    def test_matches_memory_type(self, vector_store):
        record = _make_record(memory_type="episodic")
        assert vector_store._matches_filter(record, {"memory_type": "episodic"}) is True
        assert vector_store._matches_filter(record, {"memory_type": "semantic"}) is False

    def test_matches_tags_single(self, vector_store):
        record = _make_record(tags=["python", "redis"])
        assert vector_store._matches_filter(record, {"tags": "python"}) is True
        assert vector_store._matches_filter(record, {"tags": "java"}) is False

    def test_matches_tags_list(self, vector_store):
        record = _make_record(tags=["python", "redis"])
        assert vector_store._matches_filter(record, {"tags": ["java", "redis"]}) is True
        assert vector_store._matches_filter(record, {"tags": ["java", "go"]}) is False

    def test_matches_min_importance(self, vector_store):
        record = _make_record(importance=7)
        assert vector_store._matches_filter(record, {"min_importance": 5}) is True
        assert vector_store._matches_filter(record, {"min_importance": 10}) is False

    def test_matches_default_field(self, vector_store):
        record = _make_record(custom_field="value")
        assert vector_store._matches_filter(record, {"custom_field": "value"}) is True
        assert vector_store._matches_filter(record, {"custom_field": "other"}) is False

    def test_matches_missing_field(self, vector_store):
        record = _make_record()
        assert vector_store._matches_filter(record, {"nonexistent": "value"}) is False


class TestRedisVectorStoreTTL:
    """测试 TTL 相关行为。"""

    def test_ttl_record_stored(self, vector_store_with_ttl):
        record = _make_record(id="ttl-test")
        vector_store_with_ttl.add(record)
        result = vector_store_with_ttl.get(record["id"])
        assert result is not None

    def test_ttl_expiration(self, vector_store_with_ttl):
        """TTL=2 秒，等待过期后应返回 None。

        注意：get() 内部会重新 set 记录（不带 TTL），所以不能先 get 再等过期。
        正确做法是添加后直接等过期，然后通过底层 client 验证。
        """
        record = _make_record(id="expire-test")
        vector_store_with_ttl.add(record)
        # 直接通过底层 client 验证 key 存在
        key = vector_store_with_ttl._make_key(record["id"])
        assert vector_store_with_ttl._client.get(key) is not None
        # 等待 TTL 过期
        time.sleep(2.5)
        # key 应该已过期
        assert vector_store_with_ttl._client.get(key) is None
        # count 也应不受影响（counter 不带 TTL）


class TestRedisVectorStoreEdgeCases:
    """边界情况测试。"""

    def test_add_none_id(self, vector_store):
        """id 为 None 时应自动生成。"""
        record = _make_record(id=None)
        rid = vector_store.add(record)
        assert rid is not None
        assert rid != "None"

    def test_add_empty_embedding(self, vector_store):
        """embedding 为空列表时仍可存储。"""
        record = _make_record(embedding=[])
        rid = vector_store.add(record)
        result = vector_store.get(rid)
        assert result["embedding"] == []

    def test_add_none_embedding(self, vector_store):
        """embedding 为 None 时仍可存储。"""
        record = _make_record(embedding=None)
        rid = vector_store.add(record)
        result = vector_store.get(rid)
        assert result["embedding"] is None

    def test_update_with_embedding(self, vector_store):
        """更新 embedding 字段。"""
        record = _make_record(embedding=[1, 0, 0, 0])
        rid = vector_store.add(record)
        vector_store.update(rid, embedding=[0, 1, 0, 0])
        result = vector_store.get(rid)
        assert result["embedding"] == [0, 1, 0, 0]

    def test_close_idempotent(self, vector_store):
        """多次 close 不应报错。"""
        vector_store.close()
        vector_store.close()


# ===========================================================================
# RedisCache 测试
# ===========================================================================

class TestRedisCacheGetSet:
    """测试 RedisCache 的 get/set 方法。"""

    def test_set_and_get(self, redis_cache):
        redis_cache.set("key1", "value1")
        assert redis_cache.get("key1") == "value1"

    def test_set_dict(self, redis_cache):
        data = {"name": "test", "value": 42}
        redis_cache.set("dict-key", data)
        assert redis_cache.get("dict-key") == data

    def test_set_list(self, redis_cache):
        data = [1, 2, 3]
        redis_cache.set("list-key", data)
        assert redis_cache.get("list-key") == data

    def test_get_nonexistent(self, redis_cache):
        assert redis_cache.get("nonexistent") is None

    def test_set_overwrite(self, redis_cache):
        redis_cache.set("key", "old")
        redis_cache.set("key", "new")
        assert redis_cache.get("key") == "new"

    def test_set_with_custom_ttl(self, redis_cache):
        redis_cache.set("ttl-key", "value", ttl=1)
        assert redis_cache.get("ttl-key") == "value"
        time.sleep(1.5)
        assert redis_cache.get("ttl-key") is None

    def test_set_uses_default_ttl(self, redis_cache):
        """默认 TTL 为 60 秒，设置后立即可用。"""
        redis_cache.set("default-ttl-key", "value")
        assert redis_cache.get("default-ttl-key") == "value"


class TestRedisCacheDelete:
    """测试 RedisCache 的 delete 方法。"""

    def test_delete_existing(self, redis_cache):
        redis_cache.set("del-key", "value")
        assert redis_cache.delete("del-key") is True
        assert redis_cache.get("del-key") is None

    def test_delete_nonexistent(self, redis_cache):
        assert redis_cache.delete("nonexistent") is False


class TestRedisCacheExists:
    """测试 RedisCache 的 exists 方法。"""

    def test_exists_true(self, redis_cache):
        redis_cache.set("exist-key", "value")
        assert redis_cache.exists("exist-key") is True

    def test_exists_false(self, redis_cache):
        assert redis_cache.exists("no-key") is False

    def test_exists_after_delete(self, redis_cache):
        redis_cache.set("tmp-key", "value")
        redis_cache.delete("tmp-key")
        assert redis_cache.exists("tmp-key") is False

    def test_exists_after_ttl_expires(self, redis_cache):
        redis_cache.set("expire-key", "value", ttl=1)
        assert redis_cache.exists("expire-key") is True
        time.sleep(1.5)
        assert redis_cache.exists("expire-key") is False


class TestRedisCacheClear:
    """测试 RedisCache 的 clear 方法。"""

    def test_clear(self, redis_cache):
        redis_cache.set("k1", "v1")
        redis_cache.set("k2", "v2")
        redis_cache.set("k3", "v3")
        redis_cache.clear()
        assert redis_cache.get("k1") is None
        assert redis_cache.get("k2") is None
        assert redis_cache.get("k3") is None

    def test_clear_empty(self, redis_cache):
        redis_cache.clear()  # 不应报错


class TestRedisCacheEdgeCases:
    """RedisCache 边界情况。"""

    def test_set_none_value(self, redis_cache):
        redis_cache.set("none-key", None)
        assert redis_cache.get("none-key") is None
        # 区分 "key 不存在" 和 "value 是 None"
        assert redis_cache.exists("none-key") is True

    def test_set_empty_string(self, redis_cache):
        redis_cache.set("empty-key", "")
        assert redis_cache.get("empty-key") == ""

    def test_set_nested_structure(self, redis_cache):
        data = {"a": [{"b": 1}, {"c": 2}], "d": None}
        redis_cache.set("nested", data)
        assert redis_cache.get("nested") == data

    def test_set_numeric_values(self, redis_cache):
        redis_cache.set("int-key", 42)
        redis_cache.set("float-key", 3.14)
        assert redis_cache.get("int-key") == 42
        assert redis_cache.get("float-key") == 3.14


# ===========================================================================
# 工厂函数测试
# ===========================================================================

class TestCreateRedisStore:
    """测试 create_redis_store 工厂函数。"""

    def test_create_store(self, fake_redis_server):
        with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_server):
            store = create_redis_store(host="localhost", port=6379, dimension=8)
        assert isinstance(store, RedisVectorStore)
        assert store._dimension == 8
        store.close()

    def test_create_store_with_kwargs(self, fake_redis_server):
        with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_server):
            store = create_redis_store(
                host="localhost",
                port=6379,
                dimension=4,
                prefix="factory:",
                ttl=300,
            )
        assert store._prefix == "factory:"
        assert store._ttl == 300
        store.close()


class TestCreateRedisCache:
    """测试 create_redis_cache 工厂函数。"""

    def test_create_cache(self, fake_redis_str):
        with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_str):
            cache = create_redis_cache(host="localhost", port=6379)
        assert isinstance(cache, RedisCache)

    def test_create_cache_with_kwargs(self, fake_redis_str):
        with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_str):
            cache = create_redis_cache(
                host="localhost",
                port=6379,
                prefix="factory_cache:",
                default_ttl=120,
            )
        assert cache._prefix == "factory_cache:"
        assert cache._default_ttl == 120


# ===========================================================================
# 序列化/反序列化测试
# ===========================================================================

class TestSerialization:
    """测试记录序列化与反序列化。"""

    def test_serialize_deserialize_roundtrip(self, vector_store):
        record = _make_record(
            content="test",
            embedding=[0.1, 0.2, 0.3, 0.4],
            category="test",
            tags=["a", "b"],
            importance=5,
        )
        serialized = vector_store._serialize_record(record)
        assert isinstance(serialized, bytes)
        deserialized = vector_store._deserialize_record(serialized)
        assert deserialized["content"] == "test"
        assert deserialized["embedding"] == [0.1, 0.2, 0.3, 0.4]
        assert deserialized["category"] == "test"
        assert deserialized["tags"] == ["a", "b"]
        assert deserialized["importance"] == 5

    def test_serialize_numpy_embedding(self, vector_store):
        """embedding 为 numpy 数组时应被转为 list。"""
        record = _make_record(embedding=np.array([1.0, 2.0, 3.0, 4.0]))
        serialized = vector_store._serialize_record(record)
        deserialized = vector_store._deserialize_record(serialized)
        assert isinstance(deserialized["embedding"], list)
        assert deserialized["embedding"] == [1.0, 2.0, 3.0, 4.0]


# ===========================================================================
# 键前缀测试
# ===========================================================================

class TestKeyPrefix:
    """测试键前缀功能。"""

    def test_make_key(self, vector_store):
        assert vector_store._make_key("abc") == "test_mem:record:abc"

    def test_different_prefixes_isolated(self, fake_redis_server):
        """不同前缀的 store 互不干扰。"""
        with patch.object(_rs_mod.redis, "Redis", return_value=fake_redis_server):
            store_a = RedisVectorStore(prefix="a:", dimension=4)
            store_b = RedisVectorStore(prefix="b:", dimension=4)

        store_a.add(_make_record(id="shared-id", content="from-a"))
        store_b.add(_make_record(id="shared-id", content="from-b"))

        assert store_a.get("shared-id")["content"] == "from-a"
        assert store_b.get("shared-id")["content"] == "from-b"

        store_a.close()
        store_b.close()
