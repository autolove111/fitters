#!/usr/bin/env python
"""
BaseAgent — 所有 Agent 的统一基类

【调用链路位置】ChatAgent / SolveAgent / ResearchAgent 等均继承此类

提供：
  - LLM 配置管理（api_key, base_url, model，从 get_llm_config() 加载）
  - Prompt 加载（通过 PromptManager 加载 YAML 模板）
  - 统一 LLM 调用接口：call_llm()（非流式）/ stream_llm()（流式）
    内部调用 services/llm/factory.py 的 complete() / stream()
  - Token 用量追踪（LLMStats）
"""

from abc import ABC, abstractmethod
import inspect
import logging
import time
from typing import Any, AsyncGenerator, Awaitable, Callable

from deeptutor.config.settings import settings
from deeptutor.logging import LLMStats
from deeptutor.services.config import get_agent_params
from deeptutor.services.llm import complete as llm_complete
from deeptutor.services.llm import (
    get_llm_config,
    get_token_limit_kwargs,
    prepare_multimodal_messages,
    supports_response_format,
)
from deeptutor.services.llm import stream as llm_stream
from deeptutor.services.prompt import get_prompt_manager


class BaseAgent(ABC):
    """
    所有 Agent 的统一基类。

    提供：
    - LLM 配置管理（api_key, base_url, model）
    - Agent 参数（temperature, max_tokens）从 agents.yaml 加载
    - Prompt 加载（通过 PromptManager）
    - 统一 LLM 调用接口（call_llm / stream_llm）
    - Token 用量追踪（LLMStats）
    - 日志记录

    子类必须实现 process() 方法。
    """

    # 每个模块共享的 LLMStats 追踪器（类级别）
    _shared_stats: dict[str, LLMStats] = {}
    TraceCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

    def __init__(
        self,
        module_name: str,
        agent_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        api_version: str | None = None,
        language: str = "zh",
        binding: str | None = None,
        config: dict[str, Any] | None = None,
        token_tracker: Any | None = None,
        log_dir: str | None = None,
    ):
        """
        初始化 BaseAgent。

        流程：
          1. 保存模块名、Agent 名、语言等基础信息
          2. 从 agents.yaml 加载 Agent 参数（temperature, max_tokens）
          3. 从 get_llm_config() 加载 LLM 配置（api_key, base_url, model）
          4. 从 PromptManager 加载 YAML prompt 模板
          5. 初始化日志和 Token 追踪器

        Args:
            module_name: 模块名（chat/solve/research/co_writer/question）
            agent_name: Agent 名（如 "chat_agent", "solve_agent"）
            api_key: API 密钥（可选，默认从配置加载）
            base_url: API 端点（可选，默认从配置加载）
            model: 模型名（可选，默认从配置加载）
            api_version: Azure OpenAI 的 API 版本（可选）
            language: 语言设置（'zh' | 'en'），影响 prompt 加载
            binding: Provider 类型（可选，默认 'openai'）
            config: 可选配置字典
            token_tracker: 可选的外部 TokenTracker 实例
            log_dir: 可选的日志目录
        """
        self.module_name = module_name
        self.agent_name = agent_name
        self.language = language
        self._trace_callback: BaseAgent.TraceCallback | None = None

        # 确保 config 始终是 dict（避免传入 LLMConfig 等 dataclass）
        if config is None:
            self.config = {}
        elif isinstance(config, dict):
            self.config = config
        else:
            self.config = {}

        # 从 agents.yaml 加载 Agent 参数（temperature, max_tokens 等）
        self._agent_params = get_agent_params(module_name)

        # 从 get_llm_config() 加载 LLM 配置
        try:
            env_llm = get_llm_config()
            self.api_key = api_key or env_llm.api_key
            self.base_url = base_url or env_llm.base_url
            self.model = model or env_llm.model
            self.api_version = api_version or getattr(env_llm, "api_version", None)
            self.binding = binding or getattr(env_llm, "binding", "openai")
        except Exception:
            self.api_key = api_key
            self.base_url = base_url
            self.model = model
            self.api_version = api_version
            self.binding = binding or "openai"

        # 获取 Agent 专属配置
        self.agent_config = self.config.get("agents", {}).get(agent_name, {})
        llm_cfg = self.config.get("llm", {})
        if hasattr(llm_cfg, "__dataclass_fields__"):
            from dataclasses import asdict

            self.llm_config = asdict(llm_cfg)
        else:
            self.llm_config = llm_cfg if isinstance(llm_cfg, dict) else {}

        # Agent 启用状态
        self.enabled = self.agent_config.get("enabled", True)

        # Token 追踪器（外部实例，可选）
        self.token_tracker = token_tracker

        # 初始化日志
        logger_name = f"{module_name.capitalize()}.{agent_name}"
        self.logger = logging.getLogger(f"deeptutor.{logger_name}")

        # 通过 PromptManager 加载 YAML prompt 模板
        try:
            self.prompts = get_prompt_manager().load_prompts(
                module_name=module_name,
                agent_name=agent_name,
                language=language,
            )
            if self.prompts:
                self.logger.debug(f"Prompts loaded: {agent_name} ({language})")
        except Exception as e:
            self.prompts = None
            self.logger.warning(f"Failed to load prompts for {agent_name}: {e}")

    # -------------------------------------------------------------------------
    # 模型和参数获取
    # -------------------------------------------------------------------------

    def get_model(self) -> str:
        """
        获取模型名称。

        优先级：agent_config > llm_config > self.model > 环境变量

        Returns:
            模型名称

        Raises:
            ValueError: 未配置模型时抛出
        """
        # 1. Agent 专属配置
        if self.agent_config.get("model"):
            return self.agent_config["model"]

        # 2. 通用 LLM 配置
        if self.llm_config.get("model"):
            return self.llm_config["model"]

        # 3. 实例属性
        if self.model:
            return self.model

        raise ValueError(
            f"Model not configured for agent {self.agent_name}. "
            "Please activate a model in Settings > Catalog."
        )

    def get_temperature(self) -> float:
        """
        获取 temperature 参数（从 agents.yaml 加载）。

        Returns:
            temperature 值
        """
        return self._agent_params["temperature"]

    def get_max_tokens(self) -> int:
        """
        获取最大 token 数（从 agents.yaml 加载）。

        Returns:
            最大 token 数
        """
        return self._agent_params["max_tokens"]

    def get_max_retries(self) -> int:
        """
        获取最大重试次数。

        Returns:
            重试次数
        """
        return self.agent_config.get("max_retries", settings.retry.max_retries)

    def refresh_config(self) -> None:
        """
        刷新 LLM 配置 — 重新从 get_llm_config() 加载最新配置。

        用户在 Settings 中修改配置后，调用此方法可使 Agent 使用新配置，
        无需重启服务器或重建 Agent 实例。
        """
        try:
            llm_config = get_llm_config()
            self.api_key = llm_config.api_key
            self.base_url = llm_config.base_url
            self.model = llm_config.model
            self.api_version = getattr(llm_config, "api_version", None)
            self.binding = getattr(llm_config, "binding", "openai")
            self.logger.debug(
                f"Config refreshed: model={self.model}, base_url={self.base_url[:30]}..."
                if self.base_url
                else f"Config refreshed: model={self.model}"
            )
        except Exception as e:
            self.logger.warning(f"Failed to refresh config: {e}")

    def set_trace_callback(self, callback: TraceCallback | None) -> None:
        """
        注册 trace 回调 — 接收 LLM 调用的结构化事件。

        回调函数接收 dict payload，包含 event/state/model/chunk 等字段。
        用于前端实时展示 LLM 调用进度。
        """
        self._trace_callback = callback

    async def _emit_trace_event(self, payload: dict[str, Any]) -> None:
        """
        触发 trace 事件 — 调用已注册的回调函数。

        如果回调是协程则 await，否则直接调用。
        回调失败仅记录 debug 日志，不影响主流程。
        """
        callback = self._trace_callback
        if callback is None:
            return
        try:
            result = callback(payload)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self.logger.debug(f"Trace callback failed: {exc}")

    # -------------------------------------------------------------------------
    # Token 追踪
    # -------------------------------------------------------------------------

    @classmethod
    def get_stats(cls, module_name: str) -> LLMStats:
        """
        获取或创建指定模块的 LLMStats 追踪器。

        每个模块（chat/solve/research 等）共享一个 LLMStats 实例，
        用于统计该模块所有 Agent 的 token 用量。

        Args:
            module_name: 模块名

        Returns:
            LLMStats 实例
        """
        if module_name not in cls._shared_stats:
            cls._shared_stats[module_name] = LLMStats(module_name=module_name.capitalize())
        return cls._shared_stats[module_name]

    @classmethod
    def reset_stats(cls, module_name: str | None = None):
        """
        重置统计信息。

        Args:
            module_name: 模块名（为 None 时重置所有模块）
        """
        if module_name:
            if module_name in cls._shared_stats:
                cls._shared_stats[module_name].reset()
        else:
            for stats in cls._shared_stats.values():
                stats.reset()

    @classmethod
    def print_stats(cls, module_name: str | None = None):
        """
        打印统计摘要。

        Args:
            module_name: 模块名（为 None 时打印所有模块）
        """
        if module_name:
            if module_name in cls._shared_stats:
                cls._shared_stats[module_name].print_summary()
        else:
            for stats in cls._shared_stats.values():
                stats.print_summary()

    def _track_tokens(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        stage: str | None = None,
    ):
        """
        记录 token 用量 — 同时写入外部 TokenTracker 和共享 LLMStats。

        支持两种追踪器：
          1. 外部 TokenTracker（self.token_tracker，可选）
          2. 共享 LLMStats（始终可用）

        Args:
            model: 模型名
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            response: LLM 响应文本
            stage: 阶段标记（可选，默认使用 agent_name）
        """
        stage_label = stage or self.agent_name

        # 1. 外部 TokenTracker（如果提供）
        if self.token_tracker:
            try:
                self.token_tracker.add_usage(
                    agent_name=self.agent_name,
                    stage=stage_label,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_text=response,
                )
            except Exception:
                pass  # 追踪错误不影响主流程

        # 2. 共享 LLMStats（始终写入）
        stats = self.get_stats(self.module_name)
        stats.add_call(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
        )

    # -------------------------------------------------------------------------
    # LLM 调用接口
    # -------------------------------------------------------------------------

    async def call_llm(
        self,
        user_prompt: str,
        system_prompt: str,
        messages: list[dict[str, Any]] | None = None,
        response_format: dict[str, str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        verbose: bool = True,
        stage: str | None = None,
        attachments: list[Any] | None = None,
        trace_meta: dict[str, Any] | None = None,
    ) -> str:
        """
        非流式 LLM 调用 — 等待完整响应返回。

        调用链：llm_complete() → factory.complete() → provider.chat_with_retry()

        流程：
          1. 解析参数（model, temperature, max_tokens, max_retries）
          2. 构建 kwargs（token 限制、response_format、多模态附件）
          3. 发射 trace 事件（state=running）
          4. 调用 llm_complete() → factory.complete()
          5. 记录 token 用量
          6. 发射 trace 事件（state=complete）

        Args:
            user_prompt: 用户提示词（传入 messages 时忽略）
            system_prompt: 系统提示词（传入 messages 时忽略）
            messages: 预构建的 messages 数组（可选，覆盖 prompt/system_prompt）
            response_format: 响应格式（如 {"type": "json_object"}）
            temperature: 温度参数（可选，默认从配置读取）
            max_tokens: 最大 token 数（可选，默认从配置读取）
            model: 模型名（可选，默认从配置读取）
            verbose: 是否记录详细日志
            stage: 阶段标记（用于日志和追踪）
            attachments: 图片/文件附件（多模态输入）
            trace_meta: 额外的 trace 元数据

        Returns:
            LLM 响应文本
        """
        model = model or self.get_model()
        temperature = temperature if temperature is not None else self.get_temperature()
        max_tokens = max_tokens if max_tokens is not None else self.get_max_tokens()
        max_retries = self.get_max_retries()

        # 记录调用开始时间
        start_time = time.time()

        # 构建 LLM 调用参数
        kwargs = {
            "temperature": temperature,
        }

        # 新版 OpenAI 模型使用 max_completion_tokens 而非 max_tokens
        if max_tokens:
            kwargs.update(get_token_limit_kwargs(model, max_tokens))

        # response_format 需要检查 Provider 是否支持
        if response_format:
            try:
                config = get_llm_config()
                binding = getattr(config, "binding", None) or "openai"
            except Exception:
                binding = "openai"

            if supports_response_format(binding, model):
                kwargs["response_format"] = response_format
            else:
                self.logger.debug(f"response_format not supported for {binding}/{model}, skipping")

        # 处理多模态附件（图片等）
        if attachments:
            if not messages:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            mm_result = prepare_multimodal_messages(
                messages, attachments, binding=self.binding, model=model
            )
            messages = mm_result.messages
            if mm_result.images_stripped:
                self.logger.info(
                    "Images stripped for %s/%s – model does not support vision",
                    self.binding,
                    model,
                )
        if messages:
            kwargs["messages"] = messages

        # 发射 trace 事件（running 状态）
        stage_label = stage or self.agent_name
        trace_payload_base = {
            "event": "llm_call",
            "state": "running",
            "agent_name": self.agent_name,
            "stage": stage_label,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "streaming": False,
            **(trace_meta or {}),
        }
        await self._emit_trace_event(trace_payload_base)
        self.logger.debug(
            "LLM input %s:%s model=%s system_chars=%d user_chars=%d",
            self.agent_name,
            stage_label,
            model,
            len(system_prompt),
            len(user_prompt),
        )

        # 调用 LLM（factory.complete → provider.chat_with_retry）
        response = None
        try:
            response = await llm_complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                api_key=self.api_key,
                base_url=self.base_url,
                api_version=self.api_version,
                binding=self.binding,
                max_retries=max_retries,
                **kwargs,
            )
        except Exception as e:
            await self._emit_trace_event(
                {
                    **trace_payload_base,
                    "state": "error",
                    "response": str(e),
                }
            )
            self.logger.error(f"LLM call failed: {e}")
            raise

        # 计算耗时
        call_duration = time.time() - start_time

        # 记录 token 用量
        self._track_tokens(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            stage=stage_label,
        )

        # 发射 trace 事件（complete 状态）
        await self._emit_trace_event(
            {
                **trace_payload_base,
                "state": "complete",
                "response": response,
                "duration": call_duration,
            }
        )
        self.logger.debug(
            "LLM output %s:%s chars=%d duration=%.2fs",
            self.agent_name,
            stage_label,
            len(response),
            call_duration,
        )

        if verbose:
            self.logger.debug(f"LLM response: model={model}, duration={call_duration:.2f}s")

        return response

    async def stream_llm(
        self,
        user_prompt: str,
        system_prompt: str,
        messages: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
        stage: str | None = None,
        attachments: list[Any] | None = None,
        trace_meta: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式 LLM 调用 — 逐 chunk yield 文本。

        调用链：llm_stream() → factory.stream() → provider.chat_stream_with_retry()

        流程：
          1. 解析参数（同 call_llm）
          2. 处理多模态附件
          3. 发射 trace 事件（state=running）
          4. 调用 llm_stream() → factory.stream()，逐 chunk yield
          5. 每个 chunk 发射 trace 事件（state=streaming）
          6. 流结束后记录 token 用量，发射 trace 事件（state=complete）

        Args:
            user_prompt: 用户提示词（传入 messages 时忽略）
            system_prompt: 系统提示词（传入 messages 时忽略）
            messages: 预构建的 messages 数组（可选）
            temperature: 温度参数（可选）
            max_tokens: 最大 token 数（可选）
            model: 模型名（可选）
            response_format: JSON schema（可选）
            stage: 阶段标记
            attachments: 图片/文件附件
            trace_meta: 额外的 trace 元数据

        Yields:
            响应文本片段（逐 chunk）
        """
        model = model or self.get_model()
        temperature = temperature if temperature is not None else self.get_temperature()
        max_tokens = max_tokens if max_tokens is not None else self.get_max_tokens()
        max_retries = self.get_max_retries()

        # 构建 LLM 调用参数
        kwargs = {
            "temperature": temperature,
        }

        # 新版 OpenAI 模型使用 max_completion_tokens
        if max_tokens:
            kwargs.update(get_token_limit_kwargs(model, max_tokens))

        # response_format 能力检查
        if response_format:
            try:
                config = get_llm_config()
                binding = getattr(config, "binding", None) or "openai"
            except Exception:
                binding = "openai"

            if supports_response_format(binding, model):
                kwargs["response_format"] = response_format
            else:
                self.logger.debug(f"response_format not supported for {binding}/{model}, skipping")

        # 处理多模态附件
        if attachments:
            if not messages:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            mm_result = prepare_multimodal_messages(
                messages, attachments, binding=self.binding, model=model
            )
            messages = mm_result.messages
            if mm_result.images_stripped:
                self.logger.info(
                    "Images stripped for %s/%s – model does not support vision",
                    self.binding,
                    model,
                )

        # 发射 trace 事件（running 状态）
        stage_label = stage or self.agent_name
        trace_payload_base = {
            "event": "llm_call",
            "state": "running",
            "agent_name": self.agent_name,
            "stage": stage_label,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "streaming": True,
            **(trace_meta or {}),
        }
        await self._emit_trace_event(trace_payload_base)
        self.logger.debug(
            "LLM stream input %s:%s model=%s system_chars=%d user_chars=%d",
            self.agent_name,
            stage_label,
            model,
            len(system_prompt),
            len(user_prompt),
        )

        # 记录开始时间
        start_time = time.time()
        full_response = ""

        try:
            # 流式调用（factory.stream → provider.chat_stream_with_retry）
            async for chunk in llm_stream(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                api_key=self.api_key,
                base_url=self.base_url,
                api_version=self.api_version,
                binding=self.binding,
                messages=messages,
                max_retries=max_retries,
                **kwargs,
            ):
                full_response += chunk
                # 每个 chunk 发射 trace 事件
                await self._emit_trace_event(
                    {
                        **trace_payload_base,
                        "state": "streaming",
                        "chunk": chunk,
                    }
                )
                yield chunk

            # 流结束后记录 token 用量
            self._track_tokens(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=full_response,
                stage=stage_label,
            )

            # 发射 trace 事件（complete 状态）
            call_duration = time.time() - start_time
            await self._emit_trace_event(
                {
                    **trace_payload_base,
                    "state": "complete",
                    "response": full_response,
                    "duration": call_duration,
                }
            )
            self.logger.debug(
                "LLM stream output %s:%s chars=%d duration=%.2fs",
                self.agent_name,
                stage_label,
                len(full_response),
                call_duration,
            )

        except Exception as e:
            await self._emit_trace_event(
                {
                    **trace_payload_base,
                    "state": "error",
                    "response": str(e),
                }
            )
            self.logger.error(f"LLM streaming failed: {e}")
            raise

    # -------------------------------------------------------------------------
    # Prompt 辅助方法
    # -------------------------------------------------------------------------

    def get_prompt(
        self,
        section_or_type: str = "system",
        field_or_fallback: str | None = None,
        fallback: str = "",
    ) -> str | None:
        """
        获取 prompt 内容 — 支持简单查找和嵌套查找两种模式。

        模式1（简单查找）：get_prompt("system") → prompts["system"]
        模式2（嵌套查找）：get_prompt("section", "field", "fallback") → prompts["section"]["field"]

        Args:
            section_or_type: prompt 类型键或 section 名
            field_or_fallback: 嵌套模式下的字段名，或简单模式下的回退值
            fallback: 嵌套模式下的回退值

        Returns:
            prompt 字符串，未找到时返回 fallback 或 None
        """
        if not self.prompts:
            return (
                fallback
                if fallback
                else (
                    field_or_fallback
                    if isinstance(field_or_fallback, str) and field_or_fallback
                    else None
                )
            )

        # 检查是否是嵌套查找（section.field 模式）
        section_value = self.prompts.get(section_or_type)

        if isinstance(section_value, dict) and field_or_fallback is not None:
            # 嵌套查找：get_prompt("section", "field", "fallback")
            result = section_value.get(field_or_fallback)
            if result is not None:
                return result
            return fallback if fallback else None
        else:
            # 简单查找：get_prompt("key") 或 get_prompt("key", "fallback")
            if section_value is not None:
                return section_value
            return field_or_fallback if field_or_fallback else (fallback if fallback else None)

    def has_prompts(self) -> bool:
        """检查 prompt 是否已加载。"""
        return self.prompts is not None

    # -------------------------------------------------------------------------
    # 状态
    # -------------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """
        检查 Agent 是否启用。

        Returns:
            是否启用
        """
        return self.enabled

    # -------------------------------------------------------------------------
    # 抽象方法
    # -------------------------------------------------------------------------

    @abstractmethod
    async def process(self, *args, **kwargs) -> Any:
        """
        Agent 的主处理逻辑 — 子类必须实现。

        Returns:
            处理结果
        """

    # -------------------------------------------------------------------------
    # 字符串表示
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        """Agent 的字符串表示。"""
        return (
            f"{self.__class__.__name__}("
            f"module={self.module_name}, "
            f"name={self.agent_name}, "
            f"enabled={self.enabled})"
        )


__all__ = ["BaseAgent"]
