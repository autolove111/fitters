"""Per-session in-memory conversation buffer with sliding window + summary.

This is the core short-term memory.  It holds recent messages in a
sliding window and automatically compresses older messages into a
summary when the token budget is exceeded.

Usage::

    buffer = ConversationBuffer("session_123", token_budget=2000)
    buffer.append("user", "帮我讲讲微积分")
    buffer.append("assistant", "微积分是...")

    # When total tokens exceed token_budget, old messages are
    # compressed into the summary automatically.

    context = buffer.get_context()
    # → [{"role": "system", "content": "摘要..."}, 最近的消息...]

``ContextBuilder`` is no longer needed — the buffer IS the context.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# Default token budget for the conversation window
DEFAULT_TOKEN_BUDGET = 1200

# Compression callback type: receives old messages, returns summary text
CompressFn = Callable[[list[dict[str, Any]], str], Awaitable[str]]


def _estimate_tokens(text: str) -> int:
    """Estimate token count. ~1 token per 2 CJK chars, ~1 per 4 Latin chars."""
    if not text:
        return 0
    cjk = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - cjk
    return (cjk // 2) + (other // 4) + 1


@dataclass
class _Message:
    """One message in the buffer."""
    msg_id: int
    role: str
    content: str
    parent_id: int | None = None
    tokens: int = 0  # estimated token count
    # Set after flush to SQLite
    flushed: bool = False


class ConversationBuffer:
    """In-memory sliding-window conversation buffer.

    Parameters
    ----------
    session_id : str
        The session this buffer belongs to.
    start_id : int
        The maximum existing message ID from SQLite (or 0 for fresh).
        New messages get IDs starting from ``start_id + 1``.
    token_budget : int
        Maximum tokens for the conversation window.  When total tokens
        exceed this, the oldest messages are compressed into the summary.
    compress_fn : CompressFn | None
        Async function ``(old_messages, existing_summary) -> new_summary``.
        Required for automatic compression.  If None, compression is
        skipped (buffer grows unbounded).
    """

    def __init__(
        self,
        session_id: str,
        start_id: int = 0,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        compress_fn: CompressFn | None = None,
    ) -> None:
        self.session_id = session_id
        self.token_budget = token_budget
        self.compress_fn = compress_fn

        self._messages: list[_Message] = []
        self._next_id: int = start_id
        self._lock = threading.Lock()

        # Summary of compressed older messages
        self.summary: str = ""
        self.summary_tokens: int = 0
        # How many messages have been compressed into the summary
        self._compressed_count: int = 0

    # ── Write ────────────────────────────────────────────────────────

    def append(
        self,
        role: str,
        content: str,
        parent_id: int | None = None,
    ) -> int:
        """Add a message to the buffer. Returns the assigned ID.

        Does NOT trigger compression — call :meth:`maybe_compress`
        separately (it's async).
        """
        with self._lock:
            self._next_id += 1
            msg_id = self._next_id
            self._messages.append(_Message(
                msg_id=msg_id,
                role=role,
                content=content or "",
                parent_id=parent_id,
                tokens=_estimate_tokens(content or ""),
            ))
            return msg_id

    def total_tokens(self) -> int:
        """Total tokens: summary + all messages in window."""
        with self._lock:
            msg_tokens = sum(m.tokens for m in self._messages)
            return self.summary_tokens + msg_tokens

    def needs_compression(self) -> bool:
        """True if total tokens exceed the budget."""
        return self.total_tokens() > self.token_budget

    async def maybe_compress(self) -> bool:
        """Compress oldest messages into the summary if budget exceeded.

        Returns True if compression happened.
        """
        if self.compress_fn is None:
            return False

        with self._lock:
            total = self.summary_tokens + sum(m.tokens for m in self._messages)
            if total <= self.token_budget:
                return False

            # Calculate how many tokens we need to free
            # Target: fit within 80% of budget to avoid compressing every turn
            target = int(self.token_budget * 0.8)
            excess = total - target

            # Split: old messages to compress, recent to keep
            accumulated = 0
            split_idx = 0
            for i, m in enumerate(self._messages):
                accumulated += m.tokens
                if accumulated >= excess:
                    split_idx = i + 1
                    break
            else:
                # All messages needed — keep at least the last 2
                split_idx = max(0, len(self._messages) - 2)

            if split_idx == 0:
                return False

            old_messages = self._messages[:split_idx]
            self._messages = self._messages[split_idx:]

        # Compress outside the lock (LLM call)
        old_dicts = [
            {"role": m.role, "content": m.content}
            for m in old_messages
        ]
        try:
            new_summary = await self.compress_fn(old_dicts, self.summary)
        except Exception:
            logger.warning("Compression failed, keeping old summary", exc_info=True)
            # Put old messages back
            with self._lock:
                self._messages = old_messages + self._messages
            return False

        with self._lock:
            self.summary = new_summary
            self.summary_tokens = _estimate_tokens(new_summary)
            self._compressed_count += len(old_messages)

        logger.info(
            "Compressed %d messages for session %s (total compressed: %d, summary tokens: %d)",
            len(old_messages), self.session_id, self._compressed_count, self.summary_tokens,
        )
        return True

    # ── Read ─────────────────────────────────────────────────────────

    def get_context(self) -> list[dict[str, Any]]:
        """Return the final context for the LLM.

        Returns a list of ``{role, content}`` dicts:
        - If there's a summary, it appears as a ``system`` message first.
        - Then all messages in the current sliding window.
        """
        with self._lock:
            result: list[dict[str, Any]] = []
            if self.summary.strip():
                result.append({"role": "system", "content": self.summary})
            for m in self._messages:
                result.append({"role": m.role, "content": m.content})
            return result

    def get_messages_for_context(
        self,
        leaf_message_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw messages (without summary) for backward compat."""
        with self._lock:
            if leaf_message_id is None:
                return [
                    {"id": m.msg_id, "role": m.role, "content": m.content}
                    for m in self._messages
                ]
            # Branch-aware walk
            chain: list[dict[str, Any]] = []
            current = leaf_message_id
            safety = 10_000
            while current is not None and safety > 0:
                msg = self._find_by_id(current)
                if msg is None:
                    break
                chain.append({"id": msg.msg_id, "role": msg.role, "content": msg.content})
                current = msg.parent_id
                safety -= 1
            chain.reverse()
            return chain

    # ── Flush support ────────────────────────────────────────────────

    def get_pending_flush(self) -> list[dict[str, Any]]:
        """Return messages not yet flushed to SQLite."""
        with self._lock:
            return [
                {
                    "msg_id": m.msg_id,
                    "role": m.role,
                    "content": m.content,
                    "parent_id": m.parent_id,
                }
                for m in self._messages
                if not m.flushed
            ]

    def mark_flushed(self, msg_ids: set[int]) -> None:
        """Mark messages as flushed to SQLite."""
        with self._lock:
            for m in self._messages:
                if m.msg_id in msg_ids:
                    m.flushed = True

    # ── Internal ─────────────────────────────────────────────────────

    def _find_by_id(self, msg_id: int) -> _Message | None:
        for m in self._messages:
            if m.msg_id == msg_id:
                return m
        return None

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def total_compressed(self) -> int:
        return self._compressed_count


__all__ = ["ConversationBuffer", "DEFAULT_TOKEN_BUDGET"]
