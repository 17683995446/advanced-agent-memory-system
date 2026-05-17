"""
兼容性别名模块 - 已迁移至 memory_system.core.async_memory_api_wrapper
此文件保留以支持旧版 import 路径，新代码请使用新路径。
"""

from memory_system.core.async_memory_api_wrapper import *  # noqa: F401,F403
from memory_system.core.async_memory_api_wrapper import __all__ as _all
if "_all" in dir():
    __all__ = list(_all)
