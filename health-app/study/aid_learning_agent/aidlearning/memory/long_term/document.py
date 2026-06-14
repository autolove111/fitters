"""带脚注式引用的 Markdown 文档。

每个 L2/L3 文件是如下形式的 markdown 文档::

    # <Title>

    ## <section_a>
    - <text> [^1][^2] <!--m_xxx-->
    - <text> [^1] <!--m_yyy-->

    ## <section_b>
    - <text> [^3] <!--m_zzz-->

    ---

    [^1]: notebook:abc
    [^2]: chat:def
    [^3]: chat:ghi

脚注标签是按文档中要点流的首次出现顺序分配的*整数*。
两个引用同一来源的条目共享一个标签，
因此重复的脚注行从渲染视图中消失。

每个要点后的 HTML 注释（``<!--m_xxx-->``）是条目 id 锚点。
它在往返过程中保留，被审计/去重行视图和 ``DELETE /entry/{id}`` 使用。
解析器还接受*旧版*格式，其中要点以 ``[^m_xxx]`` 结尾，
脚注行为 ``[^m_xxx]: ref1, ref2`` —
这使已有文档在下次保存迁移到新布局之前继续工作。

解析和序列化是纯函数 — 无 I/O，无 LLM。
往返 ``serialize(parse(x))`` 对任何由 ``serialize`` 产生的文档都是幂等的。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

_ENTRY_ID_RE = r"m_[0-9A-HJKMNP-TV-Z]{26}"

_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")

# 新版要点："- text [^1], [^3] <!--m_xxx-->"
# 标记是可选的（条目可能不引用任何引用）；标记之间的逗号+空白被容忍，
# 以便渲染的上标显示为 ``¹, ³`` 而非视觉合并的 ``¹³``。
_NEW_BULLET_RE = re.compile(
    rf"^\s*-\s+(?P<text>.*?)(?P<markers>(?:\s*,?\s*\[\^[^\]]+\])*)\s*<!--\s*(?P<id>{_ENTRY_ID_RE})\s*-->"
)
# 旧版要点："- text[^m_xxx]"
_OLD_BULLET_RE = re.compile(rf"^\s*-\s+(?P<text>.*?)\[\^(?P<id>{_ENTRY_ID_RE})\]\s*$")

# 旧版脚注定义："[^m_xxx]: ref1, ref2"
_OLD_FOOTNOTE_RE = re.compile(rf"^\[\^(?P<id>{_ENTRY_ID_RE})\]:\s*(?P<refs>.*?)\s*$")
# 新版脚注定义："[^1]: notebook:abc"   (标签非 m_xxx)
_NEW_FOOTNOTE_RE = re.compile(r"^\[\^(?P<label>[^\]]+)\]:\s*(?P<ref>.*?)\s*$")

_MARKER_RE = re.compile(r"\[\^([^\]]+)\]")

# 衰减元数据注释："< !--meta:created=123;accessed=456;count=3;imp=0.7-->"
_META_COMMENT_RE = re.compile(
    r"<!--meta:created=(?P<created>[\d.]+);accessed=(?P<accessed>[\d.]+);count=(?P<count>\d+);imp=(?P<imp>[\d.]+)-->"
)


@dataclass
class Entry:
    id: str
    section: str
    text: str
    refs: list[str] = field(default_factory=list)
    # 衰减元数据（可选，用于长期记忆条目）
    created_at: float | None = None
    last_accessed: float | None = None
    access_count: int = 0
    importance: float = 0.5


@dataclass
class Document:
    title: str = ""
    sections: list[tuple[str, list[Entry]]] = field(default_factory=list)

    def all_entries(self) -> list[Entry]:
        return [e for _, entries in self.sections for e in entries]

    def find(self, entry_id: str) -> Entry | None:
        for _, entries in self.sections:
            for entry in entries:
                if entry.id == entry_id:
                    return entry
        return None

    def section_entries(self, name: str) -> list[Entry]:
        """返回 ``name`` 的条目列表，如果节不存在则创建。"""
        for section, entries in self.sections:
            if section == name:
                return entries
        new_entries: list[Entry] = []
        self.sections.append((name, new_entries))
        return new_entries

    def remove(self, entry_id: str) -> bool:
        for _, entries in self.sections:
            for i, entry in enumerate(entries):
                if entry.id == entry_id:
                    del entries[i]
                    return True
        return False


def _encode_entry_meta(entry: Entry) -> str:
    """如果存在元数据，将衰减元数据编码为 HTML 注释。"""
    if entry.created_at is None and entry.last_accessed is None and entry.access_count == 0:
        return ""  # No metadata to encode
    created = entry.created_at or 0.0
    accessed = entry.last_accessed or 0.0
    return f" <!--meta:created={created};accessed={accessed};count={entry.access_count};imp={entry.importance}-->"


def _decode_entry_meta(text: str, entry: Entry) -> None:
    """从文本尾部的元数据注释中提取衰减元数据。"""
    m = _META_COMMENT_RE.search(text)
    if m:
        entry.created_at = float(m.group("created"))
        entry.last_accessed = float(m.group("accessed"))
        entry.access_count = int(m.group("count"))
        entry.importance = float(m.group("imp"))
        # 从文本中去除元数据注释
        text = text[:m.start()].rstrip()
    return text


def parse(md: str) -> Document:
    """解析新格式（引用键控）或旧格式（条目键控）的记忆 markdown。"""
    raw_lines = md.splitlines()

    # 第 1 遍 — 收集每个脚注定义。我们同时接受两种格式：
    # * 新版引用键控：``[^1]: notebook:abc``  → 按标签引用
    # * 旧版条目键控：``[^m_xxx]: r1, r2``  → 按条目 id 引用
    refs_by_entry: dict[str, list[str]] = {}
    ref_by_label: dict[str, str] = {}
    for raw in raw_lines:
        line = raw.rstrip()
        m_old_fn = _OLD_FOOTNOTE_RE.match(line)
        if m_old_fn:
            refs_raw = m_old_fn.group("refs")
            refs_by_entry[m_old_fn.group("id")] = [
                r.strip() for r in refs_raw.split(",") if r.strip()
            ]
            continue
        m_new_fn = _NEW_FOOTNOTE_RE.match(line)
        if m_new_fn:
            label = m_new_fn.group("label")
            if label.startswith("m_"):
                # 跳过 — 这是上面已处理的条目键控行。
                continue
            ref_by_label[label] = m_new_fn.group("ref").strip()

    # 第 2 遍 — 标题、节、要点。
    doc = Document()
    current_entries: list[Entry] | None = None
    current_section: str | None = None
    for raw in raw_lines:
        line = raw.rstrip()

        if not doc.title:
            m_title = _TITLE_RE.match(line)
            if m_title:
                doc.title = m_title.group(1).strip()
                continue

        m_section = _SECTION_RE.match(line)
        if m_section:
            current_section = m_section.group(1).strip()
            current_entries = []
            doc.sections.append((current_section, current_entries))
            continue

        # 优先尝试新版格式：要点以 HTML 注释条目 id 锚点结尾。
        m_new_b = _NEW_BULLET_RE.match(line)
        if m_new_b and current_entries is not None and current_section is not None:
            entry_id = m_new_b.group("id")
            text = m_new_b.group("text").rstrip()
            markers = _MARKER_RE.findall(m_new_b.group("markers") or "")
            entry_refs: list[str] = []
            for marker in markers:
                ref = ref_by_label.get(marker)
                if ref is not None and ref not in entry_refs:
                    entry_refs.append(ref)
            entry = Entry(id=entry_id, section=current_section, text=text, refs=entry_refs)
            # 如果存在，解码尾部的衰减元数据注释
            _decode_entry_meta(line, entry)
            current_entries.append(entry)
            continue

        # 旧版要点：引用来自第 1 遍构建的 refs_by_entry。
        m_old_b = _OLD_BULLET_RE.match(line)
        if m_old_b and current_entries is not None and current_section is not None:
            entry_id = m_old_b.group("id")
            text = m_old_b.group("text").strip()
            current_entries.append(
                Entry(
                    id=entry_id,
                    section=current_section,
                    text=text,
                    refs=list(refs_by_entry.get(entry_id, [])),
                )
            )
            continue

    return doc


def serialize(doc: Document) -> str:
    """以新的合并、引用键控格式渲染文档。

    所有条目中的每个唯一引用获得一个脚注标签，按首次出现顺序分配。
    要点以内联方式引用其引用为 ``[^1][^3]``。
    条目 id 作为尾部 HTML 注释保留，以确保往返 ``parse(serialize(d)) == d``。
    """
    # 1. 按首次出现顺序构建合并的 ref → label 映射。
    ref_order: list[str] = []
    ref_to_label: dict[str, int] = {}
    for entry in doc.all_entries():
        for ref in entry.refs:
            if ref in ref_to_label:
                continue
            ref_to_label[ref] = len(ref_order) + 1
            ref_order.append(ref)

    lines: list[str] = []
    if doc.title:
        lines.append(f"# {doc.title}")
        lines.append("")

    for section, entries in doc.sections:
        if not entries:
            continue
        lines.append(f"## {section}")
        lines.append("")
        for entry in entries:
            # 用逗号分隔标记，使渲染的上标显示为 "¹, ²" 而非 "¹²" —
            # 当同一要点引用两个不同来源时很重要。
            markers = ", ".join(f"[^{ref_to_label[r]}]" for r in entry.refs if r in ref_to_label)
            text = entry.text.rstrip()
            meta_comment = _encode_entry_meta(entry)
            if markers:
                lines.append(f"- {text} {markers} <!--{entry.id}-->{meta_comment}")
            else:
                lines.append(f"- {text} <!--{entry.id}-->{meta_comment}")
        lines.append("")

    if ref_order:
        lines.append("---")
        lines.append("")
        for i, ref in enumerate(ref_order, start=1):
            lines.append(f"[^{i}]: {ref}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["Document", "Entry", "parse", "serialize"]
