"""
工具注册表
==========

发现和管理所有工具（内置和插件）的中央注册表。
提供查找、列表和 OpenAI schema 生成功能。
"""

from __future__ import annotations

import logging
from typing import Any

from aidlearning.tools.protocol import BaseTool, ToolDefinition, ToolPromptHints
from aidlearning.tools.builtin import BUILTIN_TOOL_TYPES, TOOL_ALIASES
from aidlearning.tools.prompting import ToolPromptComposer

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    所有可用工具的准单例注册表。

    用法::

        registry = ToolRegistry()
        registry.load_builtins()
        rag = registry.get("rag")
        result = await rag.execute(query="hello")
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        name = tool.name
        self._tools[name] = tool
        logger.debug("Registered tool: %s", name)

    def load_builtins(self) -> None:
        """实例化并注册所有内置工具。"""
        for tool_type in BUILTIN_TOOL_TYPES:
            try:
                tool = tool_type()
            except Exception:
                logger.warning("Failed to instantiate built-in tool %s", tool_type, exc_info=True)
                continue
            if tool.name in self._tools:
                continue
            self.register(tool)

    def _resolve_request(
        self,
        name: str,
        kwargs: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if name in self._tools:
            return name, dict(kwargs or {})

        resolved_name, default_kwargs = TOOL_ALIASES.get(name, (name, {}))
        merged_kwargs = {**default_kwargs, **(kwargs or {})}

        if resolved_name == "code_execution" and "query" in merged_kwargs:
            merged_kwargs.setdefault("intent", merged_kwargs.pop("query"))

        return resolved_name, merged_kwargs

    def get(self, name: str) -> BaseTool | None:
        resolved_name, _ = self._resolve_request(name)
        return self._tools.get(resolved_name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_enabled(self, names: list[str]) -> list[BaseTool]:
        """返回给定名称的工具实例（跳过未知的）。"""
        enabled: list[BaseTool] = []
        seen: set[str] = set()
        for name in names:
            tool = self.get(name)
            if tool is None or tool.name in seen:
                continue
            enabled.append(tool)
            seen.add(tool.name)
        return enabled

    def get_definitions(self, names: list[str] | None = None) -> list[ToolDefinition]:
        """返回 *names* 的定义（如果为 None 则返回全部）。"""
        tools = self._tools.values() if names is None else self.get_enabled(names)
        return [t.get_definition() for t in tools]

    def get_prompt_hints(
        self,
        names: list[str],
        language: str = "en",
    ) -> list[tuple[str, ToolPromptHints]]:
        """返回给定工具名称的提示提示。"""
        entries: list[tuple[str, ToolPromptHints]] = []
        for tool in self.get_enabled(names):
            entries.append((tool.name, tool.get_prompt_hints(language=language)))
        return entries

    def build_prompt_text(
        self,
        names: list[str],
        format: str = "list",
        language: str = "en",
        **opts: Any,
    ) -> str:
        """为给定工具组合提示文本。"""
        composer = ToolPromptComposer(language=language)
        hints = self.get_prompt_hints(names, language=language)
        if format == "list":
            return composer.format_list(hints)
        if format == "list_with_usage":
            return composer.format_list_with_usage(hints)
        if format == "table":
            return composer.format_table(
                hints,
                control_actions=opts.get("control_actions"),
            )
        if format == "aliases":
            return composer.format_aliases(hints)
        if format == "phased":
            return composer.format_phased(hints)
        raise ValueError(f"Unsupported prompt format: {format}")

    def build_openai_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        """构建 OpenAI 函数调用工具 schema。"""
        return [d.to_openai_schema() for d in self.get_definitions(names)]

    async def execute(self, name: str, **kwargs: Any):
        """解析别名，执行工具，并返回其 ToolResult。"""
        resolved_name, resolved_kwargs = self._resolve_request(name, kwargs)
        tool = self._tools.get(resolved_name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return await tool.execute(**resolved_kwargs)


_default_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """返回全局 ToolRegistry（首次调用时创建并加载内置工具）。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        _default_registry.load_builtins()
    return _default_registry
