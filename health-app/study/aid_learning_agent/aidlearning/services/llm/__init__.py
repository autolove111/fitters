"""
LLM Service — 统一 LLM 服务层

【调用链路总览】

    Agents (ChatAgent, SolveAgent, etc.)
              ↓
         BaseAgent.call_llm() / stream_llm()
              ↓
         LLM Factory (complete / stream)      ← factory.py
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
CloudProvider      LocalProvider               ← cloud_provider.py / local_provider.py
(cloud_provider)   (local_provider)
    ↓                   ↓
OpenAICompat / Anthropic / Azure / ...         ← provider_core/*.py

对外接口：
  - complete(): 非流式 LLM 调用
  - stream(): 流式 LLM 调用
  - get_llm_config(): 获取 LLM 配置
  - get_llm_client(): 获取 LLM 客户端（旧接口）
"""

# 注意：cloud_provider 和 local_provider 通过 __getattr__ 延迟加载，
# 以避免在模块加载时导入可选的重型依赖
from .capabilities import (
    DEFAULT_CAPABILITIES,
    MODEL_OVERRIDES,
    PROVIDER_CAPABILITIES,
    get_capability,
    has_thinking_tags,
    requires_api_version,
    supports_response_format,
    supports_streaming,
    supports_tools,
    supports_vision,
    system_in_messages,
)
from .client import LLMClient, get_llm_client, reset_llm_client
from .config import (
    LLMConfig,
    clear_llm_config_cache,
    get_llm_config,
    get_token_limit_kwargs,
    reload_config,
    uses_max_completion_tokens,
)
from .exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from .factory import (
    API_PROVIDER_PRESETS,
    DEFAULT_EXPONENTIAL_BACKOFF,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    LOCAL_PROVIDER_PRESETS,
    complete,
    fetch_models,
    get_provider_presets,
    stream,
)
from .multimodal import MultimodalResult, prepare_multimodal_messages
from .utils import (
    build_auth_headers,
    build_chat_url,
    clean_thinking_tags,
    extract_response_content,
    is_local_llm_server,
    sanitize_url,
)

__all__ = [
    # 客户端（旧版，优先使用工厂函数）
    "LLMClient",
    "get_llm_client",
    "reset_llm_client",
    # 配置
    "LLMConfig",
    "get_llm_config",
    "clear_llm_config_cache",
    "reload_config",
    "uses_max_completion_tokens",
    "get_token_limit_kwargs",
    # 能力
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
    # 多模态
    "MultimodalResult",
    "prepare_multimodal_messages",
    # 异常
    "LLMError",
    "LLMConfigError",
    "LLMProviderError",
    "LLMAPIError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    "LLMModelNotFoundError",
    # 工厂（主 API）
    "complete",
    "stream",
    "fetch_models",
    "get_provider_presets",
    "API_PROVIDER_PRESETS",
    "LOCAL_PROVIDER_PRESETS",
    # 重试配置
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_EXPONENTIAL_BACKOFF",
    # 提供商（延迟加载）
    "cloud_provider",
    "local_provider",
    # 工具函数
    "sanitize_url",
    "is_local_llm_server",
    "build_chat_url",
    "build_auth_headers",
    "clean_thinking_tags",
    "extract_response_content",
]


def __getattr__(name: str):
    """延迟导入依赖重型库的提供商模块。"""
    from importlib import import_module

    if name == "cloud_provider":
        return import_module("aidlearning.services.llm.cloud_provider")
    if name == "local_provider":
        return import_module("aidlearning.services.llm.local_provider")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
