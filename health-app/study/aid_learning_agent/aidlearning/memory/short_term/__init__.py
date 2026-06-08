"""第 1 层：短期记忆 — 滑动窗口 + 压缩。

提供 ``ContextBuilder``，管理对话历史预算：最近的消息原样保留，
较旧的消息通过 LLM 摘要压缩。

提供 ``ConversationBuffer`` 和 ``BufferManager``，
用于内存消息缓冲和零 I/O 上下文构建。
"""

from .context_builder import ContextBuilder, count_tokens
from .conversation_buffer import ConversationBuffer
from .buffer_manager import BufferManager, get_buffer_manager, reset_buffer_manager

__all__ = [
    "BufferManager",
    "ContextBuilder",
    "ConversationBuffer",
    "count_tokens",
    "get_buffer_manager",
    "reset_buffer_manager",
]
