"""四层记忆子系统。

架构
------------
* **第 1 层 — 短期记忆**：滑动窗口 + LLM 压缩
  (``short_term/context_builder.py``, ``short_term/conversation_buffer.py``)
* **第 2 层 — 中期记忆**：SQLite FTS5 全文搜索
  (``mid_term/search.py``, ``session_search`` 工具)
* **第 3 层 — 长期记忆**：Markdown L2/L3 文档 + 衰减评分
  (``long_term/document.py``, ``long_term/ops.py``, ``long_term/decay.py``)
* **第 4 层 — 程序性记忆**：自动提取的技能卡片
  (``procedural/extractor.py``)

共享基础：``shared/ids.py``, ``shared/paths.py``, ``shared/trace.py``

所有外部调用方通过此顶层包导入。``store.py`` 中的 ``MemoryStore`` 门面是主要入口。
"""

# ── 共享基础 ─────────────────────────────────────────────────
from .shared.ids import is_entry_id, is_trace_id, new_entry_id, new_trace_id
from .shared.paths import L3_SLOTS, SURFACES, L3Slot, Surface
from .shared.trace import TraceEvent

# ── 长期记忆 ──────────────────────────────────────────────────
from .long_term.document import Document, Entry, parse, serialize
from .long_term.ops import AddOp, ApplyReport, DeleteOp, EditOp, apply
from .long_term.decay import compute_decay_score, is_stale

# ── 中期记忆 ───────────────────────────────────────────────────
from .mid_term.search import MemoryRetriever, UnifiedResult, get_memory_retriever

# ── 短期记忆 ─────────────────────────────────────────────────
from .short_term.context_builder import ContextBuilder, count_tokens

# ── 程序性记忆 ─────────────────────────────────────────────────
from .procedural.extractor import ProceduralMemoryExtractor

# ── 门面 ────────────────────────────────────────────────────────────
from .store import DocOverview, MemoryStore, get_memory_store, migrate_v1_if_needed

__all__ = [
    # 共享
    "L3_SLOTS",
    "L3Slot",
    "SURFACES",
    "Surface",
    "TraceEvent",
    "is_entry_id",
    "is_trace_id",
    "new_entry_id",
    "new_trace_id",
    # 长期记忆
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
    # 中期记忆
    "MemoryRetriever",
    "UnifiedResult",
    "get_memory_retriever",
    # 短期记忆
    "ContextBuilder",
    "count_tokens",
    # 程序性记忆
    "ProceduralMemoryExtractor",
    # 门面
    "DocOverview",
    "MemoryStore",
    "get_memory_store",
    "migrate_v1_if_needed",
]
