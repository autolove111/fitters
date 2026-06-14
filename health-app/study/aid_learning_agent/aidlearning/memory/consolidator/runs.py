"""持久化、可取消的整合器运行。

一次"运行"是 :func:`run_update` / :func:`run_audit` / :func:`run_dedup` 的一次调用。
运行由 asyncio 任务拥有；事件通过缓冲环流传输，断开连接的客户端可以通过
向事件端点发送 ``since=<cursor>`` 来重新连接并重放错过的所有内容。

为什么使用内存管理器而非数据库：
- 记忆整合器运行最多持续几分钟。
- 崩溃/重启会清除它们 — 这是可以接受的；文档本身每步都原子写入，
  元数据 id 差异仍然保证重启时"上次刷新以来的新内容"的正确性。

并发规则
-----------------
每个 ``(layer, key)`` 最多一个**活跃**运行。在第一个运行活跃时启动第二个运行
会返回 ``RunBusyError``。一旦运行达到终止状态（``done`` / ``cancelled`` / ``error``），
它将无限期留在注册表中，以便 UI 可以重新连接查看最终追踪；
当 ``_MAX_HISTORY`` 超出时，旧运行按 FIFO 逐出。
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Awaitable, Callable, Literal
import uuid

logger = logging.getLogger(__name__)

RunMode = Literal["update", "audit", "dedup"]
RunStatus = Literal["queued", "running", "cancelled", "done", "error"]

_MAX_EVENTS_PER_RUN = 2000
_MAX_HISTORY = 200


@dataclass
class RunEvent:
    seq: int  # 从 0 开始，每次运行内单调递增
    ts: str  # ISO-8601 UTC
    payload: dict[str, Any]


@dataclass
class UndoCheckpoint:
    id: str
    ts: str
    layer: str
    key: str
    path: str
    existed: bool
    previous_content: str
    action: str
    turn: int | None = None
    label: str | None = None


@dataclass
class Run:
    id: str
    layer: str
    key: str
    mode: RunMode
    params: dict[str, Any]
    language: str
    user_label: str
    status: RunStatus = "queued"
    started_at: str = ""
    ended_at: str | None = None
    error: str | None = None
    events: list[RunEvent] = field(default_factory=list)
    undo_stack: list[UndoCheckpoint] = field(default_factory=list)
    _waiters: list[asyncio.Event] = field(default_factory=list, repr=False)
    _task: asyncio.Task | None = field(default=None, repr=False)
    _cancel_flag: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def active(self) -> bool:
        return self.status in ("queued", "running")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "layer": self.layer,
            "key": self.key,
            "mode": self.mode,
            "params": self.params,
            "language": self.language,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "event_count": len(self.events),
            "undo_count": len(self.undo_stack),
        }


class RunBusyError(RuntimeError):
    """当 (layer, key) 已有活跃运行时抛出。"""


# ContextVar 持有当前运行中的 Run，供任务内运行的处理器使用。
# 模式代码通过 ``modes._runtime.emit`` 间接使用 :func:`emit`；
# 我们安装自己的 on_event 来同时推送到活跃运行。
_current_run: ContextVar[Run | None] = ContextVar("memory_run", default=None)


class RunManager:
    """进程级单例 — 一个管理器拥有所有整合器运行。

    实例在首次调用 :func:`get_run_manager` 时创建。
    """

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._order: list[str] = []  # FIFO 逐出队列
        self._active: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    # ── 查找 ─────────────────────────────────────────────────────────

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def active_for(self, layer: str, key: str) -> Run | None:
        run_id = self._active.get((layer, key))
        if run_id is None:
            return None
        run = self._runs.get(run_id)
        return run if run is not None and run.active else None

    def list_for(self, layer: str | None = None, key: str | None = None) -> list[Run]:
        out: list[Run] = []
        for rid in self._order:
            run = self._runs.get(rid)
            if run is None:
                continue
            if layer is not None and run.layer != layer:
                continue
            if key is not None and run.key != key:
                continue
            out.append(run)
        return out

    # ── 启动 ──────────────────────────────────────────────────────────

    async def start(
        self,
        *,
        layer: str,
        key: str,
        mode: RunMode,
        runner: Callable[[Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]],
        params: dict[str, Any] | None = None,
        language: str = "en",
        user_label: str = "anonymous",
    ) -> Run:
        """注册并启动一个新运行。

        ``runner`` 是一个可等待工厂：接收 ``on_event`` 回调并运行整合器模式。
        管理器将回调连接到事件缓冲区 + 等待器机制。
        """
        async with self._lock:
            if self.active_for(layer, key) is not None:
                raise RunBusyError(f"a run is already in progress for {layer}/{key}")
            run = Run(
                id=uuid.uuid4().hex,
                layer=layer,
                key=key,
                mode=mode,
                params=dict(params or {}),
                language=language,
                user_label=user_label,
                status="queued",
                started_at=_now_iso(),
            )
            self._runs[run.id] = run
            self._order.append(run.id)
            self._active[(layer, key)] = run.id
            self._evict_if_needed()

        run._task = asyncio.create_task(self._drive(run, runner))
        return run

    async def cancel(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None or not run.active:
            return False
        run._cancel_flag.set()
        if run._task is not None and not run._task.done():
            run._task.cancel()
        return True

    async def undo_last(self, run_id: str) -> RunEvent | None:
        """恢复最新运行写入之前的文档快照。"""
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        if run.active:
            raise RunBusyError("cancel the active run before undoing memory edits")
        if not run.undo_stack:
            return None

        checkpoint = run.undo_stack.pop()
        path = Path(checkpoint.path)
        if checkpoint.existed:
            await asyncio.to_thread(_atomic_write, path, checkpoint.previous_content)
        else:
            await asyncio.to_thread(_remove_if_exists, path)

        return await self._emit(
            run,
            {
                "stage": "undo_applied",
                "run_id": run.id,
                "undo_id": checkpoint.id,
                "undo_depth": len(run.undo_stack),
                "layer": checkpoint.layer,
                "key": checkpoint.key,
                "turn": checkpoint.turn,
                "label": checkpoint.label,
                "action": checkpoint.action,
            },
        )

    # ── 事件订阅 ─────────────────────────────────────────────────────

    async def wait_for_events(self, run: Run, *, since: int) -> list[RunEvent]:
        """返回游标之后的事件；阻塞直到新事件到达或运行完成。"""
        if since < 0:
            since = 0
        # 快速路径：事件已缓冲到游标之后。
        if since < len(run.events):
            return run.events[since:]
        if not run.active:
            return []
        waiter = asyncio.Event()
        run._waiters.append(waiter)
        try:
            await waiter.wait()
        finally:
            try:
                run._waiters.remove(waiter)
            except ValueError:
                pass
        if since < len(run.events):
            return run.events[since:]
        return []

    # ── 驱动 ──────────────────────────────────────────────────────────

    async def _drive(
        self,
        run: Run,
        runner: Callable[[Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]],
    ) -> None:
        token = _current_run.set(run)
        run.status = "running"
        await self._emit(run, {"stage": "run_started", "run_id": run.id, "mode": run.mode})
        try:

            async def on_event(evt: dict[str, Any]) -> None:
                await self._emit(run, evt)

            await runner(on_event)
            if run.status == "running":
                run.status = "done"
        except asyncio.CancelledError:
            run.status = "cancelled"
            await self._emit(run, {"stage": "cancelled"})
        except Exception as exc:  # noqa: BLE001
            run.status = "error"
            run.error = str(exc)
            logger.warning(
                "consolidator run failed (id=%s layer=%s key=%s mode=%s): %s",
                run.id,
                run.layer,
                run.key,
                run.mode,
                exc,
                exc_info=True,
            )
            await self._emit(run, {"stage": "error", "message": str(exc)})
        finally:
            run.ended_at = _now_iso()
            await self._emit(run, {"stage": "run_ended", "status": run.status})
            self._active.pop((run.layer, run.key), None)
            # 唤醒所有剩余的等待器，以便它们观察到终止状态。
            for w in list(run._waiters):
                w.set()
            _current_run.reset(token)

    async def _emit(self, run: Run, payload: dict[str, Any]) -> RunEvent:
        event = RunEvent(seq=len(run.events), ts=_now_iso(), payload=payload)
        run.events.append(event)
        if len(run.events) > _MAX_EVENTS_PER_RUN:
            # 丢弃最旧的非元数据事件，但重新编号尾部以保持
            # 单调 seq 稳定 — 客户端使用 seq 来恢复。
            run.events.pop(0)
            for i, ev in enumerate(run.events):
                run.events[i] = RunEvent(seq=i, ts=ev.ts, payload=ev.payload)
        for w in list(run._waiters):
            w.set()
        return event

    def _evict_if_needed(self) -> None:
        while len(self._order) > _MAX_HISTORY:
            old = self._order.pop(0)
            run = self._runs.pop(old, None)
            if run is not None and run.active:
                # 活跃运行受保护，不会被逐出。
                self._runs[old] = run
                self._order.insert(0, old)
                return


_manager: RunManager | None = None


def get_run_manager() -> RunManager:
    global _manager
    if _manager is None:
        _manager = RunManager()
    return _manager


def reset_run_manager_for_tests() -> None:
    global _manager
    _manager = None


def current_run() -> Run | None:
    """返回当前驱动活跃任务的运行（如果有）。

    LLM-IO 事件发射器使用它，以便将每轮 payload 附加到正在调用模型的运行。
    """
    return _current_run.get()


def push_undo_checkpoint(
    *,
    layer: str,
    key: str,
    path: Path,
    existed: bool,
    previous_content: str,
    action: str,
    turn: int | None = None,
    label: str | None = None,
) -> int:
    """在活跃运行上注册每次写入的回滚快照。"""
    run = _current_run.get()
    if run is None:
        return 0
    run.undo_stack.append(
        UndoCheckpoint(
            id=uuid.uuid4().hex,
            ts=_now_iso(),
            layer=layer,
            key=key,
            path=str(path),
            existed=existed,
            previous_content=previous_content,
            action=action,
            turn=turn,
            label=label,
        )
    )
    return len(run.undo_stack)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_str, path)
    finally:
        if os.path.exists(tmp_str):
            try:
                os.remove(tmp_str)
            except OSError:
                pass


def _remove_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


__all__ = [
    "Run",
    "RunBusyError",
    "RunEvent",
    "RunManager",
    "RunMode",
    "RunStatus",
    "UndoCheckpoint",
    "current_run",
    "get_run_manager",
    "push_undo_checkpoint",
    "reset_run_manager_for_tests",
]
