r"""基础智能体引擎原语。

这些模块将 chat 风格的 ``\`\`LABEL\`\`+content`` LLM 协议实现为可复用的构建块。
任何需要流式、标签驱动的 LLM 循环（chat、解题步骤等）的能力都可以组合它们。

分层：

* :mod:`labels`         — 协议标签解析（参数化标签集）。
* :mod:`client`         — OpenAI/Azure 客户端工厂 + 补全参数。
* :mod:`usage`          — 跨步骤共享的 token 使用量累加器。
* :mod:`labeled_step`   — 带标签路由的单次流式 LLM 调用。
* :mod:`tool_dispatch`  — 带每工具子追踪的并行工具执行。
* :mod:`loop`           — 将以上功能串联的迭代调度器。

能力特定的关注点（系统提示词组装、工具白名单、KB 枚举、即时应答快速通道、
强制终结策略、上下文窗口保护）位于各能力自己的模块中 — 原语暴露钩子
但不内联这些决策。
"""

from aidlearning.core.agentic.client import (
    LLMClientConfig,
    build_completion_kwargs,
    build_openai_client,
    can_use_native_tool_calling,
)
from aidlearning.core.agentic.labeled_step import LabeledStepResult, run_labeled_step
from aidlearning.core.agentic.labels import (
    LABEL_PROBE_MAX_CHARS,
    LABEL_UNKNOWN,
    classify_label,
    find_inline_labels,
    strip_label_probe_prefix,
)
from aidlearning.core.agentic.loop import LabelProtocol, LoopHost, LoopOutcome, run_agentic_loop
from aidlearning.tools.dispatch import (
    MAX_PARALLEL_TOOL_CALLS,
    DispatchOutcome,
    dispatch_tool_calls,
    execute_tool_call,
)
from aidlearning.core.agentic.usage import UsageTracker

__all__ = [
    "LABEL_PROBE_MAX_CHARS",
    "LABEL_UNKNOWN",
    "LLMClientConfig",
    "LabelProtocol",
    "LabeledStepResult",
    "LoopHost",
    "LoopOutcome",
    "MAX_PARALLEL_TOOL_CALLS",
    "DispatchOutcome",
    "UsageTracker",
    "build_completion_kwargs",
    "build_openai_client",
    "can_use_native_tool_calling",
    "classify_label",
    "dispatch_tool_calls",
    "execute_tool_call",
    "find_inline_labels",
    "run_agentic_loop",
    "run_labeled_step",
    "strip_label_probe_prefix",
]
