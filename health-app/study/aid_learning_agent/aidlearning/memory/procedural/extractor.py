"""程序性记忆 — 从操作模式中自动提取技能卡片。

程序性记忆捕获*如何*做事（可复用的方法和工作流）而非*发生了什么*（情节性事实）。
此模块扫描中期记忆中的重复操作模式，并使用 LLM 摘要生成技能卡片草稿。

生成的卡片遵循现有技能系统使用的相同 ``SKILL.md`` 格式，
包含 YAML frontmatter 和 markdown 正文。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from aidlearning.memory.mid_term.store import MidTermMemoryStore, MidTermEntry

logger = logging.getLogger(__name__)


@dataclass
class SkillCandidate:
    """检测到的重复操作模式。"""
    kind: str
    surface: str
    occurrences: int
    sample_contents: list[str]
    sample_entry_ids: list[str]
    first_seen: float
    last_seen: float


@dataclass
class SkillDraft:
    """生成的技能卡片草稿，等待用户确认。"""
    name: str
    description: str
    content: str  # SKILL.md body (markdown)
    tags: list[str]
    source_entry_ids: list[str]
    confidence: float  # 0-1, how confident we are this is a real pattern


@dataclass
class ExtractionResult:
    """程序性记忆提取运行的结果。"""
    candidates_found: int
    drafts_generated: int
    drafts: list[SkillDraft]


class ProceduralMemoryExtractor:
    """从中期记忆模式中提取可复用的技能卡片。"""

    def __init__(
        self,
        mid_term_store: MidTermMemoryStore,
        llm_complete: Any | None = None,
    ) -> None:
        self._mid = mid_term_store
        self._llm = llm_complete

    async def extract_candidates(
        self,
        *,
        min_occurrences: int = 3,
        time_window_days: float = 90.0,
    ) -> list[SkillCandidate]:
        """Identify repeated operation patterns in mid-term memory.

        Groups entries by (kind, surface) and returns groups with
        ≥ *min_occurrences* entries within the time window.
        """
        now = time.time()
        since = now - time_window_days * 86400

        # 获取按 kind 分组的最近条目
        entries = await self._mid.search_by_time(since=since, limit=500)

        # 按 (kind, surface) 分组
        groups: dict[tuple[str, str], list[MidTermEntry]] = {}
        for entry in entries:
            key = (entry.kind, entry.surface)
            groups.setdefault(key, []).append(entry)

        candidates: list[SkillCandidate] = []
        for (kind, surface), group_entries in groups.items():
            if len(group_entries) < min_occurrences:
                continue

            # 按时间排序
            group_entries.sort(key=lambda e: e.created_at)

            candidates.append(SkillCandidate(
                kind=kind,
                surface=surface,
                occurrences=len(group_entries),
                sample_contents=[e.content for e in group_entries[:5]],
                sample_entry_ids=[e.id for e in group_entries[:5]],
                first_seen=group_entries[0].created_at,
                last_seen=group_entries[-1].created_at,
            ))

        candidates.sort(key=lambda c: c.occurrences, reverse=True)
        return candidates

    async def generate_skill_card(
        self,
        candidate: SkillCandidate,
        *,
        language: str = "zh",
    ) -> SkillDraft | None:
        """从候选模式生成技能卡片草稿。

        使用 LLM 将操作模式总结为可复用的技能卡片。
        如果 LLM 不可用或生成失败则返回 None。
        """
        if self._llm is None:
            logger.warning("No LLM available for skill card generation")
            return None

        # 构建提示词
        samples_text = "\n".join(
            f"- [{i+1}] {content}" for i, content in enumerate(candidate.sample_contents)
        )

        lang_instruction = {
            "zh": "请用中文生成技能卡。",
            "en": "Generate the skill card in English.",
        }.get(language, "Generate the skill card in English.")

        prompt = f"""Analyze these repeated operations and generate a reusable skill card.

Operation type: {candidate.kind}
Surface: {candidate.surface}
Occurrences: {candidate.occurrences}

Sample operations:
{samples_text}

{lang_instruction}

Output a JSON object with these fields:
- "name": short skill name (lowercase, hyphenated, e.g. "csv-data-analysis")
- "description": one-line description of what this skill does
- "content": markdown body with step-by-step instructions for the AI to follow
- "tags": list of relevant tags

The content should be a clear, reusable procedure that an AI can follow
to accomplish this type of task. Focus on the HOW, not the WHAT.
"""

        try:
            response = await self._llm(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(response)
        except Exception as exc:
            logger.warning("Skill card generation failed: %s", exc)
            return None

        # 验证
        name = data.get("name", "").strip()
        if not name:
            return None

        return SkillDraft(
            name=name,
            description=data.get("description", f"{candidate.kind} on {candidate.surface}"),
            content=data.get("content", ""),
            tags=data.get("tags", [candidate.kind, candidate.surface]),
            source_entry_ids=candidate.sample_entry_ids,
            confidence=min(1.0, candidate.occurrences / 10.0),  # 出现次数越多 = 置信度越高
        )

    async def auto_extract(
        self,
        *,
        language: str = "zh",
        min_occurrences: int = 3,
    ) -> ExtractionResult:
        """全自动提取：发现模式 → 生成卡片 → 返回草稿。"""
        candidates = await self.extract_candidates(min_occurrences=min_occurrences)

        drafts: list[SkillDraft] = []
        for candidate in candidates[:5]:  # 限制为前 5 个候选
            draft = await self.generate_skill_card(candidate, language=language)
            if draft:
                drafts.append(draft)

        return ExtractionResult(
            candidates_found=len(candidates),
            drafts_generated=len(drafts),
            drafts=drafts,
        )


async def record_operation(
    mid_term_store: MidTermMemoryStore,
    *,
    session_id: str,
    turn_id: str,
    surface: str,
    kind: str,
    content: str,
    raw_payload: Any = None,
    importance: float = 0.5,
) -> str:
    """在中期记忆中记录操作的便捷函数。

    应在重要操作（工具执行、能力完成等）结束时调用，
    以建立用于程序性提取的中期记忆语料库。
    """
    return await mid_term_store.record(
        surface=surface,
        kind=kind,
        content=content,
        session_id=session_id,
        turn_id=turn_id,
        raw_payload=raw_payload,
        importance=importance,
    )


__all__ = [
    "ProceduralMemoryExtractor",
    "SkillCandidate",
    "SkillDraft",
    "ExtractionResult",
    "record_operation",
]
