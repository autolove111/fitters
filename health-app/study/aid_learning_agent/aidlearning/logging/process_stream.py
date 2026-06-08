"""用于用户可见操作日志的进程日志事件捕获。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import inspect
import logging
from typing import Any

from .context import LOG_CONTEXT_FIELDS
from .formatters import ContextFilter


@dataclass(frozen=True)
class ProcessLogEvent:
    type: str = "process_log"
    level: str = "INFO"
    message: str = ""
    logger: str = ""
    timestamp: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: logging.LogRecord) -> "ProcessLogEvent":
        context = dict(getattr(record, "log_context", {}) or {})
        for key in LOG_CONTEXT_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                context[key] = value
        return cls(
            level=record.levelname,
            message=record.getMessage(),
            logger=record.name,
            timestamp=record.created,
            context=context,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "level": self.level,
            "message": self.message,
            "logger": self.logger,
            "timestamp": self.timestamp,
            "context": self.context,
        }


class ProcessLogHandler(logging.Handler):
    """从匹配的记录中发出结构化进程日志事件。"""

    def __init__(
        self,
        emit: Callable[[ProcessLogEvent], Any],
        *,
        task_id: str | None = None,
        turn_id: str | None = None,
        min_level: int = logging.INFO,
    ) -> None:
        super().__init__(level=min_level)
        self._emit = emit
        self._task_id = task_id
        self._turn_id = turn_id
        self.addFilter(ContextFilter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = ProcessLogEvent.from_record(record)
            if self._task_id and event.context.get("task_id") != self._task_id:
                return
            if self._turn_id and event.context.get("turn_id") != self._turn_id:
                return
            result = self._emit(event)
            if inspect.isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return
                asyncio.ensure_future(result, loop=loop)
        except Exception:
            self.handleError(record)


@contextmanager
def capture_process_logs(
    emit: Callable[[ProcessLogEvent], Any],
    *,
    task_id: str | None = None,
    turn_id: str | None = None,
    min_level: int = logging.INFO,
) -> Iterator[ProcessLogHandler]:
    """捕获匹配的标准库日志记录并发出 ``ProcessLogEvent`` 对象。"""
    handler = ProcessLogHandler(
        emit,
        task_id=task_id,
        turn_id=turn_id,
        min_level=min_level,
    )
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)
        handler.close()
