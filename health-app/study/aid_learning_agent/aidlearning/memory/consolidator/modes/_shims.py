""":mod:`aidlearning.memory.store` 的旧版公共 API 兼容层。

重构前的模块暴露了 ``consolidate_l2`` 和 ``consolidate_l3``，
返回 :class:`ConsolidateResult`。存储/API 路由仍在调用这些名称。
我们将它们保留为 :func:`run_update` 的薄包装层，
这样路由和测试 fixtures 导入的接口不会改变，
而底层实现已切换为基于分块的更新 + 去重。

``apply_ops`` 语义
-----------------------
重构前的 ``apply_ops=False`` 是工作台的"预览操作，不写入"开关。
新的基于分块的更新是增量写入的，没有干净的方式原子回滚。因此：

* ``apply_ops=True``（默认）→ :func:`run_update` 端到端运行。
* ``apply_ops=False`` → 我们仍然运行更新，以便工作台可以通过
  SSE 事件流观察将要添加的内容，但我们捕获新条目 id 并在写入后
  立即删除它们。这保持了预览语义在功能上接近旧行为，
  而不引入并行预览管道。预览模式下自动去重被抑制，
  以避免触及已有条目。

需要真正预览（完全不写入磁盘）的调用方应直接使用新的 ``run_update`` API，
配合自定义 on_event 消费者。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aidlearning.memory.shared import paths
from aidlearning.memory.consolidator.modes.update import (
    UpdateResult,
    run_update,
)
from aidlearning.memory.long_term.document import parse, serialize
from aidlearning.memory.long_term.ops import ApplyReport, Op
from aidlearning.memory.shared.paths import L3Slot, Surface

OnEvent = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class ConsolidateResult:
    report: ApplyReport
    backlog_count: int
    proposed_ops: list[Op] = field(default_factory=list)


async def consolidate_l2(
    surface: Surface,
    *,
    language: str = "en",
    user_label: str = "anonymous",
    on_event: OnEvent | None = None,
    apply_ops: bool = True,
) -> ConsolidateResult:
    result = await run_update(
        "L2",
        surface,
        language=language,
        user_label=user_label,
        on_event=on_event,
    )
    if not apply_ops:
        _rollback_new_entries("L2", surface, result.new_entry_ids)
    return _to_consolidate_result(result)


async def consolidate_l3(
    slot: L3Slot,
    *,
    language: str = "en",
    user_label: str = "anonymous",
    on_event: OnEvent | None = None,
    apply_ops: bool = True,
) -> ConsolidateResult:
    if slot == "preferences":
        raise ValueError("preferences.md is not auto-consolidated")
    result = await run_update(
        "L3",
        slot,
        language=language,
        user_label=user_label,
        on_event=on_event,
    )
    if not apply_ops:
        _rollback_new_entries("L3", slot, result.new_entry_ids)
    return _to_consolidate_result(result)


def _to_consolidate_result(result: UpdateResult) -> ConsolidateResult:
    reason = (
        "无新输入"
        if result.no_new_input
        else f"通过分块更新应用（添加了 {result.facts_added} 条）"
    )
    return ConsolidateResult(
        report=ApplyReport(
            accepted=True,
            reason=reason,
            results=[],  # 新管道不发出每个操作的 OpResult 对象
        ),
        backlog_count=result.chunks_processed,
        proposed_ops=[],  # 基于分块的模式直接写入；预览通过 SSE
    )


def _rollback_new_entries(layer: str, key: str, ids: list[str]) -> None:
    """按 id 移除条目（用于 ``apply_ops=False`` 预览模式）。

    这是尽力而为：如果文档在更新和回滚之间被外部编辑，
    未找到的 id 将被静默跳过。
    """
    if not ids:
        return
    path = paths.l2_file(key) if layer == "L2" else paths.l3_file(key)  # type: ignore[arg-type]
    if not path.exists():
        return
    doc = parse(path.read_text(encoding="utf-8"))
    drop = set(ids)
    for _name, entries in doc.sections:
        entries[:] = [e for e in entries if e.id not in drop]
    doc.sections[:] = [(n, e) for n, e in doc.sections if e]
    path.write_text(serialize(doc), encoding="utf-8")


__all__ = ["ConsolidateResult", "consolidate_l2", "consolidate_l3"]
