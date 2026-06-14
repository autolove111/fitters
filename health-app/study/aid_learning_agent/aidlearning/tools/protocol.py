"""
工具协议
========

工具层（Level 1）的基类。
每个工具 —— 无论是内置的还是通过插件贡献的 —— 都实现 ``BaseTool``。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolParameter:
    """工具函数调用 schema 中的一个参数。

    Attributes:
        items: ``type="array"`` 参数的内部 JSON Schema。**严格提供商（Gemini、Anthropic）
            要求此项**，即使 OpenAI 默默容忍其缺失 —— 省略它会导致 Gemini 返回 400 错误。
            当 ``type="array"`` 且 ``items`` 为 None 时，回退为 ``{"type": "string"}``，
            使仅声明 ``ToolParameter(type="array")`` 的调用方仍能发出有效的 schema。
    """

    name: str
    type: str  # "string" | "integer" | "boolean" | "number" | "array" | "object"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None
    items: dict[str, Any] | None = None

    def to_schema(self) -> dict[str, Any]:
        """转换为 JSON Schema 属性字典。"""
        schema: dict[str, Any] = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = self.enum
        if self.type == "array":
            schema["items"] = self.items if self.items is not None else {"type": "string"}
        return schema


@dataclass
class ToolDefinition:
    """
    向 LLM 描述工具的元数据（OpenAI 函数调用格式）。
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_openai_schema(self) -> dict[str, Any]:
        """构建 OpenAI 兼容的函数工具 schema。"""
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = p.to_schema()
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class ToolAlias:
    """在提示中暴露的替代工具名称或子模式。"""

    name: str
    description: str = ""
    input_format: str = ""
    when_to_use: str = ""
    phase: str = ""


@dataclass
class ToolPromptHints:
    """描述何时以及如何使用工具的提示级指导。"""

    short_description: str = ""
    when_to_use: str = ""
    input_format: str = ""
    guideline: str = ""
    note: str = ""
    phase: str = ""
    aliases: list[ToolAlias] = field(default_factory=list)


@dataclass
class ToolResult:
    """工具执行的标准化返回值。

    Attributes:
        content: 作为 ``role=tool`` 消息体返回给 LLM 的文本。
        sources: 通过 ``stream.sources`` 呈现的引用行。
        metadata: 自由格式载荷 —— 也被聊天管道用作结构化 UI 提示的通道
            （如用于芯片渲染的 ``ask_user.options``）。
        success: ``False`` 标记显式失败路径；LLM 仍可读取 ``content``
            （通常是错误消息）。
        terminate_turn: 当为 ``True`` 时，智能体聊天循环必须在调度此工具后
            停止迭代，将工具的输出视为助手的最终轮次工件。保留给真正结束轮次的工具
            （目前无未来计划使用 —— ``ask_user`` 现在使用 ``pause_for_user`` 代替）。
        pause_for_user: 设置后，聊天循环在此工具调用后**暂停**，
            发出带有此载荷的 ``pending_user_input`` 事件，通过运行时的回复队列
            等待用户回复，然后在同一循环迭代中恢复，将回复替换到工具消息体中。
            由 ``ask_user`` 使用，在用户回答期间保持轮次活跃，
            而非结束并开始新轮次。形状与 ``AskUserPayload.to_dict()`` 一致。
    """

    content: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    terminate_turn: bool = False
    pause_for_user: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.content


class ToolEventSink(Protocol):
    """工具用于流式传输内部进度的异步回调。"""

    async def __call__(
        self,
        event_type: str,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


class BaseTool(ABC):
    """
    所有工具的抽象基类。

    子类必须实现 ``get_definition`` 和 ``execute``。

    示例::

        class MyTool(BaseTool):
            def get_definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name="my_tool",
                    description="做有用的事情。",
                    parameters=[ToolParameter(name="query", type="string")],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(content="结果")
    """

    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """返回工具的元数据和参数 schema。"""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """使用给定的关键字参数运行工具。"""
        ...

    def get_prompt_hints(self, language: str = "en") -> ToolPromptHints:
        """返回用于动态提示组装的提示级元数据。"""
        definition = self.get_definition()
        return ToolPromptHints(
            short_description=definition.description,
        )

    @property
    def name(self) -> str:
        return self.get_definition().name
