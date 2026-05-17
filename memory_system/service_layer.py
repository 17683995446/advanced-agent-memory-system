"""
兼容性别名模块 - 已迁移至 memory_system.api.fastapi_service_layer
此文件保留以支持旧版 import 路径，新代码请使用新路径。
"""

from memory_system.api.fastapi_service_layer import *  # noqa: F401,F403
from memory_system.api.fastapi_service_layer import __all__ as _all
if "_all" in dir():
    __all__ = list(_all)
