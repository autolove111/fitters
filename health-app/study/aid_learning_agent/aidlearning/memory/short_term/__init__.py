"""Layer 1: Short-term memory — sliding window + compression.

Provides ``ContextBuilder`` which manages the conversation history
budget: recent messages are kept verbatim, older ones are compressed
via LLM summarization.

Provides ``ConversationBuffer`` and ``BufferManager`` for in-memory
message buffering with zero-I/O context building.
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
