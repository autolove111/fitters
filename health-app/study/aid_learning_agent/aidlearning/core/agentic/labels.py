r"""流式 LLM 响应的协议标签解析。

智能体引擎使用 ``\`\`LABEL\`\`+content`` 协议驱动 LLM 调用：
提示词要求每个回复的第一行包含一个用双反引号包裹的允许标签，
之后是其余内容。解析器预先检测该标签，容忍少量提供商/模型格式偏差，
并相应地路由标签后的流。

标签集由调用方提供：chat 使用 ``(FINISH, TOOL, THINK)``，
解题步骤使用 ``(THINK, TOOL, FINISH, REPLAN)``，
计划使用 ``(PLAN,)`` 等。
"""

from __future__ import annotations

import re

LABEL_UNKNOWN = "UNKNOWN"
LABEL_PROBE_MAX_CHARS = 64

_INVISIBLE_PREFIX_CHARS = "﻿​‌‍"
_LABEL_SEPARATOR_CHARS = "\n\r \t:：-–—"


def strip_label_probe_prefix(buffer: str) -> str:
    """在标签探测前去除前导空白和零宽字符。"""
    stripped = str(buffer or "")
    previous = None
    while stripped != previous:
        previous = stripped
        stripped = stripped.lstrip().lstrip(_INVISIBLE_PREFIX_CHARS)
    return stripped


def classify_label(
    buffer: str,
    *,
    allowed_labels: tuple[str, ...],
    final: bool = False,
) -> tuple[str, str] | None:
    r"""检查内容缓冲区是否有前导 ``\`\`LABEL\`\``` 前缀。

    检测到允许的标签后返回 ``(label, after_text)``（在前导空白之后）—
    调用方相应地路由 ``after_text`` 和所有后续块。

    当缓冲区太短或仍是部分前缀匹配时返回 ``None``。调用方继续缓冲
    并在下一个块时重试，当缓冲区超过 :data:`LABEL_PROBE_MAX_CHARS`
    且未匹配时必须回退到 :data:`LABEL_UNKNOWN`。

    接受包裹形式（首选 ``\`\`LABEL\`\```，容忍常见的单/三反引号变体）
    和裸回退形式（``LABEL`` 后跟分隔符）— 某些模型在一次性提示词中
    会丢失或修改反引号，只要协议标签都是大写令牌，裸形式就是明确的。
    包裹形式后可以直接跟正文文本，因为 Markdown 行内代码样式在视觉上
    分离了标签，即使原始流没有空白（例如 ``\`\`FINISH\`\`你好``）。

    ``final=True`` 表示调用方知道不会有更多块，因此即使没有尾随分隔符
    也可以接受精确的裸标签（如 ``FINISH``）。
    """
    stripped = strip_label_probe_prefix(buffer)
    for label in allowed_labels:
        wrapped = re.match(
            rf"^(?P<ticks>`+)\s*{re.escape(label)}\s*(?P=ticks)(?P<after>.*)$",
            stripped,
            flags=re.DOTALL,
        )
        if wrapped is not None:
            after = wrapped.group("after")
            if after and after[0] == "`":
                # 避免接受过度关闭/仍在流式传输的包裹，如 ``FINISH```
                # 并将多余的反引号泄漏到路由的正文中。非反引号尾部是
                # 真正的正文文本，即使模型在标签后忘记了分隔符。
                continue
            # 去除标签后的分隔换行/空格/标点，使正文/推理文本
            # 不以多余的空行或特定语言的冒号开头。
            return label, after.lstrip(_LABEL_SEPARATOR_CHARS)
        # 裸标签回退：仅当标签后跟明确的分隔符时，这样我们不会
        # 对恰好以 ``FINISHED`` 等令牌开头的正文产生误报。
        # 空尾部（标签与缓冲区精确匹配）在流式传输时是模糊的 —
        # 继续缓冲直到下一个块揭示分隔符或延续字符。
        # 在流结束时（``final=True``），接受它。
        if stripped.startswith(label):
            tail = stripped[len(label) :]
            if tail and tail[0] in _LABEL_SEPARATOR_CHARS:
                return label, tail.lstrip(_LABEL_SEPARATOR_CHARS)
            if final and not tail:
                return label, ""
    return None


def find_inline_labels(text: str, *, allowed_labels: tuple[str, ...]) -> list[str]:
    """返回在标签后正文中出现的标签。

    协议要求每个回复恰好一个标签（在第一行）。在后面正文行开头
    发现的第二个标签是值得标记的违规。文本中的提及（如"接下来我应该
    使用 ``TOOL``"）不是操作标签，不应触发修复循环。
    """
    if not allowed_labels:
        return []
    pattern = "|".join(re.escape(label) for label in allowed_labels)
    raw = str(text or "")
    separators = re.escape(_LABEL_SEPARATOR_CHARS)
    wrapped = [
        match.group("label")
        for match in re.finditer(
            rf"(?m)^[^\S\r\n]*(?P<ticks>`+)\s*(?P<label>{pattern})\s*(?P=ticks)(?=$|[{separators}])",
            raw,
        )
    ]
    bare = re.findall(rf"(?m)^[^\S\r\n]*({pattern})(?=$|[{separators}])", raw)
    return [*wrapped, *bare]
