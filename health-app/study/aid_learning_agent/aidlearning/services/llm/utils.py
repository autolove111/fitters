"""
LLM 工具函数
============

URL 处理、响应解析和内容清理的共享辅助函数。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ipaddress
import os
import re
from urllib.parse import urlparse

CLOUD_DOMAINS = [
    ".openai.com",
    ".anthropic.com",
    ".deepseek.com",
    ".openrouter.ai",
    ".azure.com",
    ".googleapis.com",
    ".cohere.ai",
    ".mistral.ai",
    ".together.ai",
    ".fireworks.ai",
    ".groq.com",
    ".perplexity.ai",
]

LOCAL_PORTS = [
    ":1234",
    ":11434",
    ":8000",
    ":8080",
    ":5000",
    ":3000",
    ":8001",
    ":5001",
]

LOCAL_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # nosec B104
]

V1_SUFFIX_PORTS = {
    ":11434",
    ":1234",
    ":8000",
    ":8001",
    ":8080",
}


def is_local_llm_server(base_url: str, allow_private: bool | None = None) -> bool:
    """
    判断 URL 是否指向本地 LLM 服务器。

    Args:
        base_url: 待检查的 URL。
        allow_private: 可选覆盖参数，将私有 IP 视为本地。

    Returns:
        当 URL 看起来是本地地址时返回 True。
    """
    if not base_url:
        return False

    if allow_private is None:
        env_value = os.environ.get("LLM_TREAT_PRIVATE_AS_LOCAL")
        if env_value is not None:
            allow_private = env_value.strip().lower() in ("1", "true", "yes")

    base_url_lower = base_url.lower()
    if any(domain in base_url_lower for domain in CLOUD_DOMAINS):
        return False

    parsed = urlparse(base_url)
    hostname = parsed.hostname or parsed.netloc
    if not hostname:
        hostname = base_url

    hostname_lower = hostname.lower()
    if any(host in hostname_lower for host in LOCAL_HOSTS):
        return True

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback:
            return True
        if allow_private and ip.is_private:
            return True
    except ValueError:
        pass

    return any(port in base_url_lower for port in LOCAL_PORTS)


def _needs_v1_suffix(base_url: str) -> bool:
    """当 base_url 需要添加 /v1 后缀时返回 True。"""
    return any(port in base_url for port in V1_SUFFIX_PORTS) and not base_url.endswith("/v1")


def sanitize_url(base_url: str, model: str = "") -> str:
    """
    清理基础 URL，规范化协议并移除已知端点。

    Args:
        base_url: 基础 URL。
        model: 未使用（保留以维持 API 兼容性）。

    Returns:
        清理后的基础 URL。
    """
    if not base_url:
        return ""

    if not re.match(r"^[a-zA-Z]+://", base_url):
        base_url = f"http://{base_url}"

    url = base_url.rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "http://" + url

    for suffix in [
        "/chat/completions",
        "/completions",
        "/messages",
        "/embeddings",
    ]:
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")

    if _needs_v1_suffix(url):
        url = url.rstrip("/") + "/v1"

    return url


def clean_thinking_tags(
    content: str,
    binding: str | None = None,
    model: str | None = None,
) -> str:
    """从模型输出中移除 think 标签。"""
    if not content:
        return ""

    closed_pattern = re.compile(
        r"`?<\s*(?P<tag>think(?:ing)?)\b[^>]*>`?.*?`?<\s*/\s*(?P=tag)\s*>`?",
        re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(closed_pattern, "", content)
    # 流式提供商可能在推理已开始后因请求中断而输出最终的部分块，绝不暴露该草稿内容。
    unclosed_pattern = re.compile(
        r"`?<\s*think(?:ing)?\b[^>]*>`?.*$",
        re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(unclosed_pattern, "", cleaned)
    cleaned = re.sub(r"`?<\s*/\s*think(?:ing)?\s*>`?", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def build_chat_url(
    base_url: str,
    api_version: str | None = None,
    binding: str | None = None,
) -> str:
    """构建 chat-completions 端点 URL。"""
    base_url = base_url.rstrip("/")
    binding_lower = (binding or "openai").lower()

    if binding_lower in {"anthropic", "claude"}:
        url = f"{base_url}/messages"
    elif binding_lower == "cohere":
        url = f"{base_url}/chat"
    else:
        url = f"{base_url}/chat/completions"

    if api_version:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}api-version={api_version}"

    return url


def build_completion_url(
    base_url: str,
    api_version: str | None = None,
    binding: str | None = None,
) -> str:
    """构建旧版 completions 端点 URL。"""
    if not base_url:
        return base_url

    url = base_url.rstrip("/")
    binding_lower = (binding or "").lower()
    if binding_lower in {"anthropic", "claude"}:
        raise ValueError("Anthropic does not support /completions endpoint")

    if not url.endswith("/completions"):
        url += "/completions"

    if api_version:
        separator = "&" if "?" in url else "?"
        url += f"{separator}api-version={api_version}"

    return url


def _extract_content_field(content: object) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, Mapping) and "text" in part:
                parts.append(str(part["text"]))
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def extract_response_content(message: object) -> str:
    """从响应载荷中提取文本内容。

    当消息不包含有意义的文本时（例如 ``content=None`` 的流式 delta）返回空字符串。
    对复杂对象永远不会回退到 ``str(message)`` —— 那会将类似
    ``"{'provider_specific_fields': None, ...}"`` 的垃圾内容注入响应流并破坏下游 JSON 解析。
    """
    if message is None:
        return ""

    if isinstance(message, str):
        return message

    if isinstance(message, Mapping):
        content = _extract_content_field(message.get("content"))
        if content:
            return content
        if "text" in message and message["text"] is not None:
            return str(message["text"])
        return ""

    # LiteLLM/OpenAI SDK 响应模型通常通过属性而非字典键暴露数据。
    if hasattr(message, "content"):
        content = _extract_content_field(getattr(message, "content"))
        if content:
            return content
    if hasattr(message, "text"):
        text_value = getattr(message, "text")
        if text_value is not None:
            return str(text_value)

    if hasattr(message, "model_dump"):
        try:
            dumped = message.model_dump()
        except Exception:
            dumped = None
        if dumped is not None and dumped is not message:
            return extract_response_content(dumped)

    # 仅对简单/原始值进行字符串化；无可提取内容的复杂 SDK 对象应返回空字符串而非其 repr。
    if isinstance(message, (int, float, bool)):
        return str(message)
    return ""


def _normalize_model_name(entry: object) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, Mapping):
        for key in ("id", "name", "model"):
            value = entry.get(key)
            if isinstance(value, str):
                return value
    return None


def collect_model_names(entries: Sequence[object]) -> list[str]:
    """从提供商载荷中收集模型名称。"""
    names: list[str] = []
    for entry in entries:
        name = _normalize_model_name(entry)
        if name:
            names.append(name)
    return names


def build_auth_headers(api_key: str | None, binding: str | None = None) -> dict[str, str]:
    """为提供商请求构建认证头。"""
    headers = {"Content-Type": "application/json"}

    if not api_key:
        return headers

    binding_lower = (binding or "").lower()
    if binding_lower in {"anthropic", "claude"}:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif binding_lower in {"azure_openai", "azure"}:
        headers["api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


__all__ = [
    "sanitize_url",
    "is_local_llm_server",
    "build_chat_url",
    "build_completion_url",
    "build_auth_headers",
    "collect_model_names",
    "clean_thinking_tags",
    "extract_response_content",
    "CLOUD_DOMAINS",
    "LOCAL_PORTS",
    "LOCAL_HOSTS",
    "V1_SUFFIX_PORTS",
]
