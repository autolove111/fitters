"""Procedural memory — automatic skill card extraction from operation patterns.

Procedural memory captures *how* to do things (reusable methods and
workflows) rather than *what* happened (episodic facts).  This module
scans mid-term memory for repeated operation patterns and generates
skill card drafts using LLM summarization.

The generated cards follow the same ``SKILL.md`` format used by the
existing skill system, with YAML frontmatter and markdown body.
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
    """A detected pattern of repeated operations."""
    kind: str
    surface: str
    occurrences: int
    sample_contents: list[str]
    sample_entry_ids: list[str]
    first_seen: float
    last_seen: float


@dataclass
class SkillDraft:
    """A generated skill card draft ready for user confirmation."""
    name: str
    description: str
    content: str  # SKILL.md body (markdown)
    tags: list[str]
    source_entry_ids: list[str]
    confidence: float  # 0-1, how confident we are this is a real pattern


@dataclass
class ExtractionResult:
    """Result of a procedural memory extraction run."""
    candidates_found: int
    drafts_generated: int
    drafts: list[SkillDraft]


class ProceduralMemoryExtractor:
    """Extract reusable skill cards from mid-term memory patterns."""

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

        # Fetch recent entries grouped by kind
        entries = await self._mid.search_by_time(since=since, limit=500)

        # Group by (kind, surface)
        groups: dict[tuple[str, str], list[MidTermEntry]] = {}
        for entry in entries:
            key = (entry.kind, entry.surface)
            groups.setdefault(key, []).append(entry)

        candidates: list[SkillCandidate] = []
        for (kind, surface), group_entries in groups.items():
            if len(group_entries) < min_occurrences:
                continue

            # Sort by time
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
        """Generate a skill card draft from a candidate pattern.

        Uses LLM to summarize the operation pattern into a reusable
        skill card.  Returns None if LLM is not available or generation
        fails.
        """
        if self._llm is None:
            logger.warning("No LLM available for skill card generation")
            return None

        # Build the prompt
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

        # Validate
        name = data.get("name", "").strip()
        if not name:
            return None

        return SkillDraft(
            name=name,
            description=data.get("description", f"{candidate.kind} on {candidate.surface}"),
            content=data.get("content", ""),
            tags=data.get("tags", [candidate.kind, candidate.surface]),
            source_entry_ids=candidate.sample_entry_ids,
            confidence=min(1.0, candidate.occurrences / 10.0),  # More occurrences = higher confidence
        )

    async def auto_extract(
        self,
        *,
        language: str = "zh",
        min_occurrences: int = 3,
    ) -> ExtractionResult:
        """Fully automatic extraction: find patterns → generate cards → return drafts."""
        candidates = await self.extract_candidates(min_occurrences=min_occurrences)

        drafts: list[SkillDraft] = []
        for candidate in candidates[:5]:  # Limit to top 5 candidates
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
    """Convenience function to record an operation in mid-term memory.

    This should be called at the end of significant operations (tool
    executions, capability completions, etc.) to build up the mid-term
    memory corpus for procedural extraction.
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
