"""将可选的 loguru 记录桥接到标准库日志。"""

from __future__ import annotations

import logging
from typing import Any


def install_loguru_bridge(level: int = logging.DEBUG) -> bool:
    """如果 loguru 已安装，将 loguru 日志转发到标准库。"""
    try:
        from loguru import logger as loguru_logger
    except Exception:
        return False

    def sink(message: Any) -> None:
        record = message.record
        std_logger = logging.getLogger(record["name"])
        std_logger.log(
            record["level"].no,
            record["message"],
            exc_info=record["exception"],
            extra={"loguru": True},
        )

    loguru_logger.remove()
    loguru_logger.add(sink, level=level, enqueue=False, backtrace=False, diagnose=False)
    return True
