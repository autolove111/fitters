"""L1 原始事件追踪：仅追加的 JSONL 文件，每个 surface 每个 UTC 日一个。

追踪捕获绝不能破坏产生事件的 surface — 每次追加都被包装，
失败被记录并吞掉。写入通过 asyncio 锁按 surface 序列化，
以防止同一进程中的多个轮次交错 JSON 行。
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Iterator

from aidlearning.memory.shared.ids import new_trace_id
from aidlearning.memory.shared.paths import SURFACES, Surface, trace_dir, trace_file

logger = logging.getLogger(__name__)

_locks: dict[str, asyncio.Lock] = {}


def _lock_for(surface: Surface) -> asyncio.Lock:
    lock = _locks.get(surface)
    if lock is None:
        lock = asyncio.Lock()
        _locks[surface] = lock
    return lock


@dataclass
class TraceEvent:
    id: str
    ts: str
    surface: Surface
    kind: str
    payload: dict[str, Any]
    session_id: str | None = None
    turn_id: str | None = None

    @classmethod
    def new(
        cls,
        surface: Surface,
        kind: str,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> "TraceEvent":
        return cls(
            id=new_trace_id(surface),
            ts=datetime.now(tz=timezone.utc).isoformat(),
            surface=surface,
            kind=kind,
            payload=payload,
            session_id=session_id,
            turn_id=turn_id,
        )


async def append(event: TraceEvent) -> None:
    """将一个事件追加到今天的 surface 追踪文件。永不抛出异常。"""
    try:
        path = trace_file(event.surface, datetime.now(tz=timezone.utc).date())
        line = json.dumps(asdict(event), ensure_ascii=False, separators=(",", ":"))
        async with _lock_for(event.surface):
            await asyncio.to_thread(_append_line, path, line)
    except Exception:
        logger.warning(
            "memory trace append failed surface=%s kind=%s",
            event.surface,
            event.kind,
            exc_info=True,
        )


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")


def iter_since(surface: Surface, since: datetime | None = None) -> Iterator[TraceEvent]:
    """按时间顺序产出 ``surface`` 的事件，可选过滤 ``ts >= since`` (UTC) 的事件。"""
    files = sorted(trace_dir(surface).glob("*.jsonl"))
    cutoff_iso = since.isoformat() if since else ""
    cutoff_date_iso = since.date().isoformat() if since else ""
    for path in files:
        if cutoff_date_iso and path.stem < cutoff_date_iso:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if cutoff_iso and obj.get("ts", "") < cutoff_iso:
                        continue
                    yield TraceEvent(**obj)
        except OSError:
            continue


def iter_by_ids(ids: list[str]) -> Iterator[TraceEvent]:
    """将追踪 id 解析回其事件。跨 surface 遍历。"""
    wanted_by_surface: dict[str, set[str]] = {}
    for tid in ids:
        if ":" not in tid:
            continue
        surface, _ = tid.split(":", 1)
        if surface in SURFACES:
            wanted_by_surface.setdefault(surface, set()).add(tid)

    for surface, wanted in wanted_by_surface.items():
        for event in iter_since(surface):  # type: ignore[arg-type]
            if event.id in wanted:
                yield event


def count_since(surface: Surface, since: datetime | None = None) -> int:
    return sum(1 for _ in iter_since(surface, since))


def latest_ts(surface: Surface) -> str | None:
    """``surface`` 的最近事件时间戳，或 None。"""
    files = sorted(trace_dir(surface).glob("*.jsonl"), reverse=True)
    for path in files:
        try:
            last = ""
            with path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if raw:
                        last = raw
            if last:
                obj = json.loads(last)
                ts = obj.get("ts")
                if isinstance(ts, str):
                    return ts
        except (OSError, json.JSONDecodeError):
            continue
    return None
