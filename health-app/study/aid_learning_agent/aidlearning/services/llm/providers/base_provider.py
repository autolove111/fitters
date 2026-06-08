"""具有统一配置和重试机制的 LLM 提供商基类。"""

from abc import ABC
from collections.abc import Awaitable, Callable
import logging
from typing import TypeVar

import tenacity
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt

from aidlearning.utils.error_rate_tracker import record_provider_call
from aidlearning.utils.network.circuit_breaker import (
    is_call_allowed,
    record_call_failure,
    record_call_success,
)

from ..config import LLMConfig
from ..error_mapping import map_error
from ..exceptions import (
    LLMAPIError,
    LLMCircuitBreakerError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from ..traffic_control import TrafficController
from ..types import AsyncStreamGenerator, TutorResponse

T = TypeVar("T")

logger = logging.getLogger(__name__)

# 限制重试延迟以避免在故障期间等待过长。
MAX_RETRY_DELAY_SECONDS = 60.0
BASE_RETRY_DELAY_SECONDS = 1.0


class BaseLLMProvider(ABC):
    """所有 LLM 提供商的基类，提供统一配置和重试机制。"""

    def __init__(self, config: LLMConfig) -> None:
        """使用共享配置和流量控制初始化提供商。"""
        self.config = config
        self.provider_name = config.provider_name
        self.api_key = getattr(config, "get_api_key", lambda: config.api_key)()
        self.base_url = config.base_url or config.effective_url

        # 隔离：每个提供商拥有自己的流量控制器实例
        self.traffic_controller: TrafficController
        traffic_controller = getattr(config, "traffic_controller", None)
        if isinstance(traffic_controller, TrafficController):
            self.traffic_controller = traffic_controller
        else:
            self.traffic_controller = TrafficController(
                provider_name=self.provider_name,
                max_concurrency=getattr(config, "max_concurrency", 20),
                requests_per_minute=getattr(config, "requests_per_minute", 600),
            )

    async def complete(self, prompt: str, **kwargs: object) -> TutorResponse:
        """执行提供商的补全调用。"""
        raise NotImplementedError

    def stream(self, prompt: str, **kwargs: object) -> AsyncStreamGenerator:
        """返回用于流式补全的异步生成器。"""
        raise NotImplementedError

    def _map_exception(self, e: Exception) -> LLMError:
        return map_error(e, provider=self.provider_name)

    def calculate_cost(self, usage: dict[str, object]) -> float:
        """计算提供商调用的成本估算。"""
        return 0.0

    def _check_circuit_breaker(self) -> None:
        """当此提供商的熔断器打开时抛出异常。"""
        if not is_call_allowed(self.provider_name):
            record_provider_call(self.provider_name, success=False)
            error = LLMCircuitBreakerError(
                f"Circuit breaker open for provider {self.provider_name}",
                provider=self.provider_name,
            )
            setattr(error, "is_circuit_breaker", True)
            raise error

    def _should_record_failure(self, error: LLMError) -> bool:
        """当故障应触发熔断器时返回 True。"""
        if isinstance(error, (LLMRateLimitError, LLMTimeoutError)):
            return True
        if isinstance(error, LLMAPIError):
            status_code = error.status_code
            if status_code is None:
                return True
            return status_code >= 500
        return False

    def _should_retry_error(self, error: BaseException) -> bool:
        """当错误应触发重试时返回 True。"""
        if isinstance(error, (LLMRateLimitError, LLMTimeoutError)):
            return True
        if isinstance(error, LLMAPIError):
            status_code = error.status_code
            if status_code is None:
                return True
            return status_code >= 500
        return False

    def _wait_strategy(self, retry_state: tenacity.RetryCallState) -> float:
        """根据错误上下文返回下一次重试延迟。"""
        outcome = retry_state.outcome
        if outcome is None:
            return BASE_RETRY_DELAY_SECONDS
        exc = outcome.exception()
        if exc is None:
            return BASE_RETRY_DELAY_SECONDS
        if isinstance(exc, LLMRateLimitError):
            retry_after = getattr(exc, "retry_after", None)
            retry_after_value: float | None = None
            if retry_after is not None:
                try:
                    retry_after_value = float(retry_after)
                except (TypeError, ValueError):
                    retry_after_value = None
            if retry_after_value is not None:
                return max(0.0, min(retry_after_value, MAX_RETRY_DELAY_SECONDS))

        wait_fn = tenacity.wait_exponential(
            multiplier=1.5,
            min=BASE_RETRY_DELAY_SECONDS,
            max=MAX_RETRY_DELAY_SECONDS,
        )
        return float(wait_fn(retry_state))

    async def _execute_core(
        self,
        func: Callable[..., Awaitable[T]],
        *args: object,
        **kwargs: object,
    ) -> T:
        """
        核心执行管线：
        1) 熔断器检查
        2) 流量控制上下文
        3) 调用执行
        4) 映射 + 指标
        """
        self._check_circuit_breaker()

        try:
            async with self.traffic_controller:
                result = await func(*args, **kwargs)
                record_provider_call(self.provider_name, success=True)
                record_call_success(self.provider_name)
                return result
        except Exception as exc:
            mapped_exc = self._map_exception(exc)
            record_provider_call(self.provider_name, success=False)
            if isinstance(mapped_exc, LLMError):
                if self._should_record_failure(mapped_exc):
                    record_call_failure(self.provider_name)
                raise mapped_exc from exc
            # 内部/运行时错误应直接向上抛出，无需重新包装。
            raise mapped_exc

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: object,
        **kwargs: object,
    ) -> T:
        """执行单次尝试，不重试。"""
        return await self._execute_core(func, *args, **kwargs)

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        *args: object,
        max_retries: int = 3,
        sleep: Callable[[int | float], Awaitable[None] | None] | None = None,
        **kwargs: object,
    ) -> T:
        """使用 tenacity 执行自动重试。"""

        def _default_sleep(_delay: int | float) -> None:
            return None

        sleep_fn: Callable[[int | float], Awaitable[None] | None]
        sleep_fn = _default_sleep if sleep is None else sleep

        retrying = AsyncRetrying(
            stop=stop_after_attempt(max_retries + 1),
            wait=self._wait_strategy,
            retry=retry_if_exception(self._should_retry_error),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
            sleep=sleep_fn,
        )

        async for attempt in retrying:
            with attempt:
                return await self._execute_core(func, *args, **kwargs)

        raise RuntimeError("Retry loop exited without returning")
