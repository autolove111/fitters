"""读写设置界面中各能力的可调参数。

这是 ``/api/v1/capabilities/settings`` 端点的数据源。
它桥接两个磁盘文件：

* ``data/user/settings/agents.yaml`` — 各能力的 LLM 参数
  （``temperature``、各阶段 ``max_tokens``）。由
  :mod:`aidlearning.services.config.loader` 中的
  :func:`get_chat_params` / :func:`get_agent_params` 管理。
* ``data/user/settings/main.yaml`` — 各能力的非 LLM 运行时开关
  （research 的 ``researching.*`` 和 question 的 ``exploring.*`` 子树）。

我们向 UI 暴露的 Schema 是单个字典，以便前端渲染统一表单。
保存时会将载荷拆分回对应的文件。

我们有意不包含当前管道实际上并未读取对应 YAML 键的能力 —
展示无实际效果的开关会造成误导。随着更多硬编码常量
被提升到配置中，可以在此处添加更多能力。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aidlearning.services.config.loader import (
    DEFAULT_CHAT_PARAMS,
    PROJECT_ROOT,
    get_runtime_settings_dir,
)
from aidlearning.utils.config_manager import ConfigManager

# ── Schema 定义 ─────────────────────────────────────────────────────────


# 此处的键同时驱动 GET 响应结构和 PUT 验证。
# 每个能力列出其（文件, 子路径）读取方式，以便我们在不干扰无关 YAML 键的情况下进行值的往返转换。
_AGENTS_YAML_CAPABILITY_SECTIONS: dict[str, tuple[str, ...]] = {
    "solve": ("capabilities", "solve"),
    "research": ("capabilities", "research"),
    "question": ("capabilities", "question"),
}

_SIMPLE_LLM_DEFAULTS: dict[str, dict[str, Any]] = {
    "solve": {"temperature": 0.3, "max_tokens": 8192},
    "research": {"temperature": 0.5, "max_tokens": 16834},
    "question": {"temperature": 0.7, "max_tokens": 4096},
}

# 各能力在运行时读取的 main.yaml 子树（除 LLM 参数外）。
_MAIN_YAML_RUNTIME_DEFAULTS: dict[str, dict[str, Any]] = {
    "solve": {
        "max_iterations_per_step": 7,
        "max_replans": 2,
    },
    "research": {
        "researching": {
            "note_agent_mode": "auto",
            "tool_timeout": 60,
            "tool_max_retries": 3,
            "paper_search_years_limit": 5,
        },
    },
    "question": {
        "exploring": {
            "max_iterations": 7,
            "tool_summarizer": {
                "enabled": True,
                "max_tokens": 1024,
            },
        },
    },
}


# ── 辅助函数 ────────────────────────────────────────────────────────────


def _agents_yaml_path() -> Path:
    return get_runtime_settings_dir(PROJECT_ROOT) / "agents.yaml"


def _read_agents_yaml() -> dict[str, Any]:
    path = _agents_yaml_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_agents_yaml(data: dict[str, Any]) -> None:
    path = _agents_yaml_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _get_at(d: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    """按路径遍历嵌套字典，如果任何路径段缺失则返回 {}。"""
    node: Any = d
    for key in path:
        if not isinstance(node, dict):
            return {}
        node = node.get(key, {})
    return node if isinstance(node, dict) else {}


def _set_at(d: dict[str, Any], path: tuple[str, ...], value: dict[str, Any]) -> None:
    """在 ``d`` 的 ``path`` 处插入 ``value``，自动创建中间字典。"""
    node = d
    for key in path[:-1]:
        nxt = node.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            node[key] = nxt
        node = nxt
    node[path[-1]] = value


def _deep_merge(into: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    """递归地将 ``src`` 合并到 ``into`` 中（src 中的键优先）。"""
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(into.get(key), dict):
            _deep_merge(into[key], value)
        else:
            into[key] = value
    return into


def _coerce_float(raw: Any, default: float, *, lo: float = 0.0, hi: float = 2.0) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def _coerce_int(raw: Any, default: int, *, lo: int = 1, hi: int = 200_000) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def _coerce_bool(raw: Any, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        if raw.lower() in {"true", "1", "yes", "on"}:
            return True
        if raw.lower() in {"false", "0", "no", "off"}:
            return False
    return default


# ── Schema 构建 / 读取 ─────────────────────────────────────────────────


# 仅 chat 子节被 ``AgenticChatPipeline.__init__`` 实际读取。
# 当某个阶段的 LLM 调用开始消费其 max_tokens 时，将其添加到此处。
_CHAT_STAGES_IN_USE: tuple[str, ...] = ("responding", "answer_now")


def _build_chat_block(agents_cfg: dict[str, Any]) -> dict[str, Any]:
    """将 agents.yaml.capabilities.chat 读取到带默认值的 UI Schema 中。"""
    chat_cfg: dict[str, Any] = _get_at(agents_cfg, ("capabilities", "chat"))
    merged: dict[str, Any] = {}
    _deep_merge(merged, DEFAULT_CHAT_PARAMS)
    _deep_merge(merged, chat_cfg)
    return {
        "temperature": _coerce_float(merged.get("temperature"), DEFAULT_CHAT_PARAMS["temperature"]),
        "max_iterations": _coerce_int(
            merged.get("max_iterations"), DEFAULT_CHAT_PARAMS["max_iterations"], lo=1, hi=100
        ),
        "stage_budgets": {
            stage: _coerce_int(
                (merged.get(stage) or {}).get("max_tokens"),
                DEFAULT_CHAT_PARAMS[stage]["max_tokens"],
                lo=1,
                hi=200_000,
            )
            for stage in _CHAT_STAGES_IN_USE
        },
    }


def _build_simple_llm_block(agents_cfg: dict[str, Any], capability: str) -> dict[str, Any]:
    defaults = _SIMPLE_LLM_DEFAULTS[capability]
    section = _get_at(agents_cfg, _AGENTS_YAML_CAPABILITY_SECTIONS[capability])
    return {
        "temperature": _coerce_float(section.get("temperature"), defaults["temperature"]),
        "max_tokens": _coerce_int(section.get("max_tokens"), defaults["max_tokens"]),
    }


def _build_main_runtime_block(main_cfg: dict[str, Any], capability: str) -> dict[str, Any]:
    defaults = _MAIN_YAML_RUNTIME_DEFAULTS.get(capability)
    if defaults is None:
        return {}
    if capability == "solve":
        solve_cfg = _get_at(main_cfg, ("capabilities", "solve"))
        return {
            "max_iterations_per_step": _coerce_int(
                solve_cfg.get("max_iterations_per_step"),
                defaults["max_iterations_per_step"],
                lo=1,
                hi=50,
            ),
            "max_replans": _coerce_int(
                solve_cfg.get("max_replans"),
                defaults["max_replans"],
                lo=0,
                hi=10,
            ),
        }
    if capability == "research":
        researching_cfg = _get_at(main_cfg, ("capabilities", "research", "researching"))
        d = defaults["researching"]
        return {
            "researching": {
                "note_agent_mode": str(
                    researching_cfg.get("note_agent_mode") or d["note_agent_mode"]
                ),
                "tool_timeout": _coerce_int(
                    researching_cfg.get("tool_timeout"), d["tool_timeout"], lo=1, hi=600
                ),
                "tool_max_retries": _coerce_int(
                    researching_cfg.get("tool_max_retries"), d["tool_max_retries"], lo=0, hi=10
                ),
                "paper_search_years_limit": _coerce_int(
                    researching_cfg.get("paper_search_years_limit"),
                    d["paper_search_years_limit"],
                    lo=1,
                    hi=50,
                ),
            },
        }
    if capability == "question":
        exploring_cfg = _get_at(main_cfg, ("capabilities", "question", "exploring"))
        d = defaults["exploring"]
        summarizer_cfg = (
            exploring_cfg.get("tool_summarizer")
            if isinstance(exploring_cfg.get("tool_summarizer"), dict)
            else {}
        )
        return {
            "exploring": {
                "max_iterations": _coerce_int(
                    exploring_cfg.get("max_iterations"), d["max_iterations"], lo=1, hi=50
                ),
                "tool_summarizer": {
                    "enabled": _coerce_bool(
                        summarizer_cfg.get("enabled"), d["tool_summarizer"]["enabled"]
                    ),
                    "max_tokens": _coerce_int(
                        summarizer_cfg.get("max_tokens"), d["tool_summarizer"]["max_tokens"]
                    ),
                },
            },
        }
    return {}


def capabilities_settings_dict() -> dict[str, Any]:
    """返回完整的 Schema 作为 JSON 安全字典（已合并默认值）。"""
    agents_cfg = _read_agents_yaml()
    main_cfg = ConfigManager().load_config()

    result: dict[str, Any] = {"chat": _build_chat_block(agents_cfg)}
    for cap in _AGENTS_YAML_CAPABILITY_SECTIONS:
        block = _build_simple_llm_block(agents_cfg, cap)
        block.update(_build_main_runtime_block(main_cfg, cap))
        result[cap] = block
    return result


# ── 写入路径 ───────────────────────────────────────────────────────────


def _apply_chat_into_agents_yaml(agents_cfg: dict[str, Any], block: dict[str, Any]) -> None:
    current = _get_at(agents_cfg, ("capabilities", "chat"))
    new_chat: dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    if "temperature" in block:
        new_chat["temperature"] = _coerce_float(
            block.get("temperature"), DEFAULT_CHAT_PARAMS["temperature"]
        )
    if "max_iterations" in block:
        new_chat["max_iterations"] = _coerce_int(
            block.get("max_iterations"), DEFAULT_CHAT_PARAMS["max_iterations"], lo=1, hi=100
        )
    stage_budgets = block.get("stage_budgets") or {}
    if isinstance(stage_budgets, dict):
        for stage, default_sub in DEFAULT_CHAT_PARAMS.items():
            if not isinstance(default_sub, dict):
                continue
            if stage in stage_budgets:
                existing = new_chat.get(stage) if isinstance(new_chat.get(stage), dict) else {}
                existing = dict(existing)
                existing["max_tokens"] = _coerce_int(
                    stage_budgets[stage], default_sub["max_tokens"], lo=1, hi=200_000
                )
                new_chat[stage] = existing
    _set_at(agents_cfg, ("capabilities", "chat"), new_chat)


def _apply_simple_llm_into_agents_yaml(
    agents_cfg: dict[str, Any], capability: str, block: dict[str, Any]
) -> None:
    defaults = _SIMPLE_LLM_DEFAULTS[capability]
    section_path = _AGENTS_YAML_CAPABILITY_SECTIONS[capability]
    current = _get_at(agents_cfg, section_path)
    new_section: dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    if "temperature" in block:
        new_section["temperature"] = _coerce_float(
            block.get("temperature"), defaults["temperature"]
        )
    if "max_tokens" in block:
        new_section["max_tokens"] = _coerce_int(block.get("max_tokens"), defaults["max_tokens"])
    _set_at(agents_cfg, section_path, new_section)


def _apply_main_runtime(
    main_payload: dict[str, Any], capability: str, block: dict[str, Any]
) -> None:
    defaults = _MAIN_YAML_RUNTIME_DEFAULTS.get(capability)
    if defaults is None:
        return
    if capability == "solve":
        solve_section: dict[str, Any] = {}
        if "max_iterations_per_step" in block:
            solve_section["max_iterations_per_step"] = _coerce_int(
                block.get("max_iterations_per_step"),
                defaults["max_iterations_per_step"],
                lo=1,
                hi=50,
            )
        if "max_replans" in block:
            solve_section["max_replans"] = _coerce_int(
                block.get("max_replans"),
                defaults["max_replans"],
                lo=0,
                hi=10,
            )
        if solve_section:
            main_payload.setdefault("capabilities", {})["solve"] = solve_section
    if capability == "research" and isinstance(block.get("researching"), dict):
        d = defaults["researching"]
        r = block["researching"]
        main_payload.setdefault("capabilities", {}).setdefault("research", {})["researching"] = {
            "note_agent_mode": str(r.get("note_agent_mode") or d["note_agent_mode"]),
            "tool_timeout": _coerce_int(r.get("tool_timeout"), d["tool_timeout"], lo=1, hi=600),
            "tool_max_retries": _coerce_int(
                r.get("tool_max_retries"), d["tool_max_retries"], lo=0, hi=10
            ),
            "paper_search_years_limit": _coerce_int(
                r.get("paper_search_years_limit"), d["paper_search_years_limit"], lo=1, hi=50
            ),
        }
    if capability == "question" and isinstance(block.get("exploring"), dict):
        d = defaults["exploring"]
        e = block["exploring"]
        sm = e.get("tool_summarizer") if isinstance(e.get("tool_summarizer"), dict) else {}
        main_payload.setdefault("capabilities", {}).setdefault("question", {})["exploring"] = {
            "max_iterations": _coerce_int(
                e.get("max_iterations"), d["max_iterations"], lo=1, hi=50
            ),
            "tool_summarizer": {
                "enabled": _coerce_bool(sm.get("enabled"), d["tool_summarizer"]["enabled"]),
                "max_tokens": _coerce_int(sm.get("max_tokens"), d["tool_summarizer"]["max_tokens"]),
            },
        }


def save_capabilities_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """将 ``payload`` 合并到两个 YAML 文件中并返回新状态。

    未知键会被丢弃；值通过上述辅助函数进行强制转换和约束，
    以确保 YAML 不会写入无效数据。
    """
    agents_cfg = _read_agents_yaml()
    main_payload: dict[str, Any] = {}

    if isinstance(payload.get("chat"), dict):
        _apply_chat_into_agents_yaml(agents_cfg, payload["chat"])

    for cap in _AGENTS_YAML_CAPABILITY_SECTIONS:
        block = payload.get(cap)
        if not isinstance(block, dict):
            continue
        _apply_simple_llm_into_agents_yaml(agents_cfg, cap, block)
        _apply_main_runtime(main_payload, cap, block)

    _write_agents_yaml(agents_cfg)
    if main_payload:
        ConfigManager().save_config(main_payload)
    return capabilities_settings_dict()


__all__ = ["capabilities_settings_dict", "save_capabilities_settings"]
