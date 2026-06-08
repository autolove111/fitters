"""
统一上下文
===============

流经编排器进入每个工具/能力/插件调用的单一数据对象。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Attachment:
    """用户消息附带的文件或图片。"""

    type: str  # "image" | "file" | "pdf"
    url: str = ""
    base64: str = ""
    filename: str = ""
    mime_type: str = ""
    # 每个附件的稳定标识符；同时用作 AttachmentStore 中
    # 原始文件存储目录的路径段。
    id: str = ""
    # 二进制文档（PDF/DOCX/XLSX/PPTX）的纯文本渲染。
    # 由 ``extract_documents_from_records`` 填充，使前端在预览
    # Office 文件时能展示"LLM 看到的内容"。
    extracted_text: str = ""


@dataclass
class UnifiedContext:
    """
    能力或工具处理单个用户轮次所需的一切信息。

    属性：
        session_id: 持久化会话标识符。
        user_message: 当前用户输入。
        conversation_history: OpenAI 格式的历史消息。
        enabled_tools: 用户已开启的工具名称（第一层）。
            ``None`` 表示"未指定"，``[]`` 表示"明确禁用所有可选工具"。
        active_capability: 用户选择的能力名称，普通聊天时为 None。
        knowledge_bases: 用于 RAG 的知识库名称。
        attachments: 随消息发送的图片/文件。
        config_overrides: 每次请求的配置覆盖（如 temperature）。
        language: UI/响应语言（"en" | "zh"）。
        memory_context: 注入系统提示词的记忆快照文本。
        skills_context: 注入系统提示词的技能指令。
        source_manifest: 附件来源的纯文本清单（每个来源一行：
            id/name/type/preview）。无附件时为空。
            由 chat 能力消费，用于在系统提示词中渲染"附件来源"段，
            并启用 ``read_source`` 工具。
        metadata: 用于能力特定扩展的通用字段。
    """

    session_id: str = ""
    user_message: str = ""
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    enabled_tools: list[str] | None = None
    active_capability: str | None = None
    knowledge_bases: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    config_overrides: dict[str, Any] = field(default_factory=dict)
    language: str = "en"
    memory_context: str = ""
    skills_context: str = ""
    source_manifest: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
