"""Global buffer manager — one ``ConversationBuffer`` per session.

Buffers are created on first access and kept alive for the process
lifetime.  On first access for a session, existing messages are loaded
from SQLite so the buffer has a complete history.

The manager provides a default ``compress_fn`` that uses the LLM to
compress old messages into a summary.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aidlearning.memory.short_term.conversation_buffer import (
    ConversationBuffer,
    DEFAULT_TOKEN_BUDGET,
    _Message,
    _estimate_tokens,
)

logger = logging.getLogger(__name__)


async def _default_compress_fn(
    old_messages: list[dict[str, Any]],
    existing_summary: str,
) -> str:
    """Default compression: call LLM to summarize old messages.

    Uses the same prompt as the old ``_ContextSummaryAgent``.
    """
    from aidlearning.services.llm import complete as llm_complete

    parts: list[str] = []
    if existing_summary.strip():
        parts.append(f"Existing summary:\n{existing_summary}")

    transcript_lines: list[str] = []
    for msg in old_messages:
        role = msg.get("role", "user").capitalize()
        content = str(msg.get("content", "") or "").strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    if transcript_lines:
        parts.append("Older turns to fold in:\n" + "\n\n".join(transcript_lines))

    source_text = "\n\n".join(parts)
    if not source_text.strip():
        return existing_summary

    system_prompt = (
        "你负责把对话历史压缩成后续轮次可直接使用的上下文。保留用户目标、约束、已做决定、"
        "未解决问题，以及能力切换带来的关键信息。总结要忠实、紧凑，不要虚构。"
    )
    user_prompt = (
        f"请把下面的对话历史压缩为简洁摘要，供后续对话直接继承上下文。\n\n"
        f"{source_text}"
    )

    try:
        response = await llm_complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
        )
        return response.strip() if response else existing_summary
    except Exception:
        logger.warning("LLM compression failed", exc_info=True)
        return existing_summary


class BufferManager:
    """Process-wide manager for per-session conversation buffers."""

    def __init__(
        self,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        compress_fn: Any | None = None,
    ) -> None:
        self._token_budget = token_budget
        self._compress_fn = compress_fn or _default_compress_fn
        self._buffers: dict[str, ConversationBuffer] = {}
        self._initialized: set[str] = set()

    async def get_or_create(
        self,
        session_id: str,
        sqlite_store: Any | None = None,
    ) -> ConversationBuffer:
        """Return the buffer for *session_id*, creating and hydrating if needed."""
        buf = self._buffers.get(session_id)
        if buf is None:
            buf = ConversationBuffer(
                session_id=session_id,
                token_budget=self._token_budget,
                compress_fn=self._compress_fn,
            )
            self._buffers[session_id] = buf

        if session_id not in self._initialized and sqlite_store is not None:
            await self._hydrate_from_sqlite(session_id, buf, sqlite_store)
            self._initialized.add(session_id)

        return buf

    def has_buffer(self, session_id: str) -> bool:
        return session_id in self._buffers

    def remove(self, session_id: str) -> None:
        """Drop the buffer for a session."""
        self._buffers.pop(session_id, None)
        self._initialized.discard(session_id)

    async def _hydrate_from_sqlite(
        self,
        session_id: str,
        buf: ConversationBuffer,
        sqlite_store: Any,
    ) -> None:
        """Load buffer state from SQLite, restoring the exact window."""
        try:
            # Try loading saved buffer state first
            state = await sqlite_store.load_buffer_state(session_id)

            if state and state.get("window_message_ids"):
                # Restore from saved buffer state
                buf.summary = state.get("summary", "")
                buf.summary_tokens = state.get("summary_tokens", 0)
                buf._compressed_count = state.get("compressed_count", 0)

                window_ids = state["window_message_ids"]
                messages = await sqlite_store.get_messages_for_context(session_id)
                msg_map = {m["id"]: m for m in messages}

                for mid in window_ids:
                    msg = msg_map.get(mid)
                    if msg:
                        content = msg["content"] or ""
                        with buf._lock:
                            buf._next_id = max(buf._next_id, mid)
                            buf._messages.append(_Message(
                                msg_id=mid,
                                role=msg["role"],
                                content=content,
                                parent_id=msg.get("parent_message_id"),
                                tokens=_estimate_tokens(content),
                                flushed=True,
                            ))

                logger.debug(
                    "Restored buffer for session %s: %d messages, summary=%d tokens",
                    session_id, len(buf._messages), buf.summary_tokens,
                )
                return

            # Fallback: load from sessions table + messages table
            session = await sqlite_store.get_session(session_id)
            if session:
                buf.summary = str(session.get("compressed_summary", "") or "").strip()
                buf.summary_tokens = _estimate_tokens(buf.summary)

            messages = await sqlite_store.get_messages_for_context(session_id)
            for msg in messages:
                real_id = msg["id"]
                content = msg["content"] or ""
                with buf._lock:
                    buf._next_id = max(buf._next_id, real_id)
                    buf._messages.append(_Message(
                        msg_id=real_id,
                        role=msg["role"],
                        content=content,
                        parent_id=msg.get("parent_message_id"),
                        tokens=_estimate_tokens(content),
                        flushed=True,
                    ))

            # Remove messages already covered by summary
            session_data = await sqlite_store.get_session(session_id)
            if session_data:
                summary_up_to = int(session_data.get("summary_up_to_msg_id", 0) or 0)
                if summary_up_to > 0:
                    with buf._lock:
                        original = len(buf._messages)
                        buf._messages = [m for m in buf._messages if m.msg_id > summary_up_to]
                        buf._compressed_count = original - len(buf._messages)

            logger.debug(
                "Hydrated buffer for session %s: %d messages, summary_len=%d",
                session_id, len(buf._messages), len(buf.summary),
            )
        except Exception:
            logger.warning("Failed to hydrate buffer for session %s", session_id, exc_info=True)

    async def flush(self, session_id: str, sqlite_store: Any) -> None:
        """Flush pending messages and buffer state to SQLite."""
        buf = self._buffers.get(session_id)
        if buf is None:
            return

        pending = buf.get_pending_flush()
        flushed_ids: set[int] = set()

        if pending:
            for msg in pending:
                try:
                    await sqlite_store.add_message(
                        session_id=session_id,
                        role=msg["role"],
                        content=msg["content"],
                        parent_message_id=msg["parent_id"],
                    )
                    flushed_ids.add(msg["msg_id"])
                except Exception:
                    logger.warning("Failed to flush msg %s", msg["msg_id"], exc_info=True)
                    break

            if flushed_ids:
                buf.mark_flushed(flushed_ids)

        # Persist summary to sessions table
        if buf.summary:
            try:
                await sqlite_store.update_summary(
                    session_id, buf.summary, buf._compressed_count
                )
            except Exception:
                logger.warning("Failed to persist summary", exc_info=True)

        # Persist buffer window state
        try:
            with buf._lock:
                window_ids = [m.msg_id for m in buf._messages]
            await sqlite_store.save_buffer_state(
                session_id=session_id,
                summary=buf.summary,
                summary_tokens=buf.summary_tokens,
                compressed_count=buf._compressed_count,
                window_message_ids=window_ids,
            )
        except Exception:
            logger.warning("Failed to persist buffer state", exc_info=True)


# ── Singleton ──────────────────────────────────────────────────────────

_manager: BufferManager | None = None


def get_buffer_manager() -> BufferManager:
    global _manager
    if _manager is None:
        _manager = BufferManager()
    return _manager


def reset_buffer_manager() -> None:
    global _manager
    _manager = None


__all__ = ["BufferManager", "get_buffer_manager", "reset_buffer_manager"]
