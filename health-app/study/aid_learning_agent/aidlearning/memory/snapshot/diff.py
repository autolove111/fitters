"""两个快照状态之间的纯函数差异。

``state`` 是 ``{entity_id: fingerprint}``。``label_map`` 携带
变更日志的人类可读标题，使我们在渲染历史时不必重新读取工作区状态。
"""

from __future__ import annotations

from datetime import datetime, timezone

from aidlearning.memory.snapshot.entity import ChangeEntry


def diff_snapshots(
    prev: dict[str, str],
    curr: dict[str, str],
    *,
    label_map: dict[str, str],
    prev_label_map: dict[str, str] | None = None,
) -> list[ChangeEntry]:
    """返回 ``prev`` → ``curr`` 的变更列表。

    ``label_map`` 为当前存在的实体提供标签；
    ``prev_label_map``（可选）用于获取已移除实体的标签。
    """
    ts = datetime.now(tz=timezone.utc).isoformat()
    out: list[ChangeEntry] = []
    prev_keys = set(prev)
    curr_keys = set(curr)

    for entity_id in sorted(curr_keys - prev_keys):
        out.append(
            ChangeEntry(
                ts=ts,
                kind="added",
                entity_id=entity_id,
                label=label_map.get(entity_id, entity_id),
                prev_fingerprint=None,
                new_fingerprint=curr[entity_id],
            )
        )
    for entity_id in sorted(prev_keys - curr_keys):
        prior_label = (prev_label_map or {}).get(entity_id, "") or entity_id
        out.append(
            ChangeEntry(
                ts=ts,
                kind="removed",
                entity_id=entity_id,
                label=prior_label,
                prev_fingerprint=prev[entity_id],
                new_fingerprint=None,
            )
        )
    for entity_id in sorted(prev_keys & curr_keys):
        if prev[entity_id] != curr[entity_id]:
            out.append(
                ChangeEntry(
                    ts=ts,
                    kind="modified",
                    entity_id=entity_id,
                    label=label_map.get(entity_id, entity_id),
                    prev_fingerprint=prev[entity_id],
                    new_fingerprint=curr[entity_id],
                )
            )
    return out
