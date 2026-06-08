#!/usr/bin/env python
"""作用域内的 LlamaIndex 标准库日志配置。"""

from __future__ import annotations

from contextlib import contextmanager
import logging
from typing import Any, Iterator


class LlamaIndexLogForwarder(logging.Handler):
    """将选定的 LlamaIndex 记录转发到 AidLearning 日志记录器。"""

    def __init__(self, target: logging.Logger) -> None:
        super().__init__(logging.DEBUG)
        self._target = target

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._target.log(record.levelno, record.getMessage(), exc_info=record.exc_info)
        except Exception:
            self.handleError(record)


@contextmanager
def LlamaIndexLogContext(
    logger_name: str | None = None,
    scene: str = "llamaindex",
    min_level: str = "INFO",
) -> Iterator[None]:
    """在作用域内将冗余的 LlamaIndex 记录转发到命名的标准库日志记录器。"""
    target_name = logger_name or f"aidlearning.{scene}"
    target = logging.getLogger(target_name)
    min_level_int = getattr(logging, min_level.upper(), logging.INFO)
    llama_loggers = [
        logging.getLogger("llama_index"),
        logging.getLogger("llama_index.core"),
        logging.getLogger("llama_index.vector_stores"),
        logging.getLogger("llama_index.embeddings"),
    ]

    original_states: list[dict[str, Any]] = []
    forwarders: list[tuple[logging.Logger, LlamaIndexLogForwarder]] = []
    for llama_logger in llama_loggers:
        original_states.append(
            {
                "logger": llama_logger,
                "handlers": list(llama_logger.handlers),
                "level": llama_logger.level,
                "propagate": llama_logger.propagate,
            }
        )
        for handler in list(llama_logger.handlers):
            if isinstance(handler, logging.StreamHandler):
                llama_logger.removeHandler(handler)
        llama_logger.setLevel(logging.DEBUG)
        llama_logger.propagate = False
        forwarder = LlamaIndexLogForwarder(target)
        forwarder.setLevel(min_level_int)
        llama_logger.addHandler(forwarder)
        forwarders.append((llama_logger, forwarder))

    try:
        yield
    finally:
        for llama_logger, forwarder in forwarders:
            if forwarder in llama_logger.handlers:
                llama_logger.removeHandler(forwarder)
            forwarder.close()
        for state in original_states:
            llama_logger = state["logger"]
            llama_logger.handlers[:] = state["handlers"]
            llama_logger.setLevel(state["level"])
            llama_logger.propagate = state["propagate"]
