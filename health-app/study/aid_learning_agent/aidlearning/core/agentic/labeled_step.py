r"""带协议标签路由的单次流式 LLM 调用。

核心单轮往返原语。给定一个 OpenAI 兼容的流式客户端、可选的工具 schema
和标签协议，该模块会：

* 解析前几个块中的 ``\`\`LABEL\`\``` 前缀。
* 对于*非终结*标签（如 ``THINK``、``TOOL``、``REPLAN``），将标签后的文本
  实时流式传输到 ``stream.thinking`` 下的推理子追踪（使用提供的 ``iter_meta``）。
* 对于*终结*标签（如 ``FINISH``、``PLAN``、``SUMMARY``），缓冲标签后的文本
  并返回给调用方；由调用方决定是否将其作为正文内容发出（这样混合的
  ``FINISH+TOOL`` 回复在协议验证前不会将文本泄漏到回答区域）。
* 累积 ``tool_calls`` 增量。当 ``tool_label`` 已设置且工具调用增量在标签
  解析之前到达时，强制将标签解析为该值（工具调用的存在具有决定性）。
* 当推理模型在协议标签前附加了字面 ```` 块时，
  检测该前导部分并将其实时流式传输到推理子追踪中（与 ``THINK`` 标签
  使用相同的路由）。标签探测从 ``</think>`` 之后的内容继续：
  如果标签解析为中间标签（如 ``THINK``），标签后的文本继续流入*同一*子追踪；
  如果解析为终结标签（如 ``FINISH``），标签后的文本按常规路由到最终响应区域。
  ``<think>``/``</think>`` 标记本身不会实时发出，仅保留在累积缓冲区中，
  以便 ``clean_thinking_tags`` 可以从返回的文本中去除该块。

返回解析后的标签、累积的标签后文本（已去除提供商的 think 标签）和解析的工具调用。
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import re
from typing import Any

from aidlearning.core.agentic.labels import (
    LABEL_PROBE_MAX_CHARS,
    LABEL_UNKNOWN,
    classify_label,
    strip_label_probe_prefix,
)
from aidlearning.core.agentic.usage import UsageTracker
from aidlearning.core.stream_bus import StreamBus
from aidlearning.core.trace import merge_trace_metadata
from aidlearning.services.llm import clean_thinking_tags

# 推理模型（Qwen、通过某些代理的 Deepseek-R1 等）有时会在内容流中
# 发射协议标签之前内联一个字面 ``<think>...</think>`` 块。仅在探测缓冲区
# 的开头（去除空白后）匹配开始标签 — 之后的任何内容属于标签后的正文，
# 由 ``clean_thinking_tags`` 在末尾处理。
#
# 反引号必须成对出现（如 `` `<think>` `` 或 ``<think>``）—
# 任一侧单独的可选反引号会贪婪地吞掉后面协议标签的开头反引号
# （如 ``</think>`` 紧接 ``\`\`FINISH\`\``` 之前），从而损坏前导标签探测。
_THINK_OPEN_RE = re.compile(
    r"\A(?:`<\s*think(?:ing)?\b[^>]*>`|<\s*think(?:ing)?\b[^>]*>)",
    re.IGNORECASE,
)
_THINK_CLOSE_RE = re.compile(
    r"(?:`<\s*/\s*think(?:ing)?\s*>`|<\s*/\s*think(?:ing)?\s*>)",
    re.IGNORECASE,
)
# ``</think>`` 加上可选的周围反引号/空白的余量。
# 我们最多保留这么多前导部分的尾部字符未发送，以便跨块分割的
# 结束标签仍可被检测到。
_THINK_CLOSE_TAIL_GUARD = 24
# 一旦提供商明确发送了 ``finish_reason``，文本生成就完成了。
# 某些 OpenAI 兼容网关在等待可选的使用量尾部数据时会保持 SSE 连接打开；
# 短暂等待该帧，然后本地关闭，以便 UI 能及时收到 RESULT/DONE。
_USAGE_TRAILER_GRACE_TIMEOUT_S = 1.0
# 对于从不发射 ``finish_reason`` 但已经发送了终结标签答案然后
# 让流空闲的网关的防御性回退。
_FINAL_LABEL_IDLE_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class LabeledStepResult:
    """单次标签化 LLM 调用的结果。"""

    label: str  # allowed_labels 之一，协议失败时为 LABEL_UNKNOWN
    text: str   # 已去除提供商 think 标签的标签后内容
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class _UsageShim:
    """将流式 ``CompletionUsage`` 适配为 ``UsageTracker`` 所需的形状。"""

    def __init__(self, raw: Any) -> None:
        self.usage = raw


def _message_content_chars(message: dict[str, Any]) -> int:
    """用于使用量回退估算的最佳努力字符计数。"""
    content = message.get("content")
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    total += len(str(part.get("text") or ""))
                elif "text" in part:
                    total += len(str(part.get("text") or ""))
            elif isinstance(part, str):
                total += len(part)
        return total
    if content is None:
        return 0
    return len(str(content))


def _is_stream_options_unsupported(exc: Exception) -> bool:
    """检测拒绝 OpenAI 的 ``stream_options`` 参数的提供商。"""
    response = getattr(exc, "response", None)
    body = (
        getattr(exc, "body", None)
        or getattr(exc, "doc", None)
        or getattr(response, "text", None)
        or getattr(exc, "message", None)
        or str(exc)
    )
    text = str(body).lower()
    return any(
        marker in text
        for marker in (
            "stream_options",
            "stream options",
            "unknown parameter",
            "unrecognized request argument",
            "unsupported parameter",
            "extra inputs are not permitted",
            "unexpected keyword",
        )
    )


def _is_tool_schema_unsupported(exc: Exception) -> bool:
    """检测拒绝原生工具/函数调用 schema 的提供商。"""
    response = getattr(exc, "response", None)
    body = (
        getattr(exc, "body", None)
        or getattr(exc, "doc", None)
        or getattr(response, "text", None)
        or getattr(exc, "message", None)
        or str(exc)
    )
    text = str(body).lower()
    return any(
        marker in text
        for marker in (
            "tool",
            "function_declaration",
            "function declaration",
            "function_declarations",
            "tool_choice",
            "parameters.properties",
            "404_not_found",
            "404 not_found",
        )
    )


async def run_labeled_step(
    *,
    client: Any,
    model: str | None,
    messages: list[dict[str, Any]],
    completion_kwargs: dict[str, Any],
    tool_schemas: list[dict[str, Any]] | None,
    allowed_labels: tuple[str, ...],
    final_labels: frozenset[str],
    tool_label: str | None,
    stream: StreamBus,
    source: str,
    stage: str,
    iter_meta: dict[str, Any],
    binding: str | None = None,
    usage: UsageTracker | None = None,
    final_meta: dict[str, Any] | None = None,
    eager_sub_trace: bool = False,
    implicit_think_label: str | None = None,
) -> LabeledStepResult:
    """在标签协议下驱动一次流式 LLM 调用。

    ``final_meta`` 使标签后流启用**实时正文流式传输**：
    设置后，每个解析到 ``final_labels`` 中标签的块都会使用 ``final_meta``
    作为 :py:meth:`StreamBus.content` 事件发出（trace_kind="llm_chunk"），
    使聊天气泡逐块填充而非最后一次性出现。当 ``final_meta`` 为 ``None``
    （chat 的现有行为）时，终结标签的文本会被缓冲，调用方在协议验证后发出。

    ``eager_sub_trace=True`` 在 LLM 流开始前打开迭代的子追踪卡片，
    使追踪面板立即渲染"运行中"指示器，而非等到第一个块到达后才显示。
    这消除了每次调用的首 token 时间（通常 0.5-3 秒的网络+模型预热）
    期间的视觉空白。惰性默认保持 chat 的现有行为 — 其卡片仅在有实际
    推理文本可显示时才打开，避免为直接 FINISH 回复生成空的"推理中…"卡片。

    ``implicit_think_label`` 允许调用方（如 chat）声明"如果推理模型发出了
    ``<think>...</think>`` 但没有跟上我的协议标签，将整个迭代视为*该*标签"。
    其目的是优雅地接受原生格式的推理模型 — 它们在 ``<think>`` 块中思考，
    可能不会原样回显协议的 ``\`\`THINK\`\``` 令牌。没有此选项，循环会看到
    缺失标签而浪费迭代进行修复重试。当隐式解析触发时，前导标记保留在
    返回的 ``text`` 中，以便下一次迭代的助手上下文仍能逐字展示模型的推理。
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        **completion_kwargs,
    }
    auto_stream_options_added = False
    if usage is not None and "stream_options" not in kwargs:
        kwargs["stream_options"] = {"include_usage": True}
        auto_stream_options_added = True
    if tool_schemas:
        kwargs["tools"] = tool_schemas
        kwargs["tool_choice"] = "auto"

    label: str | None = None
    label_buf = ""
    in_prelude_think = False
    # 正在进行的前导部分的尾部切片，被暂留以便跨块分割的
    # ``</think>`` 仍可被检测到。
    prelude_tail = ""
    # 一旦我们观察到标签前 ``<think>`` 开始标记则为 True。最终的
    # ``clean_thinking_tags`` 处理由 ``binding`` 门控以保留现有行为；
    # 当检测到前导时我们始终强制清理，以防止记录的合成标记泄漏。
    saw_pre_label_think = False
    sub_trace_opened = False
    content_acc: list[str] = []
    tc_acc: dict[int, dict[str, Any]] = {}
    usage_seen: Any = None
    output_chars_seen = 0
    finish_reason_seen: str | None = None
    usage_trailer_waited = False

    async def _open_sub_trace() -> None:
        nonlocal sub_trace_opened
        if sub_trace_opened:
            return
        await stream.progress(
            iter_meta.get("label", ""),
            source=source,
            stage=stage,
            metadata=merge_trace_metadata(
                iter_meta,
                {"trace_kind": "call_status", "call_state": "running"},
            ),
        )
        sub_trace_opened = True

    async def _emit_text(text: str) -> None:
        """路由标签后的文本片段。

        * 终结标签的文本：被缓冲。如果提供了 ``final_meta``，该片段
          *也*作为 ``content`` 事件实时发出，使聊天气泡逐块流式传输
          （call_kind 为 llm_final_response）。
        * 非终结标签：流式传输到推理子追踪。
        """
        nonlocal output_chars_seen
        if not text:
            return
        output_chars_seen += len(text)
        content_acc.append(text)
        if label in final_labels:
            if final_meta is not None:
                await stream.content(
                    text,
                    source=source,
                    stage=stage,
                    metadata=merge_trace_metadata(final_meta, {"trace_kind": "llm_chunk"}),
                )
            return
        await _open_sub_trace()
        await stream.thinking(
            text,
            source=source,
            stage=stage,
            metadata=merge_trace_metadata(iter_meta, {"trace_kind": "llm_chunk"}),
        )

    async def _emit_prelude_content(text: str) -> None:
        """将标签前 ``<think>`` 正文内容流式传输到推理子追踪，
        路由方式与非终结 ``THINK`` 标签完全相同，这样后面出现的
        真正 ``THINK`` 标签自然合并到同一追踪中。原始文本也保留在
        ``content_acc`` 中，以便 :func:`clean_thinking_tags` 在最后
        可以从返回的文本中去除整个前导块。
        """
        nonlocal output_chars_seen
        if not text:
            return
        output_chars_seen += len(text)
        content_acc.append(text)
        await _open_sub_trace()
        await stream.thinking(
            text,
            source=source,
            stage=stage,
            metadata=merge_trace_metadata(iter_meta, {"trace_kind": "llm_chunk"}),
        )

    async def _emit_prelude_marker(tag_text: str) -> None:
        """将 ``<think>``/``</think>`` 标记实时流式传输到推理子追踪，
        并同时记录到 ``content_acc`` 中。

        该标记在追踪 UI 中可见（因此用户能看到模型发出的实际
        ``<think>...</think>`` 结构），累积缓冲区保留字面标签，
        使下游消费者（包括隐式 ``THINK`` 解析路径）可以按需保留或去除前导块。
        """
        nonlocal output_chars_seen
        if not tag_text:
            return
        output_chars_seen += len(tag_text)
        content_acc.append(tag_text)
        await _open_sub_trace()
        await stream.thinking(
            tag_text,
            source=source,
            stage=stage,
            metadata=merge_trace_metadata(iter_meta, {"trace_kind": "llm_chunk"}),
        )

    async def _close_prelude_artificially() -> None:
        """强制结束正在进行的 ``<think>`` 前导（用于工具调用在前导中途到达
        或流在没有结束标签的情况下结束时）。将任何暂留的尾部刷新到
        实时子追踪，并发出合成的 ``</think>`` 标记，使追踪和累积缓冲区
        都反映一个干净的关闭。"""
        nonlocal in_prelude_think, prelude_tail
        if prelude_tail:
            await _emit_prelude_content(prelude_tail)
            prelude_tail = ""
        await _emit_prelude_marker("</think>")
        in_prelude_think = False

    async def _drain_prelude_or_close() -> None:
        """当 ``in_prelude_think`` 为 True 时，扫描 ``prelude_tail`` 中的
        ``</think>`` 结束标签。如果找到，将标签前的内容实时发出，
        将结束标记实时发出，并将标签后的内容移入 ``label_buf`` 以恢复标签探测。
        如果未找到，在保持小的防护窗口的前提下尽可能多地发出尾部内容，
        以便下次跨块分割的结束标签仍可被检测到。"""
        nonlocal in_prelude_think, prelude_tail, label_buf
        close_m = _THINK_CLOSE_RE.search(prelude_tail)
        if close_m is None:
            if len(prelude_tail) > _THINK_CLOSE_TAIL_GUARD:
                split = len(prelude_tail) - _THINK_CLOSE_TAIL_GUARD
                safe = prelude_tail[:split]
                prelude_tail = prelude_tail[split:]
                await _emit_prelude_content(safe)
            return
        before = prelude_tail[: close_m.start()]
        if before:
            await _emit_prelude_content(before)
        await _emit_prelude_marker(close_m.group(0))
        in_prelude_think = False
        label_buf = prelude_tail[close_m.end() :]
        prelude_tail = ""

    async def _ingest_pre_label(text: str) -> None:
        """为单个流式块驱动标签前状态机。

        在单个块中处理（如果数据允许）：继续打开的 ``<think>`` 前导、
        在缓冲区以 ``<think>`` 开头时进入新前导、在 ``</think>`` 时关闭前导、
        解析协议标签以及探测溢出回退。
        """
        nonlocal label, label_buf, in_prelude_think, prelude_tail
        nonlocal saw_pre_label_think

        if in_prelude_think:
            prelude_tail += text
        elif text:
            label_buf += text

        # 只要当前缓冲区允许进展就驱动状态机前进。单个块可以携带
        # 整个前导、标签和标签后文本，因此我们持续循环直到标签解析
        # 或可判定的输入耗尽。
        while True:
            if in_prelude_think:
                await _drain_prelude_or_close()
                if in_prelude_think:
                    return  # 等待 ``</think>``
                # ``</think>`` 已消费；``label_buf`` 现在持有前导后的剩余内容。
                # 继续进行标签探测。

            stripped = strip_label_probe_prefix(label_buf)
            open_m = _THINK_OPEN_RE.match(stripped)
            if open_m:
                leading_len = len(label_buf) - len(stripped)
                if leading_len:
                    # 逐字保留附带的前导空白 — 最终的
                    # ``cleaned.strip()``（在 ``clean_thinking_tags`` 内）
                    # 会将其平滑处理。
                    content_acc.append(label_buf[:leading_len])
                in_prelude_think = True
                saw_pre_label_think = True
                prelude_tail = stripped[open_m.end() :]
                label_buf = ""
                # 实时发出 ``<think>`` 标记，使推理子追踪显示模型的原生结构。
                # 这也立即打开子追踪卡片，因此简短的前导（<=24 字符）
                # 在关闭标签防护窗口刷新内容之前就能在 UI 中显示活动。
                await _emit_prelude_marker(open_m.group(0))
                continue  # 重新进入循环以排空前导

            parsed = classify_label(label_buf, allowed_labels=allowed_labels)
            if parsed is not None:
                label, after_label = parsed
                label_buf = ""
                await _emit_text(after_label)
                return

            if len(label_buf) > LABEL_PROBE_MAX_CHARS:
                # 探测窗口用尽且无协议标签匹配。如果我们之前消费了
                # ``<think>`` 前导且调用方启用了隐式 THINK 语义，
                # 将此迭代视为隐式 ``THINK`` — 模型是说原生方言的推理模型。
                # 否则回退到 ``LABEL_UNKNOWN`` 让调用方修复。
                if (
                    saw_pre_label_think
                    and implicit_think_label
                    and implicit_think_label in allowed_labels
                ):
                    label = implicit_think_label
                else:
                    label = LABEL_UNKNOWN
                flushed = label_buf
                label_buf = ""
                await _emit_text(flushed)
                return

            return  # 无法在没有更多输入的情况下做出进一步决定

    if eager_sub_trace:
        # 在 LLM 流开始*之前*打开子追踪卡片，使追踪面板在即将到来的
        # 调用的首 token 时间（否则是静默 UI）期间渲染活动。
        await _open_sub_trace()

    async def _create_response_stream() -> Any:
        try:
            return await client.chat.completions.create(**kwargs)
        except Exception as exc:
            if auto_stream_options_added and _is_stream_options_unsupported(exc):
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop("stream_options", None)
                return await client.chat.completions.create(**retry_kwargs)
            if tool_schemas and _is_tool_schema_unsupported(exc):
                await stream.progress(
                    "Provider rejected native tool schemas; retrying without tools.",
                    source=source,
                    stage=stage,
                    metadata=merge_trace_metadata(
                        iter_meta,
                        {"trace_kind": "warning", "tool_schema_fallback": True},
                    ),
                )
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop("tools", None)
                retry_kwargs.pop("tool_choice", None)
                return await client.chat.completions.create(**retry_kwargs)
            raise

    response_stream = await _create_response_stream()
    try:
        stream_iter = response_stream.__aiter__()
        while True:
            timeout: float | None = None
            if finish_reason_seen:
                if usage is not None and usage_seen is None and not usage_trailer_waited:
                    timeout = _USAGE_TRAILER_GRACE_TIMEOUT_S
                    usage_trailer_waited = True
                else:
                    break
            elif label in final_labels and content_acc:
                timeout = _FINAL_LABEL_IDLE_TIMEOUT_S
            try:
                if timeout is None:
                    chunk = await stream_iter.__anext__()
                else:
                    chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=timeout)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                # 对于聊天 UI 来说足够终止：模型已经发送了终结标签答案
                # （或显式的 finish_reason），但网关仍保持连接打开。
                if finish_reason_seen or label in final_labels:
                    break
                raise
            if getattr(chunk, "usage", None):
                usage_seen = chunk.usage
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason_seen = str(choice.finish_reason)
            delta = choice.delta
            if delta is None:
                continue

            # 通过专用 ``reasoning_content``（或 ``reasoning``）字段
            # 呈现思维链的推理模型 — 如通过某些提供商的 DeepSeek-R1、
            # 某些兼容模式下的 OpenAI o1/o3 — 在推理阶段不发出
            # ``delta.content``。没有此分支，UI 会在整个推理期间冻结，
            # 然后答案块到达，用户只看到答案而没有推理追踪。将推理流
            # 实时路由到与内联 ``<think>`` 前导使用的同一子追踪，使两种
            # 风格的推理模型表现一致。``saw_pre_label_think`` 强制最终
            # 清理路径在 ``binding`` 未设置时也能运行。
            reasoning_text = getattr(delta, "reasoning_content", None) or getattr(
                delta, "reasoning", None
            )
            if reasoning_text and label is None:
                output_chars_seen += len(reasoning_text)
                saw_pre_label_think = True
                await _open_sub_trace()
                await stream.thinking(
                    reasoning_text,
                    source=source,
                    stage=stage,
                    metadata=merge_trace_metadata(iter_meta, {"trace_kind": "llm_chunk"}),
                )

            if delta.content:
                text = delta.content
                if label is None:
                    await _ingest_pre_label(text)
                else:
                    await _emit_text(text)

            for tc_delta in getattr(delta, "tool_calls", None) or []:
                fn_for_chars = getattr(tc_delta, "function", None)
                output_chars_seen += len(str(getattr(fn_for_chars, "name", "") or ""))
                output_chars_seen += len(str(getattr(fn_for_chars, "arguments", "") or ""))
                # 工具调用增量对工具分支具有决定性。如果我们在
                # 工具调用增量到达时仍在缓冲标签，强制解析为 ``tool_label``
                # 使缓冲的文本刷新到推理子追踪，后续文本继续在那里。
                if label is None and tool_label:
                    label = tool_label
                    if in_prelude_think:
                        # 在将任何缓冲的文本视为工具分支的推理前导之前
                        # 关闭前导。
                        await _close_prelude_artificially()
                    flushed = label_buf
                    label_buf = ""
                    if flushed:
                        await _emit_text(flushed)
                idx = getattr(tc_delta, "index", 0)
                entry = tc_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if getattr(tc_delta, "id", None):
                    entry["id"] = tc_delta.id
                fn = getattr(tc_delta, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        entry["name"] = entry["name"] + fn.name
                    if getattr(fn, "arguments", None):
                        entry["arguments"] = entry["arguments"] + fn.arguments
    finally:
        close = getattr(response_stream, "close", None)
        if callable(close):
            with suppress(Exception):
                await close()

    # 流在仍在缓冲标签时结束。决定如何解析：
    #
    # - 如果我们看到了 ``<think>`` 前导且调用方启用了隐式 THINK 语义，
    #   将此迭代视为隐式 ``THINK``，使循环继续（原生说
    #   ``<think>...</think>`` 的推理模型被接受而非被视为协议违反者）。
    # - 否则回退到 ``LABEL_UNKNOWN`` 让调用方修复。
    if label is None:
        if in_prelude_think:
            # 流在前导中途结束 — 将剩余的推理内容实时刷新，
            # 让用户看到模型设法产生的内容，然后合成关闭块。
            await _close_prelude_artificially()
        final_parsed = classify_label(
            label_buf,
            allowed_labels=allowed_labels,
            final=True,
        )
        if final_parsed is not None:
            label, after_label = final_parsed
            label_buf = ""
            await _emit_text(after_label)
        if (
            label is None
            and saw_pre_label_think
            and implicit_think_label
            and implicit_think_label in allowed_labels
        ):
            label = implicit_think_label
        elif label is None:
            label = LABEL_UNKNOWN
        if label_buf:
            await _emit_text(label_buf)
            label_buf = ""

    if usage_seen is not None and usage is not None:
        usage.add_from_response(_UsageShim(usage_seen))
    elif usage is not None:
        input_chars = sum(_message_content_chars(message) for message in messages)
        if input_chars or output_chars_seen:
            usage.add_estimated(
                input_chars=input_chars,
                output_chars=output_chars_seen,
            )

    if sub_trace_opened:
        await stream.progress(
            "",
            source=source,
            stage=stage,
            metadata=merge_trace_metadata(
                iter_meta,
                {"trace_kind": "call_status", "call_state": "complete"},
            ),
        )

    text = "".join(content_acc)
    # 当我们隐式地将迭代解析为 ``THINK`` 时，保留字面 ``<think>...</think>`` 块 —
    # 下一次迭代的助手上下文应该逐字反映模型的推理，而非被剥离的空草稿。
    # 对于所有其他解析，回退到标准清理，使下游消费者（助手消息、最终响应文本）
    # 不会被前导标记污染。
    implicit_think_resolved = bool(
        saw_pre_label_think and implicit_think_label and label == implicit_think_label
    )
    if (binding or saw_pre_label_think) and not implicit_think_resolved:
        text = clean_thinking_tags(text, binding, model)
    ordered_tool_calls = [tc_acc[k] for k in sorted(tc_acc.keys())]
    ordered_tool_calls = [tc for tc in ordered_tool_calls if tc.get("name")]
    return LabeledStepResult(label=label, text=text, tool_calls=ordered_tool_calls)
