"""
LLM 服务异常
===========

LLM 服务的自定义异常类。
提供一致的异常层级结构以改善错误处理。
与上游开发分支保持同步。
"""


class LLMError(Exception):
    """所有 LLM 相关错误的基异常。"""

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
        provider: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.provider = provider

    def __str__(self) -> str:
        provider_prefix = f"[{self.provider}] " if self.provider else ""
        if self.details:
            return f"{provider_prefix}{self.message} (details: {self.details})"
        return f"{provider_prefix}{self.message}"


class LLMConfigError(LLMError):
    """当 LLM 配置出错时抛出。"""

    pass


class LLMProviderError(LLMError):
    """当 LLM Provider 出错时抛出。"""

    pass


class LLMCircuitBreakerError(LLMError):
    """当断路器阻止 LLM 执行时抛出。"""

    pass


class LLMAPIError(LLMError):
    """
    当 LLM Provider 的 API 调用失败时抛出。
    标准化 status_code 和 Provider 名称。
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        provider: str | None = None,
        details: dict[str, object] | None = None,
    ):
        super().__init__(message, details, provider)
        self.status_code = status_code

    def __str__(self) -> str:
        parts = []
        if self.provider:
            parts.append(f"[{self.provider}]")
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        parts.append(self.message)
        return " ".join(parts)


class LLMTimeoutError(LLMAPIError):
    """当 API 调用超时时抛出。"""

    def __init__(
        self,
        message: str = "Request timed out",
        timeout: float | None = None,
        provider: str | None = None,
    ):
        super().__init__(message, status_code=408, provider=provider)
        self.timeout = timeout


class LLMRateLimitError(LLMAPIError):
    """当 API 限流时抛出。"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        provider: str | None = None,
    ):
        super().__init__(message, status_code=429, provider=provider)
        self.retry_after = retry_after


class LLMAuthenticationError(LLMAPIError):
    """当认证失败时抛出（无效 API 密钥等）。"""

    def __init__(
        self,
        message: str = "Authentication failed",
        provider: str | None = None,
    ):
        super().__init__(message, status_code=401, provider=provider)


class LLMModelNotFoundError(LLMAPIError):
    """当请求的模型未找到时抛出。"""

    def __init__(
        self,
        message: str = "Model not found",
        model: str | None = None,
        provider: str | None = None,
    ):
        super().__init__(message, status_code=404, provider=provider)
        self.model = model


class LLMParseError(LLMError):
    """当解析 LLM 输出失败时抛出。"""

    def __init__(
        self,
        message: str = "Failed to parse LLM output",
        provider: str | None = None,
        details: dict[str, object] | None = None,
    ):
        super().__init__(message, details=details, provider=provider)


# 多 Provider 特定别名，用于映射规则
class ProviderQuotaExceededError(LLMRateLimitError):
    pass


class ProviderContextWindowError(LLMAPIError):
    pass


__all__ = [
    "LLMError",
    "LLMConfigError",
    "LLMProviderError",
    "LLMCircuitBreakerError",
    "LLMAPIError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    "LLMModelNotFoundError",
    "LLMParseError",
    "ProviderQuotaExceededError",
    "ProviderContextWindowError",
]
