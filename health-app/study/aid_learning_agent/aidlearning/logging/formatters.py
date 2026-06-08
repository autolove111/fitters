"""AidLearning 标准库日志管道的格式化器。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from .context import LOG_CONTEXT_FIELDS, current_log_context


class ContextFilter(logging.Filter):
    """将上下文变量和显式记录字段附加到每个 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        context = current_log_context()
        for key in LOG_CONTEXT_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                context[key] = value
        record.log_context = context
        return True


class JsonlFormatter(logging.Formatter):
    """每行一个结构化 JSON 对象。"""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": getattr(record, "log_context", {}) or {},
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """用于本地开发的小型人类可读格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        context = getattr(record, "log_context", {}) or {}
        stage = f" @{context['stage']}" if context.get("stage") else ""
        task = f" #{context['task_id']}" if context.get("task_id") else ""
        return f"{record.levelname:<7} {record.name}{stage}{task} - {record.getMessage()}"
