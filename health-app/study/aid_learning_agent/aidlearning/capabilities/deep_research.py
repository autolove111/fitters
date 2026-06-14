"""深度研究能力 — 基于智能体引擎的深度研究。

薄封装层，委托给 :class:`ResearchPipeline`。所有编排逻辑
— 改写（带 ``ask_user`` 的小型智能体循环）、分解、带 ``THINK`` / ``TOOL`` /
``APPEND`` / ``FINISH`` 的逐模块研究循环、队列调度器和迭代报告
— 都在流水线模块中。该能力仅处理：

* 请求配置验证，
* 大纲预览两阶段流程（首次调用返回用户可编辑/确认的子主题；
  第二次调用使用确认后的大纲驱动第 3+4 阶段）。

工具组合委托给共享的 :mod:`aidlearning.tools.composition` 策略
— 与 chat 相同，用户的组合开关和附件的知识库决定逐模块研究循环
实际可访问哪些工具。没有单独的"来源"开关。
"""

from __future__ import annotations

from typing import Any

from aidlearning.agents.research.pipeline import ResearchPipeline, SubTopicItem
from aidlearning.agents.research.request_config import (
    build_research_runtime_config,
    validate_research_request_config,
)
from aidlearning.capabilities.request_contracts import get_capability_request_schema
from aidlearning.core.capability_protocol import BaseCapability, CapabilityManifest
from aidlearning.core.context import UnifiedContext
from aidlearning.core.stream_bus import StreamBus
from aidlearning.services.config import load_config_with_main


class DeepResearchCapability(BaseCapability):
    manifest = CapabilityManifest(
        name="deep_research",
        description="Agentic-loop deep research with iterative report generation.",
        stages=["rephrasing", "decomposing", "researching", "reporting"],
        tools_used=["rag", "web_search", "paper_search", "code_execution"],
        cli_aliases=["research"],
        request_schema=get_capability_request_schema("deep_research"),
    )

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        kb_name = context.knowledge_bases[0] if context.knowledge_bases else None
        request_config = validate_research_request_config(context.config_overrides)

        enabled_tools = list(context.enabled_tools or [])
        runtime_config = build_research_runtime_config(
            base_config=load_config_with_main("main.yaml"),
            request_config=request_config,
            kb_name=kb_name,
        )

        # 大纲预览两阶段流程：首次调用缺少确认的大纲 ->
        # 流水线返回 ``outline_preview`` 并退出；前端展示大纲编辑器，
        # 用户确认后发送第二次调用并设置 ``confirmed_outline``。
        confirmed_outline_items: list[SubTopicItem] | None = None
        if request_config.confirmed_outline is not None:
            confirmed_outline_items = [
                SubTopicItem(title=item.title, overview=item.overview or "")
                for item in request_config.confirmed_outline
            ]

        pipeline = ResearchPipeline(
            language=context.language,
            runtime_config=runtime_config,
            kb_name=kb_name,
            enabled_tools=enabled_tools,
        )
        result = await pipeline.run(
            context=context,
            topic=context.user_message,
            confirmed_outline=confirmed_outline_items,
            attachments=context.attachments,
            stream=stream,
        )

        # 大纲预览负载携带子主题和原始请求配置，以便第二次调用
        # 拥有确认和恢复所需的全部信息。字段位于顶层，因此
        # ``event.metadata.outline_preview`` 可在前端解析。
        if result.get("outline_preview"):
            research_config: dict[str, Any] = {
                "mode": request_config.mode,
                "depth": request_config.depth,
            }
            if request_config.manual_subtopics is not None:
                research_config["manual_subtopics"] = request_config.manual_subtopics
            if request_config.manual_max_iterations is not None:
                research_config["manual_max_iterations"] = request_config.manual_max_iterations
            await stream.result(
                {**result, "research_config": research_config},
                source=self.name,
            )
