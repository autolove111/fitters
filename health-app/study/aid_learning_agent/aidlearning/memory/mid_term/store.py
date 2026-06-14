"""基于 SQLite 的中期记忆存储。

中期记忆捕获结构化交互记录（任务日志、问答对、操作结果），
跨会话持久化，支持时间范围查询（"上周我做了什么？"）和语义搜索。

表与会话/消息在同一个 ``chat_history.db`` 中。
嵌入以原始 ``float32`` BLOB 存储，通过 numpy 实现零依赖向量搜索。
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass, field

from aidlearning.utils.sqlite_compat import sqlite3
from pathlib import Path
from typing import Any, Callable, Awaitable

from aidlearning.memory.long_term.decay import compute_decay_score
from aidlearning.memory.shared.ids import new_entry_id

logger = logging.getLogger(__name__)

# ── SQL 语句 ────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS mid_term_memory (
    id TEXT PRIMARY KEY,
    session_id TEXT DEFAULT '',
    turn_id TEXT DEFAULT '',
    surface TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    raw_payload TEXT DEFAULT '',
    embedding BLOB,
    created_at REAL NOT NULL,
    last_accessed REAL NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    importance REAL NOT NULL DEFAULT 0.5,
    decay_score REAL NOT NULL DEFAULT 1.0,
    superseded_by TEXT DEFAULT '',
    source_entry_id TEXT DEFAULT ''
);
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_mid_memory_session ON mid_term_memory(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_mid_memory_surface ON mid_term_memory(surface);",
    "CREATE INDEX IF NOT EXISTS idx_mid_memory_created ON mid_term_memory(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_mid_memory_kind ON mid_term_memory(kind);",
    "CREATE INDEX IF NOT EXISTS idx_mid_memory_decayed ON mid_term_memory(decay_score);",
]


# ── 数据类型 ─────────────────────────────────────────────────────────

@dataclass
class MidTermEntry:
    """一条中期记忆记录。"""
    id: str
    session_id: str
    turn_id: str
    surface: str
    kind: str
    content: str
    raw_payload: str
    embedding: list[float] | None
    created_at: float
    last_accessed: float
    access_count: int
    importance: float
    decay_score: float
    superseded_by: str
    source_entry_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "surface": self.surface,
            "kind": self.kind,
            "content": self.content,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "importance": self.importance,
            "decay_score": self.decay_score,
            "superseded_by": self.superseded_by,
            "source_entry_id": self.source_entry_id,
        }


@dataclass
class MidTermResult:
    """带评分详情的搜索结果。"""
    entry: MidTermEntry
    similarity: float
    decay: float
    final_score: float


@dataclass
class CleanupResult:
    """过时条目清理过程的结果。"""
    entries_scanned: int = 0
    entries_archived: int = 0
    entries_deleted: int = 0
    entries_superseded: int = 0


# ── Embedding helpers ──────────────────────────────────────────────────

def _pack_embedding(vec: list[float]) -> bytes:
    """Pack a float list into a compact float32 BLOB."""
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack_embedding(blob: bytes | None) -> list[float] | None:
    """Unpack a float32 BLOB back to a list."""
    if not blob:
        return None
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


# ── 存储 ──────────────────────────────────────────────────────────────

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


class MidTermMemoryStore:
    """中期记忆管理器。使用与会话相同的 SQLite DB。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_CREATE_TABLE)
            for idx_sql in _INDEXES:
                conn.execute(idx_sql)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    # ── 写入 ─────────────────────────────────────────────────────────

    async def record(
        self,
        surface: str,
        kind: str,
        content: str,
        *,
        session_id: str = "",
        turn_id: str = "",
        raw_payload: Any = None,
        importance: float = 0.5,
        source_entry_id: str = "",
    ) -> str:
        """写入一条中期记忆条目。返回新条目 ID。"""
        entry_id = new_entry_id()
        now = time.time()
        payload_str = json.dumps(raw_payload, ensure_ascii=False) if raw_payload is not None else ""

        def _insert() -> None:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO mid_term_memory
                       (id, session_id, turn_id, surface, kind, content,
                        raw_payload, created_at, last_accessed, access_count,
                        importance, decay_score, source_entry_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1.0, ?)""",
                    (entry_id, session_id, turn_id, surface, kind, content,
                     payload_str, now, now, importance, source_entry_id),
                )

        async with self._lock:
            await asyncio.to_thread(_insert)
        return entry_id

    async def embed_and_index(
        self,
        entry_ids: list[str],
        embed_fn: EmbedFn,
    ) -> int:
        """为指定条目生成嵌入。返回成功计数。"""
        if not entry_ids:
            return 0

        def _fetch() -> list[tuple[str, str]]:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT id, content FROM mid_term_memory WHERE id IN ({})".format(
                        ",".join("?" * len(entry_ids))
                    ),
                    entry_ids,
                ).fetchall()
                return [(r["id"], r["content"]) for r in rows]

        async with self._lock:
            pairs = await asyncio.to_thread(_fetch)

        if not pairs:
            return 0

        ids, texts = zip(*pairs)
        try:
            vectors = await embed_fn(list(texts))
        except Exception as exc:
            logger.warning("Mid-term embedding failed: %s", exc)
            return 0

        def _update() -> int:
            count = 0
            with self._conn() as conn:
                for entry_id, vec in zip(ids, vectors):
                    blob = _pack_embedding(vec)
                    conn.execute(
                        "UPDATE mid_term_memory SET embedding = ? WHERE id = ?",
                        (blob, entry_id),
                    )
                    count += 1
            return count

        async with self._lock:
            return await asyncio.to_thread(_update)

    # ── 搜索 ────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        surface_filter: str | None = None,
        time_range: tuple[float, float] | None = None,
        embed_fn: EmbedFn | None = None,
    ) -> list[MidTermResult]:
        """中期记忆的语义搜索。

        如果提供了 *embed_fn*，使用向量相似度。
        否则回退到纯关键词搜索。
        """
        if embed_fn is not None:
            try:
                query_vecs = await embed_fn([query])
                if query_vecs:
                    return await self._vector_search(
                        query_vecs[0], top_k=top_k,
                        surface_filter=surface_filter, time_range=time_range,
                    )
            except Exception as exc:
                logger.warning("Mid-term vector search failed, falling back: %s", exc)

        return await self._keyword_search(
            query, top_k=top_k,
            surface_filter=surface_filter, time_range=time_range,
        )

    async def _vector_search(
        self,
        query_vec: list[float],
        *,
        top_k: int,
        surface_filter: str | None,
        time_range: tuple[float, float] | None,
    ) -> list[MidTermResult]:
        """使用 numpy 的余弦相似度搜索。"""
        import numpy as np

        def _fetch() -> list[tuple[str, bytes, float, float, int, float]]:
            clauses = ["embedding IS NOT NULL", "superseded_by = ''"]
            params: list[Any] = []
            if surface_filter:
                clauses.append("surface = ?")
                params.append(surface_filter)
            if time_range:
                clauses.append("created_at BETWEEN ? AND ?")
                params.extend(time_range)
            where = " AND ".join(clauses)
            with self._conn() as conn:
                rows = conn.execute(
                    f"SELECT id, embedding, created_at, last_accessed, access_count, importance "
                    f"FROM mid_term_memory WHERE {where}",
                    params,
                ).fetchall()
            return [
                (r["id"], r["embedding"], r["created_at"],
                 r["last_accessed"], r["access_count"], r["importance"])
                for r in rows
            ]

        async with self._lock:
            rows = await asyncio.to_thread(_fetch)

        if not rows:
            return []

        ids, blobs, createds, accesseds, counts, imps = zip(*rows)

        # 构建矩阵
        vecs = np.array([_unpack_embedding(b) for b in blobs], dtype=np.float32)
        q = np.array(query_vec, dtype=np.float32)

        # 余弦相似度
        norms = np.linalg.norm(vecs, axis=1)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        sims = vecs @ q / (norms * q_norm + 1e-10)

        # 为每个结果评分
        now = time.time()
        results: list[MidTermResult] = []
        for i in range(len(ids)):
            sim = float(sims[i])
            sim_norm = (sim + 1.0) / 2.0  # [-1,1] -> [0,1]
            decay = compute_decay_score(
                createds[i], accesseds[i], counts[i], imps[i], now=now,
            )
            final = 0.55 * sim_norm + 0.20 * decay + 0.15 * imps[i] + 0.10 * sim_norm

            # 延迟获取完整条目（仅对顶部结果）
            entry = MidTermEntry(
                id=ids[i], session_id="", turn_id="", surface="",
                kind="", content="", raw_payload="",
                embedding=None,
                created_at=createds[i], last_accessed=accesseds[i],
                access_count=counts[i], importance=imps[i],
                decay_score=decay, superseded_by="", source_entry_id="",
            )
            results.append(MidTermResult(entry=entry, similarity=sim_norm, decay=decay, final_score=final))

        results.sort(key=lambda r: r.final_score, reverse=True)
        top = results[:top_k * 2]  # 超额获取以用于去重

        # 为顶部结果获取完整条目
        top_ids = [r.entry.id for r in top[:top_k]]

        def _fetch_full() -> dict[str, MidTermEntry]:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM mid_term_memory WHERE id IN ({})".format(
                        ",".join("?" * len(top_ids))
                    ),
                    top_ids,
                ).fetchall()
            entries = {}
            for r in rows:
                entries[r["id"]] = MidTermEntry(
                    id=r["id"], session_id=r["session_id"],
                    turn_id=r["turn_id"], surface=r["surface"],
                    kind=r["kind"], content=r["content"],
                    raw_payload=r["raw_payload"],
                    embedding=None,
                    created_at=r["created_at"],
                    last_accessed=r["last_accessed"],
                    access_count=r["access_count"],
                    importance=r["importance"],
                    decay_score=r["decay_score"],
                    superseded_by=r["superseded_by"],
                    source_entry_id=r["source_entry_id"],
                )
            return entries

        async with self._lock:
            full_map = await asyncio.to_thread(_fetch_full)

        # 合并并更新访问统计
        final_results: list[MidTermResult] = []
        hit_ids: list[str] = []
        for r in top[:top_k]:
            full = full_map.get(r.entry.id)
            if full:
                r.entry = full
                final_results.append(r)
                hit_ids.append(full.id)

        if hit_ids:
            await self._touch_access(hit_ids)

        return final_results

    async def _keyword_search(
        self,
        query: str,
        *,
        top_k: int,
        surface_filter: str | None,
        time_range: tuple[float, float] | None,
    ) -> list[MidTermResult]:
        """使用 SQL LIKE 的回退关键词搜索。"""
        clauses = ["superseded_by = ''"]
        params: list[Any] = []
        if surface_filter:
            clauses.append("surface = ?")
            params.append(surface_filter)
        if time_range:
            clauses.append("created_at BETWEEN ? AND ?")
            params.extend(time_range)

        # 简单 token 匹配
        tokens = [t.strip() for t in query.split() if t.strip()]
        if tokens:
            like_clauses = []
            for token in tokens[:5]:  # limit to 5 tokens
                like_clauses.append("content LIKE ?")
                params.append(f"%{token}%")
            clauses.append(f"({' OR '.join(like_clauses)})")

        where = " AND ".join(clauses)
        now = time.time()

        def _fetch() -> list[dict]:
            with self._conn() as conn:
                rows = conn.execute(
                    f"SELECT * FROM mid_term_memory WHERE {where} ORDER BY created_at DESC LIMIT ?",
                    params + [top_k * 3],
                ).fetchall()
            return [dict(r) for r in rows]

        async with self._lock:
            rows = await asyncio.to_thread(_fetch)

        results: list[MidTermResult] = []
        for r in rows:
            decay = compute_decay_score(
                r["created_at"], r["last_accessed"],
                r["access_count"], r["importance"], now=now,
            )
            # 关键词分数：在内容中找到的查询 token 比例
            content_lower = r["content"].lower()
            kw_score = sum(1 for t in tokens if t.lower() in content_lower) / max(len(tokens), 1)
            final = 0.40 * kw_score + 0.30 * decay + 0.20 * r["importance"] + 0.10

            entry = MidTermEntry(
                id=r["id"], session_id=r["session_id"],
                turn_id=r["turn_id"], surface=r["surface"],
                kind=r["kind"], content=r["content"],
                raw_payload=r["raw_payload"],
                embedding=_unpack_embedding(r["embedding"]) if r["embedding"] else None,
                created_at=r["created_at"], last_accessed=r["last_accessed"],
                access_count=r["access_count"], importance=r["importance"],
                decay_score=decay, superseded_by=r["superseded_by"],
                source_entry_id=r["source_entry_id"],
            )
            results.append(MidTermResult(entry=entry, similarity=kw_score, decay=decay, final_score=final))

        results.sort(key=lambda r: r.final_score, reverse=True)
        final = results[:top_k]

        if final:
            await self._touch_access([r.entry.id for r in final])

        return final

    async def _touch_access(self, entry_ids: list[str]) -> None:
        """更新检索条目的 last_accessed 和 access_count。"""
        now = time.time()

        def _update() -> None:
            with self._conn() as conn:
                for eid in entry_ids:
                    conn.execute(
                        """UPDATE mid_term_memory
                           SET last_accessed = ?, access_count = access_count + 1
                           WHERE id = ?""",
                        (now, eid),
                    )

        async with self._lock:
            await asyncio.to_thread(_update)

    # ── 时间范围查询 ────────────────────────────────────────────

    async def search_by_time(
        self,
        since: float,
        surface: str | None = None,
        limit: int = 50,
    ) -> list[MidTermEntry]:
        """按时间范围查询条目。用于"上周我做了什么？"。"""
        clauses = ["created_at >= ?", "superseded_by = ''"]
        params: list[Any] = [since]
        if surface:
            clauses.append("surface = ?")
            params.append(surface)

        where = " AND ".join(clauses)

        def _fetch() -> list[MidTermEntry]:
            with self._conn() as conn:
                rows = conn.execute(
                    f"SELECT * FROM mid_term_memory WHERE {where} "
                    f"ORDER BY created_at DESC LIMIT ?",
                    params + [limit],
                ).fetchall()
            return [
                MidTermEntry(
                    id=r["id"], session_id=r["session_id"],
                    turn_id=r["turn_id"], surface=r["surface"],
                    kind=r["kind"], content=r["content"],
                    raw_payload=r["raw_payload"],
                    embedding=_unpack_embedding(r["embedding"]) if r["embedding"] else None,
                    created_at=r["created_at"], last_accessed=r["last_accessed"],
                    access_count=r["access_count"], importance=r["importance"],
                    decay_score=r["decay_score"], superseded_by=r["superseded_by"],
                    source_entry_id=r["source_entry_id"],
                )
                for r in rows
            ]

        async with self._lock:
            return await asyncio.to_thread(_fetch)

    # ── 衰减管理 ──────────────────────────────────────────────

    async def refresh_decay_scores(self) -> int:
        """重新计算所有条目的 decay_score。返回更新计数。"""
        now = time.time()

        def _refresh() -> int:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT id, created_at, last_accessed, access_count, importance FROM mid_term_memory"
                ).fetchall()
                count = 0
                for r in rows:
                    score = compute_decay_score(
                        r["created_at"], r["last_accessed"],
                        r["access_count"], r["importance"], now=now,
                    )
                    conn.execute(
                        "UPDATE mid_term_memory SET decay_score = ? WHERE id = ?",
                        (score, r["id"]),
                    )
                    count += 1
            return count

        async with self._lock:
            return await asyncio.to_thread(_refresh)

    async def cleanup_stale(
        self,
        threshold: float = 0.05,
        archive_path: Path | None = None,
    ) -> CleanupResult:
        """移除 decay_score 低于阈值的条目。"""
        result = CleanupResult()

        def _cleanup() -> None:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM mid_term_memory WHERE decay_score < ? AND superseded_by = ''",
                    (threshold,),
                ).fetchall()
                result.entries_scanned = len(rows)

                for r in rows:
                    if archive_path:
                        archive_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(archive_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(dict(r), ensure_ascii=False) + "\n")
                        result.entries_archived += 1

                    conn.execute("DELETE FROM mid_term_memory WHERE id = ?", (r["id"],))
                    result.entries_deleted += 1

                # 同时清理被取代的条目
                sup_count = conn.execute(
                    "SELECT COUNT(*) FROM mid_term_memory WHERE superseded_by != ''"
                ).fetchone()[0]
                if sup_count > 0:
                    conn.execute("DELETE FROM mid_term_memory WHERE superseded_by != ''")
                    result.entries_superseded = sup_count

        async with self._lock:
            await asyncio.to_thread(_cleanup)

        return result

    # ── 统计 ─────────────────────────────────────────────────────────

    async def count(self, surface: str | None = None) -> int:
        """统计条目数，可按 surface 过滤。"""
        def _count() -> int:
            with self._conn() as conn:
                if surface:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM mid_term_memory WHERE surface = ?",
                        (surface,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM mid_term_memory"
                    ).fetchone()
            return row[0] if row else 0

        async with self._lock:
            return await asyncio.to_thread(_count)

    async def stats(self) -> dict[str, Any]:
        """返回工作台概览的摘要统计。"""
        def _stats() -> dict[str, Any]:
            with self._conn() as conn:
                total = conn.execute("SELECT COUNT(*) FROM mid_term_memory").fetchone()[0]
                by_surface = dict(conn.execute(
                    "SELECT surface, COUNT(*) FROM mid_term_memory GROUP BY surface"
                ).fetchall())
                by_kind = dict(conn.execute(
                    "SELECT kind, COUNT(*) FROM mid_term_memory GROUP BY kind"
                ).fetchall())
                embedded = conn.execute(
                    "SELECT COUNT(*) FROM mid_term_memory WHERE embedding IS NOT NULL"
                ).fetchone()[0]
                avg_decay = conn.execute(
                    "SELECT AVG(decay_score) FROM mid_term_memory"
                ).fetchone()[0] or 0.0
            return {
                "total": total,
                "embedded": embedded,
                "by_surface": by_surface,
                "by_kind": by_kind,
                "avg_decay_score": round(avg_decay, 4),
            }

        async with self._lock:
            return await asyncio.to_thread(_stats)


# ── Singleton ──────────────────────────────────────────────────────────

_store: MidTermMemoryStore | None = None


def get_mid_term_store(db_path: Path | None = None) -> MidTermMemoryStore:
    """Return the process-wide mid-term memory store singleton."""
    global _store
    if _store is None:
        if db_path is None:
            from aidlearning.services.path_service import get_path_service
            db_path = get_path_service().get_chat_history_db()
        _store = MidTermMemoryStore(db_path)
    return _store


def reset_mid_term_store() -> None:
    """重置单例（用于测试）。"""
    global _store
    _store = None


__all__ = [
    "MidTermEntry",
    "MidTermMemoryStore",
    "MidTermResult",
    "CleanupResult",
    "get_mid_term_store",
    "reset_mid_term_store",
]
