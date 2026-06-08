"""三层记忆子系统的路径解析。

每用户记忆根目录下的布局::

    trace/<surface>/<YYYY-MM-DD>.jsonl    (L1，仅追加)
    L2/<surface>.md                       (L2，每 surface 摘要)
    L3/<recent|profile|scope|preferences>.md  (L3，跨 surface)
    backup/<timestamp>/...                (v1 迁移归档)

根目录本身通过 :class:`PathService` 解析，
因此多用户上下文 (workspace_root) 在调用时而非导入时获取。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, get_args

from aidlearning.services.path_service import get_path_service

Surface = Literal[
    "chat",
    "notebook",
    "quiz",
    "kb",
    "book",
    "tutorbot",
    "cowriter",
]
L3Slot = Literal["recent", "profile", "scope", "preferences"]

SURFACES: tuple[Surface, ...] = get_args(Surface)
L3_SLOTS: tuple[L3Slot, ...] = get_args(L3Slot)

# ── L2 整合路由 ──────────────────────────────────────────────────
# 全部 7 个 surface 的 L1 事件整合为仅 2 个 L2 文件。
# L2/chat.md: chat, notebook, quiz, book, tutorbot, cowriter
# L2/kb.md:   仅 kb
_L2_TARGET: dict[Surface, str] = {
    "chat": "chat",
    "notebook": "chat",
    "quiz": "chat",
    "kb": "kb",
    "book": "chat",
    "tutorbot": "chat",
    "cowriter": "chat",
}

L2_TARGETS: tuple[str, ...] = ("chat", "kb")


def l2_target(surface: Surface) -> str:
    """将 surface 映射到其 L2 整合目标。

    除 ``kb`` 外的所有 surface 都整合到 ``chat.md``。
    只有 ``kb`` 整合到 ``kb.md``。
    """
    return _L2_TARGET.get(surface, "chat")


def memory_root() -> Path:
    return get_path_service().get_memory_dir()


def trace_dir(surface: Surface) -> Path:
    return memory_root() / "trace" / surface


def trace_file(surface: Surface, day: date) -> Path:
    return trace_dir(surface) / f"{day.isoformat()}.jsonl"


def l2_dir() -> Path:
    return memory_root() / "L2"


def l2_file(surface: Surface) -> Path:
    return l2_dir() / f"{surface}.md"


def l3_dir() -> Path:
    return memory_root() / "L3"


def l3_file(slot: L3Slot) -> Path:
    return l3_dir() / f"{slot}.md"


def backup_root() -> Path:
    return memory_root() / "backup"


def ensure_dirs() -> None:
    """创建目录骨架。幂等操作。"""
    root = memory_root()
    root.mkdir(parents=True, exist_ok=True)
    l2_dir().mkdir(parents=True, exist_ok=True)
    l3_dir().mkdir(parents=True, exist_ok=True)
    for surface in SURFACES:
        trace_dir(surface).mkdir(parents=True, exist_ok=True)
