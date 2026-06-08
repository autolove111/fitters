"""第 3 层：长期记忆 — Markdown L2/L3 文档 + 衰减评分。

从中期记忆中提取的精炼事实，以带脚注式引用的结构化 Markdown 存储。
每个条目携带可选的衰减元数据（时间戳、访问次数、重要性）
用于基于时间的相关性评分。
"""

from .decay import compute_decay_score, is_stale
from .document import Document, Entry, parse, serialize
from .ops import AddOp, ApplyReport, DeleteOp, EditOp, apply

__all__ = [
    "AddOp",
    "ApplyReport",
    "DeleteOp",
    "Document",
    "EditOp",
    "Entry",
    "apply",
    "compute_decay_score",
    "is_stale",
    "parse",
    "serialize",
]
