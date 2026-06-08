"""第 2 层：中期记忆 — SQLite FTS5 全文搜索。

提供 ``session_search`` 工具（通过 ``tools/builtin``）和 ``MemoryRetriever``
用于跨层检索。中期记忆使用 SQLite FTS5 进行跨所有历史消息内容的高效关键词搜索，
支持类似"上周我们聊了什么？"的查询。
"""

from .search import MemoryRetriever, UnifiedResult, get_memory_retriever, reset_memory_retriever

__all__ = [
    "MemoryRetriever",
    "UnifiedResult",
    "get_memory_retriever",
    "reset_memory_retriever",
]
