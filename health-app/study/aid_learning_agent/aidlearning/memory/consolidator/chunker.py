"""基于字符的分块与边界扩展。

L2 / L3 更新流程将输入拼接为一个字符串，
然后 :func:`chunk_with_boundary` 将其切割为不超过 budget 个片段。
每个片段的右边界向前扩展到下一个段落或句子边界 — 内容**绝不会在语句中间截断**。
相邻块按目标大小的百分比重叠，使得跨越切口的事实仍能被完整读取。

纯函数：无 I/O，无 LLM。易于单元测试。
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Literal

Boundary = Literal["paragraph", "sentence"]

# 段落边界：一个或多个空行。
_PARA_BOUNDARY = re.compile(r"\n\s*\n+")
# 句子边界：结尾标点后跟空格/换行。
# 覆盖 ASCII (.!?) 和 CJK (。！？)。
_SENT_BOUNDARY = re.compile(r"[.!?。！？](?:[\")»」』]+)?(?=\s|$)")


@dataclass(frozen=True)
class ChunkSpan:
    """一个块在源文本中的坐标。

    ``start`` 包含，``end`` 不包含。``index`` 是返回列表中的从 0 开始的位置（用于事件）。
    """

    index: int
    start: int
    end: int
    text: str


def chunk_with_boundary(
    text: str,
    *,
    budget: int,
    overlap_ratio: float,
    min_chunk_chars: int,
    max_chunk_chars: int,
    boundary: Boundary = "paragraph",
) -> list[ChunkSpan]:
    """将 ``text`` 切割为不超过 ``budget`` 个对齐到自然边界的块。

    * 目标大小 = ``clamp(ceil(len(text) / budget), min, max)``。
    * 每个块的右边界向前扩展到下一个 ``boundary``，以避免句子/段落被拆分。
    * 相邻块重叠 ``round(target * overlap_ratio)`` 个字符。
    * 如果输入足够短可以放入单个块，返回一个覆盖全部内容的 ``ChunkSpan``。
    """
    if not text.strip():
        return []
    if budget < 1:
        budget = 1

    n = len(text)
    target = math.ceil(n / budget)
    target = max(min_chunk_chars, min(max_chunk_chars, target))
    overlap = max(0, min(target - 1, round(target * overlap_ratio)))

    # 快速路径：输入可以放入单个块。
    if n <= target:
        return [ChunkSpan(index=0, start=0, end=n, text=text)]

    # 右边界可以被拉伸以查找边界的硬性上限。
    # 超过此限制则接受非边界切割，以确保即使在退化输入中
    # （例如无段落/句子分隔的单行长文本），块也不会超过 ``max_chunk_chars``。
    spans: list[ChunkSpan] = []
    cursor = 0
    while cursor < n:
        target_end = min(n, cursor + target)
        hard_cap = min(n, cursor + max_chunk_chars)
        if target_end >= n:
            end = n
        else:
            end = _expand_to_boundary(text, target_end, boundary, limit=hard_cap)
        # 保证前进：边界扩展可能将我们拉到 len(text)，或在退化输入中拉到 ``target_end`` 本身。
        if end <= cursor:
            end = min(n, cursor + max(1, target))
        spans.append(
            ChunkSpan(
                index=len(spans),
                start=cursor,
                end=end,
                text=text[cursor:end],
            )
        )
        if end >= n:
            break
        next_cursor = end - overlap
        # 防止无限循环：即使重叠很大，也必须至少前进一个字符。
        if next_cursor <= cursor:
            next_cursor = cursor + 1
        cursor = next_cursor

    return spans


# ── 内部函数 ───────────────────────────────────────────────────────────


def _expand_to_boundary(text: str, target_end: int, boundary: Boundary, *, limit: int) -> int:
    """将 ``target_end`` 向前推到下一个自然边界。

    搜索受 ``limit``（不包含）限制。如果在该窗口内未找到边界，
    函数返回 ``limit`` — 虽非边界切割，但有界。
    没有此限制的话，在无段落/句子标记的病态文本上，
    分块器可能将单个块膨胀到输入末尾。
    """
    pattern = _PARA_BOUNDARY if boundary == "paragraph" else _SENT_BOUNDARY
    match = pattern.search(text, target_end, limit)
    if match is None:
        return limit
    return match.end()


__all__ = ["Boundary", "ChunkSpan", "chunk_with_boundary"]
