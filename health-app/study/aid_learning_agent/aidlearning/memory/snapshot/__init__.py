"""L1 记忆的工作区快照子系统。

公共 API：

- :func:`read_snapshot` — surface 的当前实体（不操作 ``state.json`` / ``changes.jsonl``）。
- :func:`refresh_snapshot` — 重新读取工作区，与上次持久化状态对比差异，
  追加变更，持久化新状态。返回计算的变更列表。
  幂等：无变更的刷新不向变更日志写入任何内容。
- :func:`read_changes` — 一个 surface 的过去刷新的分页历史
  （git-log 风格的展示来源）。
- :func:`current_state` — surface 的已持久化 ``state.json``
  （整合器使用 ``last_refresh`` 来控制 L2 更新）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from aidlearning.memory.shared.paths import Surface
from aidlearning.memory.snapshot import adapters, store
from aidlearning.memory.snapshot.diff import diff_snapshots
from aidlearning.memory.snapshot.entity import ChangeEntry, Entity


def read_snapshot(surface: Surface) -> list[Entity]:
    return adapters.read_entities(surface)


def pending_changes(surface: Surface, entities: list[Entity] | None = None) -> list[ChangeEntry]:
    """计算当前工作区与上次持久化状态之间的差异。

    纯只读：从不写入 ``state.json`` 或 ``changes.jsonl``。
    L1 视图用于显示"刷新现在会捕获什么"。
    """
    if entities is None:
        entities = adapters.read_entities(surface)
    curr_fp = {e.id: e.fingerprint for e in entities}
    curr_labels = {e.id: e.label for e in entities}

    prev = store.load_state(surface)
    prev_fp = prev.get("fingerprints") or {}
    prev_labels = prev.get("labels") or {}

    return diff_snapshots(
        prev_fp,
        curr_fp,
        label_map=curr_labels,
        prev_label_map=prev_labels,
    )


def refresh_snapshot(surface: Surface) -> list[ChangeEntry]:
    entities = adapters.read_entities(surface)
    changes = pending_changes(surface, entities)
    curr_fp = {e.id: e.fingerprint for e in entities}
    curr_labels = {e.id: e.label for e in entities}
    store.append_changes(surface, changes)
    store.save_state(
        surface,
        fingerprints=curr_fp,
        labels=curr_labels,
        last_refresh=datetime.now(tz=timezone.utc).isoformat(),
    )
    return changes


def read_changes(surface: Surface, *, limit: int = 200, offset: int = 0) -> list[ChangeEntry]:
    bound = max(1, min(limit, 1000))
    all_changes: list[ChangeEntry] = list(store.iter_changes(surface))
    # 最近的优先 — 文件是追加顺序，反转它。
    all_changes.reverse()
    return all_changes[offset : offset + bound]


def current_state(surface: Surface) -> dict:
    return store.load_state(surface)


def clear_changes(surface: Surface) -> None:
    store.clear_changes(surface)


__all__ = [
    "Entity",
    "ChangeEntry",
    "read_snapshot",
    "pending_changes",
    "refresh_snapshot",
    "read_changes",
    "current_state",
    "clear_changes",
    "adapters",
]


# Iterable 保留以满足静态分析器，当消费者使用 import * 时。
_: Iterable = []
