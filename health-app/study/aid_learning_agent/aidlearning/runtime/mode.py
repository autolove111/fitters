"""
运行模式
========

控制 AidLearning 以 CLI 应用还是 API 服务器模式运行。
模块可以检查模式以有条件地导入仅限服务端的依赖。
"""

from enum import Enum
import os


class RunMode(str, Enum):
    CLI = "cli"
    SERVER = "server"


_current_mode: RunMode | None = None


def _resolve_mode() -> RunMode:
    raw = os.environ.get("AIDLEARNING_MODE", "").strip().lower()
    if raw == RunMode.SERVER.value:
        return RunMode.SERVER
    return RunMode.CLI


def get_mode() -> RunMode:
    global _current_mode
    if _current_mode is None:
        _current_mode = _resolve_mode()
    return _current_mode


def set_mode(mode: RunMode) -> None:
    """显式设置运行模式（在入口点早期调用）。"""
    global _current_mode
    _current_mode = mode
    os.environ["AIDLEARNING_MODE"] = mode.value


def is_cli() -> bool:
    return get_mode() == RunMode.CLI


def is_server() -> bool:
    return get_mode() == RunMode.SERVER
