"""单循环 Agent 聊天管线。

聊天能力以一个迭代式 LLM 循环运行。每次迭代是一次流式 LLM 调用，
随后根据模型首行协议标签决定后续行为：

* ``FINISH`` → 标签后的文本即为最终的用户答案；循环退出。
* ``TOOL``   → 原生 tool_calls 并行执行；结果反馈到下一次迭代。
  工具可能会暂停（``ask_user``）或终止本轮。
* ``THINK``  → 中间推理；循环继续，以便下次调用可以基于此推理。
* ``PAUSE``  → 语义上等同于 ``THINK``，但推理文本会展示给用户。
  与 ``THINK`` 行为相同（中间状态、无工具、循环继续），但标签后的
  文本会像 ``FINISH`` 一样流入聊天气泡，让用户在值得展示时看到推理过程。

本模块是*能力特定的*组装层。通用引擎位于 :mod:`aidlearning.core.agentic`：
标签解析、单次流式调用、并行工具调度和循环调度器。Chat 插入自己的：

* 工具组合 + 每轮 KB / 源 / 笔记本枚举
* 系统提示词 + 消息组装（记忆、技能、清单、附件）
* 服务端工具参数增强
* 上下文窗口守卫、强制完成、立即回答快速路径
* 协议违规文案（YAML 加载、语言感知）

历史压缩（分支安全）由上游的 ``ContextBuilder.build`` 处理，因此不在此处出现。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from aidlearning.tools.composition import (
    ToolMountFlags,
    compose_enabled_tools,
    default_optional_tools,
    user_has_memory,
)
from aidlearning.capabilities._shared import emit_capability_result
from aidlearning.core.agentic import (
    LABEL_PROBE_MAX_CHARS,
    LABEL_UNKNOWN,
    DispatchOutcome,
    LabeledStepResult,
    LabelProtocol,
    LLMClientConfig,
    UsageTracker,
    build_completion_kwargs,
    build_openai_client,
    can_use_native_tool_calling,
    dispatch_tool_calls,
    run_agentic_loop,
    run_labeled_step,
)
from aidlearning.core.agentic.labels import find_inline_labels, strip_label_probe_prefix
from aidlearning.tools.dispatch import MAX_PARALLEL_TOOL_CALLS
from aidlearning.core.context import UnifiedContext
from aidlearning.core.stream_bus import StreamBus
from aidlearning.core.trace import (
    build_trace_metadata,
    derive_trace_metadata,
    merge_trace_metadata,
    new_call_id,
)
from aidlearning.tools.registry import get_tool_registry
from aidlearning.services.config import get_chat_params, load_system_settings  # noqa: F401
from aidlearning.services.llm import (
    clean_thinking_tags,
    get_llm_config,
    get_token_limit_kwargs,  # noqa: F401  (re-exported for tests)
    prepare_multimodal_messages,
    supports_tools,  # noqa: F401  (re-exported for tests)
)
from aidlearning.services.llm import (
    stream as llm_stream,
)
from aidlearning.services.llm.context_window import resolve_effective_context_window
from aidlearning.services.prompt import get_prompt_manager
from aidlearning.services.prompt.language import append_language_directive

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 模块级配置
# ---------------------------------------------------------------------------

CHAT_EXCLUDED_TOOLS: set[str] = set()
# 用户可切换的工具 — 由 composer / 设置界面提供。在导入时通过共享工具组合策略
# 一次性计算，确保 chat 和 quiz 管线对用户可控制的工具保持一致。
CHAT_OPTIONAL_TOOLS = default_optional_tools(excluded=CHAT_EXCLUDED_TOOLS)

# 工具迭代上限：足够高以支持含 ask_user / 工具修复的多步聊天循环，
# 同时有界以防止无限循环。可通过 ``capabilities.chat.max_iterations`` 覆盖。
DEFAULT_MAX_ITERATIONS = 20
# 当消息超过模型有效上下文窗口的此比例时，轮内守卫会将最旧的过期工具结果
# 替换为截断标记。为下次 LLM 调用保留余量而不中断。
CONTEXT_WINDOW_GUARD_RATIO = 0.9
TOOL_RESULT_SNIP_MARKER = (
    "[earlier tool result snipped to stay within context window — "
    "call the same tool again if the content is still needed]"
)
FINALIZATION_REPAIR_ATTEMPTS = 3

# Chat 专属标签字符串（chat 的协议词汇）。保留为命名常量以便在
# chat YAML / 文案代码中引用。
LABEL_FINISH = "FINISH"
LABEL_TOOL = "TOOL"
LABEL_THINK = "THINK"
# ``PAUSE`` 是 chat 专属标签：语义上是可见的 ``THINK`` ——
# 与 ``THINK`` 相同的中间状态 / 无工具 / 循环继续行为，但标签后的
# 文本会流入用户可见的聊天气泡（因此同时属于 ``intermediate`` 和 ``final``）。
# LLM 仅在推理本身值得展示给用户时才会选择 ``PAUSE`` 而非 ``THINK``。
LABEL_PAUSE = "PAUSE"

# Chat 的标签协议，传入通用循环原语。
_CHAT_PROTOCOL = LabelProtocol(
    allowed=(LABEL_FINISH, LABEL_TOOL, LABEL_THINK, LABEL_PAUSE),
    terminal=frozenset({LABEL_FINISH}),
    intermediate=frozenset({LABEL_THINK, LABEL_PAUSE}),
    final=frozenset({LABEL_FINISH, LABEL_PAUSE}),
    tool_label=LABEL_TOOL,
)


# ---------------------------------------------------------------------------
# 立即回答的宽松标签解析
# ---------------------------------------------------------------------------
# 主循环拥有规范协议，现在在核心解析器层面也容忍常见的包装变体。
# 立即回答更加宽容 —— 它是一个终端的、无工具的快速路径，因此最安全的
# UI 行为是剥离常见拼写变体而非将其作为字面标签渲染。

_ANSWER_NOW_WRAPPED_LABEL_RE = re.compile(
    r"^`+\s*(FINISH|TOOL|THINK|PAUSE)\s*`+(?P<after>.*)$",
    re.DOTALL,
)
_ANSWER_NOW_UNTERMINATED_WRAPPED_LABEL_RE = re.compile(
    r"^`+\s*(FINISH|TOOL|THINK|PAUSE)\s*$",
    re.DOTALL,
)
_LABEL_SEPARATOR_CHARS = "\n\r \t:：-–—"
_ANSWER_NOW_ALLOWED_LABELS: tuple[str, ...] = (
    LABEL_FINISH,
    LABEL_TOOL,
    LABEL_THINK,
    LABEL_PAUSE,
)


# 为仍导入此名称的测试重新导出。新代码直接构造规范的 ``DispatchOutcome``。
_DispatchOutcome = DispatchOutcome


def _could_be_wrapped_answer_now_label(stripped: str) -> bool:
    """判断以反引号开头的缓冲区是否仍可能成为标签。"""
    probe = stripped.lstrip("`").lstrip()
    if not probe:
        return True
    for label in _ANSWER_NOW_ALLOWED_LABELS:
        if label.startswith(probe):
            return True
        if probe.startswith(label):
            after = probe[len(label) :]
            if not after.strip("` \t\r\n"):
                return True
    return False


def _classify_answer_now_label(
    buffer: str,
    *,
    final: bool = False,
) -> tuple[str, str] | None:
    """:meth:`AgenticChatPipeline._run_answer_now` 使用的宽松标签剥离器。

    接受规范的双反引号包装以及常见的更宽松变体（单反引号包装、
    后跟分隔符的未包装标签）。当缓冲区仍看起来像部分标签匹配时
    返回 ``None`` —— 调用方继续缓冲。
    """
    from aidlearning.core.agentic.labels import classify_label

    parsed = classify_label(buffer, allowed_labels=_ANSWER_NOW_ALLOWED_LABELS)
    if parsed is not None:
        return parsed

    stripped = strip_label_probe_prefix(buffer)
    wrapped = _ANSWER_NOW_WRAPPED_LABEL_RE.match(stripped)
    if wrapped:
        return wrapped.group(1), wrapped.group("after").lstrip(_LABEL_SEPARATOR_CHARS)
    unterminated = _ANSWER_NOW_UNTERMINATED_WRAPPED_LABEL_RE.match(stripped)
    if final and unterminated:
        return unterminated.group(1), ""

    for label in _ANSWER_NOW_ALLOWED_LABELS:
        for prefix in (f"`{label}`", label):
            if stripped.startswith(prefix):
                after = stripped[len(prefix) :]
                if after:
                    if after[0] in _LABEL_SEPARATOR_CHARS:
                        return label, after.lstrip(_LABEL_SEPARATOR_CHARS)
                    continue
                if final:
                    return label, ""
            if prefix.startswith(stripped):
                return None
    if stripped.startswith("`") and _could_be_wrapped_answer_now_label(stripped):
        return None
    return None


def _normalise_user_reply(
    raw: Any,
) -> tuple[str, list[dict[str, str]] | None]:
    """将 waiter() 的回复规范化为 ``(text, answers)``。

    接受纯字符串（遗留方式 / 测试中的直接注入）或
    字典 ``{"text": str, "answers": list | None}``（支持 v2 多问题 schema 的运行时路径）。
    """
    if isinstance(raw, str):
        return raw, None
    if isinstance(raw, dict):
        text = str(raw.get("text") or "")
        answers_raw = raw.get("answers")
        if isinstance(answers_raw, list) and answers_raw:
            answers: list[dict[str, str]] = []
            for entry in answers_raw:
                if not isinstance(entry, dict):
                    continue
                qid = str(entry.get("questionId") or entry.get("id") or "").strip()
                if not qid:
                    continue
                answers.append({"questionId": qid, "text": str(entry.get("text") or "")})
            return text, answers or None
        return text, None
    return str(raw or ""), None


def _format_user_reply_body(
    text: str,
    answers: list[dict[str, str]] | None,
    ask_user_payload: dict[str, Any],
) -> str:
    """渲染模型在恢复时看到的 ``User answered:`` 正文。

    多问题回复按每个问题渲染为一行 ``- <prompt>\n  → <answer>``，
    以便模型在上下文中保留原始问题文本。跳过或空的回答显示为 ``(skipped)``。
    """
    if answers:
        prompts_by_id: dict[str, str] = {}
        for q in ask_user_payload.get("questions") or []:
            if isinstance(q, dict):
                qid = str(q.get("id") or "")
                prompts_by_id[qid] = str(q.get("prompt") or qid)
        lines = ["User answered:"]
        for entry in answers:
            qid = entry.get("questionId", "")
            prompt = prompts_by_id.get(qid) or qid or "(question)"
            value = (entry.get("text") or "").strip() or "(skipped)"
            lines.append(f"- {prompt}\n  → {value}")
        return "\n".join(lines)
    flat = (text or "").strip() or "(empty reply)"
    return f"User answered: {flat}"


def _flatten_ask_user_summary(ask_user_payload: dict[str, Any]) -> str:
    """当未连接 waiter 时，用于回退终止器发送的单行摘要。"""
    questions = ask_user_payload.get("questions") or []
    if isinstance(questions, list) and questions:
        prompts = [str(q.get("prompt") or "") for q in questions if isinstance(q, dict)]
        prompts = [p for p in prompts if p]
        if prompts:
            return " | ".join(prompts)
    # 遗留的单问题负载格式（v2 之前）。
    return str(ask_user_payload.get("question") or "")


def _read_int(cfg: Any, *, key: str, default: int) -> int:
    """从嵌套 YAML 字典中提取整数，未找到时回退到 ``default``。"""
    if isinstance(cfg, dict):
        value = cfg.get(key, default)
    else:
        value = default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 管线
# ---------------------------------------------------------------------------


class AgenticChatPipeline:
    """以单循环迭代式 LLM 循环运行聊天，支持原生工具调用。"""

    def __init__(self, language: str = "en") -> None:
        self.language = "zh" if language.lower().startswith("zh") else "en"
        self.llm_config = get_llm_config()
        self.binding = getattr(self.llm_config, "binding", None) or "openai"
        self.model = getattr(self.llm_config, "model", None)
        self.api_key = getattr(self.llm_config, "api_key", None)
        self.base_url = getattr(self.llm_config, "base_url", None)
        self.api_version = getattr(self.llm_config, "api_version", None)
        self.extra_headers = getattr(self.llm_config, "extra_headers", None) or {}
        self.reasoning_effort = getattr(self.llm_config, "reasoning_effort", None)
        self.registry = get_tool_registry()
        self._usage = UsageTracker(model=self.model)

        try:
            chat_cfg = get_chat_params()
        except Exception as exc:
            logger.warning("Failed to load chat params, using defaults: %s", exc)
            chat_cfg = {}
        try:
            self._chat_temperature = float(chat_cfg.get("temperature", 0.2))
        except (TypeError, ValueError):
            self._chat_temperature = 0.2
        # 本管线使用的两种 LLM 调用形式的 Token 预算。
        # ``responding`` 限制每次循环迭代；``answer_now`` 限制用户在流式过程中
        # 点击"立即回答"时的单次回退调用。
        self._responding_max_tokens = _read_int(
            chat_cfg.get("responding"), key="max_tokens", default=8000
        )
        self._answer_now_max_tokens = _read_int(
            chat_cfg.get("answer_now"), key="max_tokens", default=8000
        )
        self._max_iterations = _read_int(
            chat_cfg, key="max_iterations", default=DEFAULT_MAX_ITERATIONS
        )

        try:
            self._prompts: dict[str, Any] = (
                get_prompt_manager().load_prompts(
                    module_name="chat",
                    agent_name="agentic_chat",
                    language=self.language,
                )
                or {}
            )
        except Exception as exc:
            logger.warning("Failed to load agentic_chat prompts: %s", exc)
            self._prompts = {}

        self._client_config = LLMClientConfig(
            binding=self.binding,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            extra_headers=self.extra_headers or None,
            reasoning_effort=self.reasoning_effort,
        )

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------
    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        answer_now_context = self._extract_answer_now_context(context)
        if answer_now_context is not None:
            await self._run_answer_now(context, answer_now_context, stream)
            return

        enabled_tools = self._compose_enabled_tools(context)
        use_native_tools = bool(enabled_tools) and self._can_use_native_tool_calling()
        tool_schemas = (
            self._build_llm_tool_schemas(enabled_tools, context) if use_native_tools else None
        )

        system_prompt = self._build_system_prompt(enabled_tools, context)
        user_content = self._t(
            "user_template",
            default=context.user_message,
            user_message=context.user_message,
        )
        messages = self._build_messages(
            context=context,
            system_prompt=system_prompt,
            user_content=user_content,
        )
        messages, images_stripped = self._prepare_messages_with_attachments(messages, context)

        if images_stripped:
            # ``images_stripped`` 是一个临时警告，不是子追踪，因此不携带
            # call_id（前端 ``CallTracePanel`` 按 call_id 分组，否则会产生
            # 空的子追踪行）。
            await stream.thinking(
                self._t("notices.images_stripped", model=self.model or ""),
                source="chat",
                stage="responding",
                metadata={"trace_kind": "warning"},
            )

        # 通过 ``_build_openai_client`` 构建每轮的 OpenAI 客户端，以便测试可以在
        # 实例化后对该方法进行猴子补丁以注入脚本化的客户端。
        client = self._build_openai_client()
        host = _ChatLoopHost(
            pipeline=self,
            context=context,
            stream=stream,
            client=client,
        )
        # 外层 ``stage("responding")`` 仅驱动前端的 ``currentStage``
        # 指示器（"AidLearning 正在回复…"）。它不携带 call_id，因此不会
        # 生成自己的子追踪；下面的每次 LLM 迭代和每次工具调用都会分配
        # 自己的 call_id 并在 CallTracePanel 中显示为独立的子追踪。
        async with stream.stage("responding", source="chat"):
            outcome = await run_agentic_loop(
                initial_messages=messages,
                protocol=_CHAT_PROTOCOL,
                client=client,
                model=self.model,
                completion_kwargs=self._completion_kwargs(max_tokens=self._responding_max_tokens),
                binding=self.binding,
                tool_schemas=tool_schemas,
                stream=stream,
                source="chat",
                stage="responding",
                max_iterations=max(1, self._max_iterations),
                host=host,
                usage=self._usage,
                # 原生输出 <think>...</think> 而不回显 THINK 标签的推理模型
                # 会被优雅地接受为 THINK 迭代，而不是被视为协议违规
                # （协议违规会导致在模型无法实际满足的修复重试上浪费预算）。
                implicit_think_label=LABEL_THINK,
            )

        if outcome.sources:
            await stream.sources(
                outcome.sources,
                source="chat",
                stage="responding",
                metadata={"trace_kind": "sources"},
            )

        result_payload: dict[str, Any] = {
            "response": outcome.final_text,
            "iterations": outcome.iterations,
            "completed": outcome.completed,
        }
        await emit_capability_result(stream, result_payload, source="chat", usage=self._usage)

    # ------------------------------------------------------------------
    # 迭代追踪元数据
    # ------------------------------------------------------------------
    def _build_iteration_trace_metadata(
        self, iteration: int
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """为一次模型迭代分配追踪元数据。

        ``iter_meta`` 限定 THINK/TOOL/UNKNOWN 路径打开的推理子追踪；
        FINISH 从不打开它，因此在这些情况下行保持为空。``final_meta``
        是 FINISH 路径上正文内容事件的每次迭代 ID。
        """
        iter_call_id = new_call_id(f"chat-iter-{iteration}")
        iter_meta = build_trace_metadata(
            call_id=iter_call_id,
            phase="responding",
            label=self._t("labels.reasoning", default="Reasoning"),
            call_kind="llm_reasoning",
            trace_id=iter_call_id,
            trace_role="thought",
            trace_group="stage",
        )
        final_call_id = new_call_id("chat-final-response")
        final_meta = build_trace_metadata(
            call_id=final_call_id,
            phase="responding",
            label=self._t("labels.final_response", default="Final response"),
            call_kind="llm_final_response",
            trace_id=final_call_id,
            trace_role="response",
            trace_group="stage",
        )
        return iter_meta, final_meta

    # ------------------------------------------------------------------
    # 协议文案（委托给 YAML；循环主机调用这些方法）
    # ------------------------------------------------------------------
    def _protocol_retry_notice(self) -> str:
        return self._t(
            "notices.protocol_retry",
            default="The model violated the action-label protocol; retrying this iteration.",
        )

    def _protocol_repair_message(self, violation: str) -> str:
        if self.language == "zh":
            reason = {
                "missing_label": "你上一轮回复没有以必需的协议标签开头",
                "multiple_labels": "你上一轮回复在同一次输出里出现了多个协议标签",
                "tool_without_calls": "你上一轮选择了 ``TOOL``，但没有发起真实 tool_calls",
                "think_with_tools": "你上一轮选择了 ``THINK``，但同时发起了工具调用",
                "finish_with_tools": "你上一轮选择了 ``FINISH``，但同时发起了工具调用",
                "pause_with_tools": "你上一轮选择了 ``PAUSE``，但同时发起了工具调用",
            }.get(violation, "你上一轮回复不符合协议")
            default = (
                f"协议修正：{reason}，所以本轮还不能结束。下一次回复必须"
                "只选择一个动作标签，并且只在第一行写一次：``FINISH``、"
                "``TOOL``、``THINK`` 或 ``PAUSE``。标签正文里不要再出现"
                "第二个协议标签。如果内容本来就是最终答案，用 ``FINISH``；"
                "如果需要工具，用 ``TOOL`` 并在同一次回复里发起真实 "
                "tool_calls；如果只是中间思考、用户不需要看到，用 ``THINK``"
                " 且不要调用工具；如果这段思考让用户看到比藏着更有价值，"
                "用 ``PAUSE``（等于可见的 ``THINK``）且不要调用工具。"
            )
        else:
            reason = {
                "missing_label": "your previous reply did not begin with a protocol label",
                "multiple_labels": "your previous reply contained multiple protocol labels",
                "tool_without_calls": "you chose ``TOOL`` but emitted no real tool_calls",
                "think_with_tools": "you chose ``THINK`` while also emitting tool_calls",
                "finish_with_tools": "you chose ``FINISH`` while also emitting tool_calls",
                "pause_with_tools": "you chose ``PAUSE`` while also emitting tool_calls",
            }.get(violation, "your previous reply violated the protocol")
            default = (
                f"Protocol correction: {reason}, so the turn is not complete. "
                "Your next reply must choose exactly one action label, written "
                "once on the first line only: ``FINISH``, ``TOOL``, ``THINK``, "
                "or ``PAUSE``. Do not include a second protocol label anywhere "
                "in the body. If the draft was the final answer, use "
                "``FINISH``. If tools are needed, use ``TOOL`` and emit real "
                "tool_calls in that same reply. If this is private intermediate "
                "reasoning the user doesn't need to see, use ``THINK`` and "
                "do not call tools. If your reasoning is worth showing to the "
                "user, use ``PAUSE`` (same as ``THINK`` plus visibility) and "
                "do not call tools."
            )
        return self._t(f"protocol.{violation}", default=default)

    def _force_finish_message(self) -> str:
        if self.language == "zh":
            default = (
                "迭代预算已用完。现在必须给出面向用户的最终答复：第一行必须是 "
                "``FINISH``，不要再调用工具，也不要再用 ``THINK`` 或 ``PAUSE``。"
                "如果信息仍不完整，请简短说明不确定性，但仍给出当前最有用的答案。"
            )
        else:
            default = (
                "The iteration budget is exhausted. You must now produce the "
                "user-facing final answer: the first line must be ``FINISH``. "
                "Do not call tools and do not use ``THINK`` or ``PAUSE``. If "
                "information is still incomplete, state the uncertainty briefly "
                "while giving the most useful answer possible."
            )
        return self._t("protocol.force_finish", default=default)

    def _force_finish_repair_message(self, violation: str) -> str:
        if self.language == "zh":
            reason = "没有使用 ``FINISH``"
            if violation == "multiple_labels":
                reason = "在最终化回复里混用了多个标签"
            elif violation == "tool_without_calls":
                reason = "仍然选择了 ``TOOL``"
            elif violation == "think_with_tools":
                reason = "用 ``THINK`` 的同时调用了工具"
            elif violation == "finish_with_tools":
                reason = "用 ``FINISH`` 的同时调用了工具"
            elif violation == "pause_with_tools":
                reason = "用 ``PAUSE`` 的同时调用了工具"
            default = (
                f"最终化协议修正：上一轮{reason}。现在只能输出一个最终答案："
                "第一行写 ``FINISH``，后面直接给用户答案。不要写 ``THINK``、"
                "``PAUSE``，不要写 ``TOOL``，不要调用任何工具，也不要在正文里"
                "再次出现协议标签。"
            )
        else:
            reason = "did not use ``FINISH``"
            if violation == "multiple_labels":
                reason = "mixed multiple labels in the finalization reply"
            elif violation == "tool_without_calls":
                reason = "still chose ``TOOL``"
            elif violation == "think_with_tools":
                reason = "used ``THINK`` while calling tools"
            elif violation == "finish_with_tools":
                reason = "used ``FINISH`` while calling tools"
            elif violation == "pause_with_tools":
                reason = "used ``PAUSE`` while calling tools"
            default = (
                f"Finalization protocol correction: the previous reply {reason}. "
                "Now output only a final answer: first line ``FINISH``, then the "
                "user-facing answer. Do not write ``THINK``, ``PAUSE``, or "
                "``TOOL``, do not call tools, and do not include another "
                "protocol label in the body."
            )
        return self._t("protocol.force_finish_repair", default=default)

    def _protocol_fallback_final_text(self) -> str:
        if self.language == "zh":
            default = (
                "我已经达到本轮迭代上限，但模型没有按 ``FINISH`` 协议产出合格的"
                "最终回答。请重试一次，或把问题范围收窄；我会从已有上下文继续。"
            )
        else:
            default = (
                "I reached the iteration limit, but the model did not produce "
                "a valid ``FINISH`` response. Please retry or narrow the request; "
                "I can continue from the existing context."
            )
        return self._t("protocol.fallback_final", default=default)

    # ------------------------------------------------------------------
    # 强制完成（max-iter 耗尽时的主机钩子）
    # ------------------------------------------------------------------
    async def _run_forced_finish(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        stream: StreamBus,
        start_iteration: int,
    ) -> tuple[str, bool, int]:
        """要求模型生成一次无工具的 ``FINISH`` 回复，在协议违规时重试。
        返回 ``(final_text, completed, calls)``。"""
        calls = 0
        messages.append({"role": "user", "content": self._force_finish_message()})
        await stream.progress(
            self._t("notices.max_iterations_reached"),
            source="chat",
            stage="responding",
            metadata={"trace_kind": "warning"},
        )
        for attempt in range(FINALIZATION_REPAIR_ATTEMPTS):
            await self._guard_context_window(messages, stream)
            iter_meta, final_meta = self._build_iteration_trace_metadata(start_iteration + attempt)
            step = await run_labeled_step(
                client=client,
                model=self.model,
                messages=messages,
                completion_kwargs=self._completion_kwargs(max_tokens=self._responding_max_tokens),
                tool_schemas=None,
                allowed_labels=(LABEL_FINISH,),
                final_labels=frozenset({LABEL_FINISH}),
                tool_label=None,
                stream=stream,
                source="chat",
                stage="responding",
                iter_meta=iter_meta,
                binding=self.binding,
                usage=self._usage,
            )
            calls += 1

            violation = _classify_forced_finish_violation(step)
            if step.label == LABEL_FINISH and not violation:
                await self._emit_final_text(stream, step.text, final_meta)
                return step.text, True, calls

            final_violation = violation or "final_missing_finish"
            await stream.progress(
                self._t(
                    "notices.final_protocol_failed",
                    default=(
                        "The model still did not produce a valid FINISH reply "
                        "after the finalization prompt."
                    ),
                ),
                source="chat",
                stage="responding",
                metadata={
                    "trace_kind": "warning",
                    "protocol_violation": final_violation,
                    "finalization_attempt": attempt + 1,
                },
            )
            self._append_assistant_context(messages, step.text)
            messages.append(
                {
                    "role": "user",
                    "content": self._force_finish_repair_message(final_violation),
                }
            )

        fallback = self._protocol_fallback_final_text()
        await self._emit_protocol_fallback_final_response(stream, fallback)
        return fallback, False, calls

    @staticmethod
    def _append_assistant_context(
        messages: list[dict[str, Any]],
        text: str,
    ) -> None:
        clipped = str(text or "").strip()
        if not clipped:
            return
        if len(clipped) > 500:
            clipped = clipped[:500].rstrip() + "\n...[truncated]"
        messages.append({"role": "assistant", "content": clipped})

    # ------------------------------------------------------------------
    # 发送辅助方法（主机钩子）
    # ------------------------------------------------------------------
    async def _emit_final_text(
        self,
        stream: StreamBus,
        text: str,
        final_meta: dict[str, Any],
    ) -> None:
        if not text:
            return
        await stream.content(
            text,
            source="chat",
            stage="responding",
            metadata=merge_trace_metadata(final_meta, {"trace_kind": "llm_output"}),
        )

    async def _emit_terminator_final_response(
        self,
        stream: StreamBus,
        payload: dict[str, Any] | None,
    ) -> None:
        """发送一个 ``content(call_kind=llm_final_response)`` 事件，
        包含终止工具的内容及其 UI 元数据。

        通用性足以支持未来的任何 ``terminate_turn`` 工具：工具自身的
        ``ToolResult.metadata`` 附带在 ``tool_metadata`` 槽位上，以便
        前端可以据此进行分派（例如通过 ``tool_metadata.ask_user``
        渲染 ``ask_user`` 的选项卡片）。
        """
        if not payload:
            return
        content = str(payload.get("content") or "").strip()
        tool_metadata = payload.get("metadata") or {}
        if not content:
            return
        final_call_id = new_call_id("chat-final-response")
        final_meta = build_trace_metadata(
            call_id=final_call_id,
            phase="responding",
            label=self._t("labels.final_response", default="Final response"),
            call_kind="llm_final_response",
            trace_id=final_call_id,
            trace_role="response",
            trace_group="stage",
            terminator_tool=str(payload.get("tool_name") or ""),
        )
        merged_metadata: dict[str, Any] = {"trace_kind": "llm_output"}
        if isinstance(tool_metadata, dict) and tool_metadata:
            merged_metadata["tool_metadata"] = dict(tool_metadata)
        await stream.content(
            content,
            source="chat",
            stage="responding",
            metadata=merge_trace_metadata(final_meta, merged_metadata),
        )

    async def _emit_protocol_fallback_final_response(
        self,
        stream: StreamBus,
        content: str,
    ) -> None:
        final_meta = build_trace_metadata(
            call_id=new_call_id("chat-final-response"),
            phase="responding",
            label=self._t("labels.final_response", default="Final response"),
            call_kind="llm_final_response",
            trace_id="chat-final-response",
            trace_role="response",
            trace_group="stage",
            protocol_fallback=True,
        )
        await stream.content(
            content,
            source="chat",
            stage="responding",
            metadata=merge_trace_metadata(final_meta, {"trace_kind": "llm_output"}),
        )

    @staticmethod
    def _assistant_message_with_tool_calls(
        content: str,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc.get("arguments") or "{}",
                    },
                }
                for tc in tool_calls
            ],
        }

    # ------------------------------------------------------------------
    # 工具调度（对原语的薄封装 — 保留用于测试）
    # ------------------------------------------------------------------
    async def _execute_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        *,
        stream: StreamBus | None = None,
        retrieve_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """运行单个工具，附带 chat 风格的检索进度事件。

        直接调用方（尤其是测试代码）使用此方法驱动单个工具，
        而不经过并行调度器。
        """
        from aidlearning.core.agentic import execute_tool_call

        if stream is None:
            # 没有 stream 也意味着没有检索追踪；使用虚拟 bus 使原语的
            # stream 调用变为空操作。
            stream = StreamBus()
        return await execute_tool_call(
            registry=self.registry,
            tool_name=tool_name,
            tool_args=tool_args,
            stream=stream,
            source="chat",
            stage="acting",
            retrieve_meta=retrieve_meta,
            empty_tool_result_message=self._t("notices.empty_tool_result"),
            start_retrieval_message=self._t(
                "notices.start_retrieval", default="Starting retrieval"
            ),
            retrieve_label=self._t("labels.retrieve", default="Retrieve"),
            unknown_error_message_factory=lambda tn: self._t(
                "notices.tool_unknown_error",
                tool=tn,
                default=f"An unknown error occurred while executing {tn}.",
            ),
        )

    async def _dispatch_tool_calls(
        self,
        *,
        tool_calls: list[dict[str, Any]],
        context: UnifiedContext,
        stream: StreamBus,
        iteration_index: int,
    ) -> DispatchOutcome:
        """在 chat 专属标签、参数增强器和检索追踪元数据下调度本次迭代的工具调用。"""
        too_many = None
        if len(tool_calls) > MAX_PARALLEL_TOOL_CALLS:
            too_many = self._t(
                "notices.too_many_tool_calls",
                requested=len(tool_calls),
                limit=MAX_PARALLEL_TOOL_CALLS,
            )
        return await dispatch_tool_calls(
            tool_calls=tool_calls,
            context=context,
            stream=stream,
            source="chat",
            stage="acting",
            iteration_index=iteration_index,
            registry=self.registry,
            kwarg_augmenter=self._augment_tool_kwargs,
            retrieve_meta_factory=lambda meta, tn, ta: self._retrieve_trace_metadata(
                meta, context=context, tool_name=tn, tool_args=ta
            ),
            tool_call_label=self._t("labels.tool_call", default="Tool call"),
            retrieve_label=self._t("labels.retrieve", default="Retrieve"),
            empty_tool_result_message=self._t("notices.empty_tool_result"),
            start_retrieval_message=self._t(
                "notices.start_retrieval", default="Starting retrieval"
            ),
            too_many_tool_calls_message=too_many,
            unknown_error_message_factory=lambda tn: self._t(
                "notices.tool_unknown_error",
                tool=tn,
                default=f"An unknown error occurred while executing {tn}.",
            ),
            trace_id_prefix="chat-iter",
        )

    # ------------------------------------------------------------------
    # ``ask_user`` 暂停 / 恢复
    # ------------------------------------------------------------------
    async def _await_user_reply_and_resolve(
        self,
        *,
        context: UnifiedContext,
        stream: StreamBus,
        dispatch: DispatchOutcome,
    ) -> bool:
        """在 ``ask_user`` 调用时暂停循环并等待回复。

        当用户回复已替换到匹配的 ``role=tool`` 消息中且循环可以恢复时
        返回 ``True``。如果运行时未连接回复队列则返回 ``False``
        （此时管线回退到发送终止器最终响应，镜像遗留行为以使管线的
        直接单元测试仍然有效）。

        当运行时取消轮次任务时，``asyncio.CancelledError`` 会从
        ``waiter()`` 向上传播 —— 由运行时自身的取消处理器捕获，
        该处理器会发送正确的 ERROR + DONE 事件。我们故意不在此处捕获它。
        """
        ask_user = (dispatch.pause_payload or {}).get("ask_user") or {}
        waiter = context.metadata.get("wait_for_user_reply")
        if not callable(waiter):
            logger.warning(
                "ask_user paused the loop but no wait_for_user_reply "
                "callable is wired on the context; emitting terminator."
            )
            await self._emit_terminator_final_response(
                stream,
                {
                    "tool_name": (dispatch.pause_payload or {}).get("tool_name", "ask_user"),
                    "content": _flatten_ask_user_summary(ask_user),
                    "metadata": {"ask_user": ask_user},
                },
            )
            return False

        raw_reply = await waiter()
        if raw_reply is None:
            return False

        # 规范化：调用方可能传入纯字符串（旧版测试 / 直接注入）或
        # 结构化字典（运行时 / v2 路径）。
        reply_text, answers = _normalise_user_reply(raw_reply)
        body_text = _format_user_reply_body(reply_text, answers, ask_user)

        # 就地修改暂停工具匹配的 ``role=tool`` 消息。
        # ``dispatch.tool_messages`` 与我们已扩展到 ``messages`` 上的条目
        # 共享对象标识，因此此更改对下一次 LLM 调用可见，无需重新遍历列表。
        #
        # 正文故意是指令性的：一个简单的 "User answered: X" 被某些模型
        # 误解为轮次结束。在模型决定下一步操作的确切对话位置明确写出
        # "你必须继续 / 不要在单行确认后停止"可以保持 ask_user 跨循环存活。
        resumption_directive = (
            f"{body_text}\n\n"
            "[ask_user resolved. The turn is NOT over. Use these answers "
            "to address the user's ORIGINAL request — call more tools "
            "if you need them, then close with a substantive ``FINISH`` "
            "reply. A short acknowledgment of the answer is NOT an "
            "acceptable final response.]"
        )
        for tm in dispatch.tool_messages:
            if tm.get("tool_call_id") == dispatch.pause_tool_call_id:
                tm["content"] = resumption_directive
                break

        progress_meta: dict[str, Any] = {
            "trace_kind": "user_reply",
            "ask_user_resolved": True,
            "ask_user_tool_call_id": dispatch.pause_tool_call_id,
            "reply_preview": (reply_text or "")[:200],
        }
        if answers:
            progress_meta["answers"] = list(answers)
        await stream.progress(
            "",
            source="chat",
            stage="responding",
            metadata=progress_meta,
        )
        return True

    # ------------------------------------------------------------------
    # 立即回答：取消流式生成并从已生成内容中产出最终答案。
    # 单次 LLM 调用，工具禁用，部分草稿作为假助手消息注入以便模型自然继续。
    # ------------------------------------------------------------------
    async def _run_answer_now(
        self,
        context: UnifiedContext,
        answer_now_context: dict[str, Any],
        stream: StreamBus,
    ) -> None:
        partial_response = str(answer_now_context.get("partial_response") or "").strip()
        original_user_message = str(
            answer_now_context.get("original_user_message") or context.user_message
        ).strip()

        trace_meta = build_trace_metadata(
            call_id=new_call_id("chat-answer-now"),
            phase="responding",
            label=self._t("labels.answer_now", default="Answer now"),
            call_kind="llm_final_response",
            trace_id="chat-answer-now",
            trace_role="response",
            trace_group="stage",
        )
        async with stream.stage("responding", source="chat", metadata=trace_meta):
            await stream.progress(
                trace_meta["label"],
                source="chat",
                stage="responding",
                metadata=merge_trace_metadata(
                    trace_meta, {"trace_kind": "call_status", "call_state": "running"}
                ),
            )

            system_prompt = self._build_system_prompt(enabled_tools=[], context=context)
            messages = self._build_messages(
                context=context,
                system_prompt=system_prompt,
                user_content=original_user_message,
            )
            messages, _ = self._prepare_messages_with_attachments(messages, context)
            if partial_response:
                messages.append({"role": "assistant", "content": partial_response})
            messages.append(
                {"role": "user", "content": self._t("answer_now.user", default="Finalize now.")}
            )

            chunks: list[str] = []
            label_buf = ""
            label_resolved = False

            async def _emit_answer_chunk(text: str) -> None:
                if not text:
                    return
                chunks.append(text)
                await stream.content(
                    text,
                    source="chat",
                    stage="responding",
                    metadata=merge_trace_metadata(trace_meta, {"trace_kind": "llm_chunk"}),
                )

            async for chunk in self._stream_messages(
                messages, max_tokens=self._answer_now_max_tokens
            ):
                if not chunk:
                    continue
                if not label_resolved:
                    label_buf += chunk
                    parsed = _classify_answer_now_label(label_buf)
                    if parsed is not None:
                        # 立即回答复用正常的聊天系统提示词，因此许多模型会
                        # 正确地以 ``FINISH`` 开头。在到达 UI 之前剥离该协议标签。
                        _label, after_label = parsed
                        label_resolved = True
                        label_buf = ""
                        await _emit_answer_chunk(after_label)
                    elif len(label_buf) > LABEL_PROBE_MAX_CHARS:
                        label_resolved = True
                        buffered = label_buf
                        label_buf = ""
                        await _emit_answer_chunk(buffered)
                    continue
                await _emit_answer_chunk(chunk)
            if not label_resolved and label_buf:
                parsed = _classify_answer_now_label(label_buf, final=True)
                if parsed is not None:
                    _label, after_label = parsed
                    await _emit_answer_chunk(after_label)
                else:
                    await _emit_answer_chunk(label_buf)
            await stream.progress(
                "",
                source="chat",
                stage="responding",
                metadata=merge_trace_metadata(
                    trace_meta, {"trace_kind": "call_status", "call_state": "complete"}
                ),
            )
            final_text = clean_thinking_tags("".join(chunks), self.binding, self.model)

        result_payload: dict[str, Any] = {
            "response": final_text,
            "answer_now": True,
            "source_trace": trace_meta.get("label", "Answer now"),
        }
        await emit_capability_result(stream, result_payload, source="chat", usage=self._usage)

    # ------------------------------------------------------------------
    # 每次迭代标记（告知模型其在预算中的位置）
    # ------------------------------------------------------------------
    def _append_iteration_marker(
        self,
        *,
        messages: list[dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> None:
        """附加一个 ``role=user`` 系统风格的注释，宣告当前迭代，
        以便 LLM 可以自行调节节奏。

        文案由 YAML 驱动（``iteration_marker``）。迭代在内部从 0 开始；
        标记显示 ``current = iteration + 1`` 以匹配人类计数。早期迭代的
        标记保留在历史中，以便模型也能看到它在整个轮次中如何消耗预算。
        """
        current = iteration + 1
        marker = self._t(
            "iteration_marker",
            default=(
                f"[System note] You are at iteration {current}/{max_iterations} "
                "of this turn. Once the maximum is reached, the next reply is "
                "forced to be ``FINISH``."
            ),
            current=current,
            max=max_iterations,
        )
        marker = (marker or "").strip()
        if not marker:
            return
        messages.append({"role": "user", "content": marker})

    # ------------------------------------------------------------------
    # 轮内上下文窗口守卫
    # ------------------------------------------------------------------
    async def _guard_context_window(
        self,
        messages: list[dict[str, Any]],
        stream: StreamBus,
    ) -> None:
        """将最旧的工具结果内容替换为截断标记，直到总 token 数适合
        模型有效窗口的 ``CONTEXT_WINDOW_GUARD_RATIO``。从不触及系统消息
        或原始用户消息 —— 仅处理 ``role == 'tool'`` 的负载。
        跨轮历史压缩由 ``ContextBuilder`` 单独处理。
        """
        try:
            window = resolve_effective_context_window(
                context_window=getattr(self.llm_config, "context_window", None),
                model=str(self.model or ""),
                max_tokens=getattr(self.llm_config, "max_tokens", None),
            )
        except Exception:
            return
        if not window or window <= 0:
            return
        budget = int(window * CONTEXT_WINDOW_GUARD_RATIO)
        if self._estimate_messages_tokens(messages) <= budget:
            return
        snipped = False
        for msg in messages:
            if msg.get("role") != "tool":
                continue
            current_content = msg.get("content")
            if current_content == TOOL_RESULT_SNIP_MARKER:
                continue
            msg["content"] = TOOL_RESULT_SNIP_MARKER
            snipped = True
            if self._estimate_messages_tokens(messages) <= budget:
                break
        if snipped:
            await stream.progress(
                self._t("notices.context_window_guard"),
                source="chat",
                stage="responding",
                metadata={"trace_kind": "warning"},
            )

    @staticmethod
    def _estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
        # 本地导入以打破 agents.chat ↔ services.session 的导入循环
        # （context_builder 拉取 agents.base_agent，后者在包初始化期间
        # 重新进入此模块）。
        from aidlearning.memory.short_term.context_builder import count_tokens

        total = 0
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                total += count_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += count_tokens(str(part.get("text") or ""))
        return total

    # ------------------------------------------------------------------
    # 系统提示词 + 消息构建
    # ------------------------------------------------------------------
    def _build_system_prompt(
        self,
        enabled_tools: list[str],
        context: UnifiedContext,
    ) -> str:
        # ``list_with_usage`` 为每个工具渲染一个项目符号，包括工具的
        # ``when_to_use`` 和 ``input_format`` —— 从 ``aidlearning/tools/prompting/hints/{lang}/{tool}.yaml``
        # 下的每工具 YAML 中获取。这是每工具指导进入聊天人设提示词的唯一位置：
        # 禁用的工具不贡献任何内容，因此模型永远不会看到它无法调用的工具的说明。
        tool_list = self.registry.build_prompt_text(
            enabled_tools,
            format="list_with_usage",
            language=self.language,
        )
        system = self._t(
            "system",
            tool_list=tool_list or self._fallback_empty_tool_list(),
            kb_note=self._kb_system_note(context),
        )
        return append_language_directive(system, self.language)

    def _build_messages(
        self,
        *,
        context: UnifiedContext,
        system_prompt: str,
        user_content: str,
    ) -> list[dict[str, Any]]:
        """组装 ``[system] + history + user``。

        ``memory_context``、``skills_context``、``source_manifest`` 和
        notebook 清单作为单独的 ``---`` 分隔的部分附加在主系统提示词之后，
        以便当只有清单尾部在轮次之间变化时提示词缓存仍然有效。
        """
        system_parts = [system_prompt]
        if context.memory_context:
            system_parts.append(context.memory_context)
        if context.skills_context:
            system_parts.append(context.skills_context)
        if context.source_manifest:
            system_parts.append(context.source_manifest)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "\n\n---\n\n".join(system_parts)}
        ]
        for item in context.conversation_history:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, (str, list)):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_content})
        return messages

    def _prepare_messages_with_attachments(
        self,
        messages: list[dict[str, Any]],
        context: UnifiedContext,
    ) -> tuple[list[dict[str, Any]], bool]:
        mm_result = prepare_multimodal_messages(
            messages,
            context.attachments,
            binding=self.binding,
            model=self.model,
        )
        return mm_result.messages, mm_result.images_stripped

    # ------------------------------------------------------------------
    # 工具选择 + 模式构建
    # ------------------------------------------------------------------
    def _compose_enabled_tools(self, context: UnifiedContext) -> list[str]:
        """通过共享组合策略解析本轮的工具集。

        自动挂载标志根据 chat 自身的上下文解析：

        - ``has_kb`` — 当且仅当用户附加了任何 KB。
        - ``has_sources`` — 当且仅当本轮有非空的源索引
          （笔记本 / 书籍 / 历史 / 问题 / 附件）。
        - ``has_memory`` — 当且仅当活跃用户有记忆内容。
        """
        return compose_enabled_tools(
            registry=self.registry,
            requested_tools=context.enabled_tools,
            optional_whitelist=CHAT_OPTIONAL_TOOLS,
            mount_flags=ToolMountFlags(
                has_kb=bool(self._selected_kbs(context)),
                has_sources=bool(self._source_index(context)),
                has_memory=user_has_memory(),
            ),
        )

    def _build_llm_tool_schemas(
        self,
        enabled_tools: list[str],
        context: UnifiedContext,
    ) -> list[dict[str, Any]]:
        """返回每轮的 OpenAI 工具 schema，附带每工具约束。

        - ``rag.kb_name`` 限制为已附加的 KB 的枚举。
        - ``read_source.source_id`` 限制为已附加源 ID 的枚举
          （这使 LLM 不太可能幻觉出 ID，并允许 OpenAI SDK 在客户端验证调用）。
        - ``save_to_notebook.notebook_id`` 限制为活跃用户的实际笔记本 ID
          —— 镜像人类在"保存到笔记本"对话框中看到的下拉菜单，使模型
          从字面上无法保存到用户没有的笔记本。
        """
        schemas = self.registry.build_openai_schemas(enabled_tools)
        kb_choices = self._selected_kbs(context)
        source_ids = sorted((self._source_index(context) or {}).keys())
        notebook_choices = self._notebook_choices()
        for schema in schemas:
            function = schema.get("function") if isinstance(schema, dict) else None
            if not isinstance(function, dict):
                continue
            parameters = function.get("parameters")
            if not isinstance(parameters, dict):
                continue
            properties = parameters.get("properties") or {}
            if function.get("name") == "rag" and isinstance(properties, dict):
                query_schema = properties.get("query")
                if isinstance(query_schema, dict):
                    query_schema.setdefault("minLength", 1)
                kb_schema = properties.get("kb_name")
                if isinstance(kb_schema, dict):
                    kb_schema["enum"] = kb_choices
            if function.get("name") == "read_source" and isinstance(properties, dict):
                sid_schema = properties.get("source_id")
                if isinstance(sid_schema, dict) and source_ids:
                    sid_schema["enum"] = source_ids
            parameters["additionalProperties"] = False
        return schemas

    @staticmethod
    def _extract_answer_now_context(context: UnifiedContext) -> dict[str, Any] | None:
        from aidlearning.capabilities._answer_now import extract_answer_now_context

        return extract_answer_now_context(context)

    # ------------------------------------------------------------------
    # 工具参数增强
    # ------------------------------------------------------------------
    def _augment_tool_kwargs(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: UnifiedContext,
    ) -> dict[str, Any]:
        from aidlearning.services.path_service import get_path_service

        kwargs = dict(args)
        turn_id = str(context.metadata.get("turn_id", "") or "").strip()
        task_dir = None
        if turn_id:
            task_dir = get_path_service().get_task_workspace("chat", turn_id)
        if tool_name == "rag":
            kwargs.setdefault("mode", "hybrid")
        elif tool_name == "code_execution":
            kwargs.setdefault("intent", context.user_message)
            kwargs.setdefault("timeout", 30)
            kwargs.setdefault("feature", "chat")
            kwargs.setdefault("session_id", context.session_id)
            kwargs.setdefault("turn_id", turn_id)
            if task_dir is not None:
                kwargs.setdefault("workspace_dir", str(task_dir / "code_runs"))
        elif tool_name in {"reason", "brainstorm"}:
            kwargs.setdefault("context", context.user_message)
        elif tool_name == "paper_search":
            kwargs.setdefault("max_results", 3)
            kwargs.setdefault("years_limit", 3)
            kwargs.setdefault("sort_by", "relevance")
        elif tool_name == "web_search":
            kwargs.setdefault("query", context.user_message)
            if task_dir is not None:
                kwargs.setdefault("output_dir", str(task_dir / "web_search"))
        elif tool_name == "read_source":
            # ReadSourceTool 从此每轮映射而非共享状态中读取，因此每轮的源保持隔离。
            kwargs["source_index"] = self._source_index(context)
        return kwargs

    # ------------------------------------------------------------------
    # 工具 / KB 元数据辅助
    # ------------------------------------------------------------------
    def _retrieve_trace_metadata(
        self,
        tool_meta: dict[str, Any],
        *,
        context: UnifiedContext,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> dict[str, Any] | None:
        """``rag`` 进度事件的检索风格元数据。

        每次 rag 调用已有自己的 ``tool_meta``（含自己的 ``call_id``）；
        我们派生一个"检索"变体，使工具内进度事件（提供商选择、分块检索等）
        保持附加在同一子追踪上，但以 ``trace_role=retrieve`` 显示以获取
        折叠箭头图标。对于非 rag 工具，我们返回 ``None`` 以使执行器
        跳过检索进度表面。
        """
        if tool_name != "rag":
            return None
        _ = context  # context 暂时未使用；保留以与 solve 的变体保持一致
        return derive_trace_metadata(
            tool_meta,
            label=self._t("labels.retrieve", default="Retrieve"),
            call_kind="rag_retrieval",
            trace_role="retrieve",
            trace_group="retrieve",
            query=str(tool_args.get("query", "") or ""),
        )

    @staticmethod
    def _selected_kbs(context: UnifiedContext) -> list[str]:
        return [str(kb).strip() for kb in context.knowledge_bases if str(kb).strip()]

    @staticmethod
    def _source_index(context: UnifiedContext) -> dict[str, str]:
        idx = context.metadata.get("source_index")
        if isinstance(idx, dict) and idx:
            return idx
        return {}

    def _kb_system_note(self, context: UnifiedContext) -> str:
        kbs = self._selected_kbs(context)
        if not kbs:
            return ""
        joined = ", ".join(kbs)
        if self.language == "zh":
            return f"用户已挂载知识库：{joined}。调用 rag 时，kb_name 必须从其中选一个。"
        return (
            f"Attached knowledge bases: {joined}. When calling rag, kb_name must "
            "be one of these names."
        )

    def _fallback_empty_tool_list(self) -> str:
        return "- 无" if self.language == "zh" else "- none"

    # ------------------------------------------------------------------
    # LLM 调用辅助
    # ------------------------------------------------------------------
    async def _stream_messages(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ):
        """流式调用一次无工具的 LLM。用于立即回答。"""
        output_chars = 0
        async for chunk in llm_stream(
            prompt="",
            system_prompt="",
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            binding=self.binding,
            messages=messages,
            extra_headers=self.extra_headers or None,
            **self._completion_kwargs(max_tokens=max_tokens),
        ):
            output_chars += len(chunk)
            yield chunk
        input_chars = sum(len(str(m.get("content", ""))) for m in messages)
        self._usage.add_estimated(input_chars=input_chars, output_chars=output_chars)

    def _build_openai_client(self):
        """从管线的 LLM 配置构建 OpenAI/Azure 异步客户端。

        保留为方法（而非始终复用 ``self._client``），以便任何下游测试或
        未来的调用方在需要每次调用使用新客户端时仍可获取，而无需触碰模块级状态。
        """
        return build_openai_client(self._client_config)

    def _completion_kwargs(self, max_tokens: int) -> dict[str, Any]:
        return build_completion_kwargs(
            temperature=self._chat_temperature,
            model=self.model,
            max_tokens=max_tokens,
            binding=self.binding,
            reasoning_effort=self.reasoning_effort,
        )

    def _can_use_native_tool_calling(self) -> bool:
        return can_use_native_tool_calling(binding=self.binding, model=self.model)

    # ------------------------------------------------------------------
    # YAML 提示词查找
    # ------------------------------------------------------------------
    def _t(self, key: str, default: str = "", **kwargs: Any) -> str:
        """通过点分键查找 YAML 加载的提示词。

        缺失时返回 ``default``。当提供 ``kwargs`` 时通过 ``str.format`` 渲染；
        缺失的占位符使模板保持未渲染状态，而不是使管线崩溃。
        """
        value: Any = self._prompts
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        if not isinstance(value, str):
            return default
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return value
        return value


# ---------------------------------------------------------------------------
# 循环主机适配器
# ---------------------------------------------------------------------------


class _ChatLoopHost:
    """将聊天管线 + 当前轮次的 context/stream 绑定为单个对象，
    通用循环原语可以回调到该对象。

    所有 chat 专属行为 —— 追踪元数据、工具调度、暂停/终止、
    最终发送、强制完成 —— 都作为 :class:`AgenticChatPipeline` 的方法存在；
    此适配器仅将 :class:`~aidlearning.core.agentic.LoopHost` 协议调用路由到它们。
    """

    def __init__(
        self,
        *,
        pipeline: AgenticChatPipeline,
        context: UnifiedContext,
        stream: StreamBus,
        client: Any,
    ) -> None:
        self._pipeline = pipeline
        self._context = context
        self._stream = stream
        self._client = client

    async def guard_context_window(self, messages: list[dict[str, Any]]) -> None:
        await self._pipeline._guard_context_window(messages, self._stream)

    async def before_iteration(
        self,
        *,
        messages: list[dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> None:
        """注入每次迭代计数器以便模型自行调节节奏。"""
        self._pipeline._append_iteration_marker(
            messages=messages,
            iteration=iteration,
            max_iterations=max_iterations,
        )

    def build_iteration_trace_meta(self, iteration: int) -> tuple[dict[str, Any], dict[str, Any]]:
        return self._pipeline._build_iteration_trace_metadata(iteration)

    async def dispatch_tools(
        self,
        *,
        iteration: int,
        tool_calls: list[dict[str, Any]],
    ) -> DispatchOutcome:
        return await self._pipeline._dispatch_tool_calls(
            tool_calls=tool_calls,
            context=self._context,
            stream=self._stream,
            iteration_index=iteration,
        )

    async def resolve_pause(self, dispatch: DispatchOutcome) -> bool:
        return await self._pipeline._await_user_reply_and_resolve(
            context=self._context,
            stream=self._stream,
            dispatch=dispatch,
        )

    async def emit_terminator(self, payload: dict[str, Any] | None) -> None:
        await self._pipeline._emit_terminator_final_response(self._stream, payload)

    async def emit_final(self, text: str, final_meta: dict[str, Any]) -> None:
        await self._pipeline._emit_final_text(self._stream, text, final_meta)

    def assistant_message_with_tool_calls(
        self,
        *,
        content: str,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._pipeline._assistant_message_with_tool_calls(content, tool_calls)

    def protocol_retry_notice(self) -> str:
        return self._pipeline._protocol_retry_notice()

    def protocol_repair_message(self, violation: str) -> str:
        return self._pipeline._protocol_repair_message(violation)

    async def force_finalize(
        self,
        *,
        messages: list[dict[str, Any]],
        start_iteration: int,
    ) -> tuple[str, bool, int]:
        return await self._pipeline._run_forced_finish(
            client=self._client,
            messages=messages,
            stream=self._stream,
            start_iteration=start_iteration,
        )


# ---------------------------------------------------------------------------
# 强制完成协议验证（chat 本地，因为违规键词汇镜像 chat 的修复文案键）。
# ---------------------------------------------------------------------------


def _classify_forced_finish_violation(step: LabeledStepResult) -> str | None:
    """用于仅 FINISH 完成循环的轻量级违规分类器。
    当 ``allowed_labels=(FINISH,)`` 且 ``tool_schemas=None`` 时，
    唯一可能的违规是缺失标签 / 行内重复标签。
    """
    if step.label == LABEL_UNKNOWN:
        return "missing_label"
    if find_inline_labels(
        step.text,
        allowed_labels=(LABEL_FINISH, LABEL_TOOL, LABEL_THINK, LABEL_PAUSE),
    ):
        return "multiple_labels"
    return None
