"""记忆文档的行号视图 + 行级编辑操作。

审计/去重模式要求 LLM 以与 IDE 助手操作源代码相同的方式操作记忆文档：
它看到带编号的行并发出引用这些编号的结构化编辑。

为保持文档的不变量完整，LLM 只能看到**净化后的**视图 —
节标题（``## name``）和条目要点（``- text [^m_xxx]``）。
脚注块被隐藏，由 :func:`apply_edits` 从存活条目的引用中重建。

编辑模型
-------------
三种操作类型：``ReplaceLineOp``、``DeleteLinesOp``、``InsertAfterOp``。
按**行号降序**应用，以确保前面的行不会因后面的编辑而偏移。
每个操作携带一个自由格式的 ``reason`` 用于可观测性；
审计/去重提示词要求提供该字段。替换/插入条目时引用是必需的（由运行时验证）。

公共 API
----------
* :func:`render_view` — 将 :class:`Document` 转换为带编号的 :class:`Line` 行列表 + 查找表。
* :func:`apply_edits` — 将一批编辑应用到文档；纯函数（返回新文档），
  调用方可以预览而不修改共享状态。
* :func:`parse_edits_payload` — 容错的 JSON → 类型化编辑列表解析器。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import re
from typing import Iterable, Literal, Union

from aidlearning.memory.long_term.document import Document, Entry
from aidlearning.memory.shared.ids import is_entry_id, new_entry_id

logger = logging.getLogger(__name__)

LineKind = Literal["title", "blank", "section", "bullet"]


@dataclass(frozen=True)
class Line:
    number: int  # 从 1 开始，与 LLM 看到的一致
    kind: LineKind
    text: str  # 渲染后的文本（无前缀 "n: "）
    entry_id: str | None = None  # 对于要点行，为 m_xxx id
    section: str | None = None  # 对于要点行，为所属节名称


@dataclass(frozen=True)
class LineView:
    """审计/去重 LLM 看到的净化后文档快照。"""

    lines: list[Line]
    entry_by_id: dict[str, Entry]
    entries_in_order: list[Entry]

    def render(self, *, with_numbers: bool = True) -> str:
        if with_numbers:
            width = max(2, len(str(len(self.lines))))
            return "\n".join(f"{l.number:>{width}}: {l.text}" for l in self.lines)
        return "\n".join(l.text for l in self.lines)

    def line(self, number: int) -> Line | None:
        return self.lines[number - 1] if 1 <= number <= len(self.lines) else None


# ── 编辑操作 ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReplaceLineOp:
    line: int
    new_text: str
    refs: list[str]
    reason: str = ""
    op: Literal["replace"] = "replace"


@dataclass(frozen=True)
class DeleteLinesOp:
    line_start: int
    line_end: int  # 包含
    reason: str = ""
    op: Literal["delete"] = "delete"


@dataclass(frozen=True)
class InsertAfterOp:
    after_line: int
    text: str
    refs: list[str]
    # ``section`` 是可选的：为 None 时，引擎使用包含 ``after_line`` 的节。
    # 如果 after_line 为 0（文档顶部）或指向标题/空行，则必须提供 section。
    section: str | None = None
    reason: str = ""
    op: Literal["insert"] = "insert"


Edit = Union[ReplaceLineOp, DeleteLinesOp, InsertAfterOp]


@dataclass
class EditResult:
    op: Edit
    status: Literal["applied", "rejected"]
    detail: str = ""


@dataclass
class EditReport:
    applied: list[EditResult] = field(default_factory=list)
    rejected: list[EditResult] = field(default_factory=list)

    @property
    def all_results(self) -> list[EditResult]:
        return self.applied + self.rejected


# ── 渲染：Document → LineView ─────────────────────────────────────────


def render_view(doc: Document) -> LineView:
    """生成 LLM 操作的带编号视图。"""
    lines: list[Line] = []
    entries_in_order: list[Entry] = []
    entry_by_id: dict[str, Entry] = {}

    if doc.title:
        lines.append(Line(number=len(lines) + 1, kind="title", text=f"# {doc.title}"))
        lines.append(Line(number=len(lines) + 1, kind="blank", text=""))

    for section_name, entries in doc.sections:
        if not entries:
            continue
        lines.append(Line(number=len(lines) + 1, kind="section", text=f"## {section_name}"))
        for entry in entries:
            lines.append(
                Line(
                    number=len(lines) + 1,
                    kind="bullet",
                    text=f"- {entry.text} [^{entry.id}]",
                    entry_id=entry.id,
                    section=section_name,
                )
            )
            entries_in_order.append(entry)
            entry_by_id[entry.id] = entry
        lines.append(Line(number=len(lines) + 1, kind="blank", text=""))

    # 去除尾部空行，使渲染视图不以空行结尾 — 保持行数可预测。
    while lines and lines[-1].kind == "blank":
        lines.pop()

    return LineView(
        lines=lines,
        entry_by_id=entry_by_id,
        entries_in_order=entries_in_order,
    )


# ── 应用编辑 ─────────────────────────────────────────────────────────


def apply_edits(doc: Document, edits: Iterable[Edit]) -> tuple[Document, EditReport]:
    """按行号降序将一批编辑应用到新副本。

    返回 ``(new_doc, report)``。始终返回 ``new_doc``；
    如果有编辑被拒绝，它们会被捕获到 ``report.rejected`` 中，
    其余编辑仍然会被应用。调用方决定如何处理部分成功的批次
    （审计/去重只写入部分结果）。

    降序避免行号漂移：删除第 5 行不影响"第 3 行"的含义，
    因为 3 < 5 且我们先处理第 5 行。
    """
    view = render_view(doc)
    edit_list = _sort_reverse(list(edits))
    report = EditReport()

    # Work on a deep-ish copy: the entry list per section is fresh, but
    # Entry instances themselves are reused (and possibly mutated in
    # place by replace).
    new_doc = Document(
        title=doc.title,
        sections=[(name, list(entries)) for name, entries in doc.sections],
    )

    for edit in edit_list:
        try:
            detail = _apply_one(edit, new_doc, view)
            report.applied.append(EditResult(op=edit, status="applied", detail=detail))
        except _Reject as exc:
            logger.warning("line-edit rejected: %s — %s", _short(edit), exc)
            report.rejected.append(EditResult(op=edit, status="rejected", detail=str(exc)))

    _drop_empty_sections(new_doc)
    return new_doc, report


class _Reject(Exception):
    """内部哨兵 — 表示某个编辑不安全；同级编辑仍然应用。"""


def _apply_one(edit: Edit, doc: Document, view: LineView) -> str:
    if isinstance(edit, ReplaceLineOp):
        return _apply_replace(edit, doc, view)
    if isinstance(edit, DeleteLinesOp):
        return _apply_delete(edit, doc, view)
    if isinstance(edit, InsertAfterOp):
        return _apply_insert(edit, doc, view)
    raise _Reject(f"unknown edit type {type(edit).__name__}")


def _apply_replace(edit: ReplaceLineOp, doc: Document, view: LineView) -> str:
    line = view.line(edit.line)
    if line is None:
        raise _Reject(f"line {edit.line} out of range")
    if line.kind != "bullet" or not line.entry_id:
        raise _Reject(f"line {edit.line} is not an editable entry")
    if not edit.new_text.strip():
        raise _Reject("new_text empty")
    if not edit.refs:
        raise _Reject("replace requires non-empty refs")

    entry = _entry_in_doc(doc, line.entry_id)
    if entry is None:
        raise _Reject(f"entry {line.entry_id} not found in current doc")
    entry.text = edit.new_text.strip()
    entry.refs = list(edit.refs)
    return f"replace {entry.id}"


def _apply_delete(edit: DeleteLinesOp, doc: Document, view: LineView) -> str:
    if edit.line_end < edit.line_start:
        raise _Reject(f"line_end {edit.line_end} < line_start {edit.line_start}")
    ids_to_drop: set[str] = set()
    for n in range(edit.line_start, edit.line_end + 1):
        line = view.line(n)
        if line is None or line.kind != "bullet" or not line.entry_id:
            continue  # section/blank lines are removed only as a side-effect of empties
        ids_to_drop.add(line.entry_id)
    if not ids_to_drop:
        raise _Reject("range covers no entries")
    for _name, entries in doc.sections:
        entries[:] = [e for e in entries if e.id not in ids_to_drop]
    return f"已删除 {len(ids_to_drop)} 个条目"


def _apply_insert(edit: InsertAfterOp, doc: Document, view: LineView) -> str:
    if not edit.text.strip():
        raise _Reject("insert text empty")
    if not edit.refs:
        raise _Reject("insert requires non-empty refs")

    section = edit.section
    if section is None:
        if edit.after_line < 1 or edit.after_line > len(view.lines):
            raise _Reject(
                "after_line out of range; for top-of-doc insert provide `section` explicitly"
            )
        anchor = view.line(edit.after_line)
        section = anchor.section if anchor and anchor.section else None
        if section is None and anchor and anchor.kind == "section":
            section = anchor.text.lstrip("# ").strip()
        if section is None:
            raise _Reject("no section context for insert; supply `section`")

    entry = Entry(

    entry = Entry(
        id=new_entry_id(),
        section=section,
        text=edit.text.strip(),
        refs=list(edit.refs),
    )
    target = _section_entries(doc, section)
    # 在现有节内的要点之后插入时，尊重本地位置；否则追加到末尾。
    anchor = view.line(edit.after_line) if 1 <= edit.after_line <= len(view.lines) else None
    if anchor and anchor.kind == "bullet" and anchor.section == section and anchor.entry_id:
        for idx, existing in enumerate(target):
            if existing.id == anchor.entry_id:
                target.insert(idx + 1, entry)
                break
        else:
            target.append(entry)
    else:
        target.append(entry)
    return f"已将 {entry.id} 插入 {section!r}"


# ── 解析编辑 payload ─────────────────────────────────────────────────


_REF_WRAPPER_CHARS = "`[](){}<>^ \t\n\r"
_ENTRY_ID_REF_RE = re.compile(r"^m_[0-9A-HJKMNP-TV-Z]{26}$")


def _clean_refs(raw_refs: object, *, layer: str | None) -> list[str]:
    """从一个 ``refs`` 数组中去除包装字符 + 丢弃垃圾引用。

    两次清理，按顺序：

    1. **去除包装**。审计/去重行号视图将每个要点显示为 ``- text [^m_xxx]``。
       LLM 有时会将标记（``^m_xxx``）整体复制到新的 refs 数组中 — 包括插入号。
       从两侧去除 ``` ` [ ] ( ) { } < > ^ ``` 以及空白字符。

    2. **层形状过滤**。去除包装后，如果 L2 文档的引用仍然形如 ``m_<ULID>``
       （来自行视图的条目 id），则几乎可以确定是幻觉 — 真正的 L2 引用是 ``surface:id``。
       丢弃它们。L3 引用的形状*就是* ``m_<ULID>``，所以该过滤器在那里是无操作。
    """
    if not isinstance(raw_refs, list):
        return []
    out: list[str] = []
    for r in raw_refs:
        if not r:
            continue
        s = str(r).strip(_REF_WRAPPER_CHARS).strip()
        if not s:
            continue
        if layer == "L2" and _ENTRY_ID_REF_RE.match(s):
            continue
        out.append(s)
    return out


def parse_edits_payload(raw: str, *, layer: str | None = None) -> list[Edit]:
    """容错 JSON 解析 → list[Edit]。

    接受 ``{"edits": [...]}`` 或顶层 ``[...]``。每个条目的 ``op`` 字段决定类型。
    未知操作被丢弃。

    ``layer``（``"L2"`` / ``"L3"``）控制引用形状过滤 — 参见 :func:`_clean_refs`。
    当调用方无法或不应按层过滤时省略（或传 ``None``）；引用仍会去除包装字符。
    """
    snippet = _extract_json(raw)
    if snippet is None:
        return []
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError:
        logger.warning("line-edit parse: malformed JSON")
        return []
    items = data.get("edits") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    edits: list[Edit] = []
    for raw_op in items:
        if not isinstance(raw_op, dict):
            continue
        kind = raw_op.get("op")
        try:
            if kind == "replace":
                edits.append(
                    ReplaceLineOp(
                        line=int(raw_op.get("line", 0)),
                        new_text=str(raw_op.get("new_text", "")).strip(),
                        refs=_clean_refs(raw_op.get("refs", []), layer=layer),
                        reason=str(raw_op.get("reason", "")).strip(),
                    )
                )
            elif kind == "delete":
                edits.append(
                    DeleteLinesOp(
                        line_start=int(raw_op.get("line_start", raw_op.get("line", 0))),
                        line_end=int(raw_op.get("line_end", raw_op.get("line", 0))),
                        reason=str(raw_op.get("reason", "")).strip(),
                    )
                )
            elif kind == "insert":
                section = raw_op.get("section")
                edits.append(
                    InsertAfterOp(
                        after_line=int(raw_op.get("after_line", 0)),
                        text=str(raw_op.get("text", "")).strip(),
                        refs=_clean_refs(raw_op.get("refs", []), layer=layer),
                        section=str(section).strip() if section else None,
                        reason=str(raw_op.get("reason", "")).strip(),
                    )
                )
        except (TypeError, ValueError):
            continue
    return edits


# ── 辅助函数 ─────────────────────────────────────────────────────────────


def _sort_reverse(edits: list[Edit]) -> list[Edit]:
    def key(e: Edit) -> tuple[int, int]:
        if isinstance(e, ReplaceLineOp):
            return (e.line, 0)
        if isinstance(e, DeleteLinesOp):
            return (e.line_end, 1)  # 在同一行上，删除排在插入之前
        if isinstance(e, InsertAfterOp):
            return (e.after_line, 2)
        return (0, 9)

    return sorted(edits, key=key, reverse=True)


def _entry_in_doc(doc: Document, entry_id: str) -> Entry | None:
    if not is_entry_id(entry_id):
        return None
    for _section, entries in doc.sections:
        for entry in entries:
            if entry.id == entry_id:
                return entry
    return None


def _section_entries(doc: Document, name: str) -> list[Entry]:
    for section, entries in doc.sections:
        if section == name:
            return entries
    new_entries: list[Entry] = []
    doc.sections.append((name, new_entries))
    return new_entries


def _drop_empty_sections(doc: Document) -> None:
    doc.sections[:] = [(name, entries) for name, entries in doc.sections if entries]


def _short(edit: Edit) -> str:
    if isinstance(edit, ReplaceLineOp):
        return f"replace L{edit.line}"
    if isinstance(edit, DeleteLinesOp):
        return f"delete L{edit.line_start}-{edit.line_end}"
    if isinstance(edit, InsertAfterOp):
        return f"insert@L{edit.after_line}"
    return repr(edit)


_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def _extract_json(raw: str) -> str | None:
    text = _FENCE_RE.sub("", raw.strip())
    # 查找最外层的 {...} 或 [...]。
    obj_start = text.find("{")
    arr_start = text.find("[")
    if obj_start == -1 and arr_start == -1:
        return None
    if obj_start == -1:
        start = arr_start
    elif arr_start == -1:
        start = obj_start
    else:
        start = min(obj_start, arr_start)
    end_obj = text.rfind("}")
    end_arr = text.rfind("]")
    end = max(end_obj, end_arr)
    if end <= start:
        return None
    return text[start : end + 1]


__all__ = [
    "DeleteLinesOp",
    "Edit",
    "EditReport",
    "EditResult",
    "InsertAfterOp",
    "Line",
    "LineView",
    "ReplaceLineOp",
    "apply_edits",
    "parse_edits_payload",
    "render_view",
]
