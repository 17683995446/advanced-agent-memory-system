"""
动态配置管理模块 - 多源配置 + 热重载

支持从多种来源加载配置:
- Python 字典
- JSON 文件
- YAML 文件 (可选)
- 环境变量
- 默认值

特性:
- 类型安全的配置模型 (Pydantic)
- 配置优先级覆盖
- 文件变更热重载 (可选 watchdog)
- 配置变更回调通知
- 配置导出和序列化

依赖: pydantic>=2.0.0, PyYAML>=6.0 (可选)
"""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Type, TypeVar, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Try to import yaml
try:
    import yaml
    _yaml_available = True
except ImportError:
    _yaml_available = False


# ---------------------------------------------------------------------------
# Configuration Source Types
# ---------------------------------------------------------------------------

class ConfigSource:
    """配置来源基类"""
    priority: int = 0

    def load(self) -> dict:
        raise NotImplementedError


class DictConfigSource(ConfigSource):
    """字典配置来源"""

    def __init__(self, data: dict, priority: int = 10):
        self.data = data
        self.priority = priority

    def load(self) -> dict:
        return copy.deepcopy(self.data)


class JsonFileConfigSource(ConfigSource):
    """JSON 文件配置来源"""

    def __init__(self, path: Union[str, Path], priority: int = 20):
        self.path = Path(path)
        self.priority = priority

    def load(self) -> dict:
        if not self.path.exists():
            logger.warning("Config file not found: %s", self.path)
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)


class YamlFileConfigSource(ConfigSource):
    """YAML 文件配置来源"""

    def __init__(self, path: Union[str, Path], priority: int = 20):
        self.path = Path(path)
        self.priority = priority

    def load(self) -> dict:
        if not _yaml_available:
            raise ImportError("PyYAML is required for YAML config. Install: pip install pyyaml")
        if not self.path.exists():
            logger.warning("Config file not found: %s", self.path)
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


class EnvConfigSource(ConfigSource):
    """环境变量配置来源

    支持前缀过滤和嵌套键展开:
    - APP__KEY=value → {"key": "value"}
    - APP__NESTED__KEY=value → {"nested": {"key": "value"}}
    """

    def __init__(self, prefix: str = "MEMORY_", priority: int = 50):
        self.prefix = prefix
        self.priority = priority

    def load(self) -> dict:
        result: dict = {}
        prefix_len = len(self.prefix)

        for key, value in os.environ.items():
            if key.startswith(self.prefix):
                # Remove prefix and convert to nested dict
                remaining = key[prefix_len:].lower()
                parts = [p.strip() for p in remaining.split("__") if p.strip()]

                if not parts:
                    continue

                # Auto-convert value types
                converted_value = self._convert_value(value)

                # Build nested dict
                current = result
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = converted_value

        return result

    @staticmethod
    def _convert_value(value: str) -> Any:
        """自动转换环境变量值类型"""
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value


# ---------------------------------------------------------------------------
# Configuration Change Event
# ---------------------------------------------------------------------------

@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    key: str
    old_value: Any
    new_value: Any
    source: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """
    动态配置管理器

    支持多源配置加载、优先级合并、热重载和变更通知。

    Example:
        manager = ConfigManager()

        # 添加配置源
        manager.add_source(DictConfigSource({"debug": True}))
        manager.add_source(JsonFileConfigSource("config.json"))
        manager.add_source(EnvConfigSource("APP_"))

        # 加载配置
        manager.load()

        # 获取配置值
        debug = manager.get("debug", default=False)

        # 监听变更
        manager.on_change("debug", lambda event: print(f"debug changed to {event.new_value}"))

        # 导出为 Pydantic 模型
        class MyConfig(BaseModel):
            debug: bool = False
        config = manager.as_model(MyConfig)
    """

    def __init__(self):
        self._sources: list[ConfigSource] = []
        self._config: dict = {}
        self._lock = threading.RLock()
        self._change_callbacks: dict[str, list[Callable[[ConfigChangeEvent], None]]] = {}
        self._global_callbacks: list[Callable[[ConfigChangeEvent], None]] = []
        self._loaded = False
        self._last_load_time: Optional[float] = None

    def add_source(self, source: ConfigSource):
        """添加配置源（按优先级排序）"""
        with self._lock:
            self._sources.append(source)
            self._sources.sort(key=lambda s: s.priority)  # Low priority first, high overrides

    def remove_source(self, source_type: Type[ConfigSource]):
        """移除指定类型的配置源"""
        with self._lock:
            self._sources = [s for s in self._sources if not isinstance(s, source_type)]

    def load(self) -> dict:
        """
        加载所有配置源并合并

        高优先级源覆盖低优先级源的值。
        """
        with self._lock:
            merged: dict = {}

            for source in self._sources:
                try:
                    data = source.load()
                    self._deep_merge(merged, data)
                    logger.debug("Loaded config from %s (priority=%d)", type(source).__name__, source.priority)
                except (IOError, OSError, ValueError, TypeError, json.JSONDecodeError) as e:
                    logger.error("Failed to load config from %s: %s", type(source).__name__, e)

            # Detect changes
            changes = self._detect_changes(self._config, merged)

            self._config = merged
            self._loaded = True
            self._last_load_time = time.time()

            # Notify callbacks
            for change in changes:
                self._notify_change(change)

            logger.info("Configuration loaded (%d sources, %d top-level keys)", len(self._sources), len(self._config))
            return self._config

    def reload(self) -> dict:
        """重新加载配置"""
        return self.load()

    def get(self, key: str, default: Any = None, separator: str = ".") -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔的嵌套路径
            default: 默认值
            separator: 层级分隔符

        Returns:
            配置值
        """
        with self._lock:
            parts = key.split(separator) if separator else [key]
            current = self._config

            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default

            return current

    def set(self, key: str, value: Any, separator: str = "."):
        """
        设置配置值（运行时修改，不持久化）
        """
        with self._lock:
            parts = key.split(separator) if separator else [key]
            current = self._config

            old_value = self.get(key, separator=separator)

            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = value

            # Notify
            if old_value != value:
                event = ConfigChangeEvent(
                    key=key,
                    old_value=old_value,
                    new_value=value,
                    source="runtime",
                )
                self._notify_change(event)

    def has(self, key: str, separator: str = ".") -> bool:
        """检查配置键是否存在"""
        with self._lock:
            parts = key.split(separator) if separator else [key]
            current = self._config
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return False
            return True

    def as_dict(self) -> dict:
        """导出完整配置字典"""
        with self._lock:
            return copy.deepcopy(self._config)

    def as_model(self, model_class: Type[T]) -> T:
        """导出为 Pydantic 模型"""
        with self._lock:
            return model_class.model_validate(self._config)

    def as_json(self, indent: int = 2) -> str:
        """导出为 JSON 字符串"""
        return json.dumps(self._config, indent=indent, default=str, ensure_ascii=False)

    def save_to_file(self, path: Union[str, Path], format: str = "json"):
        """保存配置到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, default=str, ensure_ascii=False)
        elif format == "yaml":
            if not _yaml_available:
                raise ImportError("PyYAML is required for YAML export")
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info("Configuration saved to %s", path)

    def on_change(self, key: str, callback: Callable[[ConfigChangeEvent], None]):
        """注册配置变更回调"""
        with self._lock:
            if key not in self._change_callbacks:
                self._change_callbacks[key] = []
            self._change_callbacks[key].append(callback)

    def on_any_change(self, callback: Callable[[ConfigChangeEvent], None]):
        """注册全局配置变更回调"""
        with self._lock:
            self._global_callbacks.append(callback)

    def _detect_changes(self, old_config: dict, new_config: dict) -> list[ConfigChangeEvent]:
        """检测配置变更"""
        changes = []
        all_keys = set(list(old_config.keys()) + list(new_config.keys()))

        for key in all_keys:
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            if old_val != new_val:
                changes.append(ConfigChangeEvent(
                    key=str(key),
                    old_value=old_val,
                    new_value=new_val,
                    source="reload",
                ))

        return changes

    def _notify_change(self, event: ConfigChangeEvent):
        """通知变更回调"""
        # Key-specific callbacks
        for key, callbacks in self._change_callbacks.items():
            if event.key == key or event.key.startswith(key + "."):
                for cb in callbacks:
                    try:
                        cb(event)
                    except (ValueError, TypeError, RuntimeError) as e:
                        logger.warning("Config change callback error for key '%s': %s", key, e)

        # Global callbacks
        for cb in self._global_callbacks:
            try:
                cb(event)
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning("Global config change callback error: %s", e)

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """深度合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value

    def get_stats(self) -> dict:
        """获取配置管理器统计"""
        return {
            "loaded": self._loaded,
            "sources_count": len(self._sources),
            "sources": [
                {"type": type(s).__name__, "priority": s.priority}
                for s in self._sources
            ],
            "config_keys_count": len(self._config),
            "callbacks_count": sum(len(cbs) for cbs in self._change_callbacks.values()) + len(self._global_callbacks),
            "last_load_time": self._last_load_time,
        }


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_config_manager(
    config_path: Optional[Union[str, Path]] = None,
    env_prefix: str = "MEMORY_",
    defaults: Optional[dict] = None,
) -> ConfigManager:
    """
    快速创建配置管理器

    Args:
        config_path: 配置文件路径（自动检测 JSON/YAML）
        env_prefix: 环境变量前缀
        defaults: 默认配置字典

    Returns:
        ConfigManager 实例
    """
    manager = ConfigManager()

    # Default values (lowest priority)
    if defaults:
        manager.add_source(DictConfigSource(defaults, priority=0))

    # File config (medium priority)
    if config_path:
        path = Path(config_path)
        if path.suffix in (".yaml", ".yml"):
            manager.add_source(YamlFileConfigSource(path, priority=20))
        elif path.suffix == ".json":
            manager.add_source(JsonFileConfigSource(path, priority=20))
        else:
            logger.warning("Unknown config file format: %s", path.suffix)

    # Environment variables (highest priority)
    manager.add_source(EnvConfigSource(env_prefix, priority=50))

    manager.load()
    return manager


__all__ = [
    "ConfigSource",
    "DictConfigSource",
    "JsonFileConfigSource",
    "YamlFileConfigSource",
    "EnvConfigSource",
    "ConfigChangeEvent",
    "ConfigManager",
    "create_config_manager",
]
