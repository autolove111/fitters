"""每个模式共享的运行时辅助函数。

这些函数使各模式文件专注于算法而非管道：

* 提示词加载（en/zh，带缓存）。
* SSE 事件发射（``_emit``）。
* 文档加载 + 原子写入。
* LLM 调用包装器，带重试 + 失败时一行警告。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Awaitable, Callable

import yaml

from aidlearning.services.llm import clean_thinking_tags
from aidlearning.services.llm import complete as llm_complete
from aidlearning.services.llm import stream as llm_stream
from aidlearning.memory.long_term.document import Document, parse, serialize

logger = logging.getLogger(__name__)

OnEvent = Callable[[dict[str, Any]], Awaitable[None]]

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_CACHE: dict[tuple[str, str], dict[str, str]] = {}


_META_CACHE: dict[str, dict[str, Any]] = {}


def load_prompt(name: str, language: str) -> dict[str, str]:
    """按名称 + 语言（en/zh）加载并缓存一个提示词 YAML。"""
    lang = _lang_code(language)
    key = (lang, name)
    cached = _PROMPT_CACHE.get(key)
    if cached is not None:
        return cached
    path = _PROMPTS_DIR / lang / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or "system" not in data or "user" not in data:
        raise RuntimeError(f"prompt {path} missing 'system'/'user' keys")
    _PROMPT_CACHE[key] = {"system": data["system"], "user": data["user"]}
    return _PROMPT_CACHE[key]


def load_focus_meta(language: str) -> dict[str, Any]:
    """加载指定语言的每 surface / 每 slot 的焦点 + 节映射。"""
    lang = _lang_code(language)
    cached = _META_CACHE.get(lang)
    if cached is not None:
        return cached
    path = _PROMPTS_DIR / lang / "_meta.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _META_CACHE[lang] = data
    return data


def surface_focus(language: str, surface: str) -> tuple[str, list[str]]:
    meta = load_focus_meta(language).get("surfaces", {}).get(surface) or {}
    return meta.get("focus", ""), list(meta.get("sections", []) or [])


def slot_focus(language: str, slot: str) -> tuple[str, list[str]]:
    meta = load_focus_meta(language).get("slots", {}).get(slot) or {}
    return meta.get("focus", ""), list(meta.get("sections", []) or [])


def _lang_code(language: str) -> str:
    return "zh" if (language or "").lower().startswith("zh") else "en"


async def emit(on_event: OnEvent | None, event: dict[str, Any]) -> None:
    if on_event is None:
        return
    try:
        await on_event(event)
    except Exception:
        logger.debug("consolidator: on_event consumer raised", exc_info=True)


async def call_llm(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    on_event: OnEvent | None = None,
    turn: int | None = None,
    chunk_index: int | None = None,
    label: str | None = None,
) -> str:
    """单次 LLM 调用。返回原始文本体；失败时返回 ""。

    模型/提供商从*活跃* LLM 配置解析 — 如果用户选择了非默认模型，
    模式预期已通过 :func:`activate_llm_selection` 安装了作用域配置。
    为工作台追踪发出 ``llm_io_start`` / ``llm_io_end`` 事件。
    """
    from aidlearning.services.llm import get_llm_config

    model_label = get_llm_config().model or None
    if on_event is not None:
        await on_event(
            {
                "stage": "llm_io_start",
                "turn": turn,
                "chunk_index": chunk_index,
                "label": label,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model_label,
            }
        )
    response_parts: list[str] = []
    in_think_block = False
    try:
        async for delta in llm_stream(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream_coalesce_chars=64,
            stream_coalesce_seconds=0.05,
        ):
            if not delta:
                continue
            response_parts.append(delta)
            visible_delta, in_think_block = _strip_thinking_delta(delta, in_think_block)
            if on_event is not None:
                if visible_delta:
                    await on_event(
                        {
                            "stage": "llm_io_delta",
                            "turn": turn,
                            "chunk_index": chunk_index,
                            "label": label,
                            "delta": visible_delta,
                            "model": model_label,
                        }
                    )
        response = clean_thinking_tags("".join(response_parts))
        if on_event is not None:
            await on_event(
                {
                    "stage": "llm_io_end",
                    "turn": turn,
                    "chunk_index": chunk_index,
                    "label": label,
                    "response": response,
                    "error": None,
                    "model": model_label,
                }
            )
        return response
    except Exception as exc:  # noqa: BLE001
        # 部分提供商尚未实现流式传输。回退到非流式路径，
        # 以确保记忆任务仍可使用。
        logger.warning("consolidator streaming LLM call failed; falling back: %s", exc)
        try:
            response = await llm_complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            response = clean_thinking_tags(response)
            if on_event is not None:
                await on_event(
                    {
                        "stage": "llm_io_delta",
                        "turn": turn,
                        "chunk_index": chunk_index,
                        "label": label,
                        "delta": response,
                        "model": model_label,
                    }
                )
                await on_event(
                    {
                        "stage": "llm_io_end",
                        "turn": turn,
                        "chunk_index": chunk_index,
                        "label": label,
                        "response": response,
                        "error": None,
                        "model": model_label,
                    }
                )
            return response
        except Exception as fallback_exc:  # noqa: BLE001
            logger.warning("consolidator LLM call failed: %s", fallback_exc)
            if on_event is not None:
                await on_event(
                    {
                        "stage": "llm_io_end",
                        "turn": turn,
                        "chunk_index": chunk_index,
                        "label": label,
                        "response": "",
                        "error": str(fallback_exc),
                        "model": model_label,
                    }
                )
            return ""


def load_doc(path: Path, *, default_title: str) -> Document:
    if not path.exists():
        return Document(title=default_title)
    return parse(path.read_text(encoding="utf-8"))


async def write_doc_atomic(path: Path, doc: Document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = serialize(doc)
    await asyncio.to_thread(_atomic_write, path, text)


async def write_doc_checkpoint(
    path: Path,
    doc: Document,
    *,
    layer: str,
    key: str,
    on_event: OnEvent | None = None,
    turn: int | None = None,
    label: str | None = None,
    action: str = "write",
) -> int:
    """立即写入文档并注册一个运行范围的撤销检查点。"""
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else ""
    await write_doc_atomic(path, doc)
    from aidlearning.memory.consolidator.runs import push_undo_checkpoint

    undo_depth = push_undo_checkpoint(
        layer=layer,
        key=key,
        path=path,
        existed=existed,
        previous_content=previous,
        action=action,
        turn=turn,
        label=label,
    )
    await emit(
        on_event,
        {
            "stage": "doc_updated",
            "layer": layer,
            "key": key,
            "turn": turn,
            "label": label,
            "action": action,
            "undo_depth": undo_depth,
        },
    )
    return undo_depth


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_str, path)
    finally:
        if os.path.exists(tmp_str):
            try:
                os.remove(tmp_str)
            except OSError:
                pass


def _strip_thinking_delta(delta: str, in_block: bool) -> tuple[str, bool]:
    """Remove streamed <think> blocks before they reach the workbench UI."""
    out: list[str] = []
    text = delta
    while text:
        lower = text.lower()
        if in_block:
            close_at = lower.find("</think>")
            close_len = len("</think>")
            alt_close = lower.find("</thinking>")
            if alt_close != -1 and (close_at == -1 or alt_close < close_at):
                close_at = alt_close
                close_len = len("</thinking>")
            if close_at == -1:
                return "".join(out), True
            text = text[close_at + close_len :]
            in_block = False
            continue

        open_at = lower.find("<think>")
        open_len = len("<think>")
        alt_open = lower.find("<thinking>")
        if alt_open != -1 and (open_at == -1 or alt_open < open_at):
            open_at = alt_open
            open_len = len("<thinking>")
        if open_at == -1:
            out.append(text)
            break
        out.append(text[:open_at])
        text = text[open_at + open_len :]
        in_block = True
    return "".join(out), in_block


def today_iso() -> str:
    return datetime.now(tz=timezone.utc).date().isoformat()


__all__ = [
    "OnEvent",
    "call_llm",
    "emit",
    "load_doc",
    "load_focus_meta",
    "load_prompt",
    "slot_focus",
    "surface_focus",
    "today_iso",
    "write_doc_atomic",
    "write_doc_checkpoint",
]
