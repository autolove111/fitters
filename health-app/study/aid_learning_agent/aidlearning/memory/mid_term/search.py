"""Unified memory retrieval pipeline.

Combines mid-term memory (SQLite FTS5 full-text search) and long-term
memory (L2/L3 markdown documents) into a single ranked result set.

Mid-term memory uses FTS5 for efficient keyword search across all
past message content.  Long-term memory uses keyword matching on
the consolidated L2/L3 markdown entries.

Scoring formula:
    final = w_sim * similarity + w_decay * decay + w_kw * keyword_score

Default weights are configured in ``RetrievalSettings``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from aidlearning.memory.long_term.decay import compute_decay_score
from aidlearning.memory.long_term.document import Entry
from aidlearning.memory.settings import RetrievalSettings, load_memory_settings

logger = logging.getLogger(__name__)

_NO_MEMORY = (
    "(No memory available — interact with AidLearning and update from the Memory page to build one.)"
)


@dataclass
class UnifiedResult:
    """A single ranked memory item from any layer."""
    source: str  # "mid_term" or "long_term"
    entry_id: str
    content: str
    surface: str
    section: str
    similarity: float
    decay: float
    final_score: float
    refs: list[str]

    def format(self) -> str:
        """Format for system prompt injection."""
        ref_str = f" [{', '.join(self.refs)}]" if self.refs else ""
        return f"- {self.content}{ref_str} ({self.surface}/{self.section})"


class MemoryRetriever:
    """Cross-layer memory retriever.

    Combines FTS5 full-text search over mid-term memory (SQLite) with
    keyword-ranked long-term memory (L2/L3 markdown docs).
    """

    def __init__(
        self,
        sqlite_store: Any,  # SQLiteSessionStore
        long_term_store: Any,  # MemoryStore
        settings: RetrievalSettings | None = None,
    ) -> None:
        self._sqlite = sqlite_store
        self._lt = long_term_store
        self._settings = settings or load_memory_settings().retrieval

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        token_budget: int | None = None,
    ) -> str:
        """Retrieve relevant memories from mid-term + long-term, merge and format.

        Returns markdown suitable for system prompt injection.
        Falls back to ``read_l3_concat()`` on failure.
        """
        if not self._settings.enabled:
            return self._fallback_concat()

        k = top_k or self._settings.top_k
        budget = token_budget or self._settings.token_budget

        try:
            results = await self._retrieve_unified(query, top_k=k)
            if not results:
                return self._fallback_concat()
            return self._format_results(results, budget)
        except Exception as exc:
            logger.warning("Memory retrieval failed, falling back to concat: %s", exc)
            return self._fallback_concat()

    async def retrieve_raw(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> list[UnifiedResult]:
        """Retrieve and return raw results (for API/debugging)."""
        return await self._retrieve_unified(query, top_k=top_k)

    async def _retrieve_unified(
        self,
        query: str,
        *,
        top_k: int,
    ) -> list[UnifiedResult]:
        """Fetch from both layers, merge, and rank."""
        import asyncio

        # Run both searches in parallel
        mid_task = asyncio.create_task(
            self._search_mid_term(query, top_k=top_k)
        )
        lt_task = asyncio.create_task(
            self._search_long_term(query, top_k=top_k)
        )

        mid_results, lt_results = await asyncio.gather(mid_task, lt_task)

        # Merge
        unified: list[UnifiedResult] = mid_results + lt_results

        # Sort by final_score
        unified.sort(key=lambda r: r.final_score, reverse=True)
        return unified[:top_k]

    async def _search_mid_term(
        self,
        query: str,
        *,
        top_k: int,
    ) -> list[UnifiedResult]:
        """FTS5 full-text search over past messages."""
        results = await self._sqlite.search_messages(
            query, limit=top_k,
        )

        now = time.time()
        unified: list[UnifiedResult] = []
        for r in results:
            # FTS5 returns relevance-ordered results, so position = rough score
            # We compute a simple keyword score based on query token overlap
            kw_score = self._keyword_score(query, r["content"])

            # Recency bonus
            age_days = max(0, (now - r["created_at"]) / 86400)
            recency = max(0.0, 1.0 - age_days / 365.0)

            final = 0.50 * kw_score + 0.30 * recency + 0.20

            unified.append(UnifiedResult(
                source="mid_term",
                entry_id=str(r["id"]),
                content=r["content"][:300],  # Truncate for prompt
                surface=r.get("session_title") or r["session_id"],
                section="session",
                similarity=kw_score,
                decay=recency,
                final_score=final,
                refs=[],
            ))

        return unified

    async def _search_long_term(
        self,
        query: str,
        *,
        top_k: int,
    ) -> list[UnifiedResult]:
        """Keyword search over L2/L3 markdown documents."""
        results: list[UnifiedResult] = []
        now = time.time()
        w = self._settings

        # Search across all L2 surfaces and L3 slots
        for layer, keys in [("L2", _L2_SURFACES), ("L3", _L3_SLOTS)]:
            for key in keys:
                try:
                    doc = self._lt.read_doc(layer, key)
                except Exception:
                    continue

                for entry in doc.all_entries():
                    kw = self._keyword_score(query, entry.text)
                    if kw < 0.05:
                        continue

                    decay = 1.0
                    if entry.created_at is not None:
                        decay = compute_decay_score(
                            entry.created_at,
                            entry.last_accessed or entry.created_at,
                            entry.access_count,
                            entry.importance,
                            now=now,
                        )

                    recency = 0.5
                    if entry.created_at is not None:
                        age_days = (now - entry.created_at) / 86400.0
                        recency = max(0.0, 1.0 - age_days / 365.0)

                    final = (
                        w.weight_similarity * kw
                        + w.weight_decay * decay
                        + w.weight_importance * entry.importance
                        + w.weight_recency * recency
                    )

                    results.append(UnifiedResult(
                        source="long_term",
                        entry_id=entry.id,
                        content=entry.text,
                        surface=key,
                        section=entry.section,
                        similarity=kw,
                        decay=decay,
                        final_score=final,
                        refs=entry.refs,
                    ))

        results.sort(key=lambda r: r.final_score, reverse=True)
        return results[:top_k]

    def _keyword_score(self, query: str, text: str) -> float:
        """Simple token overlap score."""
        query_tokens = set(query.lower().split())
        text_lower = text.lower()
        if not query_tokens:
            return 0.0
        hits = sum(1 for t in query_tokens if t in text_lower)
        return hits / len(query_tokens)

    def _format_results(self, results: list[UnifiedResult], token_budget: int) -> str:
        """Format results as markdown, respecting token budget."""
        lines: list[str] = []
        total_chars = 0
        est_chars_per_token = 3  # Conservative for mixed CJK/English

        for r in results:
            formatted = r.format()
            est_tokens = len(formatted) // est_chars_per_token
            if total_chars + est_tokens > token_budget:
                break
            lines.append(formatted)
            total_chars += est_tokens

        if not lines:
            return self._fallback_concat()

        return "## Relevant Memory\n\n" + "\n".join(lines)

    def _fallback_concat(self) -> str:
        """Fall back to full L3 concatenation."""
        try:
            return self._lt.read_l3_concat()
        except Exception:
            return _NO_MEMORY


# ── Constants ──────────────────────────────────────────────────────────

_L2_SURFACES = ("chat", "kb")  # Only 2 L2 files after consolidation routing
_L3_SLOTS = ("recent", "profile", "scope", "preferences")


# ── Singleton ──────────────────────────────────────────────────────────

_retriever: MemoryRetriever | None = None


def get_memory_retriever(
    sqlite_store: Any | None = None,
    long_term_store: Any | None = None,
) -> MemoryRetriever | None:
    """Return the process-wide retriever, or None if not initialized."""
    global _retriever
    if _retriever is not None:
        return _retriever

    if sqlite_store is None or long_term_store is None:
        return None

    settings = load_memory_settings().retrieval
    _retriever = MemoryRetriever(
        sqlite_store=sqlite_store,
        long_term_store=long_term_store,
        settings=settings,
    )
    return _retriever


def reset_memory_retriever() -> None:
    """Reset the singleton (for testing)."""
    global _retriever
    _retriever = None


__all__ = [
    "MemoryRetriever",
    "UnifiedResult",
    "get_memory_retriever",
    "reset_memory_retriever",
]
