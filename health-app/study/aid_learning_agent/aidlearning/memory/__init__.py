"""Four-layer memory subsystem.

Architecture
------------
* **Layer 1 — Short-term**: sliding window + LLM compression
  (``short_term/context_builder.py``, ``short_term/conversation_buffer.py``)
* **Layer 2 — Mid-term**: SQLite FTS5 full-text search
  (``mid_term/search.py``, ``session_search`` tool)
* **Layer 3 — Long-term**: Markdown L2/L3 docs + decay scoring
  (``long_term/document.py``, ``long_term/ops.py``, ``long_term/decay.py``)
* **Layer 4 — Procedural**: auto-extracted skill cards
  (``procedural/extractor.py``)

Shared foundations: ``shared/ids.py``, ``shared/paths.py``, ``shared/trace.py``

All external callers import through this top-level package.  The
``MemoryStore`` facade in ``store.py`` is the primary entry point.
"""

# ── Shared foundations ─────────────────────────────────────────────────
from .shared.ids import is_entry_id, is_trace_id, new_entry_id, new_trace_id
from .shared.paths import L3_SLOTS, SURFACES, L3Slot, Surface
from .shared.trace import TraceEvent

# ── Long-term memory ──────────────────────────────────────────────────
from .long_term.document import Document, Entry, parse, serialize
from .long_term.ops import AddOp, ApplyReport, DeleteOp, EditOp, apply
from .long_term.decay import compute_decay_score, is_stale

# ── Mid-term memory ───────────────────────────────────────────────────
from .mid_term.search import MemoryRetriever, UnifiedResult, get_memory_retriever

# ── Short-term memory ─────────────────────────────────────────────────
from .short_term.context_builder import ContextBuilder, count_tokens

# ── Procedural memory ─────────────────────────────────────────────────
from .procedural.extractor import ProceduralMemoryExtractor

# ── Facade ────────────────────────────────────────────────────────────
from .store import DocOverview, MemoryStore, get_memory_store, migrate_v1_if_needed

__all__ = [
    # Shared
    "L3_SLOTS",
    "L3Slot",
    "SURFACES",
    "Surface",
    "TraceEvent",
    "is_entry_id",
    "is_trace_id",
    "new_entry_id",
    "new_trace_id",
    # Long-term
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
    # Mid-term
    "MemoryRetriever",
    "UnifiedResult",
    "get_memory_retriever",
    # Short-term
    "ContextBuilder",
    "count_tokens",
    # Procedural
    "ProceduralMemoryExtractor",
    # Facade
    "DocOverview",
    "MemoryStore",
    "get_memory_store",
    "migrate_v1_if_needed",
]
