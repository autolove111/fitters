"""Layer 2: Mid-term memory — SQLite FTS5 full-text search.

Provides the ``session_search`` tool (via ``tools/builtin``) and the
``MemoryRetriever`` for cross-layer retrieval.  Mid-term memory uses
SQLite FTS5 for efficient keyword search across all past message
content, enabling queries like "what did we talk about last week?".
"""

from .search import MemoryRetriever, UnifiedResult, get_memory_retriever, reset_memory_retriever

__all__ = [
    "MemoryRetriever",
    "UnifiedResult",
    "get_memory_retriever",
    "reset_memory_retriever",
]
