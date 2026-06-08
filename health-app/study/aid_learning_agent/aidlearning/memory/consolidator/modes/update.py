"""更新模式 — 基于分块的增量事实提取。

算法
---------
1. 通过与 ``*.meta.json`` 的 id 集合差异计算"上次更新以来的新内容"。
2. 按时间拼接新输入（最旧优先）。
3. ``chunk_with_boundary`` 将拼接文本切割为不超过 budget 个片段，
   绝不在段落中间（或按设置在句子中间）截断。
4. 对每个块：LLM 调用 → 解析事实 → 按引用池过滤 → 追加到内存中的 ``Document``。
5. 原子刷新到磁盘 + 更新 ``*.meta.json``。
6. 如果设置了 ``dedup.auto_after_update``，启动去重过程。

追加步骤使用现有的 :class:`ops.AddOp` 应用路径，
使文档的不变量（id 分配、验证、序列化时的脚注重建）保持集中。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging

from aidlearning.memory.shared import paths
from aidlearning.memory import snapshot as snap
from aidlearning.memory.consolidator.chunker import (
    chunk_with_boundary,
)
from aidlearning.memory.consolidator.meta import (
    load_l2_meta,
    load_l3_meta,
    save_l2_meta,
    save_l3_meta,
)
from aidlearning.memory.consolidator.modes._runtime import (
    OnEvent,
    call_llm,
    emit,
    load_doc,
    load_prompt,
    slot_focus,
    surface_focus,
    today_iso,
    write_doc_checkpoint,
)
from aidlearning.memory.consolidator.references import (
    ExtractedFact,
    refs_in_span_l2,
    refs_in_span_l3,
    render_l2_entries_for_concat,
    render_traces_for_concat,
    validate_fact_refs,
)
from aidlearning.memory.long_term.document import Document, Entry, serialize
from aidlearning.memory.long_term.ops import AddOp
from aidlearning.memory.long_term.ops import apply as apply_ops
from aidlearning.memory.shared.paths import L3Slot, Surface
from aidlearning.memory.settings import load_memory_settings

logger = logging.getLogger(__name__)

Layer = str  # "L2" | "L3"


@dataclass
class UpdateResult:
    layer: Layer
    key: str
    chunks_processed: int
    facts_added: int
    refs_dropped: int
    new_entry_ids: list[str] = field(default_factory=list)
    no_new_input: bool = False


# ── 公共入口 ────────────────────────────────────────────────────────


async def run_update(
    layer: Layer,
    key: str,
    *,
    language: str = "en",
    user_label: str = "anonymous",
    budget: int | None = None,
    llm_selection: dict | None = None,
    on_event: OnEvent | None = None,
) -> UpdateResult:
    """分派到层特定的更新实现。

    选择的 ``llm_selection``（``{profile_id, model_id}``）在运行期间
    作为作用域 LLM 配置安装，使每个内部 :func:`call_llm` 都解析到正确的提供商。
    """
    from aidlearning.services.model_selection.runtime import (
        activate_llm_selection,
        reset_llm_selection,
    )

    settings = load_memory_settings()
    token = None
    if llm_selection:
        try:
            _config, token = activate_llm_selection(llm_selection)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "memory update: ignoring unresolvable llm_selection %s: %s", llm_selection, exc
            )
            token = None
    try:
        if layer == "L2":
            return await _run_update_l2(
                key,  # type: ignore[arg-type]
                language=language,
                user_label=user_label,
                budget=budget if budget is not None else settings.update.l2_budget,
                llm_selection=llm_selection,
                on_event=on_event,
                settings=settings,
            )
        if layer == "L3":
            return await _run_update_l3(
                key,  # type: ignore[arg-type]
                language=language,
                user_label=user_label,
                budget=budget if budget is not None else settings.update.l3_budget,
                llm_selection=llm_selection,
                on_event=on_event,
                settings=settings,
            )
        raise ValueError(f"unknown layer {layer!r}")
    finally:
        reset_llm_selection(token)


# ── L2 层 ──────────────────────────────────────────────────────────────────


async def _run_update_l2(
    surface: Surface,
    *,
    language: str,
    user_label: str,
    budget: int,
    llm_selection: dict | None,
    on_event: OnEvent | None,
    settings,
) -> UpdateResult:
    meta = load_l2_meta(surface)
    seen_msg_ids = meta.seen_message_ids

    # 从 SQLite 而非 L1 追踪中读取消息
    from aidlearning.services.session.sqlite_store import get_sqlite_session_store
    sqlite_store = get_sqlite_session_store()

    # 获取新消息（get_all_messages 已排除已见 ID）
    new_messages = await sqlite_store.get_all_messages(exclude_ids=seen_msg_ids)
    seen_now = seen_msg_ids | {int(m.get("id", 0)) for m in new_messages}

    await emit(
        on_event,
        {
            "stage": "messages_loaded",
            "surface": surface,
            "new": len(new_messages),
        },
    )

    if not new_messages:
        save_l2_meta(surface, seen_message_ids=seen_now)
        if settings.merge.auto_after_update:
            from aidlearning.memory.consolidator.modes.merge import run_merge
            await run_merge("L2", surface, language=language, user_label=user_label, on_event=on_event)
        await emit(on_event, {"stage": "done", "no_new_input": True, "facts_added": 0})
        return UpdateResult(layer="L2", key=surface, chunks_processed=0, facts_added=0, refs_dropped=0, no_new_input=True)

    from aidlearning.memory.consolidator.references import render_messages_for_concat
    text = render_messages_for_concat(new_messages, surface=surface)
    chunks = chunk_with_boundary(
        text,
        budget=budget,
        overlap_ratio=settings.chunking.overlap_ratio,
        min_chunk_chars=settings.chunking.min_chunk_chars,
        max_chunk_chars=settings.chunking.max_chunk_chars,
        boundary=settings.chunking.boundary,
    )
    await emit(
        on_event,
        {"stage": "chunked", "chunks": len(chunks), "budget": budget, "chars": len(text)},
    )

    prompt = load_prompt("update_l2", language)
    focus, sections = surface_focus(language, surface)
    # 将 surface 路由到其 L2 目标（所有非 kb surface → chat.md）
    l2_target = paths.l2_target(surface)
    l2_path = paths.l2_file(l2_target)  # type: ignore[arg-type]
    doc = load_doc(l2_path, default_title=f"{l2_target} memory")

    facts_added = 0
    refs_dropped = 0
    new_entry_ids: list[str] = []

    for chunk in chunks:
        await emit(
            on_event,
            {
                "stage": "progress",
                "mode": "update",
                "turn": chunk.index + 1,
                "total": len(chunks),
                "chunk_start": chunk.start,
                "chunk_end": chunk.end,
            },
        )
        system = prompt["system"].format(
            user_label=user_label,
            surface=surface,
            sections=", ".join(sections) if sections else "(any)",
            focus=focus,
            today=today_iso(),
        )
        # 从此块中的消息 ID 构建允许的引用
        allowed = {f"msg:{m['id']}" for m in new_messages
                   if f"msg:{m['id']}" in chunk.text}
        user = prompt["user"].format(
            surface=surface,
            existing=_render_existing_l2(doc),
            chunk=_chunk_with_ref_header(chunk.text, allowed),
            chunk_index=chunk.index + 1,
            chunk_total=len(chunks),
            chunk_start=chunk.start,
            chunk_end=chunk.end,
        )
        raw = await call_llm(
            system_prompt=system,
            user_prompt=user,
            on_event=on_event,
            turn=chunk.index + 1,
            chunk_index=chunk.index,
            label="update",
        )
        facts = _parse_facts(raw)

        kept_in_chunk: list[ExtractedFact] = []
        for fact in facts:
            kept_refs, reject_reason = validate_fact_refs(
                fact,
                allowed=allowed,
                enforce_required=settings.reference.enforce_required,
                drop_invalid=settings.reference.drop_invalid_refs,
            )
            if reject_reason is not None:
                refs_dropped += 1
                await emit(
                    on_event,
                    {
                        "stage": "refs_dropped",
                        "turn": chunk.index + 1,
                        "reason": reject_reason,
                        "text": fact.text[:120],
                    },
                )
                continue
            kept_in_chunk.append(
                ExtractedFact(text=fact.text, refs=kept_refs, section=fact.section)
            )

        added_now = _append_facts_to_doc(doc, kept_in_chunk, sections)
        facts_added += len(added_now)
        new_entry_ids.extend(added_now)
        if added_now:
            await write_doc_checkpoint(
                l2_path,
                doc,
                layer="L2",
                key=surface,
                on_event=on_event,
                turn=chunk.index + 1,
                label="update",
                action="append_facts",
            )
        await emit(
            on_event,
            {
                "stage": "facts_extracted",
                "turn": chunk.index + 1,
                "kept": len(kept_in_chunk),
                "added": len(added_now),
            },
        )

    save_l2_meta(surface, seen_message_ids=seen_now)

    await emit(
        on_event,
        {
            "stage": "done",
            "facts_added": facts_added,
            "refs_dropped": refs_dropped,
            "chunks_processed": len(chunks),
            "auto_dedup": settings.dedup.auto_after_update,
        },
    )

    if settings.dedup.auto_after_update and facts_added > 0:
        # 避免循环导入：dedup 导入 settings、refs、line_doc。
        from aidlearning.memory.consolidator.modes.dedup import run_dedup

        await run_dedup(
            "L2",
            surface,
            language=language,
            user_label=user_label,
            iterations=settings.dedup.iterations,
            llm_selection=llm_selection,
            on_event=on_event,
        )

    if settings.merge.auto_after_update:
        from aidlearning.memory.consolidator.modes.merge import run_merge

        await run_merge(
            "L2",
            surface,
            language=language,
            user_label=user_label,
            on_event=on_event,
        )

    return UpdateResult(
        layer="L2",
        key=surface,
        chunks_processed=len(chunks),
        facts_added=facts_added,
        refs_dropped=refs_dropped,
        new_entry_ids=new_entry_ids,
    )


# ── L3 层 ──────────────────────────────────────────────────────────────────


async def _run_update_l3(
    slot: L3Slot,
    *,
    language: str,
    user_label: str,
    budget: int,
    llm_selection: dict | None,
    on_event: OnEvent | None,
    settings,
) -> UpdateResult:
    if slot == "preferences":
        raise ValueError("preferences.md is not auto-consolidated")

    meta = load_l3_meta(slot)
    l2_docs = _load_all_l2_docs()
    entries_by_surface: dict[str, list[Entry]] = {}
    seen_now: dict[str, set[str]] = {}
    for surface, doc in l2_docs.items():
        all_entries = doc.all_entries()
        seen_now[surface] = {e.id for e in all_entries}
        # 按 id (ULID) 升序排列 → 大致按时间升序。
        new_entries = sorted(
            (e for e in all_entries if e.id not in meta.seen_l2_entry_ids.get(surface, set())),
            key=lambda e: e.id,
        )
        entries_by_surface[surface] = new_entries

    new_count = sum(len(v) for v in entries_by_surface.values())
    total_count = sum(len(d.all_entries()) for d in l2_docs.values())
    await emit(
        on_event,
        {
            "stage": "trace_loaded",
            "slot": slot,
            "total_l2_entries": total_count,
            "new_l2_entries": new_count,
        },
    )

    if new_count == 0:
        save_l3_meta(slot, seen_l2_entry_ids=seen_now)
        if settings.merge.auto_after_update:
            from aidlearning.memory.consolidator.modes.merge import run_merge

            await run_merge(
                "L3",
                slot,
                language=language,
                user_label=user_label,
                on_event=on_event,
            )
        await emit(on_event, {"stage": "done", "no_new_input": True, "facts_added": 0})
        return UpdateResult(
            layer="L3",
            key=slot,
            chunks_processed=0,
            facts_added=0,
            refs_dropped=0,
            no_new_input=True,
        )

    text = render_l2_entries_for_concat(entries_by_surface)
    chunks = chunk_with_boundary(
        text,
        budget=budget,
        overlap_ratio=settings.chunking.overlap_ratio,
        min_chunk_chars=settings.chunking.min_chunk_chars,
        max_chunk_chars=settings.chunking.max_chunk_chars,
        boundary=settings.chunking.boundary,
    )
    await emit(
        on_event,
        {"stage": "chunked", "chunks": len(chunks), "budget": budget, "chars": len(text)},
    )

    prompt = load_prompt("update_l3", language)
    focus, sections = slot_focus(language, slot)
    l3_path = paths.l3_file(slot)
    doc = load_doc(l3_path, default_title=_default_l3_title(slot))

    facts_added = 0
    refs_dropped = 0
    new_entry_ids: list[str] = []

    for chunk in chunks:
        await emit(
            on_event,
            {
                "stage": "progress",
                "mode": "update",
                "turn": chunk.index + 1,
                "total": len(chunks),
                "chunk_start": chunk.start,
                "chunk_end": chunk.end,
            },
        )
        system = prompt["system"].format(
            user_label=user_label,
            slot=slot,
            sections=", ".join(sections) if sections else "(any)",
            focus=focus,
            today=today_iso(),
        )
        # L3 引用是*surface 名称*（chat / notebook / ...）。
        # 池是与此块相交的 surface 块；LLM 被告知从该列表中引用。
        # 逐条目 id 的来源已被明确丢弃 — L3 指向 L2 *文件*而非 L2 条目，
        # 这给用户提供了清晰的 7 脚注链
        # （L3 → L2 md → L1 原始追踪）。
        allowed = refs_in_span_l3(
            entries_by_surface=entries_by_surface,
            full_text=text,
            start=chunk.start,
            end=chunk.end,
        )
        user = prompt["user"].format(
            slot=slot,
            existing=_render_existing_l3(doc),
            chunk=_chunk_with_ref_header(chunk.text, allowed),
            chunk_index=chunk.index + 1,
            chunk_total=len(chunks),
        )
        raw = await call_llm(
            system_prompt=system,
            user_prompt=user,
            on_event=on_event,
            turn=chunk.index + 1,
            chunk_index=chunk.index,
            label="update",
        )
        facts = _parse_facts(raw)

        kept_in_chunk: list[ExtractedFact] = []
        for fact in facts:
            kept_refs, reject_reason = validate_fact_refs(
                fact,
                allowed=allowed,
                enforce_required=settings.reference.enforce_required,
                drop_invalid=settings.reference.drop_invalid_refs,
            )
            if reject_reason is not None:
                refs_dropped += 1
                await emit(
                    on_event,
                    {
                        "stage": "refs_dropped",
                        "turn": chunk.index + 1,
                        "reason": reject_reason,
                        "text": fact.text[:120],
                    },
                )
                continue
            kept_in_chunk.append(
                ExtractedFact(text=fact.text, refs=kept_refs, section=fact.section)
            )

        added_now = _append_facts_to_doc(doc, kept_in_chunk, sections)
        facts_added += len(added_now)
        new_entry_ids.extend(added_now)
        if added_now:
            await write_doc_checkpoint(
                l3_path,
                doc,
                layer="L3",
                key=slot,
                on_event=on_event,
                turn=chunk.index + 1,
                label="update",
                action="append_facts",
            )
        await emit(
            on_event,
            {
                "stage": "facts_extracted",
                "turn": chunk.index + 1,
                "kept": len(kept_in_chunk),
                "added": len(added_now),
            },
        )

    save_l3_meta(slot, seen_l2_entry_ids=seen_now)
    await emit(
        on_event,
        {
            "stage": "done",
            "facts_added": facts_added,
            "refs_dropped": refs_dropped,
            "chunks_processed": len(chunks),
            "auto_dedup": settings.dedup.auto_after_update,
        },
    )

    if settings.dedup.auto_after_update and facts_added > 0:
        from aidlearning.memory.consolidator.modes.dedup import run_dedup

        await run_dedup(
            "L3",
            slot,
            language=language,
            user_label=user_label,
            iterations=settings.dedup.iterations,
            llm_selection=llm_selection,
            on_event=on_event,
        )

    if settings.merge.auto_after_update:
        from aidlearning.memory.consolidator.modes.merge import run_merge

        await run_merge(
            "L3",
            slot,
            language=language,
            user_label=user_label,
            on_event=on_event,
        )

    return UpdateResult(
        layer="L3",
        key=slot,
        chunks_processed=len(chunks),
        facts_added=facts_added,
        refs_dropped=refs_dropped,
        new_entry_ids=new_entry_ids,
    )


# ── 辅助函数 ─────────────────────────────────────────────────────────────


def _parse_facts(raw: str) -> list[ExtractedFact]:
    """容错 JSON 解析 → list[ExtractedFact]。任何失败时返回空列表。"""
    if not raw:
        return []
    snippet = _extract_json_object(raw)
    if snippet is None:
        return []
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError:
        return []
    items = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[ExtractedFact] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        section = str(item.get("section", "")).strip()
        refs_raw = item.get("refs", [])
        refs = [str(r).strip() for r in (refs_raw if isinstance(refs_raw, list) else []) if r]
        if not text:
            continue
        out.append(ExtractedFact(text=text, refs=refs, section=section))
    return out


def _extract_json_object(raw: str) -> str | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    return text[start : end + 1]


def _append_facts_to_doc(
    doc: Document, facts: list[ExtractedFact], allowed_sections: list[str]
) -> list[str]:
    """将每个事实作为 AddOp 追加；返回新条目 id。"""
    new_ids: list[str] = []
    fallback_section = allowed_sections[0] if allowed_sections else "Notes"
    for fact in facts:
        section = fact.section if fact.section else fallback_section
        if allowed_sections and section not in allowed_sections:
            # 将不在列表中的节映射到第一个允许的节 — 保持节目录跨运行稳定。
            section = fallback_section
        op = AddOp(section=section, text=fact.text, refs=fact.refs)
        report = apply_ops(doc, [op])
        if report.accepted and report.results:
            new_id = report.results[0].entry_id
            if new_id:
                new_ids.append(new_id)
        else:
            logger.warning(
                "update: skipped fact (%s): %s",
                report.reason,
                fact.text[:80],
            )
    return new_ids


def _render_existing_l2(doc: Document) -> str:
    if not doc.all_entries():
        return "(empty — first run)"
    return serialize(doc).strip()


def _render_existing_l3(doc: Document) -> str:
    if not doc.all_entries():
        return "(empty — first run)"
    return serialize(doc).strip()


def _chunk_with_ref_header(chunk_text: str, allowed: set[str]) -> str:
    if not allowed:
        return chunk_text
    refs = "\n".join(f"- {ref}" for ref in sorted(allowed))
    return f"# Chunk-local citeable refs\n{refs}\n\n{chunk_text}"


def _load_all_l2_docs() -> dict[str, Document]:
    from aidlearning.memory.long_term.document import parse

    docs: dict[str, Document] = {}
    for target in paths.L2_TARGETS:
        path = paths.l2_file(target)  # type: ignore[arg-type]
        if not path.exists():
            continue
        try:
            docs[target] = parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return docs


def _default_l3_title(slot: L3Slot) -> str:
    return {
        "recent": "Recent summary",
        "profile": "User profile",
        "scope": "Knowledge scope",
        "preferences": "Preferences",
    }[slot]


__all__ = ["UpdateResult", "run_update"]
