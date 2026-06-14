"""整合器共享的容错 JSON 解析器。

支持两种格式：

* :func:`parse_action` — 代理循环驱动器使用的每轮一个操作的信封格式。
  失败时返回 ``None``，以便循环可以显示重试提示而非崩溃。
* :func:`_parse_ops_response` — 旧版 ``{"ops": [...]}`` 格式，
  因为工作台的预览→应用流程通过此解析器往返操作而保留
  （参见 :mod:`aidlearning.memory.store`）。

两者都去除代码围栏并容忍散文框架，以便模型可以出声思考而不使运行失效。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from aidlearning.memory.long_term.ops import AddOp, DeleteOp, EditOp, Op

logger = logging.getLogger(__name__)


# ── 循环模式操作信封 ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedAction:
    name: str
    args: dict[str, Any]
    thought: str = ""

    def arg(self, key: str, default: Any = None) -> Any:
        return self.args.get(key, default)


def parse_action(raw: str) -> ParsedAction | None:
    """从 LLM 文本中解析一个 ``{"thought","action","args"}`` 信封。

    对任何格式错误的输入返回 ``None``；循环驱动器向下一回合渲染纠正提示，
    以便模型可以自我恢复。
    """
    snippet = _extract_json_object(raw)
    if snippet is None:
        return None
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    name_raw = data.get("action")
    if not isinstance(name_raw, str) or not name_raw.strip():
        return None
    args_raw = data.get("args")
    args: dict[str, Any] = args_raw if isinstance(args_raw, dict) else {}
    thought_raw = data.get("thought")
    thought = thought_raw.strip() if isinstance(thought_raw, str) else ""
    return ParsedAction(name=name_raw.strip(), args=args, thought=thought)


# ── 旧版操作数组格式（为 apply_ops_payload 保留）──────────────────────────


def _parse_ops_response(raw: str) -> list[Op]:
    """将旧版 ``{"ops":[...]}`` 信封容错解析为 ``Op``。"""
    snippet = _extract_json_object(raw)
    if snippet is None:
        logger.warning("memory consolidate: no JSON object in payload")
        return []
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError:
        logger.warning("memory consolidate: malformed JSON in payload")
        return []
    if not isinstance(data, dict):
        return []
    ops_raw = data.get("ops")
    if not isinstance(ops_raw, list):
        return []

    ops: list[Op] = []
    for raw_op in ops_raw:
        op = _parse_one_op(raw_op)
        if op is not None:
            ops.append(op)
    return ops


def _parse_one_op(raw_op: Any) -> Op | None:
    if not isinstance(raw_op, dict):
        return None
    kind = raw_op.get("op")
    try:
        if kind == "add":
            return AddOp(
                section=str(raw_op.get("section", "")).strip(),
                text=str(raw_op.get("text", "")).strip(),
                refs=[str(r) for r in raw_op.get("refs", []) if r],
            )
        if kind == "edit":
            return EditOp(
                target_id=str(raw_op.get("target_id", "")).strip(),
                new_text=str(raw_op.get("new_text", "")).strip(),
                new_refs=[str(r) for r in raw_op.get("new_refs", []) if r],
            )
        if kind == "delete":
            return DeleteOp(
                target_id=str(raw_op.get("target_id", "")).strip(),
                reason=str(raw_op.get("reason", "stale")).strip(),
            )
    except Exception:  # noqa: BLE001 — 在解析层保持宽容
        return None
    return None


# ── 共享文本提取 ───────────────────────────────────────────────────────


def _extract_json_object(raw: str) -> str | None:
    """去除代码围栏并提取第一个顶层 JSON 对象。"""
    text = raw.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]
