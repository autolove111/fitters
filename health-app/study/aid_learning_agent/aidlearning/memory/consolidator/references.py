"""引用验证 + 原始追踪查找，用于更新/审计。

两个不同的关注点共享此模块，因为它们都围绕"LLM 被允许引用的引用集合"：

* **更新模式** — 引用必须指向当前块源范围内出现的实体。
  :func:`refs_in_chunk` 返回允许的池；:func:`validate_fact_refs` 过滤提取的事实。
* **审计模式** — markdown 块上的每个条目都会拼接其原始追踪内容作为证据。
  :func:`annotate_line_with_evidence` 将一个条目 + 来源格式化为一个喂给 LLM 的块。

除了读取调用方已加载的相同内存中实体/L2 文档映射外，不会发生 I/O —
各模式负责在每次运行时加载这些数据。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any, Iterable

from aidlearning.memory.long_term.document import Document, Entry
from aidlearning.memory.shared.ids import is_entry_id, is_valid_ref
from aidlearning.memory.snapshot.entity import Entity

logger = logging.getLogger(__name__)


# ── 更新模式辅助函数 ─────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtractedFact:
    """LLM 在更新模式中提取的一个事实。"""

    text: str
    refs: list[str]
    section: str = ""


def refs_in_chunk_l2(
    entities: Iterable[Entity],
    *,
    surface: str,
    chunk_text: str,
) -> set[str]:
    """此块允许的引用集合（``surface:entity_id``）。

    如果实体的渲染标记出现在 ``chunk_text`` 中，则认为该实体"在此块中"。
    该标记与 :func:`render_traces_for_concat` 写入的标记相同。
    """
    allowed: set[str] = set()
    for ent in entities:
        marker = _entity_marker(surface, ent.id)
        if marker in chunk_text:
            allowed.add(f"{surface}:{ent.id}")
    return allowed


def refs_in_span_l2(
    entities: Iterable[Entity],
    *,
    surface: str,
    full_text: str,
    start: int,
    end: int,
) -> set[str]:
    """块跨度允许的 L2 引用，包括跨块的长实体。"""
    markers: list[tuple[int, str]] = []
    for ent in entities:
        marker = _entity_marker(surface, ent.id)
        pos = full_text.find(marker)
        if pos != -1:
            markers.append((pos, f"{surface}:{ent.id}"))
    return _refs_overlapping_span(markers, text_len=len(full_text), start=start, end=end)


_L3_SURFACE_HEADER_RE = re.compile(r"^### surface: ([a-z][a-z0-9_-]*)", re.MULTILINE)


def refs_in_chunk_l3(
    chunk_text: str,
    *,
    entries_by_surface: dict[str, list[Entry]],
) -> set[str]:
    """L3 引用是*surface 名称* — 指向综合所来源的 L2 markdown。
    渲染为每个 surface 块发出一个 ``### surface: <name>`` 标题；
    我们收集块文本中可见的每个标题。
    """
    del entries_by_surface  # surface 列表从渲染文本中派生
    return {m.group(1) for m in _L3_SURFACE_HEADER_RE.finditer(chunk_text)}


def refs_in_span_l3(
    *,
    entries_by_surface: dict[str, list[Entry]],
    full_text: str,
    start: int,
    end: int,
) -> set[str]:
    """渲染块与 ``[start, end)`` 相交的 surface 引用。

    一个 surface 块从其 ``### surface:`` 标题到下一个标题（或文档末尾）。
    由于重叠窗口，一个块可能合法地从块中间开始，
    因此我们保留所有块延伸到块窗口中的 surface。
    """
    del entries_by_surface
    headers = list(_L3_SURFACE_HEADER_RE.finditer(full_text))
    if not headers:
        return set()
    allowed: set[str] = set()
    for idx, match in enumerate(headers):
        block_start = match.start()
        block_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(full_text)
        if block_start < end and block_end > start:
            allowed.add(match.group(1))
    return allowed


def validate_fact_refs(
    fact: ExtractedFact,
    *,
    allowed: set[str],
    enforce_required: bool,
    drop_invalid: bool,
) -> tuple[list[str], str | None]:
    """过滤/拒绝事实的引用。

    返回 ``(kept_refs, reject_reason)``。当事实存活时 ``reject_reason`` 为 ``None``。
    行为：

    * ``enforce_required=True`` + 无引用 → 拒绝。
    * ``drop_invalid=True``：``allowed`` 之外的引用被移除；
      如果在 ``enforce_required`` 下结果为空 → 拒绝。
    * ``drop_invalid=False``：任何池外引用 → 拒绝该事实。
    """
    if not fact.refs:
        if enforce_required:
            return [], "missing refs"
        return [], None

    if drop_invalid:
        kept = [
            normalized
            for ref in fact.refs
            if (normalized := _normalize_allowed_ref(ref, allowed)) is not None
        ]
        if not kept and enforce_required:
            return [], "no surviving refs in chunk pool"
        return _dedupe(kept), None

    for ref in fact.refs:
        normalized = _normalize_allowed_ref(ref, allowed)
        if normalized is None and not is_valid_ref(ref):
            return [], f"malformed ref {ref!r}"
        if normalized is None:
            return [], f"out-of-pool ref {ref!r}"
    return _dedupe([_normalize_allowed_ref(ref, allowed) or ref for ref in fact.refs]), None


# ── 渲染：追踪 → 拼接文本 ───────────────────────────────────────────────


_ENTITY_HEADER_FMT = "=== {marker} ==="


def render_messages_for_concat(
    messages: list[dict[str, Any]],
    *,
    surface: str,
) -> str:
    """将 SQLite 消息拼接为供 LLM 使用的时间线字符串。

    每条消息获得一个标记头，块池检测器用于引用验证。
    消息格式化为::

        === msg:<id> ===
        [session:<session_id>] <role>: <content>
    """
    blocks: list[str] = []
    for msg in messages:
        msg_id = msg.get("id", 0)
        session_id = msg.get("session_id", "")[:12]
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        header = f"=== msg:{msg_id} ==="
        body = f"[session:{session_id}] {role}: {content}"
        blocks.append(f"{header}\n{body}")
    return "\n\n".join(blocks)
# ``_L2_ENTRY_HEADER_FMT`` 和 ``_l2_entry_marker`` 不再使用：
# L3 输入是纯文本，因此不发出 L2 条目标记。它们本应是 ``"=== @l2 m_xxx ==="``。


def render_traces_for_concat(entities: list[Entity], *, surface: str) -> str:
    """将 L2 原始追踪实体列表拼接为一个时间线字符串。

    块池检测器依赖于每个实体唯一的标记行，
    因此它既是人类分隔符也是机器锚点。
    """
    blocks: list[str] = []
    for ent in entities:
        header = _ENTITY_HEADER_FMT.format(marker=_entity_marker(surface, ent.id))
        meta_str = _format_meta(ent)
        body = (ent.content or "").strip()
        block = "\n".join(
            x
            for x in (
                header,
                f"ref: {surface}:{ent.id}",
                f"label: {ent.label}",
                f"ts: {ent.ts or '?'}",
                f"meta: {meta_str}" if meta_str else None,
                "",
                body,
            )
            if x is not None
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def render_l2_entries_for_concat(
    entries_by_surface: dict[str, list[Entry]],
) -> str:
    """将 L2 条目（按 surface）拼接为一个文本供 L3 分块使用。

    L3 是*纯文本*综合层：用户已明确表示 LLM 不应看到 — 或复制 — L2 脚注来源。
    因此此渲染**仅**发出 surface 标题 + 每个条目的散文。无条目 id 标记，
    无 ``ref:`` / ``refs:`` 行。因此 L3 的块池检测器始终返回空集
    （参见 :func:`refs_in_span_l3`）；L3 事实没有引用。
    """
    blocks: list[str] = []
    for surface, entries in entries_by_surface.items():
        if not entries:
            continue
        blocks.append(f"### surface: {surface}")
        for entry in entries:
            # 保留节名称（它塑造综合），但以括号标签而非结构化字段发出，
            # 这样模型将其视为上下文而非引用钩子。
            tag = f"[{entry.section}] " if entry.section else ""
            blocks.append(f"- {tag}{entry.text}")
    return "\n\n".join(blocks)


# ── 审计模式辅助函数 ──────────────────────────────────────────────────


def annotate_l2_line_with_evidence(
    line_number: int,
    entry: Entry,
    *,
    surface: str,
    entity_lookup: dict[str, Entity],
) -> str:
    """渲染一个 L2 要点 + 它引用的每个原始追踪的完整内容。

    输出有意设计为人类可读，以便模型可以推理对应关系
    （markdown 陈述 ↔ 原始措辞）。绝不截断 — 这正是审计模式的意义。
    """
    lines: list[str] = [
        f"line {line_number}: {entry.text} [^{entry.id}]",
        f"  section: {entry.section}",
    ]
    if not entry.refs:
        lines.append("  sources: (none)")
        return "\n".join(lines)
    lines.append(f"  sources ({len(entry.refs)}):")
    for ref in entry.refs:
        if ":" not in ref:
            lines.append(f"    └ {ref}: (malformed)")
            continue
        _, ent_id = ref.split(":", 1)
        ent = entity_lookup.get(ent_id)
        if ent is None:
            lines.append(f"    └ {ref}: (entity not found in current workspace)")
            continue
        body = (ent.content or "").rstrip()
        lines.append(f"    └ {ref} (ts={ent.ts or '?'}, label={ent.label!r}):")
        for src_line in body.splitlines():
            lines.append(f"        {src_line}")
    return "\n".join(lines)


def annotate_l3_line_with_evidence(
    line_number: int,
    entry: Entry,
    *,
    l2_entry_lookup: dict[str, Entry],
) -> str:
    """渲染一个 L3 要点 + 它引用的每个 L2 条目的完整文本 + 引用。"""
    lines: list[str] = [
        f"line {line_number}: {entry.text} [^{entry.id}]",
        f"  section: {entry.section}",
    ]
    if not entry.refs:
        lines.append("  sources: (none)")
        return "\n".join(lines)
    lines.append(f"  sources ({len(entry.refs)}):")
    for ref in entry.refs:
        if not is_entry_id(ref):
            lines.append(f"    └ {ref}: (malformed L2 id)")
            continue
        src = l2_entry_lookup.get(ref)
        if src is None:
            lines.append(f"    └ {ref}: (L2 entry not found)")
            continue
        lines.append(f"    └ {ref} (section={src.section!r}):")
        lines.append(f"        {src.text}")
        if src.refs:
            lines.append(f"        upstream refs: {', '.join(src.refs)}")
    return "\n".join(lines)


# ── 内部函数 ───────────────────────────────────────────────────────────


def _entity_marker(surface: str, entity_id: str) -> str:
    return f"@entity {surface}:{entity_id}"


def _format_meta(ent: Entity) -> str:
    if not ent.metadata:
        return ""
    bits = [f"{k}={v}" for k, v in ent.metadata.items() if v not in (None, "", [], {})]
    return " ".join(bits)


def _normalize_allowed_ref(ref: str, allowed: set[str]) -> str | None:
    """当模型添加了标签文本时返回规范化的允许引用。

    LLM 经常将渲染的来源复制为 ``<label>:chat:<id>``，即使提示词要求 ``chat:<id>``。
    只要它明确以允许的块本地引用结尾，就将其视为可恢复的引用。
    """
    candidate = _strip_ref_wrappers(str(ref).strip())
    if candidate in allowed and is_valid_ref(candidate):
        return candidate
    for allowed_ref in sorted(allowed, key=len, reverse=True):
        if not is_valid_ref(allowed_ref):
            continue
        if _has_ref_suffix(candidate, allowed_ref):
            return allowed_ref
    return None


def _strip_ref_wrappers(ref: str) -> str:
    return ref.strip().strip("`[](){}<>").lstrip("^").strip()


def _has_ref_suffix(candidate: str, allowed_ref: str) -> bool:
    if candidate == allowed_ref:
        return True
    if not candidate.endswith(allowed_ref):
        return False
    prefix = candidate[: -len(allowed_ref)]
    if not prefix:
        return True
    # 常见幻觉形式："Title:chat:id", "Title?chat:id", "[^m_id]"。
    # 不接受字母数字/下划线相邻。
    return prefix[-1] in {":", "：", "?", "？", "#", "/", "|", " ", "\t", "\n", "^"}


def _dedupe(refs: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        out.append(ref)
    return out


def _refs_overlapping_span(
    markers: list[tuple[int, str]], *, text_len: int, start: int, end: int
) -> set[str]:
    allowed: set[str] = set()
    ordered = sorted(markers, key=lambda item: item[0])
    for idx, (block_start, ref) in enumerate(ordered):
        block_end = ordered[idx + 1][0] if idx + 1 < len(ordered) else text_len
        if block_start < end and block_end > start:
            allowed.add(ref)
    return allowed


def collect_l2_entries(docs: dict[str, Document]) -> dict[str, list[Entry]]:
    """L3 辅助函数 — 从 {surface: Document} 映射中提取所有条目。"""
    return {surface: doc.all_entries() for surface, doc in docs.items()}


__all__ = [
    "ExtractedFact",
    "annotate_l2_line_with_evidence",
    "annotate_l3_line_with_evidence",
    "collect_l2_entries",
    "refs_in_chunk_l2",
    "refs_in_chunk_l3",
    "refs_in_span_l2",
    "refs_in_span_l3",
    "render_l2_entries_for_concat",
    "render_traces_for_concat",
    "validate_fact_refs",
]
