"""
Provider Capabilities — LLM Provider 能力配置

【调用链路位置】factory.py / base_agent.py → supports_response_format() / supports_vision()

集中管理各 Provider 的能力声明：
  - supports_response_format: 是否支持 JSON 格式输出
  - supports_streaming: 是否支持流式
  - supports_tools: 是否支持工具调用
  - supports_vision: 是否支持图片输入
  - system_in_messages: system prompt 是否放在 messages 数组中

替代了之前散落在各处的硬编码判断。
"""

# Provider 能力配置
# 键为绑定名称（小写），值为能力字典
PROVIDER_CAPABILITIES: dict[str, dict[str, object]] = {
    # OpenAI 和 OpenAI 兼容 Provider
    "openai": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,  # 系统提示放入 messages 数组
        "newer_models_use_max_completion_tokens": True,
    },
    "azure_openai": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
        "newer_models_use_max_completion_tokens": True,
        "requires_api_version": True,
    },
    # Anthropic
    "anthropic": {
        "supports_response_format": False,  # Anthropic 使用不同的格式
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "vision_url_supported": False,  # 我们的适配器仅输出 base64 图片源
        "system_in_messages": False,  # 系统提示是单独的参数
        "has_thinking_tags": False,
    },
    "claude": {  # anthropic 的别名
        "supports_response_format": False,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "vision_url_supported": False,
        "system_in_messages": False,
        "has_thinking_tags": False,
    },
    # DeepSeek
    "deepseek": {
        "supports_response_format": False,  # DeepSeek 尚不支持严格的 JSON Schema
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "system_in_messages": True,
        "has_thinking_tags": True,  # DeepSeek 推理模型有思考标签
    },
    # OpenRouter（聚合器，通常兼容 OpenAI）
    "openrouter": {
        "supports_response_format": True,  # 取决于底层模型
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,  # 取决于底层模型
        "system_in_messages": True,
    },
    # Groq（快速推理）
    "groq": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
    },
    # Together AI
    "together": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
    },
    "together_ai": {  # 别名
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
    },
    # Mistral
    "mistral": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
    },
    # Moonshot / Kimi — 视觉支持按模型区分（见下方 MODEL_OVERRIDES）。
    # 根据官方文档，图片输入必须为 base64 内联编码；URL 形式会被拒绝。
    # 因此我们强制多模态层在发送前将纯 URL 附件解析为字节。
    "moonshot": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "vision_url_supported": False,
        "system_in_messages": True,
    },
    # MiniMax 的 OpenAI 兼容端点支持 M 系列文本模型的 Chat Completions 工具/函数调用。
    # 响应格式支持仍被下方的模型覆盖禁用。
    "minimax": {
        "supports_response_format": False,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "system_in_messages": True,
    },
    # 本地 Provider（通常兼容 OpenAI）
    "ollama": {
        "supports_response_format": True,  # Ollama 支持 JSON 模式
        "supports_streaming": True,
        "supports_tools": False,  # 工具支持有限
        "supports_vision": False,  # 取决于模型；通过模型覆盖设为 True
        "system_in_messages": True,
    },
    "lm_studio": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "system_in_messages": True,
    },
    "vllm": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "system_in_messages": True,
    },
    "llama_cpp": {
        "supports_response_format": True,  # llama.cpp 服务器支持 JSON 语法
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "system_in_messages": True,
    },
}

# 未知 Provider 的默认能力（假设兼容 OpenAI）
DEFAULT_CAPABILITIES: dict[str, object] = {
    "supports_response_format": True,
    "supports_streaming": True,
    "supports_tools": False,
    "supports_vision": False,
    "vision_url_supported": True,  # 大多数 OpenAI 兼容 Provider 接受 image_url URL
    "system_in_messages": True,
    "has_thinking_tags": False,
    "forced_temperature": None,  # None 表示无强制值，使用请求的温度
}

# 模型特定覆盖
# 格式：{model_pattern: {capability: value}}
# 模式通过不区分大小写的 startswith 匹配
MODEL_OVERRIDES: dict[str, dict[str, object]] = {
    "deepseek": {
        "supports_response_format": False,
        "has_thinking_tags": True,
        "supports_vision": False,
    },
    "deepseek-reasoner": {
        "supports_response_format": False,
        "has_thinking_tags": True,
        "supports_vision": False,
    },
    # Qwen 文本模型通常与 Qwen-VL 共享同一 Provider/网关。
    # 保持思考标签处理的广泛性，但仅将明确的 VL/视觉模型名称标记为支持图片，
    # 以便 RAG 图片索引能安全失败。
    "qwen/qwen2.5-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen/qwen3-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen/qwen2-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen/qwen-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen2.5-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen3-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen2-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen-vl": {"has_thinking_tags": True, "supports_vision": True},
    "qwen": {
        "has_thinking_tags": True,
        "supports_vision": False,
    },
    "qwq": {
        "has_thinking_tags": True,
    },
    "minimax": {
        "supports_response_format": False,
    },
    # 注意：supports_response_format 和 system_in_messages 是绑定级别
    # 的能力，而非模型级别。使用 OpenRouter 或其他 OpenAI 兼容代理
    # （binding="openai"）时，它们处理 response_format 转换并期望
    # 系统提示在 messages 中。Anthropic 的原生限制已由上方的
    # PROVIDER_CAPABILITIES["anthropic"] / ["claude"] 处理。
    # 仅模型固有能力（如 has_thinking_tags）应在此处。
    # 推理模型 - 仅支持 temperature=1.0
    # 参见：https://github.com/HKUDS/AidLearning/issues/141
    "gpt-5": {
        "forced_temperature": 1.0,
    },
    "o1": {
        "forced_temperature": 1.0,
    },
    "o3": {
        "forced_temperature": 1.0,
    },
    # 支持视觉的模型系列
    "gpt-4o": {"supports_vision": True},
    "gpt-4-turbo": {"supports_vision": True},
    "gpt-4-vision": {"supports_vision": True},
    "claude-3": {"supports_vision": True},
    "claude-4": {"supports_vision": True},
    "gemini": {"supports_vision": True},
    "gemma": {"supports_vision": False, "supports_response_format": False},
    "llava": {"supports_vision": True},
    "bakllava": {"supports_vision": True},
    "moondream": {"supports_vision": True},
    "minicpm-v": {"supports_vision": True},
    "gpt-3.5": {"supports_vision": False},
    # Moonshot / Kimi 视觉模型
    # https://platform.kimi.com/docs/guide/use-kimi-vision-model
    "moonshot-v1-8k-vision": {"supports_vision": True},
    "moonshot-v1-32k-vision": {"supports_vision": True},
    "moonshot-v1-128k-vision": {"supports_vision": True},
    "kimi-k2.5": {"supports_vision": True},
    "kimi-k2.6": {"supports_vision": True},
}


def get_capability(
    binding: str,
    capability: str,
    model: str | None = None,
    default: object = None,
) -> object:
    """
    获取 Provider/模型组合的能力值。

    按以下顺序检查：
    1. 模型特定覆盖（按前缀匹配）
    2. Provider/绑定能力
    3. 未知 Provider 的默认能力
    4. 显式默认值

    Args:
        binding: Provider 绑定名称（如 "openai", "anthropic", "deepseek"）
        capability: 能力名称（如 "supports_response_format"）
        model: 可选的模型名称，用于模型特定覆盖
        default: 如果能力未定义则使用默认值

    Returns:
        能力值或默认值
    """
    binding_lower = (binding or "openai").lower()

    # 1. 首先检查模型特定覆盖
    if model:
        model_lower = model.lower()
        # 按模式长度降序排列以优先匹配最具体的
        for pattern, overrides in sorted(MODEL_OVERRIDES.items(), key=lambda x: -len(x[0])):
            if model_lower.startswith(pattern):
                if capability in overrides:
                    return overrides[capability]

    # 2. 检查 Provider 能力
    provider_caps = PROVIDER_CAPABILITIES.get(binding_lower, {})
    if capability in provider_caps:
        return provider_caps[capability]

    # 3. 检查未知 Provider 的默认能力
    if capability in DEFAULT_CAPABILITIES:
        return DEFAULT_CAPABILITIES[capability]

    # 4. 返回显式默认值
    return default


# 运行时缓存，记录请求时发现的 response_format 不兼容情况。
# 以 (binding_lower, model_lower) 为键。当 Provider 拒绝
# response_format={"type": "json_object"} 的请求时填充
# （常见于 LM Studio / Ollama 服务 Gemma/Qwen 风格模型，仅接受 "json_schema" 或 "text"）。
# 一旦记录了某对组合，后续调用将完全跳过 response_format，
# 而非付出失败请求 + 重试的代价。
_RUNTIME_DISABLED_RESPONSE_FORMAT: set[tuple[str, str]] = set()


def disable_response_format_at_runtime(binding: str | None, model: str | None) -> None:
    """标记 (binding, model) 对不支持 ``response_format``。

    后续对同一对调用 :func:`supports_response_format` 将返回 ``False``，
    无需重新检查静态配置。当 Provider 在运行时意外拒绝 ``response_format`` 时
    （如 LM Studio + ``gemma-4-e2b`` 返回
    ``"'response_format.type' must be 'json_schema' or 'text'"``），此功能非常有用。
    """
    if not binding or not model:
        return
    _RUNTIME_DISABLED_RESPONSE_FORMAT.add((binding.lower(), model.lower()))


def is_response_format_disabled_at_runtime(binding: str | None, model: str | None) -> bool:
    """如果 (binding, model) 已通过 :func:`disable_response_format_at_runtime` 禁用则返回 True。"""
    if not binding or not model:
        return False
    return (binding.lower(), model.lower()) in _RUNTIME_DISABLED_RESPONSE_FORMAT


def supports_response_format(binding: str, model: str | None = None) -> bool:
    """
    检查 Provider/模型是否支持 response_format 参数。

    这是最常见能力检查的便捷函数。
    运行时覆盖（通过 :func:`disable_response_format_at_runtime` 设置）
    始终优先于静态能力配置。

    Args:
        binding: Provider 绑定名称
        model: 可选的模型名称，用于模型特定覆盖

    Returns:
        如果支持 response_format 则返回 True
    """
    if is_response_format_disabled_at_runtime(binding, model):
        return False
    value = get_capability(binding, "supports_response_format", model, default=True)
    return bool(value)


def supports_streaming(binding: str, model: str | None = None) -> bool:
    """
    检查 Provider/模型是否支持流式响应。

    Args:
        binding: Provider 绑定名称
        model: 可选的模型名称

    Returns:
        如果支持流式则返回 True
    """
    value = get_capability(binding, "supports_streaming", model, default=True)
    return bool(value)


def system_in_messages(binding: str, model: str | None = None) -> bool:
    """
    检查系统提示应放在 messages 数组中（OpenAI 风格）
    还是作为单独参数（Anthropic 风格）。

    Args:
        binding: Provider 绑定名称
        model: 可选的模型名称

    Returns:
        如果系统提示在 messages 数组中则返回 True
    """
    value = get_capability(binding, "system_in_messages", model, default=True)
    return bool(value)


def has_thinking_tags(binding: str, model: str | None = None) -> bool:
    """
    Check if the model output may contain thinking tags (<think>...</think>).

    Args:
        binding: Provider binding name
        model: Optional model name

    Returns:
        True if thinking tags should be filtered
    """
    value = get_capability(binding, "has_thinking_tags", model, default=False)
    return bool(value)


def supports_tools(binding: str, model: str | None = None) -> bool:
    """
    检查 Provider/模型是否支持函数调用/工具。

    Args:
        binding: Provider 绑定名称
        model: 可选的模型名称

    Returns:
        如果支持工具/函数调用则返回 True
    """
    value = get_capability(binding, "supports_tools", model, default=False)
    return bool(value)


def supports_vision(binding: str, model: str | None = None) -> bool:
    """
    检查 Provider/模型是否支持多模态（图片）输入。

    Args:
        binding: Provider 绑定名称
        model: 可选的模型名称，用于模型特定覆盖

    Returns:
        如果模型能接受消息中的图片内容则返回 True
    """
    value = get_capability(binding, "supports_vision", model, default=False)
    return bool(value)


def supports_vision_url(binding: str, model: str | None = None) -> bool:
    """Provider 是否接受远程 URL 图片引用。

    某些 Provider（Moonshot、我们的 Anthropic 适配器）仅接受内联
    base64 编码的图片字节。多模态层查询此标志以决定
    纯 URL 附件是否需要在转发前解析为字节。
    """
    value = get_capability(binding, "vision_url_supported", model, default=True)
    return bool(value)


def requires_api_version(binding: str, model: str | None = None) -> bool:
    """
    检查 Provider 是否需要 API 版本参数（如 Azure OpenAI）。

    Args:
        binding: Provider 绑定名称
        model: 可选的模型名称

    Returns:
        如果需要 api_version 则返回 True
    """
    value = get_capability(binding, "requires_api_version", model, default=False)
    return bool(value)


def get_effective_temperature(
    binding: str,
    model: str | None = None,
    requested_temp: float = 0.7,
) -> float:
    """
    获取模型的有效温度值。

    某些模型（如 o1、o3、gpt-5）仅支持固定的温度值（1.0）。
    如果定义了强制温度则返回该值，否则返回请求的值。

    Args:
        binding: Provider 绑定名称
        model: 可选的模型名称，用于模型特定覆盖
        requested_temp: 调用方请求的温度值（默认：0.7）

    Returns:
        API 调用应使用的有效温度
    """
    forced_temp = get_capability(binding, "forced_temperature", model)
    if isinstance(forced_temp, (int, float)):
        return float(forced_temp)
    return requested_temp


__all__ = [
    "PROVIDER_CAPABILITIES",
    "MODEL_OVERRIDES",
    "DEFAULT_CAPABILITIES",
    "get_capability",
    "supports_response_format",
    "supports_streaming",
    "system_in_messages",
    "has_thinking_tags",
    "supports_tools",
    "supports_vision",
    "requires_api_version",
    "get_effective_temperature",
    "disable_response_format_at_runtime",
    "is_response_format_disabled_at_runtime",
]
