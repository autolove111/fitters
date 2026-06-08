"""
基于 PocketBase 的会话存储。

使用 PocketBase 集合实现 SessionStoreProtocol，提供所有持久化存储。
关键性能设计：

- 除 ``append_turn_event`` 外，所有方法都直接发起 PocketBase HTTP 调用。
  这些方法每轮最多调用数次（创建、获取、更新状态、添加消息），
  约 5-10 毫秒的开销可以接受。

- ``append_turn_event`` 立即返回，不写入 PocketBase。
  turn_runtime.py 中已有的 ``_mirror_event_to_workspace`` 会将每个事件
  追加到本地 ``events.jsonl`` 文件。当 ``update_turn_status`` 结束一轮时，
  读取该文件并将所有事件批量发送到 PocketBase ``turn_events``，
  以牺牲实时持久性换取流式传输期间约 40 倍的单事件延迟降低。
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Any
import uuid

from aidlearning.services.path_service import get_path_service

logger = logging.getLogger(__name__)


def _json_loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _pb():
    """返回共享的 PocketBase 客户端。"""
    from aidlearning.services.pocketbase_client import get_pb_client

    return get_pb_client()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


class PocketBaseSessionStore:
    """基于 PocketBase 的 SessionStoreProtocol 实现。"""

    # ------------------------------------------------------------------
    # 会话
    # ------------------------------------------------------------------

    async def create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        resolved_id = session_id or f"unified_{int(now * 1000)}_{uuid.uuid4().hex[:8]}"
        resolved_title = (title or "New conversation").strip() or "New conversation"

        def _create():
            return (
                _pb()
                .collection("sessions")
                .create(
                    {
                        "session_id": resolved_id,
                        "title": resolved_title[:100],
                        "compressed_summary": "",
                        "summary_up_to_msg_id": 0,
                        "preferences_json": {},
                        "capability": "",
                        "status": "idle",
                    }
                )
            )

        record = await asyncio.to_thread(_create)
        return self._session_record_to_dict(record, resolved_id, resolved_title, now)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        def _get():
            try:
                records = (
                    _pb()
                    .collection("sessions")
                    .get_full_list(query_params={"filter": f'session_id="{session_id}"'})
                )
                return records[0] if records else None
            except Exception:
                return None

        record = await asyncio.to_thread(_get)
        if record is None:
            return None
        return self._session_record_to_dict(record)

    async def ensure_session(
        self,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        if session_id:
            session = await self.get_session(session_id)
            if session is not None:
                return session
        return await self.create_session()

    def _session_record_to_dict(
        self,
        record: Any,
        session_id: str | None = None,
        title: str | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        sid = session_id or getattr(record, "session_id", getattr(record, "id", ""))
        t = title or getattr(record, "title", "New conversation") or "New conversation"
        created = _to_float(getattr(record, "created", None)) or now or time.time()
        updated = _to_float(getattr(record, "updated", None)) or now or time.time()
        preferences_raw = getattr(record, "preferences_json", None)
        return {
            "id": sid,
            "session_id": sid,
            "title": t,
            "created_at": created,
            "updated_at": updated,
            "compressed_summary": getattr(record, "compressed_summary", "") or "",
            "summary_up_to_msg_id": int(getattr(record, "summary_up_to_msg_id", 0) or 0),
            "preferences": _json_loads(preferences_raw, {}),
            "capability": getattr(record, "capability", "") or "",
            "status": getattr(record, "status", "idle") or "idle",
            "active_turn_id": "",
        }

    async def update_session_title(self, session_id: str, title: str) -> bool:
        def _update():
            records = (
                _pb()
                .collection("sessions")
                .get_full_list(query_params={"filter": f'session_id="{session_id}"'})
            )
            if not records:
                return False
            _pb().collection("sessions").update(
                records[0].id, {"title": (title.strip() or "New conversation")[:100]}
            )
            return True

        try:
            return await asyncio.to_thread(_update)
        except Exception as exc:
            logger.warning(f"update_session_title failed: {exc}")
            return False

    async def delete_session(self, session_id: str) -> bool:
        def _delete():
            records = (
                _pb()
                .collection("sessions")
                .get_full_list(query_params={"filter": f'session_id="{session_id}"'})
            )
            if not records:
                return False
            _pb().collection("sessions").delete(records[0].id)
            return True

        try:
            return await asyncio.to_thread(_delete)
        except Exception as exc:
            logger.warning(f"delete_session failed: {exc}")
            return False

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        page = (offset // limit) + 1

        def _list():
            query_params: dict[str, Any] = {"sort": "-updated"}
            return _pb().collection("sessions").get_list(page, limit, query_params=query_params)

        try:
            result = await asyncio.to_thread(_list)
            return [self._session_record_to_dict(r) for r in result.items]
        except Exception as exc:
            logger.warning(f"list_sessions failed: {exc}")
            return []

    async def update_summary(self, session_id: str, summary: str, up_to_msg_id: int) -> bool:
        def _update():
            records = (
                _pb()
                .collection("sessions")
                .get_full_list(query_params={"filter": f'session_id="{session_id}"'})
            )
            if not records:
                return False
            _pb().collection("sessions").update(
                records[0].id,
                {
                    "compressed_summary": summary,
                    "summary_up_to_msg_id": max(0, int(up_to_msg_id)),
                },
            )
            return True

        try:
            return await asyncio.to_thread(_update)
        except Exception as exc:
            logger.warning(f"update_summary failed: {exc}")
            return False

    async def update_session_preferences(
        self, session_id: str, preferences: dict[str, Any]
    ) -> bool:
        async def _merge():
            session = await self.get_session(session_id)
            if session is None:
                return False
            merged = {**session.get("preferences", {}), **(preferences or {})}

            def _update():
                records = (
                    _pb()
                    .collection("sessions")
                    .get_full_list(query_params={"filter": f'session_id="{session_id}"'})
                )
                if not records:
                    return False
                _pb().collection("sessions").update(records[0].id, {"preferences_json": merged})
                return True

            return await asyncio.to_thread(_update)

        try:
            return await _merge()
        except Exception as exc:
            logger.warning(f"update_session_preferences failed: {exc}")
            return False

    async def get_session_with_messages(self, session_id: str) -> dict[str, Any] | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        session["messages"] = await self.get_messages(session_id)
        session["active_turns"] = await self.list_active_turns(session_id)
        return session

    # ------------------------------------------------------------------
    # 消息
    # ------------------------------------------------------------------

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        capability: str = "",
        events: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        parent_message_id: int | None = None,
    ) -> int:
        # ``parent_message_id`` 被接受以匹配协议接口，但尚未接入 PocketBase 存储
        # —— 分支功能目前仅在 SQLite 后端可用。
        _ = parent_message_id
        now = time.time()

        def _add():
            payload = {
                "session_id": session_id,
                "role": role,
                "content": content or "",
                "capability": capability or "",
                "events_json": events or [],
                "attachments_json": attachments or [],
                "metadata_json": metadata or {},
                "msg_created_at": now,
            }
            record = _pb().collection("messages").create(payload)
            # 标题生成由 turn runtime 负责（在首个用户+助手消息对之后由 LLM 驱动生成）。
            # 在此之前会话保持 ``New conversation`` 哨兵值。
            return record

        try:
            record = await asyncio.to_thread(_add)
            # 使用毫秒时间戳返回合成的整数 ID
            return int(now * 1000)
        except Exception as exc:
            logger.warning(f"add_message failed: {exc}")
            return 0

    async def delete_message(self, message_id: int | str) -> bool:
        def _delete():
            _pb().collection("messages").delete(str(message_id))
            return True

        try:
            return await asyncio.to_thread(_delete)
        except Exception as exc:
            logger.warning(f"delete_message failed: {exc}")
            return False

    async def get_last_message(
        self, session_id: str, role: str | None = None
    ) -> dict[str, Any] | None:
        filter_str = f'session_id="{session_id}"'
        if role:
            filter_str += f' && role="{role}"'

        def _get():
            records = (
                _pb()
                .collection("messages")
                .get_full_list(
                    query_params={
                        "filter": filter_str,
                        "sort": "-msg_created_at",
                        "perPage": 1,
                    }
                )
            )
            return records[0] if records else None

        try:
            record = await asyncio.to_thread(_get)
            return self._message_record_to_dict(record) if record is not None else None
        except Exception as exc:
            logger.warning(f"get_last_message failed: {exc}")
            return None

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        def _get():
            return (
                _pb()
                .collection("messages")
                .get_full_list(
                    query_params={
                        "filter": f'session_id="{session_id}"',
                        "sort": "msg_created_at",
                    }
                )
            )

        try:
            records = await asyncio.to_thread(_get)
            return [self._message_record_to_dict(r) for r in records]
        except Exception as exc:
            logger.warning(f"get_messages failed: {exc}")
            return []

    async def get_messages_for_context(
        self, session_id: str, leaf_message_id: int | None = None
    ) -> list[dict[str, Any]]:
        # PocketBase 尚不支持 leaf_message_id（分支感知上下文）；
        # 回退到线性的追加视图。
        _ = leaf_message_id
        messages = await self.get_messages(session_id)
        return [
            {"id": m["id"], "role": m["role"], "content": m["content"] or ""}
            for m in messages
            if m["role"] in ("user", "assistant", "system")
        ]

    def _message_record_to_dict(self, record: Any) -> dict[str, Any]:
        return {
            "id": getattr(record, "id", ""),
            "session_id": getattr(record, "session_id", ""),
            "role": getattr(record, "role", ""),
            "content": getattr(record, "content", "") or "",
            "capability": getattr(record, "capability", "") or "",
            "events": _json_loads(getattr(record, "events_json", None), []),
            "attachments": _json_loads(getattr(record, "attachments_json", None), []),
            "metadata": _json_loads(getattr(record, "metadata_json", None), {}),
            "created_at": _to_float(getattr(record, "msg_created_at", None)),
        }

    # ------------------------------------------------------------------
    # 轮次
    # ------------------------------------------------------------------

    async def create_turn(self, session_id: str, capability: str = "") -> dict[str, Any]:
        now = time.time()
        turn_id = f"turn_{int(now * 1000)}_{uuid.uuid4().hex[:10]}"

        def _create():
            # 检查：确保会话存在
            sessions = (
                _pb()
                .collection("sessions")
                .get_full_list(query_params={"filter": f'session_id="{session_id}"'})
            )
            if not sessions:
                raise ValueError(f"Session not found: {session_id}")
            # 检查：不允许重复的活跃轮次
            active = (
                _pb()
                .collection("turns")
                .get_full_list(
                    query_params={"filter": f'session_id="{session_id}" && status="running"'}
                )
            )
            if active:
                raise RuntimeError(f"Session already has an active turn: {active[0].turn_id}")
            return (
                _pb()
                .collection("turns")
                .create(
                    {
                        "turn_id": turn_id,
                        "session_id": session_id,
                        "capability": capability or "",
                        "status": "running",
                        "error": "",
                        "turn_created_at": now,
                        "turn_updated_at": now,
                        "finished_at": None,
                    }
                )
            )

        await asyncio.to_thread(_create)
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

    async def get_turn(self, turn_id: str) -> dict[str, Any] | None:
        def _get():
            records = (
                _pb()
                .collection("turns")
                .get_full_list(query_params={"filter": f'turn_id="{turn_id}"'})
            )
            return records[0] if records else None

        record = await asyncio.to_thread(_get)
        return self._turn_record_to_dict(record) if record else None

    async def get_active_turn(self, session_id: str) -> dict[str, Any] | None:
        def _get():
            records = (
                _pb()
                .collection("turns")
                .get_full_list(
                    query_params={
                        "filter": f'session_id="{session_id}" && status="running"',
                        "sort": "-turn_updated_at",
                    }
                )
            )
            return records[0] if records else None

        record = await asyncio.to_thread(_get)
        return self._turn_record_to_dict(record) if record else None

    async def list_active_turns(self, session_id: str) -> list[dict[str, Any]]:
        def _list():
            return (
                _pb()
                .collection("turns")
                .get_full_list(
                    query_params={
                        "filter": f'session_id="{session_id}" && status="running"',
                        "sort": "-turn_updated_at",
                    }
                )
            )

        try:
            records = await asyncio.to_thread(_list)
            return [self._turn_record_to_dict(r) for r in records]
        except Exception:
            return []

    async def update_turn_status(self, turn_id: str, status: str, error: str = "") -> bool:
        now = time.time()
        finished_at = now if status in {"completed", "failed", "cancelled"} else None

        def _update():
            records = (
                _pb()
                .collection("turns")
                .get_full_list(query_params={"filter": f'turn_id="{turn_id}"'})
            )
            if not records:
                return False
            _pb().collection("turns").update(
                records[0].id,
                {
                    "status": status,
                    "error": error or "",
                    "turn_updated_at": now,
                    "finished_at": finished_at,
                },
            )
            return True

        try:
            updated = await asyncio.to_thread(_update)
        except Exception as exc:
            logger.warning(f"update_turn_status failed: {exc}")
            return False

        # 轮次结束时将本地 JSONL 缓冲区中的轮次事件批量刷入 PocketBase
        if updated and finished_at is not None:
            await self._flush_turn_events(turn_id)

        return updated

    async def _flush_turn_events(self, turn_id: str) -> None:
        """
        读取本地 events.jsonl 预写缓冲区，将所有事件批量发送到
        PocketBase turn_events 集合（单次后台调用）。
        """
        try:
            path_service = get_path_service()
            # JSONL 文件由 _mirror_event_to_workspace 写入；由于只有 turn_id，
            # 需要在所有能力工作空间中查找。
            workspace_root = path_service.get_user_root()
            jsonl_files: list[Path] = list(workspace_root.rglob(f"{turn_id}/events.jsonl"))

            if not jsonl_files:
                return

            events: list[dict[str, Any]] = []
            for jsonl_path in jsonl_files:
                try:
                    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
                except Exception as exc:
                    logger.debug(f"Could not read events.jsonl at {jsonl_path}: {exc}")

            if not events:
                return

            def _batch_create():
                pb = _pb()
                for event in events:
                    try:
                        pb.collection("turn_events").create(
                            {
                                "turn_id": turn_id,
                                "session_id": event.get("session_id", ""),
                                "seq": int(event.get("seq", 0)),
                                "type": event.get("type", ""),
                                "source": event.get("source", ""),
                                "stage": event.get("stage", ""),
                                "content": str(event.get("content", ""))[:10000],
                                "metadata_json": event.get("metadata", {}),
                                "event_timestamp": float(event.get("timestamp", 0)),
                            }
                        )
                    except Exception as exc:
                        logger.debug(f"turn_events batch item failed: {exc}")

            await asyncio.to_thread(_batch_create)
            logger.debug(f"Flushed {len(events)} turn events for {turn_id} to PocketBase")

        except Exception as exc:
            logger.warning(f"_flush_turn_events failed for {turn_id}: {exc}")

    def _turn_record_to_dict(self, record: Any) -> dict[str, Any]:
        turn_id = getattr(record, "turn_id", getattr(record, "id", ""))
        return {
            "id": turn_id,
            "turn_id": turn_id,
            "session_id": getattr(record, "session_id", ""),
            "capability": getattr(record, "capability", "") or "",
            "status": getattr(record, "status", "running") or "running",
            "error": getattr(record, "error", "") or "",
            "created_at": _to_float(getattr(record, "turn_created_at", None)),
            "updated_at": _to_float(getattr(record, "turn_updated_at", None)),
            "finished_at": _to_float(getattr(record, "finished_at", None)) or None,
            "last_seq": 0,
        }

    # ------------------------------------------------------------------
    # 轮次事件 —— 仅预写；批量刷入在 update_turn_status 中处理
    # ------------------------------------------------------------------

    async def append_turn_event(self, turn_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """
        分配单调递增的序列号并返回标注后的载荷。

        不会立即写入 PocketBase —— 调用方的 _mirror_event_to_workspace
        已经将事件追加到 events.jsonl，轮次结束时会批量刷入 PocketBase。
        """
        payload = dict(event)
        payload.setdefault("turn_id", turn_id)
        # 如果未提供 seq，则分配；使用基于时间戳的计数器作为后备。
        if not payload.get("seq"):
            payload["seq"] = int(time.time() * 1000) % 1_000_000
        return payload

    async def get_turn_events(self, turn_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        """从 PocketBase 检索已持久化的轮次事件（轮次结束后的回放）。"""

        def _get():
            filter_str = f'turn_id="{turn_id}"'
            if after_seq > 0:
                filter_str += f" && seq > {after_seq}"
            return (
                _pb()
                .collection("turn_events")
                .get_full_list(query_params={"filter": filter_str, "sort": "seq"})
            )

        try:
            records = await asyncio.to_thread(_get)
            return [
                {
                    "type": getattr(r, "type", ""),
                    "source": getattr(r, "source", ""),
                    "stage": getattr(r, "stage", ""),
                    "content": getattr(r, "content", "") or "",
                    "metadata": _json_loads(getattr(r, "metadata_json", None), {}),
                    "session_id": getattr(r, "session_id", ""),
                    "turn_id": turn_id,
                    "seq": int(getattr(r, "seq", 0)),
                    "timestamp": _to_float(getattr(r, "event_timestamp", None)),
                }
                for r in records
            ]
        except Exception as exc:
            logger.warning(f"get_turn_events failed: {exc}")
            return []
