"""单轮次内跨 LLM 调用共享的 token 使用量累加器。"""

from __future__ import annotations

from typing import Any


class UsageTracker:
    """跨多次流式 LLM 调用累加提示/补全 token。

    两种输入路径：

    * :meth:`add_from_response` — 当提供商返回时读取 OpenAI
      ``CompletionUsage``（或流式 ``usage`` 块）。
    * :meth:`add_estimated` — 对不返回 ``usage`` 的提供商回退为
      粗略的 ``chars / 3.5`` 估算（chat 的即时应答路径使用）。

    构造时传入 ``model=<name>``，以便 :meth:`summary`` 可通过
    ``aidlearning.logging.stats`` 中的定价表解析 ``total_cost_usd``。
    """

    def __init__(self, *, model: str | None = None) -> None:
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.calls: int = 0
        self.model: str | None = model

    def add_from_response(self, response_or_usage: Any) -> None:
        usage = getattr(response_or_usage, "usage", None) or response_or_usage
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", prompt + completion) or 0)
        if prompt or completion or total:
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.total_tokens += total
            self.calls += 1

    def add_estimated(self, *, input_chars: int, output_chars: int) -> None:
        est_input = int(input_chars / 3.5)
        est_output = int(output_chars / 3.5)
        self.prompt_tokens += est_input
        self.completion_tokens += est_output
        self.total_tokens += est_input + est_output
        self.calls += 1

    def add_usage(
        self,
        *,
        agent_name: str = "",
        stage: str = "",
        model: str = "",
        system_prompt: str = "",
        user_prompt: str = "",
        response_text: str = "",
    ) -> None:
        """适配 :class:`~aidlearning.agents.base_agent.BaseAgent`。

        ``BaseAgent._track_tokens`` 查找暴露 ``add_usage(...)`` 的外部追踪器；
        此方法使 :class:`UsageTracker`` 可作为 ``token_tracker`` 构造参数传递，
        使能力流水线可以在一个位置聚合其所有 BaseAgent 派生子智能体的费用。

        我们回退到基于字符的估算，因为 BaseAgent 只给我们提示/响应文本
        （原始提供商使用量对象在该层不可用）。
        """
        if model and not self.model:
            self.model = model
        input_chars = len(system_prompt or "") + len(user_prompt or "")
        output_chars = len(response_text or "")
        if input_chars or output_chars:
            self.add_estimated(input_chars=input_chars, output_chars=output_chars)

    def summary(self) -> dict[str, Any] | None:
        if self.calls == 0:
            return None
        cost_usd = 0.0
        if self.model:
            # 本地导入使 ``core.agentic`` 在模块加载时保持轻量。
            from aidlearning.logging.stats.llm_stats import get_pricing

            pricing = get_pricing(self.model)
            cost_usd = (self.prompt_tokens / 1000.0) * pricing.get("input", 0.0) + (
                self.completion_tokens / 1000.0
            ) * pricing.get("output", 0.0)
        return {
            "total_cost_usd": cost_usd,
            "total_tokens": self.total_tokens,
            "total_calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }
