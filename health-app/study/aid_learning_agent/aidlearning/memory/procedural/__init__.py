"""Layer 4: Procedural memory — automatic skill card extraction.

Scans mid-term memory for repeated operation patterns and generates
reusable ``SKILL.md`` skill cards via LLM summarization.
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
