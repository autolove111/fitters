"""聊天/测验管道共享的每轮工具组合策略。

拥有规则"给定用户的编辑器开关 + 轮次的上下文标志，应启用哪些工具？"。
位于任何单一管道之外，使聊天和测验在用户控制的工具与管道自动挂载的工具上保持一致。

两部分：

* :data:`AUTO_MOUNTED_TOOLS` —— 由管道控制挂载的工具（在特定条件下自动开启），
  而非由用户开关控制。此处的成员资格会将工具从用户的编辑器/设置 UI 中隐藏。
* :func:`compose_enabled_tools` —— 纯函数，接收用户的开关列表 + :class:`ToolMountFlags`，
  返回单轮的最终有序启用工具列表。

调用方自行解析标志（聊天检查选定的知识库/源索引/记忆/笔记本；
测验原样复用聊天的策略）。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from aidlearning.tools.builtin import BUILTIN_TOOL_NAMES, USER_TOGGLEABLE_TOOL_NAMES

# 由管道控制挂载的工具（在特定上下文条件下自动开启），
# 而非由用户的编辑器开关控制。将工具添加到此处会将其从 ``{tool_list}`` 中隐藏，
# 直到其对应条件在 :func:`compose_enabled_tools` 中触发。
AUTO_MOUNTED_TOOLS: frozenset[str] = frozenset(
    {
        "rag",
        "read_source",
        "read_memory",
        "write_memory",
        "session_search",
        "ask_user",
        "web_fetch",
        "github",
    }
)


def default_optional_tools(excluded: Iterable[str] = ()) -> list[str]:
    """返回用户可切换的工具列表（聊天的默认集合）。

    来源于 :mod:`aidlearning.tools.builtin`，使 /settings/tools UI
    和管道在用户实际控制哪些工具上始终保持一致。
    """
    excluded_set = frozenset(excluded)
    return [
        name
        for name in USER_TOGGLEABLE_TOOL_NAMES
        if name in BUILTIN_TOOL_NAMES
        and name not in excluded_set
        and name not in AUTO_MOUNTED_TOOLS
    ]


@dataclass(frozen=True)
class ToolMountFlags:
    """驱动自动挂载策略的每轮标志。

    每个能力从自身的上下文解析这些标志（聊天检查 ``UnifiedContext.knowledge_bases``、
    源索引、记忆服务；测验复用相同的检查）。
    """

    has_kb: bool = False
    has_sources: bool = False
    has_memory: bool = False


def compose_enabled_tools(
    *,
    registry: Any,
    requested_tools: list[str] | None,
    optional_whitelist: list[str],
    mount_flags: ToolMountFlags,
) -> list[str]:
    """组合每轮启用的工具列表。

    顺序：

    1. 用户切换的工具（通过注册表的 ``get_enabled`` 过滤以排除禁用的工具，
       并与 ``optional_whitelist`` 取交集以仅接受合法的编辑器开关）。
    2. 条件自动挂载（附加了知识库时启用 ``rag``，存在源索引时启用 ``read_source``，
       记忆有内容时启用 ``read_memory``）。
    3. 始终开启的自动挂载（``write_memory``、``web_fetch``、``github``、``ask_user``）。

    结果是有序的（不应用去重 —— 调用方的前提是 ``optional_whitelist``
    排除了 ``AUTO_MOUNTED_TOOLS``，由 :func:`default_optional_tools` 保证）。
    """
    composed: list[str] = [
        tool.name
        for tool in registry.get_enabled(requested_tools or [])
        if tool.name in optional_whitelist
    ]
    if mount_flags.has_kb:
        composed.append("rag")
    if mount_flags.has_sources:
        composed.append("read_source")
    if mount_flags.has_memory:
        composed.append("read_memory")
    composed.append("session_search")
    composed.append("write_memory")
    composed.append("web_fetch")
    composed.append("github")
    composed.append("ask_user")
    return composed


def user_has_memory() -> bool:
    """当前用户是否有任何 L3 记忆内容。

    驱动 ``read_memory`` 的自动挂载。每用户路径通过运行时设置的
    多用户 ContextVars 解析。任何错误时安全关闭（返回 ``False``），
    使损坏的记忆目录不会暴露一个没有载荷可读的工具。
    """
    try:
        from aidlearning.memory import get_memory_store

        store = get_memory_store()
        return any(
            store.read_raw("L3", slot).strip()
            for slot in ("recent", "profile", "scope", "preferences")
        )
    except Exception:
        return False


__all__ = [
    "AUTO_MOUNTED_TOOLS",
    "ToolMountFlags",
    "compose_enabled_tools",
    "default_optional_tools",
    "user_has_memory",
]
