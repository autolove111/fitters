"""
提示词服务
==========

所有 AidLearning 模块的统一提示词管理。

用法：
    from aidlearning.services.prompt import get_prompt_manager, PromptManager

    # 获取单例管理器
    pm = get_prompt_manager()

    # 加载 Agent 的提示词
    prompts = pm.load_prompts("solve", "solve_agent", language="en")

    # 获取特定提示词
    system_prompt = pm.get_prompt(prompts, "system", "base")
"""

from .language import (
    append_language_directive,
    language_directive,
    language_label,
    normalize_language,
)
from .manager import PromptManager, get_prompt_manager

__all__ = [
    "PromptManager",
    "append_language_directive",
    "get_prompt_manager",
    "language_directive",
    "language_label",
    "normalize_language",
]
