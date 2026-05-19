"""
兼容性别名模块 - 已迁移至 memory_system.infra.blinker_event_bus
此文件保留以支持旧版 import 路径，新代码请使用新路径。
"""

try:
    from memory_system.infra.blinker_event_bus import *  # noqa: F401,F403
    from memory_system.infra.blinker_event_bus import __all__ as _all
    if "_all" in dir():
        __all__ = list(_all)
except ImportError:
    # 如果 blinker 不可用，提供空实现
    __all__ = []
