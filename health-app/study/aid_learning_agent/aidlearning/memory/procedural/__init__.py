"""第 4 层：程序性记忆 — 自动技能卡片提取。

扫描中期记忆中的重复操作模式，并通过 LLM 摘要生成可复用的 ``SKILL.md`` 技能卡片。
"""

from .extractor import (
    ExtractionResult,
    ProceduralMemoryExtractor,
    SkillCandidate,
    SkillDraft,
    record_operation,
)

__all__ = [
    "ExtractionResult",
    "ProceduralMemoryExtractor",
    "SkillCandidate",
    "SkillDraft",
    "record_operation",
]
