"""
聊天编排器
=================

统一入口点，将用户消息路由到相应的能力。
所有消费者（CLI、WebSocket、SDK）都调用编排器。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator
import uuid

from aidlearning.core.context import UnifiedContext
from aidlearning.core.stream import StreamEvent, StreamEventType
from aidlearning.core.stream_bus import StreamBus
from aidlearning.events.event_bus import Event, EventType, get_event_bus
from aidlearning.runtime.registry.capability_registry import get_capability_registry
from aidlearning.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """将 ``UnifiedContext`` 路由到正确的能力，管理 ``StreamBus`` 生命周期，并发布完成事件。"""

    def __init__(self) -> None:
        self._cap_registry = get_capability_registry()
        self._tool_registry = get_tool_registry()

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        """
        执行单次用户回合并生成流式事件。

        如果设置了 ``context.active_capability``，则由对应的能力处理该回合。
        否则使用默认的 ``chat`` 能力。
        """
        if not context.session_id:
            context.session_id = str(uuid.uuid4())

        # "立即回答"是通用的快速通道，但实际的快速路径是*能力特定的*：
        # chat 在其自身的 ``run()`` 顶部检查 ``answer_now_context``。
        # 解题 / 测验 / 研究刻意不暴露"立即回答"（UI 隐藏了该按钮）。
        # 编排器在此仅添加防御性回退：如果请求的能力已从注册表中移除，
        # 但用户正在使用 ``answer_now``，则路由到 ``chat``，
        # 使其仍能获得某种响应，而不是硬错误。
        cap_name = context.active_capability or "chat"
        capability = self._cap_registry.get(cap_name)

        is_answer_now = bool(
            isinstance(context.config_overrides, dict)
            and context.config_overrides.get("answer_now_context")
        )
        if capability is None and is_answer_now:
            fallback = self._cap_registry.get("chat")
            if fallback is not None:
                logger.info(
                    "Capability %s missing for answer_now; falling back to chat.",
                    cap_name,
                )
                cap_name = "chat"
                capability = fallback

        if capability is None:
            bus = StreamBus()
            await bus.error(
                f"Unknown capability: {cap_name}. "
                f"Available: {self._cap_registry.list_capabilities()}",
                source="orchestrator",
            )
            await bus.close()
            async for event in bus.subscribe():
                yield event
            return

        yield StreamEvent(
            type=StreamEventType.SESSION,
            source="orchestrator",
            metadata={
                "session_id": context.session_id,
                "turn_id": str(context.metadata.get("turn_id", "")),
            },
        )

        bus = StreamBus()

        async def _run() -> None:
            try:
                await capability.run(context, bus)
            except Exception as exc:
                logger.error("Capability %s failed: %s", cap_name, exc, exc_info=True)
                await bus.error(str(exc), source=cap_name)
            finally:
                await bus.emit(StreamEvent(type=StreamEventType.DONE, source=cap_name))
                await bus.close()

        stream = bus.subscribe()
        task = asyncio.create_task(_run())

        async for event in stream:
            yield event

        await task
        await self._publish_completion(context, cap_name)

    async def _publish_completion(self, context: UnifiedContext, cap_name: str) -> None:
        """向全局 EventBus 发布 CAPABILITY_COMPLETE 事件。"""
        try:
            bus = get_event_bus()
            await bus.publish(
                Event(
                    type=EventType.CAPABILITY_COMPLETE,
                    task_id=str(context.metadata.get("turn_id") or context.session_id),
                    user_input=context.user_message,
                    agent_output="",
                    metadata={
                        "capability": cap_name,
                        "session_id": context.session_id,
                        "turn_id": str(context.metadata.get("turn_id", "")),
                    },
                )
            )
        except Exception:
            logger.debug("EventBus publish failed (may not be running)", exc_info=True)

    def list_tools(self) -> list[str]:
        return self._tool_registry.list_tools()

    def list_capabilities(self) -> list[str]:
        return self._cap_registry.list_capabilities()

    def get_capability_manifests(self) -> list[dict[str, Any]]:
        return self._cap_registry.get_manifests()

    def get_tool_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        return self._tool_registry.build_openai_schemas(names)
