#!/usr/bin/env python
"""知识库包导出（延迟加载）。"""

from __future__ import annotations

from typing import Any

__all__ = [
    "DocumentAdder",
    "KnowledgeBaseInitializer",
    "KnowledgeBaseManager",
]


def __getattr__(name: str) -> Any:
    if name == "DocumentAdder":
        from .add_documents import DocumentAdder

        return DocumentAdder
    if name == "KnowledgeBaseInitializer":
        from .initializer import KnowledgeBaseInitializer

        return KnowledgeBaseInitializer
    if name == "KnowledgeBaseManager":
        from .manager import KnowledgeBaseManager

        return KnowledgeBaseManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
