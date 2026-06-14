"""内置能力的公开请求契约和配置验证器。"""

from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aidlearning.agents.research.request_config import (
    DeepResearchRequestConfig,
    validate_research_request_config,
)

_RUNTIME_ONLY_KEYS = {
    "_persist_user_message",
    "followup_question_context",
    # "answer_now" 是通用逃逸机制：编排器在检测到此字段时会将
    # 任何能力重路由到 chat。它从不在任何按能力的 ``RequestConfig``
    # schema 中声明，因此我们在 pydantic 验证前将其剥离，
    # 然后在运行时侧重新附加。
    "answer_now_context",
}


class ChatRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeepSolveRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeepQuestionRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["custom", "mimic"] = "custom"
    topic: str = ""
    num_questions: int = Field(default=1, ge=1, le=50)
    difficulty: str = ""
    # 允许的题型白名单。空列表表示"任意类型 — 让规划器按题选择"。
    # 前端发送用户的多选结果。
    question_types: list[str] = Field(default_factory=list)
    # 可选的每种题型数量目标。非空时，总和必须等于 ``num_questions``
    # （前端负责同步）。空字典表示"无每类型目标 — 在允许的类型间自由分配"。
    per_type_counts: dict[str, int] = Field(default_factory=dict)
    paper_path: str = ""
    max_questions: int = Field(default=10, ge=1, le=100)


DeepQuestionRequestConfig.model_rebuild()


def _clean_public_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    if raw_config is None:
        return {}
    if not isinstance(raw_config, dict):
        raise ValueError("Capability config must be an object.")
    cleaned = dict(raw_config)
    for key in _RUNTIME_ONLY_KEYS:
        cleaned.pop(key, None)
    return cleaned


def _validate_model(
    model_type: type[BaseModel],
    raw_config: dict[str, Any] | None,
    *,
    label: str,
) -> BaseModel:
    cleaned = _clean_public_config(raw_config)
    try:
        return model_type.model_validate(cleaned)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(f"Invalid {label} config: {details}") from exc


def validate_chat_request_config(raw_config: dict[str, Any] | None) -> ChatRequestConfig:
    return _validate_model(ChatRequestConfig, raw_config, label="chat")


def validate_deep_solve_request_config(
    raw_config: dict[str, Any] | None,
) -> DeepSolveRequestConfig:
    return _validate_model(DeepSolveRequestConfig, raw_config, label="deep solve")


def validate_deep_question_request_config(
    raw_config: dict[str, Any] | None,
) -> DeepQuestionRequestConfig:
    return _validate_model(DeepQuestionRequestConfig, raw_config, label="deep question")



def build_request_schema(model_type: type[BaseModel]) -> dict[str, Any]:
    return model_type.model_json_schema(mode="validation")


CAPABILITY_CONFIG_VALIDATORS: dict[str, Callable[[dict[str, Any] | None], Any]] = {
    "chat": validate_chat_request_config,
    "deep_solve": validate_deep_solve_request_config,
    "deep_question": validate_deep_question_request_config,
    "deep_research": validate_research_request_config,
}

CAPABILITY_REQUEST_SCHEMAS: dict[str, dict[str, Any]] = {
    "chat": build_request_schema(ChatRequestConfig),
    "deep_solve": build_request_schema(DeepSolveRequestConfig),
    "deep_question": build_request_schema(DeepQuestionRequestConfig),
    "deep_research": build_request_schema(DeepResearchRequestConfig),
}


def validate_capability_config(
    capability: str, raw_config: dict[str, Any] | None
) -> dict[str, Any]:
    validator = CAPABILITY_CONFIG_VALIDATORS.get(capability)
    if validator is None:
        return _clean_public_config(raw_config)
    model = validator(raw_config)
    if isinstance(model, BaseModel):
        return model.model_dump(exclude_none=True)
    return _clean_public_config(raw_config)


def get_capability_request_schema(capability: str) -> dict[str, Any]:
    return dict(CAPABILITY_REQUEST_SCHEMAS.get(capability, {}))


__all__ = [
    "CAPABILITY_CONFIG_VALIDATORS",
    "CAPABILITY_REQUEST_SCHEMAS",
    "ChatRequestConfig",
    "DeepQuestionRequestConfig",
    "DeepSolveRequestConfig",
    "build_request_schema",
    "get_capability_request_schema",
    "validate_capability_config",
    "validate_chat_request_config",
    "validate_deep_question_request_config",
    "validate_deep_solve_request_config",
]
