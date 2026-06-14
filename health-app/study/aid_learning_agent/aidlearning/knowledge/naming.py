"""知识库名称验证辅助工具。"""

from __future__ import annotations

import re
import unicodedata

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_FORBIDDEN_CHARS = set('<>:"/\\|?*#%')
_MAX_KB_NAME_LENGTH = 120


def validate_knowledge_base_name(name: str) -> str:
    """验证并规范化面向用户的知识库名称。

    名称可以包含 Unicode 字母、空格、点号、连字符、下划线和
    常见标点符号，但不能包含会破坏知识库目录或 API 路由路径的
    文件系统或 URL 保留分隔符。
    """
    normalized = unicodedata.normalize("NFC", str(name or "")).strip()
    if not normalized:
        raise ValueError("Knowledge base name is required")
    if normalized in {".", ".."}:
        raise ValueError("Knowledge base name cannot be '.' or '..'")
    if len(normalized) > _MAX_KB_NAME_LENGTH:
        raise ValueError(
            f"Knowledge base name is too long; maximum length is {_MAX_KB_NAME_LENGTH}"
        )
    if _CONTROL_CHARS.search(normalized):
        raise ValueError("Knowledge base name cannot contain control characters")

    forbidden = sorted(ch for ch in _FORBIDDEN_CHARS if ch in normalized)
    if forbidden:
        joined = " ".join(forbidden)
        raise ValueError(
            "Knowledge base name contains reserved characters: "
            f"{joined}. Avoid path or URL separators such as /, \\, ?, #, and %."
        )

    return normalized
