"""问题生成包。

主入口是 :class:`~aidlearning.agents.question.pipeline.QuestionPipeline`。
轻量级名称（``FollowupAgent``、``QuizTemplate``、``QuizPair`` 等）
延迟解析，以便只需要一个符号的调用方不会急切地导入完整管线及其 LLM 依赖。
"""

from importlib import import_module
from typing import Any

__all__ = [
    "AgentCoordinator",
    "FollowupAgent",
    "QuestionPipeline",
    "QuizTemplate",
    "QuizPair",
    "QuizPlan",
    "QuizHistoryEntry",
]


def __getattr__(name: str) -> Any:
    if name == "AgentCoordinator":
        module = import_module("aidlearning.agents.question.coordinator")
        return getattr(module, name)
    if name == "FollowupAgent":
        module = import_module("aidlearning.agents.question.agents.followup_agent")
        return getattr(module, name)
    if name in {"QuestionPipeline", "QuizTemplate", "QuizPair", "QuizPlan", "QuizHistoryEntry"}:
        module = import_module("aidlearning.agents.question.pipeline")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
