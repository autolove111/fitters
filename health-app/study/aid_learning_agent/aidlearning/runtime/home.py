"""已安装和源码运行 AidLearning 的运行时主目录解析。"""

from __future__ import annotations

import os
from pathlib import Path

AIDLEARNING_HOME_ENV = "AIDLEARNING_HOME"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def get_runtime_home(home: str | Path | None = None) -> Path:
    """返回当前进程的运行时数据目录。

    优先级：
    1. 显式的 *home* 参数。
    2. ``AIDLEARNING_HOME`` 环境变量。
    3. 当前工作目录。

    返回的路径是工作区根目录；运行时数据位于 ``<home>/data`` 下。
    """

    raw = home if home is not None else os.getenv(AIDLEARNING_HOME_ENV)
    if raw is None or str(raw).strip() == "":
        return Path.cwd().resolve()
    return Path(raw).expanduser().resolve()


def get_runtime_data_root(home: str | Path | None = None) -> Path:
    """返回 ``<runtime-home>/data``。"""

    return get_runtime_home(home) / "data"


__all__ = [
    "AIDLEARNING_HOME_ENV",
    "PACKAGE_ROOT",
    "get_runtime_home",
    "get_runtime_data_root",
]
