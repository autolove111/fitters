"""将 Chat Completions 消息/工具转换为 Responses API 格式。"""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

_CHAT_TOKEN_LIMIT_ALIASES = ("max_completion_tokens", "max_tokens")


def convert_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """将 Chat Completions 消息转换为 Responses API 输入项。"""
    system_prompt = ""
    input_items: list[dict[str, Any]] = []

    for idx, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            system_prompt = content if isinstance(content, str) else ""
            continue

        if role == "user":
            input_items.append(convert_user_message(content))
            continue

        if role == "assistant":
            if isinstance(content, str) and content:
                input_items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": content}],
                        "status": "completed",
                        "id": f"msg_{idx}",
                    }
                )
            for tool_call in msg.get("tool_calls", []) or []:
                fn = tool_call.get("function") or {}
                call_id, item_id = split_tool_call_id(tool_call.get("id"))
                input_items.append(
                    {
                        "type": "function_call",
                        "id": item_id or f"fc_{idx}",
                        "call_id": call_id or f"call_{idx}",
                        "name": fn.get("name"),
                        "arguments": fn.get("arguments") or "{}",
                    }
                )
            continue

        if role == "tool":
            call_id, _ = split_tool_call_id(msg.get("tool_call_id"))
            output_text = (
                content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            )
            input_items.append(
                {"type": "function_call_output", "call_id": call_id, "output": output_text}
            )

    return system_prompt, input_items


def convert_user_message(content: Any) -> dict[str, Any]:
    """将用户消息内容转换为 Responses API 块。"""
    if isinstance(content, str):
        return {"role": "user", "content": [{"type": "input_text", "text": content}]}
    if isinstance(content, list):
        converted: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                converted.append({"type": "input_text", "text": item.get("text", "")})
            elif item.get("type") == "image_url":
                url = (item.get("image_url") or {}).get("url")
                if url:
                    converted.append({"type": "input_image", "image_url": url, "detail": "auto"})
        if converted:
            return {"role": "user", "content": converted}
    return {"role": "user", "content": [{"type": "input_text", "text": ""}]}


def convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将 OpenAI 函数调用模式转换为 Responses API 工具。"""
    converted: list[dict[str, Any]] = []
    for tool in tools:
        fn = (tool.get("function") or {}) if tool.get("type") == "function" else tool
        name = fn.get("name")
        if not name:
            continue
        params = fn.get("parameters") or {}
        converted.append(
            {
                "type": "function",
                "name": name,
                "description": fn.get("description") or "",
                "parameters": params if isinstance(params, dict) else {},
            }
        )
    return converted


def split_tool_call_id(tool_call_id: Any) -> tuple[str, str | None]:
    """拆分复合的 call_id|item_id 工具 ID。"""
    if isinstance(tool_call_id, str) and tool_call_id:
        if "|" in tool_call_id:
            call_id, item_id = tool_call_id.split("|", 1)
            return call_id, item_id or None
        return tool_call_id, None
    return "call_0", None


def adapt_chat_kwargs_to_responses(extra_kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """将 Chat Completions 参数转换为 Responses API 等效参数。

    为 Chat Completions 端点构建请求的调用方可能会为较新的 OpenAI 模型
    （o1/o3/gpt-4o/gpt-5.x）传递 ``max_completion_tokens``，或为较旧的
    聊天模型传递 ``max_tokens``。Responses API 不接受这两个名称，而是使用
    ``max_output_tokens``，因此 OpenAI SDK 会在任何 HTTP 请求发出之前从
    ``responses.create`` 抛出 ``TypeError``。参见 AidLearning#437。

    丢弃值为 ``None`` 的键以匹配现有的合并过滤器，并且仅在调用方未显式
    设置 Responses 名称时应用别名。
    """
    result = {
        key: value
        for key, value in extra_kwargs.items()
        if value is not None and key not in _CHAT_TOKEN_LIMIT_ALIASES
    }
    if "max_output_tokens" in result:
        return result

    for key in _CHAT_TOKEN_LIMIT_ALIASES:
        value = extra_kwargs.get(key)
        if value is not None:
            result["max_output_tokens"] = value
            break
    return result
