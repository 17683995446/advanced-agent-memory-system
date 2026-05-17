"""
插件系统 - 基于 pluggy 的可扩展架构

使用 pluggy (pytest 的插件引擎) 实现 Hook 机制，
支持第三方扩展记忆系统的各个生命周期。

依赖: pluggy>=1.0.0
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import pluggy
    _pluggy_available = True
except ImportError:
    _pluggy_available = False
    pluggy = None

logger = logging.getLogger(__name__)

_PROJECT_NAME = "memory_system"

if _pluggy_available:
    _hookspec = pluggy.HookspecMarker(_PROJECT_NAME)
    _hookimpl = pluggy.HookimplMarker(_PROJECT_NAME)
else:
    def _hookspec(func):
        return func
    def _hookimpl(func):
        return func


# ---------------------------------------------------------------------------
# Hook 规范定义
# ---------------------------------------------------------------------------

class MemoryPluginSpec:
    """
    记忆系统插件 Hook 规范

    定义了所有可扩展的 Hook 点，第三方插件通过实现这些 Hook 来扩展系统。

    Hook 生命周期:
    1. memory_configure  → 系统配置阶段
    2. memory_before_store → 存储前处理
    3. memory_after_store  → 存储后处理
    4. memory_before_recall → 检索前处理
    5. memory_after_recall  → 检索后处理
    6. memory_importance    → 重要性评分
    7. memory_consolidate   → 记忆整合
    8. memory_export        → 数据导出
    9. memory_import        → 数据导入
    """

    # 配置阶段
    @_hookspec
    def memory_configure(self, config: dict) -> dict:
        """
        修改系统配置

        Args:
            config: 原始配置字典

        Returns:
            修改后的配置字典
        """
        pass

    # 存储生命周期
    @_hookspec
    def memory_before_store(self, content: str, metadata: dict) -> tuple[str, dict]:
        """
        存储前处理

        Args:
            content: 待存储的内容
            metadata: 元数据

        Returns:
            (修改后的内容, 修改后的元数据)
        """
        pass

    @_hookspec
    def memory_after_store(self, record_id: str, content: str, metadata: dict) -> None:
        """存储后通知"""
        pass

    # 检索生命周期
    @_hookspec
    def memory_before_recall(self, query: str, top_k: int, filters: dict) -> tuple[str, int, dict]:
        """
        检索前处理

        Returns:
            (修改后的查询, 修改后的 top_k, 修改后的 filters)
        """
        pass

    @_hookspec
    def memory_after_recall(self, results: list[dict], query: str) -> list[dict]:
        """
        检索后处理（可重排序、过滤、增强）

        Returns:
            处理后的结果列表
        """
        pass

    # 重要性评分
    @_hookspec
    def memory_importance(self, content: str, metadata: dict, access_count: int, age_seconds: float) -> Optional[float]:
        """
        计算记忆重要性分数

        Returns:
            重要性分数 (0.0-1.0)，返回 None 表示使用默认评分
        """
        pass

    # 整合
    @_hookspec
    def memory_consolidate(self, memories: list[dict]) -> list[dict]:
        """
        记忆整合

        Args:
            memories: 待整合的记忆列表

        Returns:
            整合后的记忆列表
        """
        pass

    # 导入导出
    @_hookspec
    def memory_export(self, records: list[dict], format: str) -> Optional[bytes]:
        """
        导出记忆数据

        Returns:
            导出数据的字节流，返回 None 表示不处理
        """
        pass

    @_hookspec
    def memory_import(self, data: bytes, format: str) -> Optional[list[dict]]:
        """
        导入记忆数据

        Returns:
            导入的记录列表，返回 None 表示不处理
        """
        pass


# ---------------------------------------------------------------------------
# 插件管理器
# ---------------------------------------------------------------------------

@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str = "0.1.0"
    description: str = ""
    enabled: bool = True


class PluginManager:
    """
    插件管理器

    基于 pluggy 的插件注册与 Hook 调度。

    Example:
        pm = PluginManager()

        # 注册插件
        pm.register(MyPlugin())

        # 调用 Hook
        config = pm.hook.memory_configure(config={"key": "value"})

        # 列出已注册插件
        for info in pm.list_plugins():
            print(f"{info.name} v{info.version}")
    """

    def __init__(self):
        if not _pluggy_available:
            raise ImportError(
                "pluggy is required for PluginManager. "
                "Install it with: pip install pluggy"
            )

        self._pm = pluggy.PluginManager(_PROJECT_NAME)
        self._pm.add_hookspecs(MemoryPluginSpec)
        self._plugins: dict[str, PluginInfo] = {}
        self._hook = self._pm.hook

    @property
    def hook(self):
        """获取 Hook 对象"""
        return self._hook

    def register(self, plugin: Any, name: Optional[str] = None) -> bool:
        """
        注册插件

        Args:
            plugin: 插件实例（需实现 MemoryPluginSpec 中的 Hook）
            name: 可选的插件名称

        Returns:
            是否注册成功
        """
        plugin_name = name or getattr(plugin, '__name__', type(plugin).__name__)

        try:
            self._pm.register(plugin)
            self._plugins[plugin_name] = PluginInfo(
                name=plugin_name,
                version=getattr(plugin, 'version', '0.1.0'),
                description=getattr(plugin, 'description', ''),
            )
            logger.info("Plugin registered: %s", plugin_name)
            return True
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.error("Failed to register plugin %s: %s", plugin_name, e)
            return False

    def unregister(self, name: str) -> bool:
        """
        注销插件

        Args:
            name: 插件名称

        Returns:
            是否注销成功
        """
        if name not in self._plugins:
            return False

        try:
            # pluggy 不支持按名称注销，标记为禁用
            self._plugins[name].enabled = False
            logger.info("Plugin unregistered: %s", name)
            return True
        except (AttributeError, KeyError, RuntimeError) as e:
            logger.error("Failed to unregister plugin %s: %s", name, e)
            return False

    def list_plugins(self) -> list[PluginInfo]:
        """列出所有已注册插件"""
        return list(self._plugins.values())

    def get_plugin(self, name: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugins.get(name)

    def is_registered(self, name: str) -> bool:
        """检查插件是否已注册"""
        return name in self._plugins and self._plugins[name].enabled

    # ------------------------------------------------------------------
    # 便捷 Hook 调用方法
    # ------------------------------------------------------------------

    def on_configure(self, config: dict) -> dict:
        """调用 memory_configure Hook"""
        if not self._plugins:
            return config
        results = self._hook.memory_configure(config=config)
        # 取最后一个非 None 结果
        for r in reversed(results):
            if r is not None:
                return r
        return config

    def on_before_store(self, content: str, metadata: dict) -> tuple[str, dict]:
        """调用 memory_before_store Hook"""
        if not self._plugins:
            return content, metadata
        results = self._hook.memory_before_store(content=content, metadata=metadata)
        for r in reversed(results):
            if r is not None:
                return r
        return content, metadata

    def on_after_store(self, record_id: str, content: str, metadata: dict):
        """调用 memory_after_store Hook"""
        if not self._plugins:
            return
        self._hook.memory_after_store(record_id=record_id, content=content, metadata=metadata)

    def on_before_recall(self, query: str, top_k: int, filters: Optional[dict] = None) -> tuple[str, int, dict]:
        """调用 memory_before_recall Hook"""
        if not self._plugins:
            return query, top_k, filters or {}
        results = self._hook.memory_before_recall(query=query, top_k=top_k, filters=filters or {})
        for r in reversed(results):
            if r is not None:
                return r
        return query, top_k, filters or {}

    def on_after_recall(self, results: list[dict], query: str) -> list[dict]:
        """调用 memory_after_recall Hook"""
        if not self._plugins:
            return results
        processed = self._hook.memory_after_recall(results=results, query=query)
        for r in reversed(processed):
            if r is not None:
                return r
        return results

    def on_importance(self, content: str, metadata: dict, access_count: int, age_seconds: float) -> Optional[float]:
        """调用 memory_importance Hook"""
        if not self._plugins:
            return None
        results = self._hook.memory_importance(
            content=content, metadata=metadata,
            access_count=access_count, age_seconds=age_seconds,
        )
        for r in reversed(results):
            if r is not None:
                return r
        return None

    def on_consolidate(self, memories: list[dict]) -> list[dict]:
        """调用 memory_consolidate Hook"""
        if not self._plugins:
            return memories
        results = self._hook.memory_consolidate(memories=memories)
        for r in reversed(results):
            if r is not None:
                return r
        return memories

    def get_stats(self) -> dict:
        """获取插件系统统计"""
        return {
            "total_plugins": len(self._plugins),
            "enabled_plugins": sum(1 for p in self._plugins.values() if p.enabled),
            "plugins": [
                {"name": p.name, "version": p.version, "enabled": p.enabled}
                for p in self._plugins.values()
            ],
        }


# ---------------------------------------------------------------------------
# 全局插件管理器
# ---------------------------------------------------------------------------

_global_pm: Optional[PluginManager] = None
_pm_lock = threading.Lock()


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器（线程安全）"""
    global _global_pm
    if _global_pm is None:
        with _pm_lock:
            if _global_pm is None:
                _global_pm = PluginManager()
    return _global_pm


def reset_plugin_manager():
    """重置全局插件管理器（主要用于测试）"""
    global _global_pm
    with _pm_lock:
        _global_pm = None


__all__ = [
    "MemoryPluginSpec",
    "PluginManager",
    "PluginInfo",
    "get_plugin_manager",
    "reset_plugin_manager",
]
