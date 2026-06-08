"""``QuestionPipeline`` 的运行时配置构建器。

镜像 :mod:`aidlearning.agents.research.request_config` 使用的形状，但接口小得多
—— 问题管线只需要服务配置中的少量旋钮：

* ``exploring.max_iterations``（int，默认 8）—— Explore 阶段的 Agent 循环上限。
* ``exploring.tool_summarizer.enabled``（bool，默认 True）—— 切换每工具结果的
  LLM 反思步骤，该步骤在下游阶段看到之前压缩原始工具输出。
* ``exploring.tool_summarizer.max_tokens``（int，默认 800）—— 每次摘要调用的 token 上限。

此辅助函数故意宽容：缺失的键/错误的类型折叠为默认值，因此调用方可以传递任何基础配置
（例如 ``main.yaml``），而无需先定义 ``capabilities.deep_question`` 部分。
"""

from __future__ import annotations

from typing import Any


def _read_int(source: dict[str, Any], key: str, default: int) -> int:
    value = source.get(key)
    if isinstance(value, int) and value > 0:
        return value
    return default


def _read_bool(source: dict[str, Any], key: str, default: bool) -> bool:
    value = source.get(key)
    if isinstance(value, bool):
        return value
    return default


def build_question_runtime_config(
    *,
    base_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """构建传递给 :class:`QuestionPipeline` 的 runtime_config 字典。

    管线从 ``runtime_config["exploring"]`` 读取其旋钮 ——
    ``base_config`` 中的其他内容目前被 question 忽略。
    """
    base = base_config if isinstance(base_config, dict) else {}
    capabilities = base.get("capabilities") if isinstance(base.get("capabilities"), dict) else {}
    question_root = (
        capabilities.get("deep_question")
        if isinstance(capabilities.get("deep_question"), dict)
        else {}
    )
    exploring_root = (
        question_root.get("exploring") if isinstance(question_root.get("exploring"), dict) else {}
    )
    summarizer_root = (
        exploring_root.get("tool_summarizer")
        if isinstance(exploring_root.get("tool_summarizer"), dict)
        else {}
    )

    exploring = {
        "max_iterations": _read_int(exploring_root, "max_iterations", 8),
        "tool_summarizer": {
            "enabled": _read_bool(summarizer_root, "enabled", True),
            "max_tokens": _read_int(summarizer_root, "max_tokens", 800),
        },
    }

    runtime_config = dict(base)
    runtime_config["exploring"] = exploring
    return runtime_config


__all__ = ["build_question_runtime_config"]
