"""
LLM 客户端
==========

AidLearning 所有服务的统一 LLM 客户端。

注意：这是旧版接口。建议直接使用工厂函数：
    from aidlearning.services.llm import complete, stream
"""

from collections.abc import Awaitable, Callable
import logging
from typing import cast

from .capabilities import supports_vision
from .config import LLMConfig, get_llm_config
from .utils import sanitize_url


class LLMClient:
    """
    所有服务的统一 LLM 客户端。

    以类接口封装 LLM 工厂。
    新代码建议直接使用工厂函数（complete, stream）。
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        """
        初始化 LLM 客户端。

        Args:
            config: LLM 配置。如果为 None，则从环境加载。
        """

        self.config = config or get_llm_config()
        self.logger = logging.getLogger(__name__)

        # Keep OPENAI_* env vars aligned for libraries that still read from env.
        self._setup_openai_env_vars()

    def _setup_openai_env_vars(self) -> None:
        """
        设置 OpenAI 环境变量以兼容 OpenAI 风格的 SDK。
        """
        import os

        binding = getattr(self.config, "binding", "openai")

        # 仅为 OpenAI 兼容绑定设置环境变量
        if binding in ("openai", "azure_openai", "gemini"):
            if self.config.api_key:
                os.environ["OPENAI_API_KEY"] = self.config.api_key
                self.logger.debug("Set OPENAI_API_KEY env var")

            if self.config.base_url:
                from .utils import sanitize_url as _sanitize

                clean_url = _sanitize(self.config.base_url)
                os.environ["OPENAI_BASE_URL"] = clean_url
                self.logger.debug(f"Set OPENAI_BASE_URL env var to {clean_url}")

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> str:
        """
        通过工厂调用 LLM 补全。

        Args:
            prompt: 用户提示
            system_prompt: 可选的系统提示
            history: 可选的对话历史
            **kwargs: 传递给 API 的附加参数

        Returns:
            LLM 响应文本
        """
        from . import factory

        factory_complete = cast(Callable[..., Awaitable[str]], factory.complete)
        messages = history or None
        return await factory_complete(
            prompt=prompt,
            system_prompt=system_prompt or "You are a helpful assistant.",
            model=self.config.model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            api_version=getattr(self.config, "api_version", None),
            binding=getattr(self.config, "binding", "openai"),
            reasoning_effort=getattr(self.config, "reasoning_effort", None),
            extra_headers=getattr(self.config, "extra_headers", None),
            messages=messages,
            **kwargs,
        )

    def complete_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> str:
        """
        complete() 的同步包装。

        当需要从非异步上下文调用时使用。
        """
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的事件循环 -> 可以安全地同步运行。
            return asyncio.run(self.complete(prompt, system_prompt, history, **kwargs))

        raise RuntimeError(
            "LLMClient.complete_sync() 不能从运行中的事件循环调用。"
            "请改用 `await llm.complete(...)`。"
        )

    def get_model_func(self) -> Callable[..., object]:
        """
        获取与通用 llm_model_func 钩子兼容的异步可调用对象。

        Returns:
            可用作 llm_model_func 的可调用对象
        """
        return self._build_factory_model_func(allow_multimodal=False)

    def get_vision_model_func(self) -> Callable[..., object]:
        """
        获取与 vision_model_func 钩子兼容的异步可调用对象。

        Returns:
            可用作 vision_model_func 的可调用对象
        """
        return self._build_factory_model_func(allow_multimodal=True)

    def supports_multimodal_images(self) -> bool:
        """返回已配置的 LLM 是否能接受图片输入。"""
        return supports_vision(getattr(self.config, "binding", "openai"), self.config.model)

    def _build_factory_model_func(self, allow_multimodal: bool) -> Callable[..., object]:
        """在统一的 factory.complete API 之上构建适配器可调用对象。"""
        from . import factory

        async def model_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, object]] | None = None,
            image_data: str | None = None,
            messages: list[dict[str, object]] | None = None,
            **kwargs: object,
        ) -> str:
            payload_kwargs: dict[str, object] = dict(kwargs)

            # 标准化旧版调用点的别名。
            payload_kwargs.pop("history_messages", None)
            payload_kwargs.pop("messages", None)
            payload_kwargs.pop("prompt", None)
            payload_kwargs.pop("system_prompt", None)

            resolved_messages = messages or cast(list[dict[str, object]] | None, history_messages)

            if allow_multimodal and image_data is not None:
                payload_kwargs["image_data"] = image_data

            factory_complete = cast(Callable[..., Awaitable[str]], factory.complete)
            return await factory_complete(
                prompt=prompt,
                system_prompt=system_prompt or "You are a helpful assistant.",
                model=self.config.model,
                api_key=self.config.api_key,
                base_url=sanitize_url(self.config.base_url) if self.config.base_url else None,
                api_version=getattr(self.config, "api_version", None),
                binding=getattr(self.config, "binding", "openai"),
                reasoning_effort=getattr(self.config, "reasoning_effort", None),
                extra_headers=getattr(self.config, "extra_headers", None),
                messages=resolved_messages,
                **payload_kwargs,
            )

        return model_func


_client: LLMClient | None = None


def get_llm_client(config: LLMConfig | None = None) -> LLMClient:
    """
    获取或创建 LLM 客户端单例。

    Args:
        config: 可选配置。仅在首次调用时使用。

    Returns:
        LLMClient 实例
    """
    global _client
    if _client is None:
        _client = LLMClient(config)
    return _client


def reset_llm_client() -> None:
    """重置 LLM 客户端单例。"""
    global _client
    _client = None
