"""Unit tests for the config_manager module."""
import pytest
import sys
import os
import json
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.infra.dynamic_config_manager import (
    DictConfigSource,
    JsonFileConfigSource,
    YamlFileConfigSource,
    EnvConfigSource,
    ConfigChangeEvent,
    ConfigManager,
    create_config_manager,
)
from pydantic import BaseModel


class TestDictConfigSource:
    def test_load(self):
        source = DictConfigSource({"key": "value", "nested": {"a": 1}})
        data = source.load()
        assert data == {"key": "value", "nested": {"a": 1}}

    def test_priority(self):
        source = DictConfigSource({}, priority=99)
        assert source.priority == 99

    def test_deep_copy(self):
        original = {"list": [1, 2, 3]}
        source = DictConfigSource(original)
        data = source.load()
        data["list"].append(4)
        assert original["list"] == [1, 2, 3]


class TestJsonFileConfigSource:
    def test_load_valid_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"debug": True, "port": 8080}))

        source = JsonFileConfigSource(config_file)
        data = source.load()
        assert data["debug"] is True
        assert data["port"] == 8080

    def test_load_missing_file(self, tmp_path):
        source = JsonFileConfigSource(tmp_path / "nonexistent.json")
        data = source.load()
        assert data == {}

    def test_priority(self):
        source = JsonFileConfigSource("dummy.json", priority=20)
        assert source.priority == 20


class TestYamlFileConfigSource:
    def test_load_missing_yaml(self):
        if not hasattr(sys.modules.get('yaml', None), 'safe_load'):
            pytest.skip("PyYAML not available")
        source = YamlFileConfigSource("/nonexistent.yaml")
        data = source.load()
        assert data == {}


class TestEnvConfigSource:
    def test_load_simple(self, monkeypatch):
        monkeypatch.setenv("MEMORY_DEBUG", "true")
        monkeypatch.setenv("MEMORY_PORT", "8080")

        source = EnvConfigSource("MEMORY_")
        data = source.load()
        assert data["debug"] is True
        assert data["port"] == 8080

    def test_load_nested(self, monkeypatch):
        monkeypatch.setenv("MEMORY_DB__HOST", "localhost")
        monkeypatch.setenv("MEMORY_DB__PORT", "5432")
        
        source = EnvConfigSource("MEMORY_")
        data = source.load()
        assert data["db"]["host"] == "localhost"
        assert data["db"]["port"] == 5432

    def test_load_non_matching_prefix(self, monkeypatch):
        monkeypatch.setenv("OTHER_KEY", "value")

        source = EnvConfigSource("MEMORY_")
        data = source.load()
        assert data == {}

    def test_convert_value_types(self, monkeypatch):
        monkeypatch.setenv("MEMORY_ENABLED", "true")
        monkeypatch.setenv("MEMORY_DISABLED", "false")
        monkeypatch.setenv("MEMORY_COUNT", "42")
        monkeypatch.setenv("MEMORY_RATE", "3.14")
        monkeypatch.setenv("MEMORY_NAME", "test")

        source = EnvConfigSource("MEMORY_")
        data = source.load()
        assert data["enabled"] is True
        assert data["disabled"] is False
        assert data["count"] == 42
        assert data["rate"] == 3.14
        assert data["name"] == "test"


class TestConfigChangeEvent:
    def test_create(self):
        event = ConfigChangeEvent(
            key="debug",
            old_value=False,
            new_value=True,
            source="runtime",
        )
        assert event.key == "debug"
        assert event.old_value is False
        assert event.new_value is True
        assert event.source == "runtime"
        assert event.timestamp > 0


class TestConfigManager:
    def test_empty_manager(self):
        manager = ConfigManager()
        manager.load()
        assert manager.as_dict() == {}

    def test_add_dict_source(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "value"}))
        manager.load()
        assert manager.get("key") == "value"

    def test_priority_override(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "low"}, priority=10))
        manager.add_source(DictConfigSource({"key": "high"}, priority=20))
        manager.load()
        assert manager.get("key") == "high"

    def test_deep_merge(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({
            "db": {"host": "localhost", "port": 5432},
            "debug": False,
        }, priority=10))
        manager.add_source(DictConfigSource({
            "db": {"host": "remotehost"},
        }, priority=20))
        manager.load()
        assert manager.get("db.host") == "remotehost"
        assert manager.get("db.port") == 5432
        assert manager.get("debug") is False

    def test_get_with_default(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"a": 1}))
        manager.load()
        assert manager.get("nonexistent", default="default") == "default"

    def test_get_nested(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"a": {"b": {"c": "deep"}}}))
        manager.load()
        assert manager.get("a.b.c") == "deep"
        assert manager.get("a.b.d", default="missing") == "missing"

    def test_set_runtime(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "original"}))
        manager.load()
        manager.set("key", "modified")
        assert manager.get("key") == "modified"

    def test_set_nested_runtime(self):
        manager = ConfigManager()
        manager.load()
        manager.set("a.b.c", "value")
        assert manager.get("a.b.c") == "value"

    def test_has(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"exists": True}))
        manager.load()
        assert manager.has("exists") is True
        assert manager.has("nonexistent") is False

    def test_as_dict(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "value"}))
        manager.load()
        d = manager.as_dict()
        assert d == {"key": "value"}

    def test_as_model(self):
        class MyConfig(BaseModel):
            debug: bool = False
            port: int = 8080

        manager = ConfigManager()
        manager.add_source(DictConfigSource({"debug": True, "port": 9090}))
        manager.load()
        config = manager.as_model(MyConfig)
        assert config.debug is True
        assert config.port == 9090

    def test_as_json(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "value"}))
        manager.load()
        json_str = manager.as_json()
        parsed = json.loads(json_str)
        assert parsed["key"] == "value"

    def test_save_to_json_file(self, tmp_path):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "value"}))
        manager.load()

        output_file = tmp_path / "output.json"
        manager.save_to_file(output_file, format="json")

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["key"] == "value"

    def test_on_change_callback(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "old"}))
        manager.load()

        changes = []
        manager.on_change("key", lambda e: changes.append(e))

        manager.set("key", "new")
        assert len(changes) == 1
        assert changes[0].old_value == "old"
        assert changes[0].new_value == "new"

    def test_on_any_change_callback(self):
        manager = ConfigManager()
        manager.load()

        changes = []
        manager.on_any_change(lambda e: changes.append(e))

        manager.set("a", 1)
        manager.set("b", 2)
        assert len(changes) == 2

    def test_reload(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"version": 1}))
        manager.load()
        assert manager.get("version") == 1

        # Simulate source change
        manager._sources.clear()
        manager.add_source(DictConfigSource({"version": 2}))
        manager.reload()
        assert manager.get("version") == 2

    def test_remove_source(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"keep": True}, priority=10))
        manager.add_source(DictConfigSource({"remove": True}, priority=20))
        manager.remove_source(DictConfigSource)
        # Only the removed type is gone
        assert len(manager._sources) == 0

    def test_get_stats(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"key": "value"}))
        manager.load()
        stats = manager.get_stats()
        assert stats["loaded"] is True
        assert stats["sources_count"] == 1
        assert stats["config_keys_count"] == 1

    def test_json_file_source_integration(self, tmp_path):
        config_file = tmp_path / "test_config.json"
        config_file.write_text(json.dumps({
            "database": {"host": "localhost", "port": 5432},
            "cache": {"ttl": 300},
        }))

        manager = ConfigManager()
        manager.add_source(JsonFileConfigSource(config_file))
        manager.load()

        assert manager.get("database.host") == "localhost"
        assert manager.get("database.port") == 5432
        assert manager.get("cache.ttl") == 300

    def test_env_source_integration(self, monkeypatch):
        monkeypatch.setenv("MEMORY_LOG__LEVEL", "INFO")

        manager = ConfigManager()
        manager.add_source(EnvConfigSource("MEMORY_"))
        manager.load()

        assert manager.get("log.level") == "INFO"

    def test_multi_source_merge(self, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"debug": False, "port": 8080}))

        monkeypatch.setenv("MEMORY_DEBUG", "true")

        manager = ConfigManager()
        manager.add_source(DictConfigSource({"app_name": "test"}, priority=0))
        manager.add_source(JsonFileConfigSource(config_file, priority=20))
        manager.add_source(EnvConfigSource("MEMORY_", priority=50))
        manager.load()

        assert manager.get("app_name") == "test"
        assert manager.get("debug") is True  # ENV overrides JSON
        assert manager.get("port") == 8080

    def test_concurrent_access(self):
        manager = ConfigManager()
        manager.add_source(DictConfigSource({"counter": 0}))
        manager.load()

        def worker(i):
            manager.set(f"key_{i}", i)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert manager.has("key_49")


class TestCreateConfigManager:
    def test_with_defaults(self):
        manager = create_config_manager(defaults={"key": "value"})
        assert manager.get("key") == "value"

    def test_with_json_file(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"from_file": True}))

        manager = create_config_manager(config_path=config_file)
        assert manager.get("from_file") is True

    def test_with_env_prefix(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "env_value")
        manager = create_config_manager(env_prefix="TEST_")
        assert manager.get("key") == "env_value"
