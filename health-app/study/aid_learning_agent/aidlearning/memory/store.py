"""四层记忆子系统的高层门面。

所有调用方 — API 路由、LLM 工具、表面事件钩子 — 都通过 :class:`MemoryStore` 访问。
该存储是无状态的；用户隔离通过 :func:`paths.memory_root` 继承，
该函数通过上下文变量延迟解析 :class:`PathService`。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil
from typing import Literal

from aidlearning.memory import consolidator
from aidlearning.memory.shared import paths, trace
from aidlearning.memory.consolidator import ConsolidateResult, OnEvent
from aidlearning.memory.long_term.document import Document, parse, serialize
from aidlearning.memory.long_term.ops import AddOp, ApplyReport, EditOp
from aidlearning.memory.long_term.ops import apply as ops_apply
from aidlearning.memory.shared.paths import L3Slot, Surface
from aidlearning.memory.shared.trace import TraceEvent

logger = logging.getLogger(__name__)

Layer = Literal["L2", "L3"]

_V1_FILES = ("PROFILE.md", "SUMMARY.md")
_NO_MEMORY = (
    "(No memory available — interact with AidLearning and update from the Memory page to build one.)"
)


@dataclass
class DocOverview:
    layer: Layer
    key: str  # surface 名称 (L2) 或 slot 名称 (L3)
    exists: bool
    updated_at: str | None
    entry_count: int
    backlog: int  # 上次更新以来的 L1 事件数（仅 L2；L3 为 0）


class MemoryStore:
    """无状态门面。可安全用作进程级单例。"""

    def __init__(self) -> None:
        self._write_locks: dict[str, asyncio.Lock] = {}

    # ── L1 层 ────────────────────────────────────────────────────────────────

    async def emit(self, event: TraceEvent) -> None:
        await trace.append(event)

    # ── L2 / L3 读取 ──────────────────────────────────────────────────────

    def read_doc(self, layer: Layer, key: str) -> Document:
        path = self._path(layer, key)
        if not path.exists():
            return Document(title=_default_title(layer, key))
        return parse(path.read_text(encoding="utf-8"))

    def read_raw(self, layer: Layer, key: str) -> str:
        path = self._path(layer, key)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def read_l3_concat(self) -> str:
        """拼接全部四个 L3 文档，供 ``read_memory`` 工具使用。"""
        parts: list[str] = []
        for slot in paths.L3_SLOTS:
            body = self.read_raw("L3", slot).strip()
            if body:
                parts.append(body)
        if not parts:
            return _NO_MEMORY
        return "\n\n---\n\n".join(parts) + "\n"

    # ── L2 / L3 写入（手动路径）──────────────────────────────────────────────

    async def overwrite_doc(self, layer: Layer, key: str, md: str) -> None:
        """从工作台编辑器直接由用户驱动的保存。"""
        path = self._path(layer, key)
        async with self._lock_for(path):
            await asyncio.to_thread(_atomic_write, path, md)

    async def delete_entry(self, layer: Layer, key: str, entry_id: str) -> bool:
        path = self._path(layer, key)
        if not path.exists():
            return False
        async with self._lock_for(path):
            doc = parse(path.read_text(encoding="utf-8"))
            if not doc.remove(entry_id):
                return False
            await asyncio.to_thread(_atomic_write, path, serialize(doc))
            return True

    # ── L2 / L3 写入（整合器路径）───────────────────────────────────────

    async def update_l2(
        self,
        surface: Surface,
        *,
        language: str = "en",
        user_label: str = "anonymous",
        on_event: OnEvent | None = None,
        apply_ops: bool = True,
    ) -> ConsolidateResult:
        path = paths.l2_file(surface)
        async with self._lock_for(path):
            return await consolidator.consolidate_l2(
                surface,
                language=language,
                user_label=user_label,
                on_event=on_event,
                apply_ops=apply_ops,
            )

    async def update_l3(
        self,
        slot: L3Slot,
        *,
        language: str = "en",
        user_label: str = "anonymous",
        on_event: OnEvent | None = None,
        apply_ops: bool = True,
    ) -> ConsolidateResult:
        if slot == "preferences":
            raise ValueError("preferences.md is not auto-consolidated")
        path = paths.l3_file(slot)
        async with self._lock_for(path):
            return await consolidator.consolidate_l3(
                slot,
                language=language,
                user_label=user_label,
                on_event=on_event,
                apply_ops=apply_ops,
            )

    async def apply_ops_payload(
        self, layer: Layer, key: str, ops_payload: list[dict]
    ) -> ApplyReport:
        """将 JSON 格式的操作列表原子性地应用到层文档。

        用于工作台的预览→应用两步流程。该 payload 通常来自
        之前的 ``apply_ops=False`` 整合调用，呈现给用户进行审查。
        """
        from aidlearning.memory.consolidator import _parse_ops_response

        path = self._path(layer, key)
        json_like = {"ops": ops_payload}
        import json as _json

        ops = _parse_ops_response(_json.dumps(json_like, ensure_ascii=False))
        async with self._lock_for(path):
            default_title = _default_title(layer, key)
            doc = (
                parse(path.read_text(encoding="utf-8"))
                if path.exists()
                else Document(title=default_title)
            )
            report = ops_apply(doc, ops)
            if report.accepted and ops:
                path.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(_atomic_write, path, serialize(doc))
            return report

    async def write_preference(
        self,
        *,
        op: Literal["add", "edit"],
        text: str,
        target_id: str | None = None,
        reason: str | None = None,
        trace_id: str,
    ) -> ApplyReport:
        """写入聊天模式的偏好信号。``write_memory`` 工具是唯一调用方；
        ``trace_id`` 是运行时注入的当前聊天轮次的 L1 id。"""
        path = paths.l3_file("preferences")
        async with self._lock_for(path):
            doc = (
                parse(path.read_text(encoding="utf-8"))
                if path.exists()
                else Document(title=_default_title("L3", "preferences"))
            )
            section = "Preferences"
            if op == "add":
                report = ops_apply(
                    doc,
                    [AddOp(section=section, text=text, refs=[trace_id])],
                )
            else:
                if not target_id:
                    return ApplyReport(accepted=False, reason="edit requires target_id")
                report = ops_apply(
                    doc,
                    [
                        EditOp(
                            target_id=target_id,
                            new_text=text,
                            new_refs=[trace_id],
                        )
                    ],
                )
            if report.accepted:
                await asyncio.to_thread(_atomic_write, path, serialize(doc))
            if reason:
                # 在日志中记录原因，便于工作台可观测性。
                logger.info("write_memory %s id=%s reason=%s", op, target_id or "new", reason)
            return report

    # ── 智能检索（中期+长期记忆）─────────────────────────────────────

    async def retrieve_memory(
        self,
        query: str,
        *,
        top_k: int = 10,
        token_budget: int = 2000,
    ) -> str:
        """结合中期和长期记忆的智能检索。

        替代 ``read_l3_concat()`` 作为主要的上下文注入方法。
        失败时回退到完整的 L3 拼接。
        """
        from aidlearning.memory.mid_term.search import get_memory_retriever
        from aidlearning.services.session.sqlite_store import get_sqlite_session_store

        retriever = get_memory_retriever(
            sqlite_store=get_sqlite_session_store(),
            long_term_store=self,
        )
        if retriever is None:
            return self.read_l3_concat()
        return await retriever.retrieve(query, top_k=top_k, token_budget=token_budget)

    # ── 工作台概览 ─────────────────────────────────────────────────────────

    def overview(self) -> list[DocOverview]:
        rows: list[DocOverview] = []
        for target in paths.L2_TARGETS:
            rows.append(self._overview_for("L2", target))
        for slot in paths.L3_SLOTS:
            rows.append(self._overview_for("L3", slot))
        return rows

    def _overview_for(self, layer: Layer, key: str) -> DocOverview:
        path = self._path(layer, key)
        if not path.exists():
            backlog = trace.count_since(key) if layer == "L2" else 0  # type: ignore[arg-type]
            return DocOverview(
                layer=layer,
                key=key,
                exists=False,
                updated_at=None,
                entry_count=0,
                backlog=backlog,
            )

        stat = path.stat()
        updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        try:
            doc = parse(path.read_text(encoding="utf-8"))
            entry_count = len(doc.all_entries())
        except Exception:
            entry_count = 0

        backlog = 0
        if layer == "L2":
            try:
                cutoff = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                backlog = trace.count_since(key, since=cutoff)  # type: ignore[arg-type]
            except Exception:
                backlog = 0

        return DocOverview(
            layer=layer,
            key=key,
            exists=True,
            updated_at=updated_at,
            entry_count=entry_count,
            backlog=backlog,
        )

    # ── 内部方法 ─────────────────────────────────────────────────────────

    def _path(self, layer: Layer, key: str) -> Path:
        if layer == "L2":
            if key not in paths.SURFACES:
                raise ValueError(f"unknown surface {key!r}")
            return paths.l2_file(key)  # type: ignore[arg-type]
        if key not in paths.L3_SLOTS:
            raise ValueError(f"unknown L3 slot {key!r}")
        return paths.l3_file(key)  # type: ignore[arg-type]

    def _lock_for(self, path: Path) -> asyncio.Lock:
        key = str(path)
        lock = self._write_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._write_locks[key] = lock
        return lock


# ── v1 → v2 启动迁移 ─────────────────────────────────────────────────────


def migrate_v1_if_needed() -> Path | None:
    """如果记忆根目录下存在 v1 格式的记忆文件，
    将整个记忆目录的散文件移动到 ``memory/backup/<ts>/``。

    幂等操作：如果根目录下没有 v1 格式的文件，则不执行任何操作。

    迁移时返回备份目录路径，否则返回 ``None``。
    """
    root = paths.memory_root()
    if not root.exists():
        return None
    v1_present = [name for name in _V1_FILES if (root / name).exists()]
    if not v1_present:
        return None

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = paths.backup_root() / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    for item in list(root.iterdir()):
        if item.name in {"trace", "L2", "L3", "backup"}:
            continue
        try:
            shutil.move(str(item), str(backup_dir / item.name))
        except OSError:
            logger.warning("v1 memory migration: failed to move %s", item, exc_info=True)
    logger.info("v1 memory migrated to %s", backup_dir)
    return backup_dir


# ── 单例访问器 ────────────────────────────────────────────────────────────


_singleton: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _singleton
    if _singleton is None:
        _singleton = MemoryStore()
    return _singleton


# ── 辅助函数 ───────────────────────────────────────────────────────────────


def _default_title(layer: Layer, key: str) -> str:
    if layer == "L2":
        return f"{key} memory"
    return {
        "recent": "Recent summary",
        "profile": "User profile",
        "scope": "Knowledge scope",
        "preferences": "Preferences",
    }.get(key, key)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
