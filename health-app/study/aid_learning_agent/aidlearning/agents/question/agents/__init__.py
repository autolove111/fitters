"""问题生成子 Agent。

目前仅独立的单次调用 ``FollowupAgent`` 在此 —— 每问题/每批次的 Agent
（idea_agent、generator）在 Phase A → C 重构期间已被单一的
:mod:`aidlearning.agents.question.pipeline` 模块替代。
"""

from importlib import import_module
from typing import Any

__all__ = ["FollowupAgent"]


def __getattr__(name: str) -> Any:
    if name == "FollowupAgent":
        module = import_module("aidlearning.agents.question.agents.followup_agent")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
