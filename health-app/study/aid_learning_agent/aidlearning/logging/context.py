"""请求级别的日志上下文。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import contextvars
from typing import Any

LOG_CONTEXT_FIELDS = (
    "request_id",
    "turn_id",
    "session_id",
    "task_id",
    "capability",
    "stage",
    "sink",
)

_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "aidlearning_log_context", default={}
)


def current_log_context() -> dict[str, Any]:
    """返回当前活跃日志上下文的副本。"""
    return dict(_context.get())


@contextmanager
def bind_log_context(**fields: Any) -> Iterator[dict[str, Any]]:
    """在此上下文中临时将结构化字段绑定到所有日志记录。"""
    clean_fields = {key: value for key, value in fields.items() if value is not None}
    previous = _context.get()
    token = _context.set({**previous, **clean_fields})
    try:
        yield current_log_context()
    finally:
        _context.reset(token)
