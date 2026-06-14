"""
基于 SQLite 的统一聊天会话存储。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any
import uuid

from aidlearning.utils.sqlite_compat import sqlite3

from aidlearning.services.path_service import get_path_service


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# 哨兵值，用于让 ``add_message`` 区分"调用方想要旧版自动选择最新消息的默认行为"
# 和"调用方明确希望将消息挂载到会话根节点（parent = NULL）"。
# 两者在公开的 ``parent_message_id`` 参数中都表现为 ``None``，
# 因此需要一个独立于 None 的哨兵值。
class _Unset:
    pass


_PARENT_AUTO = _Unset()


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


@dataclass
class TurnRecord:
    id: str
    session_id: str
    capability: str
    status: str
    error: str
    created_at: float
    updated_at: float
    finished_at: float | None
    last_seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "turn_id": self.id,
            "session_id": self.session_id,
            "capability": self.capability,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "last_seq": self.last_seq,
        }


class SQLiteSessionStore:
    """在 SQLite 数据库中持久化统一聊天会话和消息。"""

    def __init__(self, db_path: Path | None = None) -> None:
        path_service = get_path_service()
        self.db_path = db_path or path_service.get_chat_history_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_db(path_service)
        self._lock = asyncio.Lock()
        self._initialize()

    def _migrate_legacy_db(self, path_service) -> None:
        """将旧版 ``data/chat_history.db`` 一次性迁移到 ``data/user/``。"""
        legacy_path = path_service.project_root / "data" / "chat_history.db"
        if self.db_path.exists() or not legacy_path.exists() or legacy_path == self.db_path:
            return
        try:
            os.replace(legacy_path, self.db_path)
        except OSError:
            # 如果操作系统级别的移动不可行，则保留旧版数据库在原位；
            # 新的数据库路径将以空状态初始化。
            pass

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    compressed_summary TEXT DEFAULT '',
                    summary_up_to_msg_id INTEGER DEFAULT 0,
                    preferences_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    capability TEXT DEFAULT '',
                    events_json TEXT DEFAULT '',
                    attachments_json TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    -- 编辑分支：会话中的第一条消息为 NULL；
                    -- 否则为当前消息所在路径上的前一条消息。
                    -- 兄弟节点（相同父节点）是用户可以切换的备选分支。
                    parent_message_id INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_created
                    ON messages(session_id, created_at, id);
                -- ``idx_messages_parent`` 在 parent_message_id 迁移完成后创建（见下文）。
                -- 放在此脚本中会在旧版数据库上失败，因为该列是通过下方的
                -- ALTER TABLE 添加的。

                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                    ON sessions(updated_at DESC);

                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    capability TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'running',
                    error TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    finished_at REAL
                );

                CREATE INDEX IF NOT EXISTS idx_turns_session_updated
                    ON turns(session_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_turns_session_status
                    ON turns(session_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS turn_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    stage TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '',
                    timestamp REAL NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(turn_id, seq)
                );

                CREATE INDEX IF NOT EXISTS idx_turn_events_turn_seq
                    ON turn_events(turn_id, seq);

                CREATE TABLE IF NOT EXISTS notebook_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    turn_id TEXT NOT NULL DEFAULT '',
                    question_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    question_type TEXT DEFAULT '',
                    options_json TEXT DEFAULT '{}',
                    correct_answer TEXT DEFAULT '',
                    explanation TEXT DEFAULT '',
                    difficulty TEXT DEFAULT '',
                    user_answer TEXT DEFAULT '',
                    user_answer_images_json TEXT DEFAULT '[]',
                    is_correct INTEGER DEFAULT 0,
                    bookmarked INTEGER DEFAULT 0,
                    followup_session_id TEXT DEFAULT '',
                    ai_judgment TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(session_id, turn_id, question_id)
                );

                CREATE INDEX IF NOT EXISTS idx_notebook_entries_session
                    ON notebook_entries(session_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_notebook_entries_bookmarked
                    ON notebook_entries(bookmarked, created_at DESC);

                CREATE TABLE IF NOT EXISTS notebook_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notebook_entry_categories (
                    entry_id INTEGER NOT NULL REFERENCES notebook_entries(id) ON DELETE CASCADE,
                    category_id INTEGER NOT NULL REFERENCES notebook_categories(id) ON DELETE CASCADE,
                    PRIMARY KEY (entry_id, category_id)
                );
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            if "preferences_json" not in columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN preferences_json TEXT DEFAULT '{}'")
            if "kind" in columns:
                try:
                    conn.execute("ALTER TABLE sessions DROP COLUMN kind")
                except sqlite3.OperationalError:
                    # 较旧的 SQLite 版本可能不支持 DROP COLUMN。
                    # 应用程序不再读取或写入此旧版字段。
                    pass
            message_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()
            }
            if "metadata_json" not in message_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT DEFAULT '{}'")
            if "parent_message_id" not in message_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN parent_message_id INTEGER")
                # 回填：对于每个现有会话，将消息流视为单一的线性路径
                # —— 每行的父节点是同一会话中的上一行（按 id 排序）。
                # 没有前驱的行保持 NULL。使用纯 Python 逐会话处理，
                # 避免依赖窗口函数（较旧的 SQLite 版本可能不支持）。
                sessions_rows = conn.execute("SELECT id FROM sessions").fetchall()
                for srow in sessions_rows:
                    prev_id: int | None = None
                    msg_rows = conn.execute(
                        "SELECT id FROM messages WHERE session_id = ? ORDER BY id ASC",
                        (srow[0],),
                    ).fetchall()
                    for mrow in msg_rows:
                        if prev_id is not None:
                            conn.execute(
                                "UPDATE messages SET parent_message_id = ? WHERE id = ?",
                                (prev_id, mrow[0]),
                            )
                        prev_id = mrow[0]
            # 始终确保父节点查找索引存在 —— 涵盖旧版迁移情况（刚添加列）
            # 和全新数据库情况（上方创建时未内联索引）。
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_parent "
                "ON messages(session_id, parent_message_id)"
            )
            self._migrate_notebook_entries_add_turn_id(conn)
            self._migrate_notebook_entries_add_user_answer_images(conn)
            self._migrate_notebook_entries_add_ai_judgment(conn)
            self._ensure_fts_table(conn)
            self._ensure_buffer_state_table(conn)
            conn.commit()

    @staticmethod
    def _migrate_notebook_entries_add_turn_id(conn: sqlite3.Connection) -> None:
        """向旧版 notebook_entries 添加 ``turn_id``，并将 UNIQUE 约束
        重新限定为 ``(session_id, turn_id, question_id)``。

        旧的唯一约束会混淆同一聊天中生成的测验（issue #487）：
        使用相同位置 ``question_id``（如 ``q_1``）重新生成测验时会与
        上一个测验的笔记本条目冲突，导致 UI 填充了过期的答案。
        通过 ``turn_id`` 限定范围可保持每个测验的隔离性。
        """
        notebook_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(notebook_entries)").fetchall()
        }
        if not notebook_cols:
            return
        if "turn_id" not in notebook_cols:
            conn.execute("ALTER TABLE notebook_entries ADD COLUMN turn_id TEXT NOT NULL DEFAULT ''")
        # SQLite 将表级 UNIQUE 约束存储为以 ``sqlite_autoindex_notebook_entries_``
        # 开头的自动索引；它们覆盖的列在 PRAGMA index_info 中。
        # 检测是否存在仅覆盖 (session_id, question_id) 的自动索引，
        # 如果存在则重建表以替换为新的范围。
        needs_rebuild = False
        for idx_row in conn.execute("PRAGMA index_list(notebook_entries)").fetchall():
            idx_name = idx_row[1]
            if not idx_name.startswith("sqlite_autoindex_notebook_entries_"):
                continue
            cols = [r[2] for r in conn.execute(f"PRAGMA index_info({idx_name})").fetchall()]
            if cols == ["session_id", "question_id"]:
                needs_rebuild = True
                break
        if not needs_rebuild:
            return
        conn.executescript(
            """
            CREATE TABLE notebook_entries_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                turn_id TEXT NOT NULL DEFAULT '',
                question_id TEXT NOT NULL,
                question TEXT NOT NULL,
                question_type TEXT DEFAULT '',
                options_json TEXT DEFAULT '{}',
                correct_answer TEXT DEFAULT '',
                explanation TEXT DEFAULT '',
                difficulty TEXT DEFAULT '',
                user_answer TEXT DEFAULT '',
                is_correct INTEGER DEFAULT 0,
                bookmarked INTEGER DEFAULT 0,
                followup_session_id TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(session_id, turn_id, question_id)
            );

            INSERT INTO notebook_entries_new (
                id, session_id, turn_id, question_id, question, question_type,
                options_json, correct_answer, explanation, difficulty,
                user_answer, is_correct, bookmarked, followup_session_id,
                created_at, updated_at
            )
            SELECT
                id, session_id, COALESCE(turn_id, ''), question_id, question,
                question_type, options_json, correct_answer, explanation,
                difficulty, user_answer, is_correct, bookmarked,
                followup_session_id, created_at, updated_at
            FROM notebook_entries;

            DROP TABLE notebook_entries;
            ALTER TABLE notebook_entries_new RENAME TO notebook_entries;

            CREATE INDEX IF NOT EXISTS idx_notebook_entries_session
                ON notebook_entries(session_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_notebook_entries_bookmarked
                ON notebook_entries(bookmarked, created_at DESC);
            """
        )

    @staticmethod
    def _migrate_notebook_entries_add_user_answer_images(
        conn: sqlite3.Connection,
    ) -> None:
        """在旧版数据库上回填 ``user_answer_images_json``。

        该列存储 ``{id, url, filename, mime_type}`` 记录的 JSON 数组，
        用于学习者作答时上传的图片附件。图片字节本身存储在 AttachmentStore 中；
        我们只在行中保留引用，以保持 notebook_entries 的精简。
        """
        cols = {row[1] for row in conn.execute("PRAGMA table_info(notebook_entries)").fetchall()}
        if not cols:
            return
        if "user_answer_images_json" not in cols:
            conn.execute(
                "ALTER TABLE notebook_entries ADD COLUMN user_answer_images_json TEXT DEFAULT '[]'"
            )

    @staticmethod
    def _migrate_notebook_entries_add_ai_judgment(
        conn: sqlite3.Connection,
    ) -> None:
        """在旧版数据库上回填 ``ai_judgment``。

        以纯 Markdown 格式存储每个条目的最新 AI 评判文本。
        空字符串表示学习者尚未对此条目运行 AI 评判。
        """
        cols = {row[1] for row in conn.execute("PRAGMA table_info(notebook_entries)").fetchall()}
        if not cols:
            return
        if "ai_judgment" not in cols:
            conn.execute("ALTER TABLE notebook_entries ADD COLUMN ai_judgment TEXT DEFAULT ''")

    @staticmethod
    def _ensure_fts_table(conn: sqlite3.Connection) -> None:
        """在消息表上创建 FTS5 全文搜索索引。

        这启用了 ``session_search`` —— 一个让 LLM 通过关键词回忆过去对话的中期记忆工具。
        FTS5 提供对所有消息内容的高效全文搜索，无需嵌入向量或向量数据库。
        """
        # 通过尝试创建临时表来检查 FTS5 是否可用
        has_fts5 = False
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_test USING fts5(content)")
            conn.execute("DROP TABLE _fts5_test")
            has_fts5 = True
        except Exception:
            pass

        if not has_fts5:
            return

        # 如果不存在则创建 FTS5 虚拟表。
        # content=messages 将其链接到消息表，
        # 以便在 INSERT/UPDATE/DELETE 时自动同步。
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
            USING fts5(content, content=messages, content_rowid=id)
            """
        )

        # 从现有消息填充 FTS 索引（幂等操作）。
        # REPLACE INTO 技巧确保不会重复已索引的行。
        conn.execute(
            """
            INSERT OR IGNORE INTO messages_fts(rowid, content)
            SELECT id, content FROM messages
            """
        )

    @staticmethod
    def _ensure_buffer_state_table(conn: sqlite3.Connection) -> None:
        """创建 buffer_state 表用于持久化对话缓冲区快照。

        存储滑动窗口状态，使缓冲区在进程重启后能够恢复。
        """
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS buffer_state (
                session_id TEXT PRIMARY KEY,
                summary TEXT DEFAULT '',
                summary_tokens INTEGER DEFAULT 0,
                compressed_count INTEGER DEFAULT 0,
                window_message_ids TEXT DEFAULT '[]',
                updated_at REAL NOT NULL
            );
            """
        )

    def _save_buffer_state_sync(
        self,
        session_id: str,
        summary: str,
        summary_tokens: int,
        compressed_count: int,
        window_message_ids: list[int],
    ) -> None:
        """将缓冲区窗口状态持久化到 SQLite。"""
        import json
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO buffer_state
                   (session_id, summary, summary_tokens, compressed_count,
                    window_message_ids, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, summary, summary_tokens, compressed_count,
                 json.dumps(window_message_ids), time.time()),
            )
            conn.commit()

    def _load_buffer_state_sync(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        """从 SQLite 加载缓冲区窗口状态。"""
        import json
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM buffer_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "summary": row["summary"] or "",
                "summary_tokens": row["summary_tokens"] or 0,
                "compressed_count": row["compressed_count"] or 0,
                "window_message_ids": json.loads(row["window_message_ids"] or "[]"),
            }

    async def save_buffer_state(
        self,
        session_id: str,
        summary: str,
        summary_tokens: int,
        compressed_count: int,
        window_message_ids: list[int],
    ) -> None:
        """保存缓冲区状态的公开异步接口。"""
        import functools
        fn = functools.partial(
            self._save_buffer_state_sync,
            session_id, summary, summary_tokens,
            compressed_count, window_message_ids,
        )
        await self._run(fn)

    async def load_buffer_state(self, session_id: str) -> dict[str, Any] | None:
        """加载缓冲区状态的公开异步接口。"""
        import functools
        fn = functools.partial(self._load_buffer_state_sync, session_id)
        return await self._run(fn)

    def _search_messages_fts_sync(
        self,
        query: str,
        *,
        session_id: str | None = None,
        since: float | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """跨消息内容的全文搜索。

        如果可用则使用 FTS5，否则回退到 LIKE 查询。
        返回带有会话上下文的匹配消息，按时间排序。
        供 ``session_search`` 工具用于中期记忆回忆。
        """
        tokens = [t.strip() for t in query.split() if t.strip()]
        if not tokens:
            return []

        with self._connect() as conn:
            # 优先尝试 FTS5
            has_fts = False
            try:
                conn.execute("SELECT count(*) FROM messages_fts LIMIT 1")
                has_fts = True
            except Exception:
                pass

            if has_fts:
                # FTS5 路径
                fts_expr = " OR ".join(f'"{t}"' for t in tokens[:10])
                clauses = ["messages_fts MATCH ?"]
                params: list[Any] = [fts_expr]
                if session_id:
                    clauses.append("m.session_id = ?")
                    params.append(session_id)
                if since:
                    clauses.append("m.created_at >= ?")
                    params.append(since)
                where = " AND ".join(clauses)
                params.append(limit)

                rows = conn.execute(
                    f"""
                    SELECT m.id, m.session_id, m.role, m.content,
                           m.created_at, s.title AS session_title
                    FROM messages_fts f
                    JOIN messages m ON f.rowid = m.id
                    LEFT JOIN sessions s ON m.session_id = s.id
                    WHERE {where}
                    ORDER BY m.created_at DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
            else:
                # LIKE 回退路径
                like_clauses = []
                like_params: list[Any] = []
                for t in tokens[:5]:
                    like_clauses.append("m.content LIKE ?")
                    like_params.append(f"%{t}%")
                like_where = " OR ".join(like_clauses)

                extra_clauses = []
                extra_params: list[Any] = []
                if session_id:
                    extra_clauses.append("m.session_id = ?")
                    extra_params.append(session_id)
                if since:
                    extra_clauses.append("m.created_at >= ?")
                    extra_params.append(since)

                full_where = f"({like_where})"
                if extra_clauses:
                    full_where += " AND " + " AND ".join(extra_clauses)

                all_params = like_params + extra_params + [limit]
                rows = conn.execute(
                    f"""
                    SELECT m.id, m.session_id, m.role, m.content,
                           m.created_at, s.title AS session_title
                    FROM messages m
                    LEFT JOIN sessions s ON m.session_id = s.id
                    WHERE {full_where}
                    ORDER BY m.created_at DESC
                    LIMIT ?
                    """,
                    all_params,
                ).fetchall()

        return [
            {
                "id": r["id"],
                "session_id": r["session_id"],
                "session_title": r["session_title"] or "",
                "role": r["role"],
                "content": r["content"] or "",
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    async def search_messages(
        self,
        query: str,
        *,
        session_id: str | None = None,
        since: float | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """FTS 搜索的公开异步接口。"""
        import functools
        fn = functools.partial(
            self._search_messages_fts_sync,
            query,
            session_id=session_id,
            since=since,
            limit=limit,
        )
        return await self._run(fn)

    def _get_all_messages_sync(
        self,
        *,
        exclude_ids: set[int] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """获取用于整合的消息，可选择排除已见的 ID。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT m.id, m.session_id, m.role, m.content, m.created_at, "
                "s.title AS session_title "
                "FROM messages m LEFT JOIN sessions s ON m.session_id = s.id "
                "WHERE m.role IN ('user', 'assistant') "
                "ORDER BY m.created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()

        result = []
        for r in rows:
            msg_id = r["id"]
            if exclude_ids and msg_id in exclude_ids:
                continue
            result.append({
                "id": msg_id,
                "session_id": r["session_id"],
                "session_title": r["session_title"] or "",
                "role": r["role"],
                "content": r["content"] or "",
                "created_at": r["created_at"],
            })
        return result

    async def get_all_messages(
        self,
        *,
        exclude_ids: set[int] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """获取用于整合的消息。"""
        import functools
        fn = functools.partial(
            self._get_all_messages_sync,
            exclude_ids=exclude_ids,
            limit=limit,
        )
        return await self._run(fn)

    async def _run(self, fn, *args):
        async with self._lock:
            return await asyncio.to_thread(fn, *args)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _create_session_sync(
        self,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        resolved_id = session_id or f"unified_{int(now * 1000)}_{uuid.uuid4().hex[:8]}"
        resolved_title = (title or "New conversation").strip() or "New conversation"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, title, created_at, updated_at,
                    compressed_summary, summary_up_to_msg_id
                )
                VALUES (?, ?, ?, ?, '', 0)
                """,
                (resolved_id, resolved_title[:100], now, now),
            )
            conn.commit()
        return {
            "id": resolved_id,
            "session_id": resolved_id,
            "title": resolved_title[:100],
            "created_at": now,
            "updated_at": now,
            "compressed_summary": "",
            "summary_up_to_msg_id": 0,
        }

    async def create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._run(self._create_session_sync, title, session_id)

    def _get_session_sync(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    s.compressed_summary,
                    s.summary_up_to_msg_id,
                    s.preferences_json,
                    COALESCE(
                        (
                            SELECT t.status
                            FROM turns t
                            WHERE t.session_id = s.id
                            ORDER BY t.updated_at DESC
                            LIMIT 1
                        ),
                        'idle'
                    ) AS status,
                    COALESCE(
                        (
                            SELECT t.id
                            FROM turns t
                            WHERE t.session_id = s.id AND t.status = 'running'
                            ORDER BY t.updated_at DESC
                            LIMIT 1
                        ),
                        ''
                    ) AS active_turn_id,
                    COALESCE(
                        (
                            SELECT t.capability
                            FROM turns t
                            WHERE t.session_id = s.id
                            ORDER BY t.updated_at DESC
                            LIMIT 1
                        ),
                        ''
                    ) AS capability
                FROM sessions
                s
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["session_id"] = payload["id"]
        payload["preferences"] = _json_loads(payload.pop("preferences_json", ""), {})
        return payload

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return await self._run(self._get_session_sync, session_id)

    async def ensure_session(
        self,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        if session_id:
            session = await self.get_session(session_id)
            if session is not None:
                return session
        return await self.create_session()

    @staticmethod
    def _serialize_turn(row: sqlite3.Row) -> dict[str, Any]:
        return TurnRecord(
            id=row["id"],
            session_id=row["session_id"],
            capability=row["capability"] or "",
            status=row["status"] or "running",
            error=row["error"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            finished_at=row["finished_at"],
            last_seq=row["last_seq"] if "last_seq" in row.keys() else 0,
        ).to_dict()

    def _create_turn_sync(self, session_id: str, capability: str = "") -> dict[str, Any]:
        now = time.time()
        turn_id = f"turn_{int(now * 1000)}_{uuid.uuid4().hex[:10]}"
        with self._connect() as conn:
            session = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if session is None:
                raise ValueError(f"Session not found: {session_id}")
            active = conn.execute(
                """
                SELECT id
                FROM turns
                WHERE session_id = ? AND status = 'running'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if active is not None:
                raise RuntimeError(f"Session already has an active turn: {active['id']}")
            conn.execute(
                """
                INSERT INTO turns (id, session_id, capability, status, error, created_at, updated_at, finished_at)
                VALUES (?, ?, ?, 'running', '', ?, ?, NULL)
                """,
                (turn_id, session_id, capability or "", now, now),
            )
            conn.commit()
        return {
            "id": turn_id,
            "turn_id": turn_id,
            "session_id": session_id,
            "capability": capability or "",
            "status": "running",
            "error": "",
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
            "last_seq": 0,
        }

    async def create_turn(self, session_id: str, capability: str = "") -> dict[str, Any]:
        return await self._run(self._create_turn_sync, session_id, capability)

    def _get_turn_sync(self, turn_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    t.*,
                    COALESCE((SELECT MAX(seq) FROM turn_events te WHERE te.turn_id = t.id), 0) AS last_seq
                FROM turns t
                WHERE t.id = ?
                """,
                (turn_id,),
            ).fetchone()
        if row is None:
            return None
        return self._serialize_turn(row)

    async def get_turn(self, turn_id: str) -> dict[str, Any] | None:
        return await self._run(self._get_turn_sync, turn_id)

    def _get_active_turn_sync(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    t.*,
                    COALESCE((SELECT MAX(seq) FROM turn_events te WHERE te.turn_id = t.id), 0) AS last_seq
                FROM turns t
                WHERE t.session_id = ? AND t.status = 'running'
                ORDER BY t.updated_at DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return self._serialize_turn(row)

    async def get_active_turn(self, session_id: str) -> dict[str, Any] | None:
        return await self._run(self._get_active_turn_sync, session_id)

    def _list_active_turns_sync(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    t.*,
                    COALESCE((SELECT MAX(seq) FROM turn_events te WHERE te.turn_id = t.id), 0) AS last_seq
                FROM turns t
                WHERE t.session_id = ? AND t.status = 'running'
                ORDER BY t.updated_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [self._serialize_turn(row) for row in rows]

    async def list_active_turns(self, session_id: str) -> list[dict[str, Any]]:
        return await self._run(self._list_active_turns_sync, session_id)

    def _update_turn_status_sync(self, turn_id: str, status: str, error: str = "") -> bool:
        now = time.time()
        finished_at = now if status in {"completed", "failed", "cancelled"} else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE turns
                SET status = ?, error = ?, updated_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, error or "", now, finished_at, turn_id),
            )
            conn.commit()
        return cur.rowcount > 0

    async def update_turn_status(self, turn_id: str, status: str, error: str = "") -> bool:
        return await self._run(self._update_turn_status_sync, turn_id, status, error)

    def _append_turn_event_sync(self, turn_id: str, event: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        with self._connect() as conn:
            turn = conn.execute(
                "SELECT id, session_id FROM turns WHERE id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                raise ValueError(f"Turn not found: {turn_id}")
            provided_seq = int(event.get("seq") or 0)
            if provided_seq > 0:
                seq = provided_seq
            else:
                row = conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) AS last_seq FROM turn_events WHERE turn_id = ?",
                    (turn_id,),
                ).fetchone()
                seq = int(row["last_seq"]) + 1 if row else 1
            payload = dict(event)
            payload["seq"] = seq
            payload["turn_id"] = payload.get("turn_id") or turn_id
            payload["session_id"] = payload.get("session_id") or turn["session_id"]
            conn.execute(
                """
                INSERT OR REPLACE INTO turn_events (
                    turn_id, seq, type, source, stage, content, metadata_json, timestamp, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    seq,
                    payload.get("type", ""),
                    payload.get("source", ""),
                    payload.get("stage", ""),
                    payload.get("content", "") or "",
                    _json_dumps(payload.get("metadata", {})),
                    float(payload.get("timestamp") or now),
                    now,
                ),
            )
            conn.execute(
                "UPDATE turns SET updated_at = ? WHERE id = ?",
                (now, turn_id),
            )
            conn.commit()
        return payload

    async def append_turn_event(self, turn_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return await self._run(self._append_turn_event_sync, turn_id, event)

    def _get_turn_events_sync(self, turn_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT turn_id, seq, type, source, stage, content, metadata_json, timestamp
                FROM turn_events
                WHERE turn_id = ? AND seq > ?
                ORDER BY seq ASC
                """,
                (turn_id, max(0, int(after_seq))),
            ).fetchall()
            turn = conn.execute("SELECT session_id FROM turns WHERE id = ?", (turn_id,)).fetchone()
        session_id = turn["session_id"] if turn else ""
        return [
            {
                "type": row["type"],
                "source": row["source"] or "",
                "stage": row["stage"] or "",
                "content": row["content"] or "",
                "metadata": _json_loads(row["metadata_json"], {}),
                "session_id": session_id,
                "turn_id": row["turn_id"],
                "seq": row["seq"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    async def get_turn_events(self, turn_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        return await self._run(self._get_turn_events_sync, turn_id, after_seq)

    def _update_session_title_sync(self, session_id: str, title: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE sessions
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                ((title.strip() or "New conversation")[:100], time.time(), session_id),
            )
            conn.commit()
        return cur.rowcount > 0

    async def update_session_title(self, session_id: str, title: str) -> bool:
        return await self._run(self._update_session_title_sync, session_id, title)

    def _delete_session_sync(self, session_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
        return cur.rowcount > 0

    async def delete_session(self, session_id: str) -> bool:
        return await self._run(self._delete_session_sync, session_id)

    def _add_message_sync(
        self,
        session_id: str,
        role: str,
        content: str,
        capability: str = "",
        events: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        parent_message_id: int | None | _Unset = _PARENT_AUTO,
    ) -> int:
        now = time.time()
        with self._connect() as conn:
            session = conn.execute(
                "SELECT id, title FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None:
                raise ValueError(f"Session not found: {session_id}")

            resolved_parent_id: int | None
            if isinstance(parent_message_id, _Unset):
                    # 旧版自动追加路径：链接到会话中的最新行，
                # 保持线程的连贯性。
                last_row = conn.execute(
                    "SELECT id FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
                resolved_parent_id = int(last_row["id"]) if last_row is not None else None
            else:
                # 调用方明确指定了父节点 —— 包括 ``None``，
                # 表示"挂载到会话根节点"（用于编辑会话中第一条消息的情况）。
                resolved_parent_id = (
                    int(parent_message_id) if parent_message_id is not None else None
                )

            cur = conn.execute(
                """
                INSERT INTO messages (
                    session_id, role, content, capability, events_json,
                    attachments_json, metadata_json, created_at, parent_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content or "",
                    capability or "",
                    _json_dumps(events or []),
                    _json_dumps(attachments or []),
                    _json_dumps(metadata or {}),
                    now,
                    resolved_parent_id,
                ),
            )

            # 标题不再从第一条用户消息推导 —— turn runtime 在首个
            # 用户+助手消息对完成后调用 LLM 生成真正的摘要标题。
            # 在此之前会话保持默认哨兵值 ``New conversation``，
            # 前端将其渲染为呼吸动画的"新对话"标签。
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            conn.commit()
            return int(cur.lastrowid)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        capability: str = "",
        events: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        parent_message_id: int | None | _Unset = _PARENT_AUTO,
    ) -> int:
        return await self._run(
            self._add_message_sync,
            session_id,
            role,
            content,
            capability,
            events,
            attachments,
            metadata,
            parent_message_id,
        )

    def _delete_message_sync(self, message_id: int | str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM messages WHERE id = ?", (int(message_id),))
            conn.commit()
        return cur.rowcount > 0

    async def delete_message(self, message_id: int | str) -> bool:
        return await self._run(self._delete_message_sync, message_id)

    def _delete_turn_by_message_sync(self, session_id: str, message_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            msg = conn.execute(
                """
                SELECT id, session_id, role, attachments_json, created_at
                FROM messages
                WHERE id = ?
                """,
                (int(message_id),),
            ).fetchone()
            if msg is None or msg["session_id"] != session_id:
                return {
                    "deleted": False,
                    "attachment_ids": [],
                    "turn_id": None,
                    "was_running": False,
                }

            role = msg["role"]
            paired_msg = None
            if role == "user":
                paired_msg = conn.execute(
                    """
                    SELECT id, session_id, role, attachments_json, created_at
                    FROM messages
                    WHERE session_id = ? AND role = 'assistant' AND id > ?
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (session_id, int(message_id)),
                ).fetchone()
            elif role == "assistant":
                paired_msg = conn.execute(
                    """
                    SELECT id, session_id, role, attachments_json, created_at
                    FROM messages
                    WHERE session_id = ? AND role = 'user' AND id < ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (session_id, int(message_id)),
                ).fetchone()

            user_msg = msg if role == "user" else paired_msg
            turn_id = None
            was_running = False
            if user_msg is not None:
                user_created_at = user_msg["created_at"]
                turn_row = conn.execute(
                    """
                    SELECT id, status
                    FROM turns
                    WHERE session_id = ? AND created_at >= ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (session_id, user_created_at),
                ).fetchone()
                if turn_row is not None:
                    turn_id = turn_row["id"]
                    was_running = turn_row["status"] == "running"

            if was_running:
                return {
                    "deleted": False,
                    "attachment_ids": [],
                    "turn_id": turn_id,
                    "was_running": True,
                }

            attachment_ids: list[str] = []
            for m in [msg, paired_msg]:
                if m is not None:
                    atts = _json_loads(m["attachments_json"], [])
                    for att in atts:
                        aid = att.get("id") or att.get("attachment_id")
                        if aid:
                            attachment_ids.append(aid)

            if turn_id is not None:
                conn.execute("DELETE FROM turn_events WHERE turn_id = ?", (turn_id,))
                conn.execute("DELETE FROM turns WHERE id = ?", (turn_id,))

            ids_to_delete = [int(message_id)]
            if paired_msg is not None:
                ids_to_delete.append(int(paired_msg["id"]))
            conn.execute(
                f"DELETE FROM messages WHERE id IN ({','.join('?' * len(ids_to_delete))})",  # nosec B608
                tuple(ids_to_delete),
            )

            session_row = conn.execute(
                "SELECT summary_up_to_msg_id FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if session_row is not None:
                summary_up_to = int(session_row["summary_up_to_msg_id"])
                if any(mid <= summary_up_to for mid in ids_to_delete):
                    conn.execute(
                        "UPDATE sessions SET summary_up_to_msg_id = 0 WHERE id = ?",
                        (session_id,),
                    )

            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )
            conn.commit()

        return {
            "deleted": True,
            "attachment_ids": attachment_ids,
            "turn_id": turn_id,
            "was_running": was_running,
        }

    async def delete_turn_by_message(self, session_id: str, message_id: int) -> dict[str, Any]:
        return await self._run(self._delete_turn_by_message_sync, session_id, message_id)

    def _get_last_message_sync(
        self, session_id: str, role: str | None = None
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            if role is None:
                row = conn.execute(
                    """
                    SELECT id, session_id, role, content, capability, events_json,
                           attachments_json, metadata_json, created_at, parent_message_id
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id, session_id, role, content, capability, events_json,
                           attachments_json, metadata_json, created_at, parent_message_id
                    FROM messages
                    WHERE session_id = ? AND role = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (session_id, role),
                ).fetchone()
        if row is None:
            return None
        return self._serialize_message(row)

    async def get_last_message(
        self, session_id: str, role: str | None = None
    ) -> dict[str, Any] | None:
        return await self._run(self._get_last_message_sync, session_id, role)

    def _serialize_message(self, row: sqlite3.Row) -> dict[str, Any]:
        row_keys = row.keys()
        parent_id = row["parent_message_id"] if "parent_message_id" in row_keys else None
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "capability": row["capability"] or "",
            "events": _json_loads(row["events_json"], []),
            "attachments": _json_loads(row["attachments_json"], []),
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "parent_message_id": int(parent_id) if parent_id is not None else None,
        }

    def _get_messages_sync(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, capability, events_json,
                       attachments_json, metadata_json, created_at, parent_message_id
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [self._serialize_message(row) for row in rows]

    def _get_message_path_sync(self, session_id: str, leaf_message_id: int) -> list[dict[str, Any]]:
        """返回从会话根节点到 ``leaf_message_id``（含）的消息链，按时间顺序排列。

        用于 turn runtime 构建分支重跑的 LLM 上下文：
        仅包含新用户消息的祖先节点，因此任何深度的兄弟分支都会被排除。
        """
        with self._connect() as conn:
            chain: list[dict[str, Any]] = []
            current: int | None = int(leaf_message_id)
            # 防御性地限制遍历深度，防止父指针损坏导致的无限循环。
            safety = 10_000
            while current is not None and safety > 0:
                row = conn.execute(
                    """
                    SELECT id, session_id, role, content, capability, events_json,
                           attachments_json, metadata_json, created_at, parent_message_id
                    FROM messages
                    WHERE id = ? AND session_id = ?
                    """,
                    (current, session_id),
                ).fetchone()
                if row is None:
                    break
                chain.append(self._serialize_message(row))
                parent = row["parent_message_id"]
                current = int(parent) if parent is not None else None
                safety -= 1
        chain.reverse()
        return chain

    async def get_message_path(self, session_id: str, leaf_message_id: int) -> list[dict[str, Any]]:
        return await self._run(self._get_message_path_sync, session_id, int(leaf_message_id))

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        return await self._run(self._get_messages_sync, session_id)

    def _get_messages_for_context_sync(
        self, session_id: str, leaf_message_id: int | None = None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if leaf_message_id is None:
                rows = conn.execute(
                    """
                    SELECT id, role, content
                    FROM messages
                    WHERE session_id = ?
                      AND role IN ('user', 'assistant', 'system')
                    ORDER BY id ASC
                    """,
                    (session_id,),
                ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "role": row["role"],
                        "content": row["content"] or "",
                    }
                    for row in rows
                ]
            # 分支感知路径遍历：仅包含祖先节点（+叶子节点），
            # 使任何深度的兄弟分支都被排除在 LLM 上下文之外。
            chain: list[dict[str, Any]] = []
            current: int | None = int(leaf_message_id)
            safety = 10_000
            while current is not None and safety > 0:
                row = conn.execute(
                    """
                    SELECT id, role, content, parent_message_id
                    FROM messages
                    WHERE id = ? AND session_id = ?
                      AND role IN ('user', 'assistant', 'system')
                    """,
                    (current, session_id),
                ).fetchone()
                if row is None:
                    break
                chain.append(
                    {
                        "id": row["id"],
                        "role": row["role"],
                        "content": row["content"] or "",
                    }
                )
                parent = row["parent_message_id"]
                current = int(parent) if parent is not None else None
                safety -= 1
        chain.reverse()
        return chain

    async def get_messages_for_context(
        self, session_id: str, leaf_message_id: int | None = None
    ) -> list[dict[str, Any]]:
        return await self._run(self._get_messages_for_context_sync, session_id, leaf_message_id)

    def _list_sessions_sync(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    s.compressed_summary,
                    s.summary_up_to_msg_id,
                    s.preferences_json,
                    COUNT(m.id) AS message_count,
                    COALESCE(
                        (
                            SELECT t.status
                            FROM turns t
                            WHERE t.session_id = s.id
                            ORDER BY t.updated_at DESC
                            LIMIT 1
                        ),
                        'idle'
                    ) AS status,
                    COALESCE(
                        (
                            SELECT t.id
                            FROM turns t
                            WHERE t.session_id = s.id AND t.status = 'running'
                            ORDER BY t.updated_at DESC
                            LIMIT 1
                        ),
                        ''
                    ) AS active_turn_id,
                    COALESCE(
                        (
                            SELECT t.capability
                            FROM turns t
                            WHERE t.session_id = s.id
                            ORDER BY t.updated_at DESC
                            LIMIT 1
                        ),
                        ''
                    ) AS capability,
                    COALESCE(
                        (
                            SELECT m2.content
                            FROM messages m2
                            WHERE m2.session_id = s.id
                              AND TRIM(COALESCE(m2.content, '')) != ''
                            ORDER BY m2.id DESC
                            LIMIT 1
                        ),
                        ''
                    ) AS last_message
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        sessions = []
        for row in rows:
            payload = dict(row)
            payload["session_id"] = payload["id"]
            payload["preferences"] = _json_loads(payload.pop("preferences_json", ""), {})
            sessions.append(payload)
        return sessions

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._run(self._list_sessions_sync, limit, offset)

    def _update_summary_sync(self, session_id: str, summary: str, up_to_msg_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE sessions
                SET compressed_summary = ?, summary_up_to_msg_id = ?, updated_at = updated_at
                WHERE id = ?
                """,
                (summary, max(0, int(up_to_msg_id)), session_id),
            )
            conn.commit()
        return cur.rowcount > 0

    async def update_summary(self, session_id: str, summary: str, up_to_msg_id: int) -> bool:
        return await self._run(self._update_summary_sync, session_id, summary, up_to_msg_id)

    def _update_session_preferences_sync(
        self, session_id: str, preferences: dict[str, Any]
    ) -> bool:
        with self._connect() as conn:
            current = conn.execute(
                "SELECT preferences_json FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if current is None:
                return False
            merged = {
                **_json_loads(current["preferences_json"], {}),
                **(preferences or {}),
            }
            cur = conn.execute(
                """
                UPDATE sessions
                SET preferences_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (_json_dumps(merged), time.time(), session_id),
            )
            conn.commit()
        return cur.rowcount > 0

    async def update_session_preferences(
        self, session_id: str, preferences: dict[str, Any]
    ) -> bool:
        return await self._run(self._update_session_preferences_sync, session_id, preferences)

    async def get_session_with_messages(self, session_id: str) -> dict[str, Any] | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        session["messages"] = await self.get_messages(session_id)
        session["active_turns"] = await self.list_active_turns(session_id)
        return session

    # ── 笔记本条目 ──────────────────────────────────────────────

    def _upsert_notebook_entries_sync(self, session_id: str, items: list[dict[str, Any]]) -> int:
        if not items:
            return 0
        now = time.time()
        with self._connect() as conn:
            if (
                conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
                is None
            ):
                raise ValueError(f"Session not found: {session_id}")
            upserted = 0
            for item in items:
                question = (item.get("question") or "").strip()
                question_id = (item.get("question_id") or "").strip()
                if not question or not question_id:
                    continue
                turn_id = (item.get("turn_id") or "").strip()
                # ``user_answer_images`` 是可选的记录列表
                # ``[{id, url, filename, mime_type}, ...]``。在此序列化，
                # 使只处理文本的调用方无需了解 JSON。``None`` 在 UPDATE 时
                # 保留现有列值（避免在仅更改 ``is_correct`` 的部分更新中
                # 覆盖已存储的图片）。
                images_value = item.get("user_answer_images")
                images_json = _json_dumps(images_value) if isinstance(images_value, list) else None
                if images_json is None:
                    conn.execute(
                        """
                        INSERT INTO notebook_entries (
                            session_id, turn_id, question_id, question, question_type,
                            options_json, correct_answer, explanation, difficulty,
                            user_answer, user_answer_images_json, is_correct,
                            bookmarked, followup_session_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, 0, '', ?, ?)
                        ON CONFLICT(session_id, turn_id, question_id) DO UPDATE SET
                            user_answer = excluded.user_answer,
                            is_correct = excluded.is_correct,
                            updated_at = excluded.updated_at
                        """,
                        (
                            session_id,
                            turn_id,
                            question_id,
                            question,
                            item.get("question_type") or "",
                            _json_dumps(item.get("options") or {}),
                            item.get("correct_answer") or "",
                            item.get("explanation") or "",
                            item.get("difficulty") or "",
                            item.get("user_answer") or "",
                            1 if item.get("is_correct") else 0,
                            now,
                            now,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO notebook_entries (
                            session_id, turn_id, question_id, question, question_type,
                            options_json, correct_answer, explanation, difficulty,
                            user_answer, user_answer_images_json, is_correct,
                            bookmarked, followup_session_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?)
                        ON CONFLICT(session_id, turn_id, question_id) DO UPDATE SET
                            user_answer = excluded.user_answer,
                            user_answer_images_json = excluded.user_answer_images_json,
                            is_correct = excluded.is_correct,
                            updated_at = excluded.updated_at
                        """,
                        (
                            session_id,
                            turn_id,
                            question_id,
                            question,
                            item.get("question_type") or "",
                            _json_dumps(item.get("options") or {}),
                            item.get("correct_answer") or "",
                            item.get("explanation") or "",
                            item.get("difficulty") or "",
                            item.get("user_answer") or "",
                            images_json,
                            1 if item.get("is_correct") else 0,
                            now,
                            now,
                        ),
                    )
                upserted += 1
            conn.commit()
        return upserted

    async def upsert_notebook_entries(self, session_id: str, items: list[dict[str, Any]]) -> int:
        return await self._run(self._upsert_notebook_entries_sync, session_id, items)

    @staticmethod
    def _serialize_notebook_entry(row: sqlite3.Row) -> dict[str, Any]:
        keys = set(row.keys())
        images: list[dict[str, Any]] = []
        if "user_answer_images_json" in keys:
            raw_images = _json_loads(row["user_answer_images_json"], [])
            if isinstance(raw_images, list):
                images = [r for r in raw_images if isinstance(r, dict)]
        return {
            "id": int(row["id"]),
            "session_id": row["session_id"],
            "session_title": row["session_title"] or "" if "session_title" in keys else "",
            "turn_id": (row["turn_id"] or "") if "turn_id" in keys else "",
            "question_id": row["question_id"] or "",
            "question": row["question"],
            "question_type": row["question_type"] or "",
            "options": _json_loads(row["options_json"], {}),
            "correct_answer": row["correct_answer"] or "",
            "explanation": row["explanation"] or "",
            "difficulty": row["difficulty"] or "",
            "user_answer": row["user_answer"] or "",
            "user_answer_images": images,
            "is_correct": bool(row["is_correct"]),
            "bookmarked": bool(row["bookmarked"]),
            "followup_session_id": row["followup_session_id"] or "",
            "ai_judgment": (row["ai_judgment"] or "") if "ai_judgment" in keys else "",
            "created_at": float(row["created_at"]),
            "updated_at": float(row["updated_at"]),
        }

    def _list_notebook_entries_sync(
        self,
        category_id: int | None,
        bookmarked: bool | None,
        is_correct: bool | None,
        limit: int,
        offset: int,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        base = """
            SELECT
                n.id, n.session_id, COALESCE(s.title, '') AS session_title,
                n.turn_id, n.question_id, n.question, n.question_type, n.options_json,
                n.correct_answer, n.explanation, n.difficulty,
                n.user_answer, n.user_answer_images_json, n.is_correct, n.bookmarked,
                n.followup_session_id, n.ai_judgment, n.created_at, n.updated_at
            FROM notebook_entries n
            LEFT JOIN sessions s ON s.id = n.session_id
        """
        count_base = "SELECT COUNT(*) AS cnt FROM notebook_entries n"
        conditions: list[str] = []
        params: list[Any] = []
        if category_id is not None:
            join = " INNER JOIN notebook_entry_categories ec ON ec.entry_id = n.id"
            base += join
            count_base += join
            conditions.append("ec.category_id = ?")
            params.append(category_id)
        if bookmarked is not None:
            conditions.append("n.bookmarked = ?")
            params.append(1 if bookmarked else 0)
        if is_correct is not None:
            conditions.append("n.is_correct = ?")
            params.append(1 if is_correct else 0)
        if session_id is not None:
            conditions.append("n.session_id = ?")
            params.append(session_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._connect() as conn:
            total_row = conn.execute(count_base + where, tuple(params)).fetchone()
            total = int(total_row["cnt"]) if total_row else 0
            rows = conn.execute(
                base + where + " ORDER BY n.created_at DESC LIMIT ? OFFSET ?",
                tuple(params) + (limit, offset),
            ).fetchall()
        items = [self._serialize_notebook_entry(r) for r in rows]
        return {"items": items, "total": total}

    async def list_notebook_entries(
        self,
        category_id: int | None = None,
        bookmarked: bool | None = None,
        is_correct: bool | None = None,
        limit: int = 50,
        offset: int = 0,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._run(
            self._list_notebook_entries_sync,
            category_id,
            bookmarked,
            is_correct,
            limit,
            offset,
            session_id,
        )

    def _get_notebook_entry_sync(self, entry_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    n.*, COALESCE(s.title, '') AS session_title
                FROM notebook_entries n
                LEFT JOIN sessions s ON s.id = n.session_id
                WHERE n.id = ?
                """,
                (entry_id,),
            ).fetchone()
            if row is None:
                return None
            entry = self._serialize_notebook_entry(row)
            cats = conn.execute(
                """
                SELECT c.id, c.name
                FROM notebook_categories c
                INNER JOIN notebook_entry_categories ec ON ec.category_id = c.id
                WHERE ec.entry_id = ?
                ORDER BY c.name
                """,
                (entry_id,),
            ).fetchall()
            entry["categories"] = [{"id": c["id"], "name": c["name"]} for c in cats]
        return entry

    async def get_notebook_entry(self, entry_id: int) -> dict[str, Any] | None:
        return await self._run(self._get_notebook_entry_sync, entry_id)

    def _find_notebook_entry_sync(
        self,
        session_id: str,
        question_id: str,
        turn_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            if turn_id is not None:
                row = conn.execute(
                    """
                    SELECT n.*, COALESCE(s.title, '') AS session_title
                    FROM notebook_entries n
                    LEFT JOIN sessions s ON s.id = n.session_id
                    WHERE n.session_id = ?
                      AND n.turn_id = ?
                      AND n.question_id = ?
                    """,
                    (session_id, turn_id, question_id),
                ).fetchone()
            else:
                # 旧版查找：返回跨轮次的最近匹配条目。
                # 同一会话中的两个测验可以共享 question_id
                # （位置 ID 如 ``q_1``），因此明确选择最新的一个，
                # 以确保尚未传递 turn_id 的调用方行为确定性。
                row = conn.execute(
                    """
                    SELECT n.*, COALESCE(s.title, '') AS session_title
                    FROM notebook_entries n
                    LEFT JOIN sessions s ON s.id = n.session_id
                    WHERE n.session_id = ? AND n.question_id = ?
                    ORDER BY n.updated_at DESC, n.id DESC
                    LIMIT 1
                    """,
                    (session_id, question_id),
                ).fetchone()
        if row is None:
            return None
        return self._serialize_notebook_entry(row)

    async def find_notebook_entry(
        self,
        session_id: str,
        question_id: str,
        turn_id: str | None = None,
    ) -> dict[str, Any] | None:
        return await self._run(self._find_notebook_entry_sync, session_id, question_id, turn_id)

    def _update_notebook_entry_sync(self, entry_id: int, updates: dict[str, Any]) -> bool:
        allowed = {
            "bookmarked",
            "followup_session_id",
            "user_answer",
            "is_correct",
            "ai_judgment",
        }
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False
        fields["updated_at"] = time.time()
        if "bookmarked" in fields:
            fields["bookmarked"] = 1 if fields["bookmarked"] else 0
        if "is_correct" in fields:
            fields["is_correct"] = 1 if fields["is_correct"] else 0
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [entry_id]
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE notebook_entries SET {set_clause} WHERE id = ?",  # nosec B608
                tuple(values),
            )
            conn.commit()
        return cur.rowcount > 0

    async def update_notebook_entry(self, entry_id: int, updates: dict[str, Any]) -> bool:
        return await self._run(self._update_notebook_entry_sync, entry_id, updates)

    def _delete_notebook_entry_sync(self, entry_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM notebook_entries WHERE id = ?", (entry_id,))
            conn.commit()
        return cur.rowcount > 0

    async def delete_notebook_entry(self, entry_id: int) -> bool:
        return await self._run(self._delete_notebook_entry_sync, entry_id)

    # ── 笔记本分类 ────────────────────────────────────────

    def _create_category_sync(self, name: str) -> dict[str, Any]:
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO notebook_categories (name, created_at) VALUES (?, ?)",
                (name.strip(), now),
            )
            conn.commit()
        return {"id": int(cur.lastrowid), "name": name.strip(), "created_at": now}

    async def create_category(self, name: str) -> dict[str, Any]:
        return await self._run(self._create_category_sync, name)

    def _list_categories_sync(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.created_at,
                       COUNT(ec.entry_id) AS entry_count
                FROM notebook_categories c
                LEFT JOIN notebook_entry_categories ec ON ec.category_id = c.id
                GROUP BY c.id
                ORDER BY c.name
                """,
            ).fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "created_at": float(r["created_at"]),
                "entry_count": int(r["entry_count"]),
            }
            for r in rows
        ]

    async def list_categories(self) -> list[dict[str, Any]]:
        return await self._run(self._list_categories_sync)

    def _rename_category_sync(self, category_id: int, name: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE notebook_categories SET name = ? WHERE id = ?",
                (name.strip(), category_id),
            )
            conn.commit()
        return cur.rowcount > 0

    async def rename_category(self, category_id: int, name: str) -> bool:
        return await self._run(self._rename_category_sync, category_id, name)

    def _delete_category_sync(self, category_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM notebook_categories WHERE id = ?", (category_id,))
            conn.commit()
        return cur.rowcount > 0

    async def delete_category(self, category_id: int) -> bool:
        return await self._run(self._delete_category_sync, category_id)

    def _add_entry_to_category_sync(self, entry_id: int, category_id: int) -> bool:
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO notebook_entry_categories (entry_id, category_id) VALUES (?, ?)",
                    (entry_id, category_id),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return False
        return True

    async def add_entry_to_category(self, entry_id: int, category_id: int) -> bool:
        return await self._run(self._add_entry_to_category_sync, entry_id, category_id)

    def _remove_entry_from_category_sync(self, entry_id: int, category_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM notebook_entry_categories WHERE entry_id = ? AND category_id = ?",
                (entry_id, category_id),
            )
            conn.commit()
        return cur.rowcount > 0

    async def remove_entry_from_category(self, entry_id: int, category_id: int) -> bool:
        return await self._run(self._remove_entry_from_category_sync, entry_id, category_id)

    def _get_entry_categories_sync(self, entry_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name FROM notebook_categories c
                INNER JOIN notebook_entry_categories ec ON ec.category_id = c.id
                WHERE ec.entry_id = ?
                ORDER BY c.name
                """,
                (entry_id,),
            ).fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    async def get_entry_categories(self, entry_id: int) -> list[dict[str, Any]]:
        return await self._run(self._get_entry_categories_sync, entry_id)


_instances: dict[str, SQLiteSessionStore] = {}


def get_sqlite_session_store() -> SQLiteSessionStore:
    db_path = get_path_service().get_chat_history_db().resolve()
    key = str(db_path)
    if key not in _instances:
        _instances[key] = SQLiteSessionStore(db_path=db_path)
    return _instances[key]


__all__ = ["SQLiteSessionStore", "get_sqlite_session_store"]
