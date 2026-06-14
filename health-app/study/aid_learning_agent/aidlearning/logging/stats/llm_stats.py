"""
LLM 统计跟踪器
=================

用于跟踪所有模块 LLM token 使用量和成本的简单工具。
通过统一日志系统输出摘要。

用法：
    from aidlearning.logging import LLMStats

    stats = LLMStats("Solver")

    # 每次 LLM 调用后：
    stats.add_call(
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50
    )

    # 最后：
    stats.log_summary()  # 使用日志系统
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any, Optional

# 每 1K token 的模型定价（美元）
MODEL_PRICING = {
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
}


def get_pricing(model: str) -> dict[str, float]:
    """获取模型定价（模糊匹配）。"""
    model_lower = model.lower()
    for key, pricing in MODEL_PRICING.items():
        if key in model_lower or model_lower in key:
            return pricing
    return MODEL_PRICING.get("gpt-4o-mini", {"input": 0.00015, "output": 0.0006})


def estimate_tokens(text: str) -> int:
    """粗略估计 token 数量（每词约 1.3 个 token）。"""
    return int(len(text.split()) * 1.3)


@dataclass
class LLMCall:
    """单次 LLM 调用记录。"""

    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class LLMStats:
    """
    LLM 使用统计跟踪器。
    跟踪 token 使用量和成本，向终端输出摘要。
    """

    def __init__(self, module_name: str = "Module"):
        """
        初始化统计跟踪器。

        Args:
            module_name: 模块名称（用于显示）
        """
        self.module_name = module_name
        self.calls: list[LLMCall] = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0
        self.model_used: Optional[str] = None

    def add_call(
        self,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        # 替代方案：从文本估算
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        response: Optional[str] = None,
    ):
        """
        将 LLM 调用添加到统计中。

        Args:
            model: 模型名称
            prompt_tokens: 提示 token 数量（如果已知）
            completion_tokens: 补全 token 数量（如果已知）
            system_prompt: 系统提示文本（用于估算）
            user_prompt: 用户提示文本（用于估算）
            response: 响应文本（用于估算）
        """
        # 如果未提供则估算 token 数量
        if prompt_tokens is None and (system_prompt or user_prompt):
            prompt_text = (system_prompt or "") + "\n" + (user_prompt or "")
            prompt_tokens = estimate_tokens(prompt_text)

        if completion_tokens is None and response:
            completion_tokens = estimate_tokens(response)

        prompt_tokens = prompt_tokens or 0
        completion_tokens = completion_tokens or 0

        # 计算成本
        pricing = get_pricing(model)
        cost = (prompt_tokens / 1000.0) * pricing["input"] + (completion_tokens / 1000.0) * pricing[
            "output"
        ]

        # 记录调用
        call = LLMCall(
            model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost=cost
        )
        self.calls.append(call)

        # 更新总计
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost += cost

        # 跟踪主模型
        if self.model_used is None:
            self.model_used = model

    def get_summary(self) -> dict[str, Any]:
        """获取摘要字典。"""
        return {
            "module": self.module_name,
            "model": self.model_used or "Unknown",
            "calls": len(self.calls),
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "cost_usd": self.total_cost,
        }

    def log_summary(self, logger: Optional[logging.Logger] = None):
        """
        使用统一日志系统记录摘要。

        Args:
            logger: 可选的 Logger 实例。如果为 None，使用 module_name 创建一个。
        """
        if len(self.calls) == 0:
            return

        if logger is None:
            logger = logging.getLogger(f"aidlearning.stats.{self.module_name}")

        total_tokens = self.total_prompt_tokens + self.total_completion_tokens

        logger.info("=" * 60)
        logger.info(f"LLM Usage Summary for {self.module_name}")
        logger.info("=" * 60)
        logger.info(f"Model       : {self.model_used or 'Unknown'}")
        logger.info(f"API Calls   : {len(self.calls)}")
        logger.info(
            f"Tokens      : {total_tokens:,} (Input: {self.total_prompt_tokens:,}, Output: {self.total_completion_tokens:,})"
        )
        logger.info(f"Cost        : ${self.total_cost:.6f} USD")
        logger.info("=" * 60)

    def print_summary(self):
        """
        将摘要打印到终端。

        已弃用：请使用 log_summary() 以获得一致的日志记录。
        """
        self.log_summary()

    def reset(self):
        """重置所有统计信息。"""
        self.calls.clear()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0
        self.model_used = None
