"""
流式总线
==========

工具/能力向其中发射事件、消费者
（CLI 渲染器、WebSocket 推送器、JSON 写入器）从中读取的异步事件通道。

用法::

    bus = StreamBus()

    # 生产者端（在能力内部）
    await bus.emit(StreamEvent(type=StreamEventType.CONTENT, content="Hello"))

    # 消费者端
    async for event in bus.subscribe():
        print(event.content)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from typing import Any, AsyncIterator

from .stream import StreamEvent, StreamEventType
from .trace import merge_trace_metadata


class StreamBus:
    """单个聊天轮次的扇出异步事件总线。"""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[StreamEvent | None]] = []
        self._closed = False
        self._history: list[StreamEvent] = []

    async def emit(self, event: StreamEvent) -> None:
        """将 *event* 推送给每个活跃的订阅者。"""
        if self._closed:
            return
        self._history.append(event)
        for q in self._subscribers:
            await q.put(event)

    async def subscribe(self) -> AsyncIterator[StreamEvent]:
        """产出事件直到总线关闭。"""
        q: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
        self._subscribers.append(q)
        try:
            for event in self._history:
                yield event
            if self._closed and q.empty():
                return
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            self._subscribers.remove(q)

    async def close(self) -> None:
        """通知所有订阅者流已结束。"""
        self._closed = True
        for q in self._subscribers:
            await q.put(None)

    # ---- 生产者便捷方法 ----

    @asynccontextmanager
    async def stage(
        self,
        name: str,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        """在代码块前后发射 STAGE_START / STAGE_END 的上下文管理器。"""
        await self.emit(
            StreamEvent(
                type=StreamEventType.STAGE_START,
                source=source,
                stage=name,
                metadata=metadata or {},
            )
        )
        try:
            yield
        finally:
            await self.emit(
                StreamEvent(
                    type=StreamEventType.STAGE_END,
                    source=source,
                    stage=name,
                    metadata=metadata or {},
                )
            )

    async def content(
        self,
        text: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.CONTENT,
                source=source,
                stage=stage,
                content=text,
                metadata=metadata or {},
            )
        )

    async def thinking(
        self,
        text: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.THINKING,
                source=source,
                stage=stage,
                content=text,
                metadata=metadata or {},
            )
        )

    async def observation(
        self,
        text: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.OBSERVATION,
                source=source,
                stage=stage,
                content=text,
                metadata=metadata or {},
            )
        )

    async def tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.TOOL_CALL,
                source=source,
                stage=stage,
                content=tool_name,
                metadata=merge_trace_metadata({"args": args}, metadata),
            )
        )

    async def tool_result(
        self,
        tool_name: str,
        result: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                source=source,
                stage=stage,
                content=result,
                metadata=merge_trace_metadata({"tool": tool_name}, metadata),
            )
        )

    async def progress(
        self,
        message: str,
        current: int = 0,
        total: int = 0,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.PROGRESS,
                source=source,
                stage=stage,
                content=message,
                metadata=merge_trace_metadata(
                    {"current": current, "total": total},
                    metadata,
                ),
            )
        )

    async def sources(
        self,
        sources: list[dict[str, Any]],
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.SOURCES,
                source=source,
                stage=stage,
                metadata=merge_trace_metadata({"sources": sources}, metadata),
            )
        )

    async def result(
        self,
        data: dict[str, Any],
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.RESULT,
                source=source,
                metadata=merge_trace_metadata(data, metadata),
            )
        )

    async def error(
        self,
        message: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.ERROR,
                source=source,
                stage=stage,
                content=message,
                metadata=metadata or {},
            )
        )

    # ---- 消费者适配器 ----

    @staticmethod
    def event_to_json(event: StreamEvent) -> str:
        """将事件序列化为单行 JSON 字符串（NDJSON 格式）。"""
        return json.dumps(event.to_dict(), ensure_ascii=False)
