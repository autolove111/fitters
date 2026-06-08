"""AidLearning 所有模块的统一 Embedding 客户端和适配器。

支持的绑定由 ``services.config.provider_runtime`` 解析，
当前包括 openai、custom、azure_openai、cohere、jina、ollama、vllm、
siliconflow、aliyun、openrouter，以及旧版 custom_openai_sdk 配置。
"""

from .adapters import (
    BaseEmbeddingAdapter,
    CohereEmbeddingAdapter,
    DashScopeMultiModalEmbeddingAdapter,
    EmbeddingProviderError,
    EmbeddingRequest,
    EmbeddingResponse,
    JinaEmbeddingAdapter,
    OllamaEmbeddingAdapter,
    OpenAICompatibleEmbeddingAdapter,
    OpenAISDKEmbeddingAdapter,
)
from .client import EmbeddingClient, get_embedding_client, reset_embedding_client
from .config import EmbeddingConfig, get_embedding_config
from .validation import validate_embedding_batch

__all__ = [
    "EmbeddingClient",
    "EmbeddingConfig",
    "get_embedding_client",
    "get_embedding_config",
    "reset_embedding_client",
    "validate_embedding_batch",
    "BaseEmbeddingAdapter",
    "EmbeddingProviderError",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "OpenAICompatibleEmbeddingAdapter",
    "OpenAISDKEmbeddingAdapter",
    "DashScopeMultiModalEmbeddingAdapter",
    "CohereEmbeddingAdapter",
    "JinaEmbeddingAdapter",
    "OllamaEmbeddingAdapter",
]
