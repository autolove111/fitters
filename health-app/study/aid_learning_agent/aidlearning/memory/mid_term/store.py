"""Mid-term memory store backed by SQLite.

Mid-term memory captures structured interaction records (task logs, Q&A
pairs, operation results) that persist across sessions and support both
time-range queries ("what did I do last week?") and semantic search.

The table lives in the same ``chat_history.db`` as sessions/messages.
Embeddings are stored as raw ``float32`` BLOBs for zero-dependency
vector search via numpy.
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

# ── SQL ────────────────────────────────────────────────────────────────

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


# ── Data types ─────────────────────────────────────────────────────────

@dataclass
class MidTermEntry:
    """One mid-term memory record."""
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
    """A search result with scoring details."""
    entry: MidTermEntry
    similarity: float
    decay: float
    final_score: float


@dataclass
class CleanupResult:
    """Result of a stale-entry cleanup pass."""
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


# ── Store ──────────────────────────────────────────────────────────────

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


class MidTermMemoryStore:
    """Mid-term memory manager. Uses the same SQLite DB as sessions."""

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

    # ── Write ─────────────────────────────────────────────────────────

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
        """Write a mid-term memory entry. Returns the new entry ID."""
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
        """Generate embeddings for specified entries. Returns success count."""
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

    # ── Search ────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        surface_filter: str | None = None,
        time_range: tuple[float, float] | None = None,
        embed_fn: EmbedFn | None = None,
    ) -> list[MidTermResult]:
        """Semantic search over mid-term memory.

        If *embed_fn* is provided, uses vector similarity.
        Falls back to keyword-only search otherwise.
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
        """Cosine similarity search using numpy."""
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

        # Build matrix
        vecs = np.array([_unpack_embedding(b) for b in blobs], dtype=np.float32)
        q = np.array(query_vec, dtype=np.float32)

        # Cosine similarity
        norms = np.linalg.norm(vecs, axis=1)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        sims = vecs @ q / (norms * q_norm + 1e-10)

        # Score each result
        now = time.time()
        results: list[MidTermResult] = []
        for i in range(len(ids)):
            sim = float(sims[i])
            sim_norm = (sim + 1.0) / 2.0  # [-1,1] -> [0,1]
            decay = compute_decay_score(
                createds[i], accesseds[i], counts[i], imps[i], now=now,
            )
            final = 0.55 * sim_norm + 0.20 * decay + 0.15 * imps[i] + 0.10 * sim_norm

            # Fetch full entry lazily (only for top results)
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
        top = results[:top_k * 2]  # over-fetch for dedup

        # Fetch full entries for the top results
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

        # Merge and update access stats
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
        """Fallback keyword search using SQL LIKE."""
        clauses = ["superseded_by = ''"]
        params: list[Any] = []
        if surface_filter:
            clauses.append("surface = ?")
            params.append(surface_filter)
        if time_range:
            clauses.append("created_at BETWEEN ? AND ?")
            params.extend(time_range)

        # Simple token matching
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
            # Keyword score: fraction of query tokens found in content
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
        """Update last_accessed and access_count for retrieved entries."""
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

    # ── Time-range queries ────────────────────────────────────────────

    async def search_by_time(
        self,
        since: float,
        surface: str | None = None,
        limit: int = 50,
    ) -> list[MidTermEntry]:
        """Query entries by time range. For "what did I do last week?"."""
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

    # ── Decay management ──────────────────────────────────────────────

    async def refresh_decay_scores(self) -> int:
        """Recompute decay_score for all entries. Returns count updated."""
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
        """Remove entries with decay_score below threshold."""
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

                # Also clean up superseded entries
                sup_count = conn.execute(
                    "SELECT COUNT(*) FROM mid_term_memory WHERE superseded_by != ''"
                ).fetchone()[0]
                if sup_count > 0:
                    conn.execute("DELETE FROM mid_term_memory WHERE superseded_by != ''")
                    result.entries_superseded = sup_count

        async with self._lock:
            await asyncio.to_thread(_cleanup)

        return result

    # ── Stats ─────────────────────────────────────────────────────────

    async def count(self, surface: str | None = None) -> int:
        """Count entries, optionally filtered by surface."""
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
        """Return summary stats for the workbench overview."""
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
    """Reset the singleton (for testing)."""
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
