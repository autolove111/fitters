"""共享的 LLM 响应数据模型。"""

from collections.abc import AsyncGenerator
import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TutorResponse(BaseModel):
    """LLM 补全响应容器。"""

    content: str
    raw_response: dict[str, object] = Field(default_factory=dict)
    usage: dict[str, int] = Field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    )
    provider: str = ""
    model: str = ""
    finish_reason: str | None = None
    cost_estimate: float = 0.0


class TutorStreamChunk(BaseModel):
    """流式 LLM 响应中输出的分块数据。"""

    delta: str
    content: str = ""
    provider: str = ""
    model: str = ""
    is_complete: bool = False
    usage: dict[str, int] | None = None


AsyncStreamGenerator = AsyncGenerator[TutorStreamChunk, None]

# 向后兼容的类型别名，供部分调用方/测试使用。
LLMResponse = TutorResponse
StreamChunk = TutorStreamChunk

__all__ = [
    "AsyncStreamGenerator",
    "LLMResponse",
    "StreamChunk",
    "TutorResponse",
    "TutorStreamChunk",
]
