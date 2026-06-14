"""清理模式 — 根据衰减分数移除过时的记忆条目。

此模式识别衰减分数已降至可配置阈值以下的条目，
将其归档+删除或标记为被同节中更新的条目取代。

无需 LLM 调用 — 算法纯粹基于规则。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aidlearning.memory.shared import paths
from aidlearning.memory.consolidator.modes._runtime import (
    OnEvent, emit, load_doc, write_doc_checkpoint,
)
from aidlearning.memory.long_term.decay import compute_decay_score
from aidlearning.memory.long_term.document import Entry
from aidlearning.memory.settings import load_memory_settings

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    layer: str
    key: str
    entries_scanned: int
    entries_archived: int
    entries_deleted: int
    entries_superseded: int


async def run_cleanup(
    layer: str,
    key: str,
    *,
    language: str = "en",
    threshold: float | None = None,
    archive: bool = True,
    on_event: OnEvent | None = None,
) -> CleanupResult:
    """根据衰减分数识别并移除过时的记忆条目。

    参数
    ----------
    layer : str
        "L2" 或 "L3"。
    key : str
        Surface 名称 (L2) 或 slot 名称 (L3)。
    language : str
        提示语言（此处未使用，为 API 一致性保留）。
    threshold : float | None
        衰减分数阈值，低于此值的条目为清理候选。
        默认为 ``settings.decay.cleanup_threshold``。
    archive : bool
        如果为 True，在删除前归档被删除的条目。
    on_event : OnEvent | None
        SSE 事件回调。
    """
    settings = load_memory_settings()
    decay_settings = settings.decay
    threshold = threshold if threshold is not None else decay_settings.cleanup_threshold

    # 加载文档
    if layer == "L2":
        doc_path = paths.l2_file(key)  # type: ignore[arg-type]
        default_title = f"{key} memory"
    else:
        doc_path = paths.l3_file(key)  # type: ignore[arg-type]
        default_title = key.title()

    doc = load_doc(doc_path, default_title=default_title)
    entries = doc.all_entries()
    now = time.time()

    result = CleanupResult(
        layer=layer,
        key=key,
        entries_scanned=len(entries),
        entries_archived=0,
        entries_deleted=0,
        entries_superseded=0,
    )

    if not entries:
        await emit(on_event, {"stage": "cleanup", "message": f"No entries to scan in {layer}/{key}."})
        return result

    await emit(on_event, {
        "stage": "cleanup",
        "message": (
            f"Scanning {len(entries)} entries in {layer}/{key} "
            f"(threshold={threshold:.3f}, half_life={decay_settings.half_life_days}d)..."
        ),
    })

    # ── 阶段 1：识别过时条目 ──────────────────────────────────────
    stale_ids: list[str] = []
    for entry in entries:
        if entry.created_at is None:
            # 无衰减元数据 — 跳过尚未索引的条目
            continue

        score = compute_decay_score(
            entry.created_at,
            entry.last_accessed or entry.created_at,
            entry.access_count,
            entry.importance,
            half_life_days=decay_settings.half_life_days,
            now=now,
        )
        if score < threshold:
            stale_ids.append(entry.id)
            logger.debug(
                "Stale entry %s: decay=%.4f, age=%.1fd, text=%s",
                entry.id, score,
                (now - entry.created_at) / 86400,
                entry.text[:60],
            )

    if not stale_ids:
        await emit(on_event, {"stage": "cleanup", "message": "No stale entries found."})
        return result

    await emit(on_event, {
        "stage": "cleanup",
        "message": f"Found {len(stale_ids)} stale entries (decay < {threshold:.3f}).",
    })

    # ── 阶段 2：检查被取代的条目 ─────────────────────────────────
    # 如果同节中有更新的条目且重要性相似或更高，则该条目被取代。
    entries_by_section: dict[str, list[Entry]] = {}
    for entry in entries:
        entries_by_section.setdefault(entry.section, []).append(entry)

    superseded_ids: set[str] = set()
    for stale_id in stale_ids:
        stale_entry = doc.find(stale_id)
        if not stale_entry or stale_entry.created_at is None:
            continue

        section_entries = entries_by_section.get(stale_entry.section, [])
        for other in section_entries:
            if other.id == stale_id:
                continue
            if other.created_at is None:
                continue
            # 同节中更新的条目取代过时的条目
            if (other.created_at > stale_entry.created_at
                    and other.importance >= stale_entry.importance * 0.8):
                superseded_ids.add(stale_id)
                break

    # ── 阶段 3：归档并删除 ──────────────────────────────────
    archive_path: Path | None = None
    if archive and decay_settings.archive_before_delete:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_path = paths.memory_root() / "backup" / "decay_archive" / f"{ts}.jsonl"

    ids_to_remove = set(stale_ids)

    for entry_id in ids_to_remove:
        entry = doc.find(entry_id)
        if not entry:
            continue

        # 删除前归档
        if archive_path is not None:
            _archive_entry(archive_path, entry, layer, key, "superseded" if entry_id in superseded_ids else "stale")

        if entry_id in superseded_ids:
            result.entries_superseded += 1
        else:
            result.entries_archived += 1

        doc.remove(entry_id)
        result.entries_deleted += 1

    # ── 阶段 4：回写 ──────────────────────────────────────────
    if result.entries_deleted > 0:
        await write_doc_checkpoint(
            doc_path, doc,
            layer=layer, key=key,
            on_event=on_event,
            label="cleanup",
        )
        await emit(on_event, {
            "stage": "done",
            "message": (
                f"Cleanup complete: {result.entries_deleted} entries removed "
                f"({result.entries_superseded} superseded, {result.entries_archived} stale+archived)."
            ),
        })
    else:
        await emit(on_event, {"stage": "done", "message": "No entries removed."})

    return result


def _archive_entry(
    archive_path: Path,
    entry: Entry,
    layer: str,
    key: str,
    reason: str,
) -> None:
    """将一个条目追加到衰减归档 JSONL 文件。"""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": entry.id,
        "layer": layer,
        "key": key,
        "section": entry.section,
        "text": entry.text,
        "refs": entry.refs,
        "created_at": entry.created_at,
        "last_accessed": entry.last_accessed,
        "access_count": entry.access_count,
        "importance": entry.importance,
        "reason": reason,
        "archived_at": time.time(),
    }
    with open(archive_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


__all__ = ["CleanupResult", "run_cleanup"]
