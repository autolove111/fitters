"""
能力协议
===================

能力层（第二层）的基类。
能力是当用户选择深度模式（如深度解题、深度出题）时调用的多步智能体流水线。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .context import UnifiedContext
from .stream_bus import StreamBus


@dataclass
class CapabilityManifest:
    """能力的静态元数据。"""

    name: str
    description: str
    stages: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    cli_aliases: list[str] = field(default_factory=list)
    request_schema: dict[str, Any] = field(default_factory=dict)
    config_defaults: dict[str, Any] = field(default_factory=dict)


class BaseCapability(ABC):
    """
    所有能力（深度模式）的抽象基类。

    子类必须提供 ``manifest`` 并实现 ``run``。

    示例::

        class MySolverCapability(BaseCapability):
            manifest = CapabilityManifest(
                name="deep_solve",
                description="Multi-agent problem solving.",
                stages=["planning", "reasoning", "writing"],
                tools_used=["rag", "web_search", "code_execution"],
            )

            async def run(self, context, stream):
                async with stream.stage("planning", source=self.manifest.name):
                    plan = await self._plan(context)
                ...
    """

    manifest: CapabilityManifest

    @abstractmethod
    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        """执行完整的能力流水线，向 *stream* 发射事件。"""
        ...

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def stages(self) -> list[str]:
        return self.manifest.stages
