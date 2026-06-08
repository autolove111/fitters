"""追踪事件和文档条目的稳定、时间有序标识符。

格式：26 字符 Crockford-base32（ULID 风格）。

- 追踪 id：``<surface>:<ULID>`` — 例如 ``chat:01HZK4ABCDEFGHJKMNPQRSTVWX``
- 条目 id：``m_<ULID>``        — 用于 MD 脚注标签

ULID 的前 10 个字符编码毫秒时间戳，提供跨文件和文件内的自然时间排序。
"""

from __future__ import annotations

import re
import secrets
import time

_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford
_ULID_TS_LEN = 10
_ULID_RAND_LEN = 16
_ULID_LEN = _ULID_TS_LEN + _ULID_RAND_LEN

_ENTRY_RE = re.compile(r"^m_[0-9A-HJKMNP-TV-Z]{26}$")
_TRACE_RE = re.compile(r"^[a-z][a-z0-9_-]*:[0-9A-HJKMNP-TV-Z]{26}$")
# 快照引用指向当前工作区实体。id 部分是每 surface 适配器选择的内容
# （doc_id / record_id / kb_name / bot name / session_id / "session:question" 组合）。
# 足够宽松以允许嵌入的 ``:``；足够严格以保持引用安全地嵌入逗号分隔的脚注序列化中。
_SNAPSHOT_RE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z0-9_.:\-]+$")
# L3 surface 引用 — 纯 surface 名称如 ``chat``、``notebook``。L3 是综合层，
# 指向 L2 *文件*而非 L2 条目，因此其引用不需要 id 部分。
# 白名单（非宽松正则），以防止格式错误的引用如 ``not-an-id`` 意外通过验证。
# 镜像 :data:`paths.SURFACES`；如果添加 surface，也要在此处添加。
_SHORTNAME_REFS = frozenset({"chat", "notebook", "quiz", "kb", "book", "tutorbot", "cowriter"})


def _encode(n: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_BASE32[n & 0x1F])
        n >>= 5
    return "".join(reversed(chars))


def new_ulid() -> str:
    ts = int(time.time() * 1000) & ((1 << (_ULID_TS_LEN * 5)) - 1)
    rand = secrets.randbits(_ULID_RAND_LEN * 5)
    return _encode(ts, _ULID_TS_LEN) + _encode(rand, _ULID_RAND_LEN)


def new_entry_id() -> str:
    return f"m_{new_ulid()}"


def new_trace_id(surface: str) -> str:
    return f"{surface}:{new_ulid()}"


def is_entry_id(s: str) -> bool:
    return bool(_ENTRY_RE.match(s))


def is_trace_id(s: str) -> bool:
    return bool(_TRACE_RE.match(s))


def is_snapshot_ref(s: str) -> bool:
    return bool(_SNAPSHOT_RE.match(s))


def is_shortname_ref(s: str) -> bool:
    """纯 surface 名称 — L3 引用使用的形式（白名单）。"""
    return s in _SHORTNAME_REFS


def is_valid_ref(s: str) -> bool:
    """操作验证器接受的任何形式的引用。"""
    return is_entry_id(s) or is_trace_id(s) or is_snapshot_ref(s) or is_shortname_ref(s)
