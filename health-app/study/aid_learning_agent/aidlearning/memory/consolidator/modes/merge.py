"""合并模式 — 在单个文档上合并脚注引用。

此模式是*无需 LLM*的重构过程。它加载 L2 或 L3 文档，
并通过 :func:`serialize` 重写，该函数：

1. 将旧版条目键控脚注（``[^m_xxx]: r1, r2``）迁移到新的引用键控布局
   （``[^1]: r1``, ``[^2]: r2``）。
2. 合并重复的脚注定义 — N 个引用同一来源的条目共享一个脚注标签，
   因此渲染视图不再为每个条目重复 ``notebook:3a563e6f``。
3. 按首次出现顺序重新编号标签，使输出稳定。

**仅对 L3 文档**，合并还会运行一次数据迁移：
每个旧版 ``m_<ULID>`` 引用（曾经指向 L2 条目）会被解析为其所属 surface 名称，
这样文档就可以被引用为 ``L3 → L2 md → L1 原始追踪``。
在下一次更新过程后，此迁移无需再做任何事 —
它纯粹是对 pivot 之前文档的清理。

合并被调用的方式：

* 在成功的 :func:`run_update`、:func:`run_audit` 或 :func:`run_dedup` 之后自动调用
  （由三个 ``memory.merge.auto_after_*`` 设置控制），或
* 通过工作台的 `[Merge]` 按钮显式调用 → ``mode="merge"``。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from aidlearning.memory.shared import paths
from aidlearning.memory.consolidator.modes._runtime import (
    OnEvent,
    emit,
    load_doc,
    write_doc_checkpoint,
)
from aidlearning.memory.shared.ids import is_entry_id

logger = logging.getLogger(__name__)

# 低成本预写检查：计算磁盘文本中的脚注定义数，
# 以告知工作台合并减少了多少行。我们在*原始*字节而非解析后的条目上执行，
# 因为解析后的模型已有合并的引用（`Entry.refs` 每条目携带唯一引用），
# 所以有意义的"之前"数字是文件中的内容。
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^[^\]]+\]:\s*", re.MULTILINE)


@dataclass
class MergeResult:
    layer: str
    key: str
    footnote_rows_before: int
    footnote_rows_after: int
    rewrote: bool
    legacy_l3_refs_migrated: int = 0


async def run_merge(
    layer: str,
    key: str,
    *,
    language: str = "en",
    user_label: str = "anonymous",
    on_event: OnEvent | None = None,
) -> MergeResult:
    """重新序列化 ``layer/key``；将重复引用合并为每个一个脚注。

    幂等：在已合并的文档上重新运行会重写相同的字节
    并报告 ``rewrote=False``（不推送检查点）。
    """
    # 注意：``language`` / ``user_label`` 为与其他模式的签名对称而接受；
    # 合合本身不做本地化工作也不调用 LLM，因此在函数体中均未使用。
    del language, user_label

    path = _path_for(layer, key)
    if not path.exists():
        await emit(on_event, {"stage": "done", "no_doc": True, "rewrote": False})
        return MergeResult(
            layer=layer, key=key, footnote_rows_before=0, footnote_rows_after=0, rewrote=False
        )

    raw_before = path.read_text(encoding="utf-8")
    rows_before = len(_FOOTNOTE_DEF_RE.findall(raw_before))
    doc = load_doc(path, default_title=_default_title(layer, key))

    legacy_migrated = 0
    if layer == "L3":
        legacy_migrated = _migrate_l3_legacy_refs(doc)

    # 统计文档中的唯一引用数 — 这是 :func:`serialize` 合并后的"之后"脚注行数。
    unique_refs: set[str] = set()
    for entry in doc.all_entries():
        for ref in entry.refs:
            unique_refs.add(ref)
    rows_after = len(unique_refs)

    await emit(
        on_event,
        {
            "stage": "progress",
            "mode": "merge",
            "footnote_rows_before": rows_before,
            "footnote_rows_after": rows_after,
            "legacy_l3_refs_migrated": legacy_migrated,
        },
    )

    # 当文档有条目时我们总是重写 — 即使 before == after，
    # 重新序列化的行为也会重新规范化空白并迁移旧版条目键控布局。
    # 仅当文件与 :func:`serialize` 将产生的内容字节相等时才跳过。
    from aidlearning.memory.long_term.document import serialize

    expected = serialize(doc)
    rewrote = raw_before != expected
    if rewrote:
        await write_doc_checkpoint(
            path,
            doc,
            layer=layer,
            key=key,
            on_event=on_event,
            turn=1,
            label="merge",
            action="merge_footnotes",
        )

    await emit(
        on_event,
        {
            "stage": "done",
            "footnote_rows_before": rows_before,
            "footnote_rows_after": rows_after,
            "rewrote": rewrote,
            "legacy_l3_refs_migrated": legacy_migrated,
        },
    )
    return MergeResult(
        layer=layer,
        key=key,
        footnote_rows_before=rows_before,
        footnote_rows_after=rows_after,
        rewrote=rewrote,
        legacy_l3_refs_migrated=legacy_migrated,
    )


# ── 辅助函数 ─────────────────────────────────────────────────────────────


def _migrate_l3_legacy_refs(doc) -> int:
    """将旧版 ``m_<ULID>`` L3 引用解析为纯 surface 名称。

    Pivot 之前的 L3 文档通过条目 id 引用 L2 条目。当前设计
    只需要 surface 级别的来源（"该综合来自哪个 L2 markdown"）。
    对于每个 ``m_<ULID>`` 引用，我们扫描每个 L2 markdown
    寻找拥有该条目的文档并替换为 surface 名称。

    返回已迁移的条目引用数。无法解析的 id（条目已删除或从未存在）
    被静默丢弃 — 下一轮 ``run_update`` 将从当前 L2 文本重新综合。
    """
    from aidlearning.memory.long_term.document import parse

    # 缓存 L2 entry-id → surface 查找：每个 L2 markdown 扫描一次，
    # 在文档中的每个 L3 引用之间复用。
    l2_owner: dict[str, str] = {}
    for target in paths.L2_TARGETS:
        l2_path = paths.l2_file(target)  # type: ignore[arg-type]
        if not l2_path.exists():
            continue
        try:
            l2_doc = parse(l2_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — 格式错误的 L2 不应阻止 L3 迁移
            continue
        for entry in l2_doc.all_entries():
            l2_owner.setdefault(entry.id, surface)

    migrated = 0
    for entry in doc.all_entries():
        if not entry.refs:
            continue
        new_refs: list[str] = []
        seen: set[str] = set()
        for ref in entry.refs:
            if is_entry_id(ref):
                migrated += 1
                resolved = l2_owner.get(ref)
                if resolved is None or resolved in seen:
                    continue
                seen.add(resolved)
                new_refs.append(resolved)
            else:
                if ref in seen:
                    continue
                seen.add(ref)
                new_refs.append(ref)
        entry.refs = new_refs
    return migrated


def _path_for(layer: str, key: str):
    if layer == "L2":
        return paths.l2_file(key)  # type: ignore[arg-type]
    if layer == "L3":
        return paths.l3_file(key)  # type: ignore[arg-type]
    raise ValueError(f"unknown layer {layer!r}")


def _default_title(layer: str, key: str) -> str:
    if layer == "L2":
        return f"{key} memory"
    return {
        "recent": "Recent summary",
        "profile": "User profile",
        "scope": "Knowledge scope",
        "preferences": "Preferences",
    }.get(key, f"{key} memory")


__all__ = ["MergeResult", "run_merge"]
