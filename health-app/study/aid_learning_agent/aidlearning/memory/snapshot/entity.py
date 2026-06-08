"""快照数据类型。

``Entity`` 是非 KB surface 的一个 L1 内容单元 — 例如一个笔记本记录、
一个协作文档、一本书、一个聊天会话。
快照是磁盘上这些内容的*当前*集合；差异日志记录该集合在刷新间的变化。

这些类型有意设计为无 I/O 的纯 dataclass。
适配器构建 ``Entity`` 列表；``diff.diff_snapshots`` 消费两个 ``state``
字典以产生 ``ChangeEntry`` 记录。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class Entity:
    id: str
    label: str
    ts: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ChangeKind = Literal["added", "modified", "removed"]


@dataclass
class ChangeEntry:
    ts: str
    kind: ChangeKind
    entity_id: str
    label: str
    prev_fingerprint: str | None = None
    new_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
