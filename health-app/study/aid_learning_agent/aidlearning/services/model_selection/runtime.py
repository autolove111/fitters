"""请求作用域模型选择的运行时辅助函数。"""

from __future__ import annotations

from contextvars import Token
from typing import Any

from aidlearning.services.config.provider_runtime import ResolvedLLMConfig, resolve_llm_runtime_config
from aidlearning.services.llm import config as llm_config_module
from aidlearning.services.llm.config import LLMConfig


def llm_config_from_resolved(resolved: ResolvedLLMConfig) -> LLMConfig:
    """将提供商运行时输出转换为 LLM 服务配置格式。"""
    return LLMConfig(
        model=resolved.model,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        effective_url=resolved.effective_url,
        binding=resolved.binding,
        provider_name=resolved.provider_name,
        provider_mode=resolved.provider_mode,
        api_version=resolved.api_version,
        extra_headers=resolved.extra_headers,
        reasoning_effort=resolved.reasoning_effort,
        context_window=resolved.context_window,
    )


def resolve_llm_config_for_selection(selection: Any) -> LLMConfig:
    """解析聊天/会话选择引用的 LLM 配置。"""
    if selection is None:
        return llm_config_module.get_llm_config()
    return llm_config_from_resolved(resolve_llm_runtime_config(llm_selection=selection))


def activate_llm_selection(selection: Any) -> tuple[LLMConfig, Token[LLMConfig | None]]:
    """为当前异步上下文解析并安装作用域 LLM 配置。"""
    config = resolve_llm_config_for_selection(selection)
    token = llm_config_module.set_scoped_llm_config(config)
    return config, token


def reset_llm_selection(token: Token[LLMConfig | None] | None) -> None:
    if token is not None:
        llm_config_module.reset_scoped_llm_config(token)


__all__ = [
    "activate_llm_selection",
    "llm_config_from_resolved",
    "reset_llm_selection",
    "resolve_llm_config_for_selection",
]
