"""
即时应答辅助模块
==================

为通用"即时应答"中断提供的各能力快速通道工具。

每个能力决定其快速通道输出的内容（文本回答、测验 JSON、manim 代码等）。
本模块提供共享的基础设施：

* :func:`extract_answer_now_context` — 解析并验证前端随取消轮次一起打包的负载。
* :func:`format_trace_summary` — 将捕获的流事件渲染为紧凑的、适合提示词的摘要，
  供 LLM 一次性读取。
* :func:`stream_synthesis` — 围绕 LLM 服务的轻量异步生成器封装，
  在产出文本块的同时将其推送到 StreamBus。
* :func:`make_skip_notice` — 国际化感知的通知，附加在快速通道输出的前/后，
  让用户了解哪些阶段被跳过。

编排器不再将 ``answer_now`` 重路由到 ``chat``；而是每个支持该功能的能力
在 ``run()`` 入口处检查该负载并分派到自己的即时应答路径。``chat`` 保留
其原有的综合行为。``deep_solve`` / ``deep_question`` / ``deep_research``
故意不暴露即时应答 — 它们的 UI 会屏蔽该按钮，因此本模块不会为它们调用。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from aidlearning.core.context import UnifiedContext
from aidlearning.core.stream_bus import StreamBus
from aidlearning.core.trace import build_trace_metadata, merge_trace_metadata, new_call_id
from aidlearning.services.config import get_chat_params
from aidlearning.services.llm import (
    clean_thinking_tags,
    get_llm_config,
    get_token_limit_kwargs,
    supports_response_format,
)
from aidlearning.services.llm import (
    stream as llm_stream,
)
from aidlearning.services.prompt.manager import get_prompt_manager

# 单事件内容上限。追踪记录可能无限增长（尤其是包含大量工具调用的
# deep_research / deep_solve），因此我们截断每个条目而非整个记录 —
# 这在牺牲每步细节的同时保留了事件覆盖。
_MAX_EVENT_SNIPPET = 800
# 追踪摘要总上限。远超此值会开始占用小上下文模型的回答预算。
_MAX_TRACE_TOTAL = 6000


def extract_answer_now_context(context: UnifiedContext) -> dict[str, Any] | None:
    """
    返回已验证的 ``answer_now_context`` 负载，若无效则返回 ``None``。

    前端始终打包 ``original_user_message`` + 可选的 ``partial_response`` + ``events`` 数组。
    我们至少要求一个非空的 ``original_user_message``，因为每个快速通道提示词
    都以此为基础；如果缺失，该能力将回退到其正常流水线。
    """
    raw = context.config_overrides.get("answer_now_context")
    if not isinstance(raw, dict):
        return None
    if not str(raw.get("original_user_message") or "").strip():
        return None
    return raw


def format_trace_summary(events: Any, *, language: str = "en") -> str:
    """将捕获的流事件渲染为紧凑的文本摘要。

    将每个事件截断至 ``_MAX_EVENT_SNIPPET`` 个字符，将整个记录截断至
    ``_MAX_TRACE_TOTAL`` 个字符，以保持提示词长度可控。
    """
    fallback = (
        "没有可用的中间执行记录。"
        if language.startswith("zh")
        else "No intermediate execution trace was provided."
    )
    if not isinstance(events, list) or not events:
        return fallback

    lines: list[str] = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "event").strip()
        stage = str(event.get("stage") or "").strip()
        content = str(event.get("content") or "").strip()
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}

        label_parts = [event_type]
        if stage:
            label_parts.append(stage)
        line = f"{index}. {' / '.join(label_parts)}"
        if content:
            snippet = (
                content
                if len(content) <= _MAX_EVENT_SNIPPET
                else content[: _MAX_EVENT_SNIPPET - 3].rstrip() + "..."
            )
            line += f": {snippet}"
        if isinstance(metadata, dict):
            tool_name = str(metadata.get("tool_name") or metadata.get("tool") or "").strip()
            if tool_name:
                line += f" [tool={tool_name}]"
        lines.append(line)

    if not lines:
        return fallback

    text = "\n".join(lines)
    if len(text) > _MAX_TRACE_TOTAL:
        text = text[: _MAX_TRACE_TOTAL - 3].rstrip() + "..."
    return text


def labeled_block(label: str, content: str) -> str:
    """以 LLM 能可靠识别的格式化标记段落。"""
    body = content.strip() if isinstance(content, str) and content.strip() else "(empty)"
    return f"[{label}]\n{body}"


def make_skip_notice(*, capability: str, language: str, stages_skipped: list[str]) -> str:
    """附加在快速通道输出前的简短用户可见提示。

    帮助用户理解该结果是"尽力而为的提前退出"，而非完整流水线输出。
    """
    if not stages_skipped:
        return ""
    if language.startswith("zh"):
        joined = "、".join(stages_skipped)
        return f"> ⚡ 已跳过 `{capability}` 的 {joined} 阶段，以下为基于已有信息的快速结果。"
    joined = ", ".join(stages_skipped)
    return (
        f"> ⚡ Skipped {joined} stage(s) of `{capability}`; the result below is "
        f"a best-effort synthesis from the partial trace."
    )


def build_answer_now_trace_metadata(
    *,
    capability: str,
    phase: str,
    label: str,
) -> dict[str, Any]:
    """即时应答阶段的标准追踪卡片元数据。"""
    return build_trace_metadata(
        call_id=new_call_id(f"{capability}-answer-now"),
        phase=phase,
        label=label,
        call_kind="llm_final_response",
        trace_id=f"{capability}-answer-now",
        trace_role="response",
        trace_group="stage",
    )


async def stream_synthesis(
    *,
    stream: StreamBus,
    source: str,
    stage: str,
    trace_meta: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    push_content: bool = True,
    response_format: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """
    将单次 LLM 综合调用以流式方式传入 StreamBus。

    产出原始文本块（对需要解析块的能力仍然有用，如结构化 JSON 输出）。
    当 ``push_content`` 为 true（默认）时，每个块还会作为 ``CONTENT`` 事件推送，
    以便前端实时渲染回答。

    ``temperature`` 和默认的 ``max_tokens`` 来自 ``agents.yaml`` 中的
    ``capabilities.chat``（与 chat 能力自身的即时应答回退使用的配置相同），
    因此用户可以从设置 UI 全局调优即时应答，而无需修改代码。
    调用方仍可传递显式的 ``max_tokens`` 以按调用点覆盖设置
    （例如可视化功能为 ``html`` 调高该值）。
    """
    llm_config = get_llm_config()
    model = getattr(llm_config, "model", None)

    chat_cfg = get_chat_params()
    try:
        temperature = float(chat_cfg.get("temperature", 0.2))
    except (TypeError, ValueError):
        temperature = 0.2
    if max_tokens is None:
        answer_now_cfg = chat_cfg.get("answer_now") or {}
        if isinstance(answer_now_cfg, dict):
            try:
                max_tokens = int(answer_now_cfg.get("max_tokens", 8000))
            except (TypeError, ValueError):
                max_tokens = 8000
        else:
            max_tokens = 8000

    await stream.progress(
        trace_meta.get("label", "Answer now"),
        source=source,
        stage=stage,
        metadata=merge_trace_metadata(
            trace_meta,
            {"trace_kind": "call_status", "call_state": "running"},
        ),
    )

    extra_kwargs: dict[str, Any] = {"temperature": temperature}
    if model:
        extra_kwargs.update(get_token_limit_kwargs(model, max_tokens))
    if response_format is not None:
        binding = getattr(llm_config, "binding", None) or "openai"
        if supports_response_format(binding, model):
            extra_kwargs["response_format"] = response_format

    chunks: list[str] = []
    try:
        async for chunk in llm_stream(
            prompt=user_prompt,
            system_prompt=system_prompt,
            **extra_kwargs,
        ):
            if not chunk:
                continue
            chunks.append(chunk)
            if push_content:
                await stream.content(
                    chunk,
                    source=source,
                    stage=stage,
                    metadata=merge_trace_metadata(trace_meta, {"trace_kind": "llm_chunk"}),
                )
            yield chunk
    finally:
        await stream.progress(
            "",
            source=source,
            stage=stage,
            metadata=merge_trace_metadata(
                trace_meta,
                {"trace_kind": "call_status", "call_state": "complete"},
            ),
        )


def join_chunks(chunks: list[str]) -> str:
    """拼接文本块并去除 OpenAI 风格的 think 标签封装。"""
    text = "".join(chunks)
    llm_config = get_llm_config()
    binding = getattr(llm_config, "binding", None) or "openai"
    model = getattr(llm_config, "model", None)
    return clean_thinking_tags(text, binding, model)


def load_answer_now_prompts(module: str, language: str) -> dict[str, Any]:
    """为指定能力加载双语 answer_now.yaml 提示词。

    所有能力的快速通道共享相同的负载契约
    （original、current_draft、execution_trace）；
    各能力仅在语气和 JSON 结构上有所不同。集中加载器使
    aidlearning/capabilities/*.py 不包含任何按语言区分的字符串 —
    Python 代码仅使用能力特定的变量格式化用户模板。
    """
    return get_prompt_manager().load_prompts(module, "answer_now", language)


__all__ = [
    "build_answer_now_trace_metadata",
    "extract_answer_now_context",
    "format_trace_summary",
    "join_chunks",
    "labeled_block",
    "load_answer_now_prompts",
    "make_skip_notice",
    "stream_synthesis",
]
