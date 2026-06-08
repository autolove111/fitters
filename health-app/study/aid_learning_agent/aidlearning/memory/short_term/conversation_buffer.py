"""每会话内存对话缓冲区，带滑动窗口 + 摘要。

这是核心短期记忆。它在滑动窗口中保存最近的消息，
当 token 预算超出时自动将旧消息压缩为摘要。

用法::

    buffer = ConversationBuffer("session_123", token_budget=2000)
    buffer.append("user", "帮我讲讲微积分")
    buffer.append("assistant", "微积分是...")

    # 当总 token 超出 token_budget 时，旧消息自动压缩到摘要中。

    context = buffer.get_context()
    # → [{"role": "system", "content": "摘要..."}, 最近的消息...]

不再需要 ``ContextBuilder`` — 缓冲区本身就是上下文。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# 对话窗口的默认 token 预算
DEFAULT_TOKEN_BUDGET = 1200

# 压缩回调类型：接收旧消息，返回摘要文本
CompressFn = Callable[[list[dict[str, Any]], str], Awaitable[str]]


def _estimate_tokens(text: str) -> int:
    """估算 token 数。每 2 个 CJK 字符约 1 个 token，每 4 个拉丁字符约 1 个 token。"""
    if not text:
        return 0
    cjk = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - cjk
    return (cjk // 2) + (other // 4) + 1


@dataclass
class _Message:
    """缓冲区中的一条消息。"""
    msg_id: int
    role: str
    content: str
    parent_id: int | None = None
    tokens: int = 0  # 估算的 token 数
    # 刷新到 SQLite 后设置
    flushed: bool = False


class ConversationBuffer:
    """内存滑动窗口对话缓冲区。

    参数
    ----------
    session_id : str
        此缓冲区所属的会话。
    start_id : int
        SQLite 中已有的最大消息 ID（新会话为 0）。
        新消息从 ``start_id + 1`` 开始分配 ID。
    token_budget : int
        对话窗口的最大 token 数。当总 token 超出此值时，
        最旧的消息被压缩到摘要中。
    compress_fn : CompressFn | None
        异步函数 ``(old_messages, existing_summary) -> new_summary``。
        自动压缩所需。如果为 None，压缩被跳过（缓冲区无界增长）。
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

        # 已压缩旧消息的摘要
        self.summary: str = ""
        self.summary_tokens: int = 0
        # 已压缩到摘要中的消息数量
        self._compressed_count: int = 0

    # ── 写入 ────────────────────────────────────────────────────────

    def append(
        self,
        role: str,
        content: str,
        parent_id: int | None = None,
    ) -> int:
        """向缓冲区添加一条消息。返回分配的 ID。

        不触发压缩 — 单独调用 :meth:`maybe_compress`（它是异步的）。
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
        """总 token 数：摘要 + 窗口中的所有消息。"""
        with self._lock:
            msg_tokens = sum(m.tokens for m in self._messages)
            return self.summary_tokens + msg_tokens

    def needs_compression(self) -> bool:
        """如果总 token 超出预算则返回 True。"""
        return self.total_tokens() > self.token_budget

    async def maybe_compress(self) -> bool:
        """如果预算超出，将最旧的消息压缩到摘要中。

        如果发生了压缩则返回 True。
        """
        if self.compress_fn is None:
            return False

        with self._lock:
            total = self.summary_tokens + sum(m.tokens for m in self._messages)
            if total <= self.token_budget:
                return False

            # 计算需要释放多少 token
            # 目标：控制在预算的 80% 以内，以避免每轮都压缩
            target = int(self.token_budget * 0.8)
            excess = total - target

            # 分割：要压缩的旧消息，要保留的最近消息
            accumulated = 0
            split_idx = 0
            for i, m in enumerate(self._messages):
                accumulated += m.tokens
                if accumulated >= excess:
                    split_idx = i + 1
                    break
            else:
                # 所有消息都需要 — 至少保留最后 2 条
                split_idx = max(0, len(self._messages) - 2)

            if split_idx == 0:
                return False

            old_messages = self._messages[:split_idx]
            self._messages = self._messages[split_idx:]

        # 在锁外压缩（LLM 调用）
        old_dicts = [
            {"role": m.role, "content": m.content}
            for m in old_messages
        ]
        try:
            new_summary = await self.compress_fn(old_dicts, self.summary)
        except Exception:
            logger.warning("Compression failed, keeping old summary", exc_info=True)
            # 将旧消息放回
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

    # ── 读取 ─────────────────────────────────────────────────────────

    def get_context(self) -> list[dict[str, Any]]:
        """返回 LLM 的最终上下文。

        返回 ``{role, content}`` 字典列表：
        - 如果有摘要，它首先作为 ``system`` 消息出现。
        - 然后是当前滑动窗口中的所有消息。
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
        """返回原始消息（不含摘要），用于向后兼容。"""
        with self._lock:
            if leaf_message_id is None:
                return [
                    {"id": m.msg_id, "role": m.role, "content": m.content}
                    for m in self._messages
                ]
            # 分支感知遍历
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

    # ── 刷新支持 ────────────────────────────────────────────────

    def get_pending_flush(self) -> list[dict[str, Any]]:
        """返回尚未刷新到 SQLite 的消息。"""
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
        """将消息标记为已刷新到 SQLite。"""
        with self._lock:
            for m in self._messages:
                if m.msg_id in msg_ids:
                    m.flushed = True

    # ── 内部方法 ─────────────────────────────────────────────────────

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
