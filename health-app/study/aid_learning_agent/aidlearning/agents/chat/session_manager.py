#!/usr/bin/env python
"""
SessionManager — 对话会话管理器

【调用链路位置】chat.py → SessionManager → BaseSessionManager → JSON 文件持久化

职责：
  - 创建新会话（生成 session_id）
  - 添加消息（user / assistant）
  - 读取会话历史
  - 列出最近会话
  - 删除会话

存储位置：data/user/workspace/chat/chat/sessions.json
"""

from typing import Any

from aidlearning.services.session import BaseSessionManager


class SessionManager(BaseSessionManager):
    """
    管理会话的持久化存储。

    遗留 JSON 会话存储在 ``data/user/workspace/chat/chat/sessions.json``。
    每个会话包含：
    - session_id: 唯一标识符
    - title: 会话标题（通常是第一条用户消息）
    - messages: 消息列表，包含 role、content、sources、timestamp
    - settings: 使用的 RAG/网页搜索设置
    - created_at: 创建时间戳
    - updated_at: 最后更新时间戳
    """

    def __init__(self):
        """初始化 SessionManager。"""
        super().__init__("chat")

    # =========================================================================
    # BaseSessionManager 抽象方法实现
    # =========================================================================

    def _get_session_id_prefix(self) -> str:
        """返回会话 ID 的前缀。"""
        return "chat_"

    def _get_default_title(self) -> str:
        """返回新会话的默认标题。"""
        return "New Chat"

    def _create_session_data(
        self,
        settings: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        创建 chat 专属的会话数据。

        Args:
            settings: 聊天设置（kb_name、enable_rag、enable_web_search）

        Returns:
            包含设置的字典
        """
        return {
            "settings": settings or {},
        }

    def _get_session_summary(self, session: dict[str, Any]) -> dict[str, Any]:
        """
        创建聊天会话的摘要用于列表展示。

        Args:
            session: 完整的会话数据

        Returns:
            包含摘要字段的字典
        """
        messages = session.get("messages", [])
        return {
            "session_id": session.get("session_id"),
            "title": session.get("title"),
            "message_count": len(messages),
            "settings": session.get("settings"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            # 包含最后一条消息的预览
            "last_message": (messages[-1].get("content", "")[:100] if messages else ""),
        }

    # =========================================================================
    # Chat 专属方法
    # =========================================================================

    def create_session(
        self,
        title: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        创建新的聊天会话。

        Args:
            title: 会话标题（为 None 时使用默认值）
            settings: 可选设置（kb_name、enable_rag、enable_web_search）

        Returns:
            包含 session_id 的新会话字典
        """
        return super().create_session(
            title=title,
            settings=settings,
        )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        向会话添加单条消息。

        Args:
            session_id: 会话标识符
            role: 消息角色（'user' 或 'assistant'）
            content: 消息内容
            sources: 可选的来源字典（用于助手消息）

        Returns:
            更新后的会话，未找到时返回 None
        """
        return super().add_message(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
        )

    def update_session(
        self,
        session_id: str,
        messages: list[dict[str, Any]] | None = None,
        title: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        用新数据更新会话。

        Args:
            session_id: 会话标识符
            messages: 新消息列表（替换现有）
            title: 新标题（可选）
            settings: 新设置（可选）

        Returns:
            更新后的会话，未找到时返回 None
        """
        return super().update_session(
            session_id=session_id,
            messages=messages,
            title=title,
            settings=settings,
        )


# 便捷的单例实例
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """获取或创建全局 SessionManager 实例。"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


__all__ = ["SessionManager", "get_session_manager"]
