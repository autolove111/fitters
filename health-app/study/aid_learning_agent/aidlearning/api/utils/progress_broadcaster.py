"""
进度广播器 - 管理知识库进度的 WebSocket 广播
"""

import asyncio
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ProgressBroadcaster:
    """管理知识库进度的 WebSocket 广播"""

    _instance: Optional["ProgressBroadcaster"] = None
    _connections: dict[str, set[WebSocket]] = {}  # 知识库名称 -> WebSocket 集合
    _lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "ProgressBroadcaster":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self, kb_name: str, websocket: WebSocket):
        """将 WebSocket 连接到指定的知识库"""
        async with self._lock:
            if kb_name not in self._connections:
                self._connections[kb_name] = set()
            self._connections[kb_name].add(websocket)
            logger.debug(
                f"Connected WebSocket for KB '{kb_name}' (total: {len(self._connections[kb_name])})"
            )

    async def disconnect(self, kb_name: str, websocket: WebSocket):
        """断开 WebSocket 连接"""
        async with self._lock:
            if kb_name in self._connections:
                self._connections[kb_name].discard(websocket)
                if not self._connections[kb_name]:
                    del self._connections[kb_name]
                logger.debug(f"Disconnected WebSocket for KB '{kb_name}'")

    async def broadcast(self, kb_name: str, progress: dict):
        """向指定知识库的所有 WebSocket 连接广播进度更新"""
        async with self._lock:
            if kb_name not in self._connections:
                return

            # 创建待移除的连接列表（已关闭的连接）
            to_remove = []

            for websocket in self._connections[kb_name]:
                try:
                    await websocket.send_json({"type": "progress", "data": progress})
                except Exception as e:
                    # 连接已关闭或出错，标记为待移除
                    logger.debug(f"Error sending to WebSocket for KB '{kb_name}': {e}")
                    to_remove.append(websocket)

            # 移除已关闭的连接
            for ws in to_remove:
                self._connections[kb_name].discard(ws)

            if not self._connections[kb_name]:
                del self._connections[kb_name]

    def get_connection_count(self, kb_name: str) -> int:
        """获取指定知识库的连接数"""
        return len(self._connections.get(kb_name, set()))
