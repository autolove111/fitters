#!/usr/bin/env python
"""
Uvicorn 服务器启动脚本
使用 Python API 代替命令行，避免 Windows 路径解析问题。
"""

import asyncio
import os
from pathlib import Path
import sys

from aidlearning.runtime.home import get_runtime_home

# Windows 下 uvicorn 默认使用 SelectorEventLoop，不支持 asyncio.create_subprocess_exec。
# 切换为 ProactorEventLoop 以确保子进程 API（如 Math Animator 渲染器等）正常工作。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

# 强制无缓冲输出
os.environ["PYTHONUNBUFFERED"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, errors="replace")


def main() -> None:
    # 运行时工作区根目录，包含 data/user/settings 和生成的输出文件。
    project_root = get_runtime_home()
    os.chdir(str(project_root))

    # 从配置中获取端口
    from aidlearning.logging import configure_logging
    from aidlearning.runtime.mode import RunMode, set_mode
    from aidlearning.services.setup import get_backend_port

    set_mode(RunMode.SERVER)
    configure_logging()
    backend_port = get_backend_port(project_root)

    # 配置 reload_excludes 以跳过不应触发重载的目录
    # 使用绝对路径确保正确解析
    reload_excludes = [
        str(project_root / "venv"),  # 虚拟环境
        str(project_root / ".venv"),  # 虚拟环境（备用名称）
        str(project_root / "data"),  # 数据目录（包含 knowledge_bases、用户数据、日志）
        str(project_root / "node_modules"),  # Node 模块（根目录下如有）
        str(project_root / "web" / "node_modules"),  # Web 端 Node 模块
        str(project_root / "web" / ".next"),  # Next.js 构建产物
        str(project_root / ".git"),  # Git 目录
        str(project_root / "scripts"),  # 脚本目录——启动器变更不应触发重载
    ]

    # 过滤掉不存在的目录以避免警告
    reload_excludes = [d for d in reload_excludes if Path(d).exists()]

    # 启用热重载，启动 uvicorn 服务器
    uvicorn.run(
        "aidlearning.api.main:app",
        host="0.0.0.0",
        port=backend_port,
        reload=True,
        reload_excludes=reload_excludes,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
