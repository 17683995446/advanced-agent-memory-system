"""Unit tests for the plugin module."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pluggy

from memory_system.infra.plugin_extension_system import (
    PluginManager,
    PluginInfo,
    MemoryPluginSpec,
    get_plugin_manager,
    reset_plugin_manager,
)

_hookimpl = pluggy.HookimplMarker("memory_system")


class TestPluginManager:
    """Test PluginManager class"""

    def setup_method(self):
        reset_plugin_manager()

    def test_create_plugin_manager(self):
        pm = PluginManager()
        assert pm is not None

    def test_register_plugin(self):
        pm = PluginManager()
        class MyPlugin:
            version = "1.0.0"
            description = "Test plugin"
        result = pm.register(MyPlugin(), name="test_plugin")
        assert result is True

    def test_register_duplicate_name(self):
        pm = PluginManager()
        class MyPlugin:
            version = "1.0.0"
        pm.register(MyPlugin(), name="dup")
        # Second registration with same name overwrites
        result = pm.register(MyPlugin(), name="dup")
        assert result is True

    def test_unregister_plugin(self):
        pm = PluginManager()
        class MyPlugin:
            version = "1.0.0"
        pm.register(MyPlugin(), name="to_remove")
        result = pm.unregister("to_remove")
        assert result is True
        assert not pm.is_registered("to_remove")

    def test_unregister_nonexistent(self):
        pm = PluginManager()
        result = pm.unregister("nonexistent")
        assert result is False

    def test_list_plugins(self):
        pm = PluginManager()
        class P1:
            version = "1.0"
            description = "First"
        class P2:
            version = "2.0"
            description = "Second"
        pm.register(P1(), name="p1")
        pm.register(P2(), name="p2")
        plugins = pm.list_plugins()
        assert len(plugins) == 2

    def test_is_registered(self):
        pm = PluginManager()
        class MyPlugin:
            version = "1.0"
        assert not pm.is_registered("test")
        pm.register(MyPlugin(), name="test")
        assert pm.is_registered("test")

    def test_on_configure_no_plugins(self):
        pm = PluginManager()
        config = pm.on_configure({"key": "value"})
        assert config == {"key": "value"}

    def test_on_before_store_no_plugins(self):
        pm = PluginManager()
        content, meta = pm.on_before_store("hello", {})
        assert content == "hello"

    def test_on_after_recall_no_plugins(self):
        pm = PluginManager()
        results = pm.on_after_recall([{"content": "test"}], "query")
        assert len(results) == 1

    def test_on_importance_no_plugins(self):
        pm = PluginManager()
        score = pm.on_importance("test", {}, 0, 0)
        assert score is None

    def test_get_stats(self):
        pm = PluginManager()
        class MyPlugin:
            version = "1.0"
        pm.register(MyPlugin(), name="test")
        stats = pm.get_stats()
        assert stats["total_plugins"] == 1
        assert stats["enabled_plugins"] == 1

    def test_hook_with_plugin(self):
        pm = PluginManager()
        class ConfigPlugin:
            version = "1.0"
            @_hookimpl
            def memory_configure(self, config):
                config["modified"] = True
                return config
        pm.register(ConfigPlugin(), name="config_plugin")
        config = pm.on_configure({"key": "val"})
        assert config.get("modified") is True


class TestGlobalPluginManager:
    def setup_method(self):
        reset_plugin_manager()

    def test_get_singleton(self):
        pm1 = get_plugin_manager()
        pm2 = get_plugin_manager()
        assert pm1 is pm2

    def test_reset(self):
        pm1 = get_plugin_manager()
        reset_plugin_manager()
        pm2 = get_plugin_manager()
        assert pm1 is not pm2


class TestPluginInfo:
    def test_create(self):
        info = PluginInfo(name="test", version="1.0", description="desc")
        assert info.name == "test"
        assert info.enabled is True


class TestPluginHookCallbacks:
    """Test actual hook callback execution"""
    
    def setup_method(self):
        reset_plugin_manager()
    
    def test_before_store_hook_modifies_content(self):
        pm = PluginManager()
        class StorePlugin:
            version = "1.0"
            @_hookimpl
            def memory_before_store(self, content, metadata):
                return content.strip(), metadata
        pm.register(StorePlugin(), name="store_plugin")
        content, meta = pm.on_before_store("  hello  ", {"key": "val"})
        assert content == "hello"
    
    def test_after_recall_hook_reorders_results(self):
        pm = PluginManager()
        class RecallPlugin:
            version = "1.0"
            @_hookimpl
            def memory_after_recall(self, results, query):
                return results[::-1]  # Reverse order
        pm.register(RecallPlugin(), name="recall_plugin")
        results = [{"content": "a"}, {"content": "b"}]
        processed = pm.on_after_recall(results, "query")
        assert processed[0]["content"] == "b"
    
    def test_importance_hook_returns_score(self):
        pm = PluginManager()
        class ScorePlugin:
            version = "1.0"
            @_hookimpl
            def memory_importance(self, content, metadata, access_count, age_seconds):
                return 0.9
        pm.register(ScorePlugin(), name="score_plugin")
        score = pm.on_importance("test", {}, 0, 0)
        assert score == 0.9
    
    def test_consolidate_hook(self):
        pm = PluginManager()
        class ConsolidatePlugin:
            version = "1.0"
            @_hookimpl
            def memory_consolidate(self, memories):
                return memories[:1]  # Keep only first
        pm.register(ConsolidatePlugin(), name="consolidate_plugin")
        memories = [{"id": "1"}, {"id": "2"}]
        result = pm.on_consolidate(memories)
        assert len(result) == 1
    
    def test_before_recall_hook(self):
        pm = PluginManager()
        class RecallBeforePlugin:
            version = "1.0"
            @_hookimpl
            def memory_before_recall(self, query, top_k, filters):
                return query.strip(), min(top_k, 5), filters
        pm.register(RecallBeforePlugin(), name="recall_before")
        q, k, f = pm.on_before_recall("  hello  ", 100, {"cat": "test"})
        assert q == "hello"
        assert k == 5
    
    def test_after_store_hook_called(self):
        pm = PluginManager()
        calls = []
        class AfterStorePlugin:
            version = "1.0"
            @_hookimpl
            def memory_after_store(self, record_id, content, metadata):
                calls.append(record_id)
        pm.register(AfterStorePlugin(), name="after_store")
        pm.on_after_store("id-1", "content", {})
        assert len(calls) == 1
        assert calls[0] == "id-1"
    
    def test_multiple_plugins_chain(self):
        pm = PluginManager()
        class Plugin1:
            version = "1.0"
            @_hookimpl
            def memory_configure(self, config):
                config["p1"] = True
                return config
        class Plugin2:
            version = "1.0"
            @_hookimpl
            def memory_configure(self, config):
                config["p2"] = True
                return config
        pm.register(Plugin1(), name="p1")
        pm.register(Plugin2(), name="p2")
        config = pm.on_configure({})
        assert config.get("p1") is True or config.get("p2") is True
    
    def test_get_plugin_info(self):
        pm = PluginManager()
        class MyPlugin:
            version = "2.0"
            description = "Test"
        pm.register(MyPlugin(), name="my")
        info = pm.get_plugin("my")
        assert info is not None
        assert info.version == "2.0"
        assert info.description == "Test"
    
    def test_get_plugin_nonexistent(self):
        pm = PluginManager()
        assert pm.get_plugin("nonexistent") is None
