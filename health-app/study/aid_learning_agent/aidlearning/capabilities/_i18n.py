"""能力状态/UI 字符串的共享国际化辅助模块。

能力的 ``run()`` 方法向聊天 UI 流式发送短状态消息
（``stream.thinking``、``stream.progress``、``stream.error``）。
这些字符串必须遵循用户的语言设置。本模块将它们接入现有的
``PromptManager``，使每个能力可以将其 UI 文案与 LLM 提示词一起
放在 ``aidlearning/capabilities/prompts/{en,zh}/<name>.yaml`` 中。

约定：

* YAML 文件包含一个顶层 ``status:`` 映射，键 -> 字符串。
* 字符串可以使用 ``{name}`` 占位符，通过 ``str.format`` 渲染。
* 缺失的键/文件会回退到 ``default`` 参数，这样新增的硬编码字符串
  在翻译添加之前仍能正常工作。
"""

from __future__ import annotations

from typing import Any

from aidlearning.services.prompt import get_prompt_manager


class StatusI18n:
    """按能力的本地化状态字符串查找。

    在 ``run()`` 顶部使用能力名称和 ``context.language`` 构造一次，
    然后在之前输出硬编码英文字符串的地方调用 ``t(key, default, **kwargs)``。
    """

    __slots__ = ("_strings",)

    def __init__(self, capability_name: str, language: str) -> None:
        prompts = get_prompt_manager().load_prompts(
            module_name="capabilities",
            agent_name=capability_name,
            language=language,
        )
        raw = prompts.get("status") if isinstance(prompts, dict) else None
        self._strings: dict[str, Any] = raw if isinstance(raw, dict) else {}

    def t(self, key: str, default: str = "", /, **kwargs: Any) -> str:
        value = self._strings.get(key)
        text = value if isinstance(value, str) and value else default
        if kwargs and text:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text


__all__ = ["StatusI18n"]
