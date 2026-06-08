"""
Local LLM Provider — 本地/自托管 LLM 调用实现

【调用链路位置】factory.complete/stream → provider.chat_with_retry/chat_stream_with_retry

处理本地 LLM 调用（LM Studio、Ollama、vLLM、llama.cpp 等）。
使用 aiohttp（httpx 与部分本地服务器有兼容问题）。
支持 <think> 标签解析（如 Qwen 等推理模型）。
超时时间较长，适配本地推理速度。
"""

from collections.abc import AsyncGenerator
import json
import logging

import aiohttp

from .exceptions import LLMAPIError, LLMConfigError
from .utils import (
    build_auth_headers,
    build_chat_url,
    clean_thinking_tags,
    collect_model_names,
    extract_response_content,
    sanitize_url,
)

logger = logging.getLogger(__name__)


def _extract_message_from_payload(payload: dict[str, object]) -> str:
    """从本地 Provider 载荷中提取消息内容。

    Args:
        payload: Provider 响应载荷。
    Returns:
        提取的内容字符串。
    Raises:
        无。
    """
    if not payload:
        return ""

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        for key in ("message", "delta"):
            if not isinstance(choice, dict):
                break
            part = choice.get(key)
            if part is not None:
                return extract_response_content(part)
        if isinstance(choice, dict) and "text" in choice:
            return str(choice.get("text") or "")

    if "message" in payload:
        return extract_response_content(payload.get("message"))

    return ""


# 本地服务器的扩展超时（可能比云端慢）
DEFAULT_TIMEOUT = 300  # 5 分钟


async def complete(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    messages: list[dict[str, str]] | None = None,
    **kwargs: object,
) -> str:
    """
    使用本地 LLM 服务器补全提示。

    使用 aiohttp 以获得与本地服务器更好的兼容性。

    Args:
        prompt: 用户提示（如果提供了 messages 则忽略）
        system_prompt: 系统提示上下文
        model: 模型名称
        api_key: API 密钥（大多数本地服务器可选）
        base_url: 本地服务器的基础 URL
        messages: 预构建的消息数组（可选）
        **kwargs: 附加参数（temperature, max_tokens 等）

    Returns:
        str: LLM 响应
    """
    if not base_url:
        raise LLMConfigError("base_url is required for local LLM provider")

    # 清理 URL 并构建聊天端点
    base_url = sanitize_url(base_url, model or "")
    url = build_chat_url(base_url)

    # 使用统一工具构建请求头
    headers = build_auth_headers(api_key)

    # 构建消息
    if messages:
        msg_list = messages
    else:
        msg_list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

    # 构建请求数据
    data = {
        "model": model or "default",
        "messages": msg_list,
        "temperature": kwargs.get("temperature", 0.7),
        "stream": False,
    }

    # 添加可选参数
    if kwargs.get("max_tokens"):
        data["max_tokens"] = kwargs["max_tokens"]

    timeout_value = kwargs.get("timeout", DEFAULT_TIMEOUT)
    timeout_seconds = (
        float(timeout_value) if isinstance(timeout_value, (int, float)) else DEFAULT_TIMEOUT
    )
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=data, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise LLMAPIError(
                    f"Local LLM error: {error_text}",
                    status_code=response.status,
                    provider="local",
                )

            result = await response.json()
            content = _extract_message_from_payload(result)
            content = clean_thinking_tags(content)
            if content:
                return content

            logger.warning("Local LLM returned no choices: %s", result)
            return ""


async def stream(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    messages: list[dict[str, str]] | None = None,
    **kwargs: object,
) -> AsyncGenerator[str, None]:
    """
    从本地 LLM 服务器流式获取响应。

    使用 aiohttp 以获得与本地服务器更好的兼容性。
    流式失败时回退到非流式。

    Args:
        prompt: 用户提示（如果提供了 messages 则忽略）
        system_prompt: 系统提示上下文
        model: 模型名称
        api_key: API 密钥（大多数本地服务器可选）
        base_url: 本地服务器的基础 URL
        messages: 预构建的消息数组（可选）
        **kwargs: 附加参数（temperature, max_tokens 等）

    Yields:
        str: 响应分块
    """
    if not base_url:
        raise LLMConfigError("base_url is required for local LLM provider")

    # 清理 URL 并构建聊天端点
    base_url = sanitize_url(base_url, model or "")
    url = build_chat_url(base_url)

    # 使用统一工具构建请求头
    headers = build_auth_headers(api_key)

    # 构建消息
    if messages:
        msg_list = messages
    else:
        msg_list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

    # 构建请求数据
    data = {
        "model": model or "default",
        "messages": msg_list,
        "temperature": kwargs.get("temperature", 0.7),
        "stream": True,
    }

    if kwargs.get("max_tokens"):
        data["max_tokens"] = kwargs["max_tokens"]

    timeout_value = kwargs.get("timeout", DEFAULT_TIMEOUT)
    timeout_seconds = (
        float(timeout_value) if isinstance(timeout_value, (int, float)) else DEFAULT_TIMEOUT
    )
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMAPIError(
                        f"Local LLM stream error: {error_text}",
                        status_code=response.status,
                        provider="local",
                    )

                # 跟踪是否在思考块内
                in_thinking_block = False
                thinking_buffer = ""

                async for line in response.content:
                    line_str = line.decode("utf-8").strip()

                    # 跳过空行
                    if not line_str:
                        continue

                    # 处理 SSE 格式
                    if line_str.startswith("data:"):
                        data_str = line_str[5:].strip()

                        if data_str == "[DONE]":
                            break

                        try:
                            chunk_data = json.loads(data_str)
                            content = _extract_message_from_payload(chunk_data)
                            if content:
                                # Handle thinking tags in streaming
                                if "<think>" in content:
                                    in_thinking_block = True
                                    # Handle case where content has text BEFORE <think>
                                    parts = content.split("<think>", 1)
                                    if parts[0]:
                                        yield parts[0]
                                    thinking_buffer = "<think>" + parts[1]

                                    # Check if closed immediately in same chunk
                                    if "</think>" in thinking_buffer:
                                        cleaned = clean_thinking_tags(thinking_buffer)
                                        if cleaned:
                                            yield cleaned
                                        thinking_buffer = ""
                                        in_thinking_block = False
                                    continue
                                elif in_thinking_block:
                                    thinking_buffer += content
                                    if "</think>" in thinking_buffer:
                                        # Block finished
                                        cleaned = clean_thinking_tags(thinking_buffer)
                                        if cleaned:
                                            yield cleaned
                                        in_thinking_block = False
                                        thinking_buffer = ""
                                    continue
                                else:
                                    yield content

                        except json.JSONDecodeError:
                            # 记录并跳过格式错误的 JSON 块
                            logger.warning(
                                "Skipping malformed JSON chunk: %s...",
                                data_str[:50],
                            )
                            continue

                    # 某些服务器不使用 SSE 格式
                    elif line_str.startswith("{"):
                        try:
                            chunk_data = json.loads(line_str)
                            content = _extract_message_from_payload(chunk_data)
                            if content:
                                # TODO: Implement <think> tag parsing for non-SSE JSON streams if supported
                                yield content
                        except json.JSONDecodeError:
                            pass

    except LLMAPIError:
        raise  # 原样重新抛出 LLM 错误
    except Exception as e:
        # 流式失败，回退到非流式
        logger.warning("Streaming failed (%s), falling back to non-streaming", e)

        try:
            content = await complete(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                api_key=api_key,
                base_url=base_url,
                messages=messages,
                **kwargs,
            )
            if content:
                yield content
        except Exception as e2:
            raise LLMAPIError(
                f"Local LLM failed: streaming={e}, non-streaming={e2}",
                provider="local",
            )


async def fetch_models(
    base_url: str,
    api_key: str | None = None,
) -> list[str]:
    """
    从本地 LLM 服务器获取可用模型。

    支持：
    - Ollama (/api/tags)
    - OpenAI 兼容 (/models)

    Args:
        base_url: 本地服务器的基础 URL
        api_key: API 密钥（可选）

    Returns:
        可用模型名称列表
    """
    base_url = base_url.rstrip("/")

    # 使用统一工具构建请求头
    headers = build_auth_headers(api_key)
    # Remove Content-Type for GET request
    headers.pop("Content-Type", None)

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 先尝试 Ollama /api/tags
        is_ollama = ":11434" in base_url or "ollama" in base_url.lower()
        if is_ollama:
            try:
                ollama_url = base_url.replace("/v1", "") + "/api/tags"
                async with session.get(ollama_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "models" in data:
                            return collect_model_names(data["models"])
            except Exception as exc:
                logger.debug(
                    "Failed to fetch Ollama models from %s: %s",
                    base_url,
                    exc,
                )

        # 尝试 OpenAI 兼容 /models
        try:
            models_url = f"{base_url}/models"
            async with session.get(models_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # 处理不同的响应格式
                    if "data" in data and isinstance(data["data"], list):
                        return collect_model_names(data["data"])
                    elif "models" in data and isinstance(data["models"], list):
                        return collect_model_names(data["models"])
                    elif isinstance(data, list):
                        return collect_model_names(data)
        except Exception as e:
            logger.error("Error fetching models from %s: %s", base_url, e)

        return []


__all__ = [
    "complete",
    "stream",
    "fetch_models",
]
