"""操作发出守卫：禁用短语过滤器 + 预算。

在操作发出时（循环过程中）运行，以便模型在操作被拒绝时能获得观测反馈并重写。
之前的预重构代码在 LLM 调用一次性返回所有操作后才过滤禁用短语，
这意味着拒绝是静默丢弃。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Iterable

from aidlearning.memory.long_term.ops import Op

logger = logging.getLogger(__name__)

# L3 客观性守卫：LLM 被提示词禁止输出的短语。
# 运行时通过丢弃文本中包含这些短语的 L3 操作来强制执行
# （引用的用户原话 「」 / "…" 中的除外）。记录为警告日志，
# 以便我们可以根据实际的提示词回归来调整列表。
BANNED_PHRASES: tuple[str, ...] = (
    # English absolutes
    "deeply",
    "truly",
    "mastered",
    "expert in",
    "passionate",
    "loves",
    "hates",
    "always",
    "never",
    "fully understands",
    # Chinese absolutes
    "深刻",
    "彻底",
    "完美掌握",
    "完美理解",
    "完全理解",
    "完全掌握",
    "专家",
    "热爱",
    "总是",
    "从来不",
)


# 每轮循环预算。超出后调度器发出提示观测而非执行操作；
# 提示词引导模型完成任务。
@dataclass(frozen=True)
class ToolBudgets:
    read_entity: int = 30
    search: int = 20
    list_pending: int = 50  # 开销低的导航操作，慷慨限制
    list_sections: int = 50
    recent_changes: int = 3
    add_entry: int = 12
    edit_entry: int = 12
    delete_entry: int = 12
    note: int = 8


_QUOTED_RE = re.compile(r"「[^」]*」|\"[^\"]*\"")


def _has_banned(text: str) -> bool:
    """当且仅当禁用短语出现在所有引用之外时返回 ``True``。

    首先剥离引用区域（CJK 「…」 或 ASCII "…"），
    因为提示词允许用户的逐字引用包含被禁止的绝对化表述。
    """
    stripped = _QUOTED_RE.sub("", text).lower()
    for phrase in BANNED_PHRASES:
        if phrase in stripped:
            return True
    return False


def _op_text(op: Op) -> str:
    text = getattr(op, "text", "") or getattr(op, "new_text", "")
    return str(text)


def _filter_banned(ops: Iterable[Op]) -> list[Op]:
    """丢弃文本包含禁用绝对化措辞的操作。

    作为循环后的安全网使用，即使每个操作的发出路径已经拒绝了它们。
    保留按名称调用的方式，以兼容旧测试和 apply_ops_payload 预览/应用往返。
    """
    kept: list[Op] = []
    for op in ops:
        text = _op_text(op)
        if text and _has_banned(text):
            logger.warning(
                "memory consolidate: dropped op with banned phrase: %s",
                text[:80],
            )
            continue
        kept.append(op)
    return kept
