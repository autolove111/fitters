"""统一记忆检索管道。

将中期记忆（SQLite FTS5 全文搜索）和长期记忆（L2/L3 markdown 文档）
合并为单一的排序结果集。

中期记忆使用 FTS5 进行跨所有历史消息内容的高效关键词搜索。
长期记忆对合并的 L2/L3 markdown 条目使用关键词匹配。

评分公式：
    final = w_sim * similarity + w_decay * decay + w_kw * keyword_score

默认权重在 ``RetrievalSettings`` 中配置。
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
    """来自任意层的单个排序记忆项。"""
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
        """格式化为系统提示词注入。"""
        ref_str = f" [{', '.join(self.refs)}]" if self.refs else ""
        return f"- {self.content}{ref_str} ({self.surface}/{self.section})"


class MemoryRetriever:
    """跨层记忆检索器。

    将中期记忆 (SQLite) 的 FTS5 全文搜索与关键词排序的长期记忆
    （L2/L3 markdown 文档）相结合。
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
        """从中期+长期记忆中检索相关记忆，合并并格式化。

        返回适用于系统提示词注入的 markdown。
        失败时回退到 ``read_l3_concat()``。
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
        """检索并返回原始结果（用于 API/调试）。"""
        return await self._retrieve_unified(query, top_k=top_k)

    async def _retrieve_unified(
        self,
        query: str,
        *,
        top_k: int,
    ) -> list[UnifiedResult]:
        """从两层获取、合并并排序。"""
        import asyncio

        # 并行运行两个搜索
        mid_task = asyncio.create_task(
            self._search_mid_term(query, top_k=top_k)
        )
        lt_task = asyncio.create_task(
            self._search_long_term(query, top_k=top_k)
        )

        mid_results, lt_results = await asyncio.gather(mid_task, lt_task)

        # 合并
        unified: list[UnifiedResult] = mid_results + lt_results

        # 按 final_score 排序
        unified.sort(key=lambda r: r.final_score, reverse=True)
        return unified[:top_k]

    async def _search_mid_term(
        self,
        query: str,
        *,
        top_k: int,
    ) -> list[UnifiedResult]:
        """对历史消息进行 FTS5 全文搜索。"""
        results = await self._sqlite.search_messages(
            query, limit=top_k,
        )

        now = time.time()
        unified: list[UnifiedResult] = []
        for r in results:
            # FTS5 返回按相关性排序的结果，因此位置 = 粗略分数
            # 我们基于查询 token 重叠计算简单的关键词分数
            kw_score = self._keyword_score(query, r["content"])

            # 新近度加成
            age_days = max(0, (now - r["created_at"]) / 86400)
            recency = max(0.0, 1.0 - age_days / 365.0)

            final = 0.50 * kw_score + 0.30 * recency + 0.20

            unified.append(UnifiedResult(
                source="mid_term",
                entry_id=str(r["id"]),
                content=r["content"][:300],  # 为提示词截断
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
        """对 L2/L3 markdown 文档进行关键词搜索。"""
        results: list[UnifiedResult] = []
        now = time.time()
        w = self._settings

        # 搜索所有 L2 surface 和 L3 slot
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
        """简单的 token 重叠分数。"""
        query_tokens = set(query.lower().split())
        text_lower = text.lower()
        if not query_tokens:
            return 0.0
        hits = sum(1 for t in query_tokens if t in text_lower)
        return hits / len(query_tokens)

    def _format_results(self, results: list[UnifiedResult], token_budget: int) -> str:
        """将结果格式化为 markdown，遵守 token 预算。"""
        lines: list[str] = []
        total_chars = 0
        est_chars_per_token = 3  # 对中英混合文本保守估计

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
        """回退到完整的 L3 拼接。"""
        try:
            return self._lt.read_l3_concat()
        except Exception:
            return _NO_MEMORY


# ── 常量 ──────────────────────────────────────────────────────────

_L2_SURFACES = ("chat", "kb")  # 整合路由后只有 2 个 L2 文件
_L3_SLOTS = ("recent", "profile", "scope", "preferences")


# ── 单例 ──────────────────────────────────────────────────────────

_retriever: MemoryRetriever | None = None


def get_memory_retriever(
    sqlite_store: Any | None = None,
    long_term_store: Any | None = None,
) -> MemoryRetriever | None:
    """返回进程级检索器，如果未初始化则返回 None。"""
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
    """重置单例（用于测试）。"""
    global _retriever
    _retriever = None


__all__ = [
    "MemoryRetriever",
    "UnifiedResult",
    "get_memory_retriever",
    "reset_memory_retriever",
]
