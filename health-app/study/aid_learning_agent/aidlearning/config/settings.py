"""
AidLearning 的配置设置

环境变量：
    LLM_RETRY__MAX_RETRIES: LLM 调用的最大重试次数（默认：3）
    LLM_RETRY__BASE_DELAY: 重试之间的基础延迟秒数（默认：1.0）
    LLM_RETRY__EXPONENTIAL_BACKOFF: 是否使用指数退避（默认：True）

示例：
    export LLM_RETRY__MAX_RETRIES=5
    export LLM_RETRY__BASE_DELAY=2.0
    export LLM_RETRY__EXPONENTIAL_BACKOFF=false
"""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMRetryConfig(BaseModel):
    max_retries: int = Field(default=8, description="Maximum retry attempts for LLM calls")
    base_delay: float = Field(default=5.0, description="Base delay between retries in seconds")
    exponential_backoff: bool = Field(
        default=True, description="Whether to use exponential backoff"
    )


class Settings(BaseSettings):
    # LLM 重试配置
    retry: LLMRetryConfig = Field(default_factory=LLMRetryConfig)

    # 已弃用：请改用 retry
    @property
    def llm_retry(self):
        import warnings

        warnings.warn(
            "settings.llm_retry is deprecated, use settings.retry instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.retry

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_nested_delimiter="__",
    )


# 全局设置实例
settings = Settings()
