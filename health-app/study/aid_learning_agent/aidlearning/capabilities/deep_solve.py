"""深度解题能力 — 基于智能体引擎的多步问题求解。

薄封装层，委托给 :class:`SolvePipeline`。所有编排逻辑（预检索子 DAG、
带 ``THINK`` / ``TOOL`` / ``FINISH`` / ``REPLAN`` 的逐步智能体循环、
重规划回边、综合）都在流水线模块中；该能力仅挂载清单。
"""

from __future__ import annotations

from aidlearning.agents.solve.pipeline import SolvePipeline
from aidlearning.capabilities.request_contracts import get_capability_request_schema
from aidlearning.core.capability_protocol import BaseCapability, CapabilityManifest
from aidlearning.core.context import UnifiedContext
from aidlearning.core.stream_bus import StreamBus


class DeepSolveCapability(BaseCapability):
    manifest = CapabilityManifest(
        name="deep_solve",
        description="Multi-agent problem solving (Plan -> ReAct -> Write).",
        stages=["planning", "reasoning", "writing"],
        tools_used=["rag", "web_search", "code_execution", "reason"],
        cli_aliases=["solve"],
        request_schema=get_capability_request_schema("deep_solve"),
    )

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        # 知识库是判断 ``rag`` 是否可用的唯一依据。
        # 没有单独的"启用 rag"开关。
        kb_name = context.knowledge_bases[0] if context.knowledge_bases else None
        requested = list(
            self.manifest.tools_used if context.enabled_tools is None else context.enabled_tools
        )
        # 从用户可见的工具列表中移除 ``rag`` — 流水线在有知识库挂载时
        # 自行加载 rag，没有知识库时不加载。
        enabled_tools = [tool for tool in requested if tool != "rag"]

        pipeline = SolvePipeline(
            language=context.language,
            kb_name=kb_name,
            enabled_tools=enabled_tools,
        )
        await pipeline.run(
            context=context,
            question=context.user_message,
            attachments=context.attachments,
            conversation_context=str(
                context.metadata.get("conversation_context_text", "") or ""
            ).strip(),
            memory_context=str(context.memory_context or "").strip(),
            stream=stream,
        )
