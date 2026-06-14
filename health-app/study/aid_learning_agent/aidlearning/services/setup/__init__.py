"""
设置服务
=======

AidLearning 的系统设置和初始化。

端口配置通过 data/user/settings/system.json 完成。

用法：
    from aidlearning.services.setup import init_user_directories, get_backend_port

    # 初始化用户目录
    init_user_directories()

    # 获取服务器端口
    backend_port = get_backend_port()
    frontend_port = get_frontend_port()
"""

from .init import (
    get_backend_port,
    get_frontend_port,
    get_ports,
    init_user_directories,
)

__all__ = [
    "init_user_directories",
    "get_backend_port",
    "get_frontend_port",
    "get_ports",
]
