"""
基础异常类，用于应用中一致的错误处理。
提供标准化方式来区分程序缺陷、可恢复错误和配置问题。
"""

from typing import Any, Dict, Optional


class AidLearningError(Exception):
    """AidLearning 中所有应用错误的基类。"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigurationError(AidLearningError):
    """当出现配置相关错误时抛出。"""

    pass


class ValidationError(AidLearningError):
    """当输入验证失败时抛出。"""

    pass


class ServiceError(AidLearningError):
    """服务层错误的基类。"""

    pass


class LLMServiceError(ServiceError):
    """LLM 服务相关错误的基类。"""

    pass


class LLMContextError(LLMServiceError):
    """当提示词超过模型上下文窗口时抛出。"""

    pass


class EnvironmentConfigError(ConfigurationError):
    """当出现环境相关配置错误时抛出。"""

    pass
