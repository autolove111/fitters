"""记忆文档上的原子增/删/改操作。

一批操作作为整体验证，仅在所有操作通过时才应用。
冲突的操作（例如同一批次中对同一 id 的 ``delete`` 和 ``edit``）
会拒绝整个批次 — LLM 不能自相矛盾。

纯函数；无 I/O，无 LLM。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union

from aidlearning.memory.long_term.document import Document, Entry
from aidlearning.memory.shared.ids import is_entry_id, is_valid_ref, new_entry_id

_MAX_TEXT_LEN = 240
_MAX_SECTION_LEN = 80
_DELETE_REASONS = frozenset({"contradicted", "superseded", "stale", "low-signal"})


@dataclass(frozen=True)
class AddOp:
    section: str
    text: str
    refs: list[str]
    op: Literal["add"] = "add"


@dataclass(frozen=True)
class EditOp:
    target_id: str
    new_text: str
    new_refs: list[str]
    op: Literal["edit"] = "edit"


@dataclass(frozen=True)
class DeleteOp:
    target_id: str
    reason: str
    op: Literal["delete"] = "delete"


Op = Union[AddOp, EditOp, DeleteOp]


@dataclass
class OpResult:
    op: Op
    status: Literal["applied"]
    entry_id: str | None = None  # 为 add 操作填充
    detail: str = ""


@dataclass
class ApplyReport:
    accepted: bool
    results: list[OpResult] = field(default_factory=list)
    reason: str = ""


class OpValidationError(Exception):
    """当批次未通过预检验证时抛出。"""


def _validate(doc: Document, ops: list[Op]) -> None:
    edits: set[str] = set()
    deletes: set[str] = set()

    for op in ops:
        if isinstance(op, AddOp):
            if not op.text or len(op.text) > _MAX_TEXT_LEN:
                raise OpValidationError(
                    f"add: text length must be 1..{_MAX_TEXT_LEN} (got {len(op.text)})"
                )
            if not op.section or len(op.section) > _MAX_SECTION_LEN:
                raise OpValidationError(f"add: invalid section {op.section!r}")
            if not op.refs:
                raise OpValidationError("add: refs must be non-empty")
            for ref in op.refs:
                if not is_valid_ref(ref):
                    raise OpValidationError(f"add: malformed ref {ref!r}")
        elif isinstance(op, EditOp):
            if not is_entry_id(op.target_id):
                raise OpValidationError(f"edit: malformed target_id {op.target_id!r}")
            if doc.find(op.target_id) is None:
                raise OpValidationError(f"edit: target_id {op.target_id} not found")
            if not op.new_text or len(op.new_text) > _MAX_TEXT_LEN:
                raise OpValidationError(
                    f"edit: text length must be 1..{_MAX_TEXT_LEN} (got {len(op.new_text)})"
                )
            if not op.new_refs:
                raise OpValidationError("edit: refs must be non-empty")
            for ref in op.new_refs:
                if not is_valid_ref(ref):
                    raise OpValidationError(f"edit: malformed ref {ref!r}")
            if op.target_id in deletes:
                raise OpValidationError(
                    f"batch conflict: edit and delete on same id {op.target_id}"
                )
            edits.add(op.target_id)
        elif isinstance(op, DeleteOp):
            if not is_entry_id(op.target_id):
                raise OpValidationError(f"delete: malformed target_id {op.target_id!r}")
            if doc.find(op.target_id) is None:
                raise OpValidationError(f"delete: target_id {op.target_id} not found")
            if op.reason not in _DELETE_REASONS:
                raise OpValidationError(f"delete: reason must be one of {sorted(_DELETE_REASONS)}")
            if op.target_id in edits:
                raise OpValidationError(
                    f"batch conflict: edit and delete on same id {op.target_id}"
                )
            deletes.add(op.target_id)
        else:
            raise OpValidationError(f"unknown op {type(op).__name__}")


def apply(doc: Document, ops: list[Op]) -> ApplyReport:
    """将操作作为原子批次应用。成功时就地修改 ``doc``。

    验证失败时文档不被修改，报告携带 ``accepted=False`` 和 ``reason``。
    """
    try:
        _validate(doc, ops)
    except OpValidationError as exc:
        return ApplyReport(accepted=False, reason=str(exc))

    results: list[OpResult] = []
    for op in ops:
        if isinstance(op, AddOp):
            new_id = new_entry_id()
            doc.section_entries(op.section).append(
                Entry(id=new_id, section=op.section, text=op.text, refs=list(op.refs))
            )
            results.append(OpResult(op=op, status="applied", entry_id=new_id))
        elif isinstance(op, EditOp):
            entry = doc.find(op.target_id)
            assert entry is not None  # _validate ensured this
            entry.text = op.new_text
            entry.refs = list(op.new_refs)
            results.append(OpResult(op=op, status="applied"))
        else:  # DeleteOp
            doc.remove(op.target_id)
            results.append(OpResult(op=op, status="applied", detail=op.reason))

    return ApplyReport(accepted=True, results=results)
