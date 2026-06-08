"""标签驱动的迭代调度器。

智能体循环驱动与 LLM 的对话，直到调用方声明的*终结标签*之一触发。
每次迭代是一次 :func:`~aidlearning.core.agentic.labeled_step.run_labeled_step` 调用，
之后循环会：

* 验证协议（一个标签、无内联重复、仅在工具标签时使用工具），
* 在终结标签时，可选地将缓冲的标签后文本作为正文内容发出
  （针对 :attr:`LabelProtocol.final` 中的标签）并退出，
* 在工具标签时，追加助手 + 工具消息并通过宿主分派请求的工具调用，
* 在中间标签时（如 ``THINK``），保留文本作为助手上下文，
  使下一次迭代以此为基础构建，
* 在协议违反时，发出重试通知并将宿主的修复消息反馈到对话中。

能力特定的部分 — 上下文窗口保护、迭代追踪元数据、工具分派、
暂停/终止处理、最大迭代强制终结、协议违反文案 — 委托给 :class:`LoopHost`。
循环本身保持能力无关。
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Protocol

from aidlearning.core.agentic.labeled_step import LabeledStepResult, run_labeled_step
from aidlearning.core.agentic.labels import LABEL_UNKNOWN, find_inline_labels
from aidlearning.tools.dispatch import DispatchOutcome
from aidlearning.core.agentic.usage import UsageTracker
from aidlearning.core.stream_bus import StreamBus


@dataclass(frozen=True)
class LabelProtocol:
    """能力标签词汇的声明式描述。

    * ``allowed``      — LLM 可能在第一行发出的所有标签。
    * ``terminal``     — 退出循环的标签。结果的 ``final_label`` 反映触发了哪一个。
    * ``intermediate`` — 保持循环运行的标签（标签后的文本追加为助手上下文）。
    * ``final``        — 标签后文本应通过宿主的 ``emit_final`` 作为正文内容发出的标签。
      ``final`` 独立于 ``terminal`` / ``intermediate``：终结标签可以选择不发出正文
      （如 ``REPLAN`` 向上冒泡文本而不流式传输），中间标签可以选择**加入**正文发出，
      使其文本出现在用户可见的聊天气泡中而循环继续
      （如 chat 的 ``PAUSE`` — 在推理过程中向用户叙述而不结束轮次）。
    * ``tool_label``   — 表示"本轮调用工具"的单个标签
      （或 ``None`` 以禁用此循环的原生工具调用）。
    """

    allowed: tuple[str, ...]
    terminal: frozenset[str]
    intermediate: frozenset[str]
    final: frozenset[str]
    tool_label: str | None


@dataclass(frozen=True)
class LoopOutcome:
    """单次智能体循环运行的结果。"""

    final_label: str  # 退出循环的标签（被工具终止时为空）
    final_text: str   # 标签后文本（如果在 protocol.final 中则已流式传输）
    iterations: int
    sources: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    completed: bool = False


class LoopHost(Protocol):
    """能力提供的、循环回调的钩子。

    实现类打包所有 chat/solve 等特定行为（追踪元数据、工具分派、
    提示词文案），使循环核心保持通用。
    """

    async def guard_context_window(self, messages: list[dict[str, Any]]) -> None:
        """可选地修剪 ``messages`` 以保持在模型的上下文窗口内。"""

    def build_iteration_trace_meta(self, iteration: int) -> tuple[dict[str, Any], dict[str, Any]]:
        """为一次迭代分配 ``(iter_meta, final_meta)``。"""

    async def dispatch_tools(
        self,
        *,
        iteration: int,
        tool_calls: list[dict[str, Any]],
    ) -> DispatchOutcome:
        """并行执行本轮迭代的工具调用。"""

    async def resolve_pause(self, dispatch: DispatchOutcome) -> bool:
        """处理 ``pause_for_user`` 请求。返回 ``True`` 以继续。"""

    async def emit_terminator(self, payload: dict[str, Any] | None) -> None:
        """将终止工具的内容作为最终响应事件发出。"""

    async def emit_final(self, text: str, final_meta: dict[str, Any]) -> None:
        """为 :attr:`LabelProtocol.final` 中的标签发出正文内容。"""

    async def validate_terminal(self, label: str, text: str) -> str | None:
        """接受终结标签前的可选有状态验证。

        返回协议违反键以进行修复/重试而非结束循环，
        或 ``None`` 以接受终结标签。
        """
        return None

    def assistant_message_with_tool_calls(
        self,
        *,
        content: str,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """格式化携带本轮工具调用的助手轮次。"""

    def protocol_retry_notice(self) -> str:
        """协议违反触发重试时显示的通知文本。"""

    def protocol_repair_message(self, violation: str) -> str:
        """反馈给下一次 LLM 调用的按违反类型纠正提示词。"""

    async def force_finalize(
        self,
        *,
        messages: list[dict[str, Any]],
        start_iteration: int,
    ) -> tuple[str, bool, int]:
        """当 ``max_iterations`` 耗尽且无终结标签时，驱动能力所需的恢复逻辑。
        返回 ``(final_text, completed, extra_iterations_consumed)``。"""

    async def before_iteration(
        self,
        *,
        messages: list[dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> None:
        """可选钩子，在每次迭代开始时触发，在
        :py:meth:`guard_context_window` **之后**、LLM 调用**之前**。

        能力可以使用此钩子注入模型应该看到的每迭代上下文 —
        例如一个小的"你在第 N/M 次迭代"标记，使 LLM 能自行控制节奏。
        钩子就地修改 ``messages``；循环通过 ``getattr`` 检查方法是否存在，
        使现有的宿主保持不变。返回任何值都会被忽略。
        """
        return None

    async def on_intermediate(self, label: str, text: str) -> str | None:
        """中间标签的可选副作用钩子。

        在循环将中间标签的标签后文本作为助手消息追加**之后**、
        下一次迭代开始**之前**调用。能力可以覆盖以修改自身状态
        （例如当 ``APPEND`` 标签触发动态主题队列扩展时），
        并可选地返回非空字符串，循环将其作为 ``role=user`` 反馈消息追加 —
        用于确认成功的变更或报告拒绝，使 LLM 能在下一次迭代中适应。

        返回 ``None``（默认）是空操作。实现此钩子是可选的 —
        省略它的宿主保留旧行为（仅追加文本并继续）。循环通过 ``getattr``
        检查方法是否存在，使现有宿主（chat、solve）无需显式声明存根
        即可保持正常工作。
        """
        return None


async def run_agentic_loop(
    *,
    initial_messages: list[dict[str, Any]],
    protocol: LabelProtocol,
    client: Any,
    model: str | None,
    completion_kwargs: dict[str, Any],
    binding: str | None,
    tool_schemas: list[dict[str, Any]] | None,
    stream: StreamBus,
    source: str,
    stage: str,
    max_iterations: int,
    host: LoopHost,
    usage: UsageTracker | None = None,
    stream_body_live: bool = False,
    eager_sub_trace: bool = False,
    implicit_think_label: str | None = None,
) -> LoopOutcome:
    """运行标签驱动的 LLM 循环，直到终结标签触发或迭代预算耗尽。

    ``initial_messages`` 被就地修改（并通过 :attr:`LoopOutcome.messages` 返回），
    以便调用方可以检查/重用完整的消息历史。

    ``stream_body_live=True`` 使标签化步骤将终结标签的块直接流式传输到
    ``stream.content``（逐块正文输出），并导致循环跳过 :py:meth:`LoopHost.emit_final`` —
    文本已在传输中。默认 ``False`` 保持 chat 现有的一次性发出行为。

    ``eager_sub_trace=True`` 在 LLM 流开始前打开每迭代的子追踪卡片，
    消除每次调用首 token 时间（网络 + 模型预热）期间可见的"无活动"间隙。
    默认 ``False`` 保持 chat 的惰性打开行为，使仅 FINISH 的迭代不会
    生成空的"推理中…"卡片。
    """
    messages = initial_messages
    aggregated_sources: list[dict[str, Any]] = []
    final_text = ""
    final_label_seen = ""
    completed = False
    iterations_run = 0
    max_iter = max(1, max_iterations)

    for iteration in range(max_iter):
        await host.guard_context_window(messages)
        before_iteration = getattr(host, "before_iteration", None)
        if before_iteration is not None:
            await before_iteration(
                messages=messages,
                iteration=iteration,
                max_iterations=max_iter,
            )
        iter_meta, final_meta = host.build_iteration_trace_meta(iteration)

        step = await run_labeled_step(
            client=client,
            model=model,
            messages=messages,
            completion_kwargs=completion_kwargs,
            tool_schemas=tool_schemas,
            allowed_labels=protocol.allowed,
            final_labels=protocol.final,
            tool_label=protocol.tool_label,
            stream=stream,
            source=source,
            stage=stage,
            iter_meta=iter_meta,
            binding=binding,
            usage=usage,
            final_meta=final_meta if stream_body_live else None,
            eager_sub_trace=eager_sub_trace,
            implicit_think_label=implicit_think_label,
        )
        iterations_run += 1

        violation = _protocol_violation(step, protocol)
        if violation:
            await _emit_retry_notice(
                stream=stream,
                source=source,
                stage=stage,
                host=host,
                violation=violation,
            )
            _append_repair_messages(
                messages=messages,
                iteration_text=step.text,
                violation=violation,
                host=host,
            )
            continue

        if step.label in protocol.terminal:
            validate_terminal = getattr(host, "validate_terminal", None)
            if validate_terminal is not None:
                violation = await validate_terminal(step.label, step.text)
                if violation:
                    await _emit_retry_notice(
                        stream=stream,
                        source=source,
                        stage=stage,
                        host=host,
                        violation=violation,
                    )
                    _append_repair_messages(
                        messages=messages,
                        iteration_text=step.text,
                        violation=violation,
                        host=host,
                    )
                    continue
            if step.label in protocol.final and not stream_body_live:
                # 当 ``run_labeled_step`` 已实时流式传输正文块时，
                # 此处调用 ``host.emit_final`` 会将文本重复发到聊天气泡中。
                await host.emit_final(step.text, final_meta)
            final_text = step.text
            final_label_seen = step.label
            completed = True
            break

        if protocol.tool_label is not None and step.label == protocol.tool_label:
            messages.append(
                host.assistant_message_with_tool_calls(
                    content=step.text,
                    tool_calls=step.tool_calls,
                )
            )
            outcome = await host.dispatch_tools(
                iteration=iteration,
                tool_calls=step.tool_calls,
            )
            aggregated_sources.extend(outcome.sources)
            messages.extend(outcome.tool_messages)
            if outcome.pause:
                resumed = await host.resolve_pause(outcome)
                if not resumed:
                    completed = False
                    break
                continue
            if outcome.terminate:
                await host.emit_terminator(outcome.terminate_payload)
                final_text = (outcome.terminate_payload or {}).get("content", "")
                completed = True
                break
            continue

        if step.label in protocol.intermediate:
            # 中间标签也可以标记为 ``final``：这意味着"将此文本流式传输到
            # 用户可见的聊天气泡中，但不要结束轮次"（chat 的 ``PAUSE``）。
            # 文本也作为助手上下文保留在下面，使下一次迭代能看到
            # 已经告诉用户的内容。
            if step.label in protocol.final and step.text and not stream_body_live:
                await host.emit_final(step.text, final_meta)
            if step.text:
                messages.append({"role": "assistant", "content": step.text})
            # 可选钩子，用于将副作用附加到中间标签的能力
            # （如 research 的 ``APPEND`` 修改主题队列）。当钩子返回
            # 非空字符串时，我们将其注入为下一次迭代的用户消息，
            # 使模型看到结构化的反馈（如"已追加第 4 个模块"）。
            on_intermediate = getattr(host, "on_intermediate", None)
            if on_intermediate is not None:
                feedback = await on_intermediate(step.label, step.text)
                if feedback:
                    messages.append({"role": "user", "content": feedback})
            continue

        # 对于上面未覆盖的任何未来标签值的防御性回退。不终止；修复并重试。
        await _emit_retry_notice(
            stream=stream,
            source=source,
            stage=stage,
            host=host,
            violation="unknown_action",
        )
        _append_repair_messages(
            messages=messages,
            iteration_text=step.text,
            violation="unknown_action",
            host=host,
        )
        continue
    else:
        finish_text, did_finish, extra_calls = await host.force_finalize(
            messages=messages,
            start_iteration=max_iter,
        )
        iterations_run += extra_calls
        final_text = finish_text
        completed = did_finish

    return LoopOutcome(
        final_label=final_label_seen,
        final_text=final_text,
        iterations=iterations_run,
        sources=aggregated_sources,
        messages=messages,
        completed=completed,
    )


def _protocol_violation(
    step: LabeledStepResult,
    protocol: LabelProtocol,
) -> str | None:
    """将标签化步骤结果与协议对比分类；返回违反键
    （匹配宿主的修复消息词汇）或合规时返回 ``None``。"""
    if step.label == LABEL_UNKNOWN:
        return "missing_label"
    if find_inline_labels(step.text, allowed_labels=protocol.allowed):
        return "multiple_labels"
    if protocol.tool_label is not None:
        if step.label == protocol.tool_label and not step.tool_calls:
            return "tool_without_calls"
        if step.label != protocol.tool_label and step.tool_calls:
            # 违反键携带实际的违规标签，以便宿主能渲染准确的修复消息。
            # 旧版键 ``think_with_tools`` / ``finish_with_tools`` 仍为
            # 标准 THINK/FINISH 标签生成，但新的标签词汇
            # （如 chat 的 ``PAUSE`` — 中间 + 终结）获得各自的
            # ``{label}_with_tools`` 键。
            return f"{step.label.lower()}_with_tools"
    return None


async def _emit_retry_notice(
    *,
    stream: StreamBus,
    source: str,
    stage: str,
    host: LoopHost,
    violation: str,
) -> None:
    await stream.progress(
        host.protocol_retry_notice(),
        source=source,
        stage=stage,
        metadata={"trace_kind": "warning", "protocol_violation": violation},
    )


_REPAIR_PREVIEW_CHARS = 500


def _append_repair_messages(
    *,
    messages: list[dict[str, Any]],
    iteration_text: str,
    violation: str,
    host: LoopHost,
) -> None:
    """保留模型未标记的草稿作为助手上下文，然后添加纠正提示词，
    告知下一次迭代该做什么。"""
    clipped = str(iteration_text or "").strip()
    if clipped:
        if len(clipped) > _REPAIR_PREVIEW_CHARS:
            clipped = clipped[:_REPAIR_PREVIEW_CHARS].rstrip() + "\n...[truncated]"
        messages.append({"role": "assistant", "content": clipped})
    messages.append({"role": "user", "content": host.protocol_repair_message(violation)})


# 在此处重新导出 ``Awaitable``，使消费者无需仅为宿主实现的类型标注
# 而单独导入它（镜像 ``asyncio`` 对 ``Future`` 的做法）。
__all__ = [
    "Awaitable",
    "LabelProtocol",
    "LoopHost",
    "LoopOutcome",
    "run_agentic_loop",
]
