"""Layer 3: Long-term memory — Markdown L2/L3 documents + decay scoring.

Refined facts extracted from mid-term memory, stored as structured
Markdown with footnote-style citations.  Each entry carries optional
decay metadata (timestamps, access count, importance) for time-based
relevance scoring.
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
