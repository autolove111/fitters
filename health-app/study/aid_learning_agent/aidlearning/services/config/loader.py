#!/usr/bin/env python
"""
配置加载器
==========

AidLearning 所有模块的统一配置加载。
提供 YAML 配置加载、路径解析和语言解析。
"""

import asyncio
from pathlib import Path
from typing import Any

import yaml

from aidlearning.runtime.home import get_runtime_home
from aidlearning.services.path_service import get_path_service

# 运行时工作区根目录。应用设置位于 PROJECT_ROOT/data/user/settings 下。
PROJECT_ROOT = get_runtime_home()


def get_runtime_settings_dir(project_root: Path | None = None) -> Path:
    """返回 ``data/user/settings`` 下的标准运行时设置目录。"""
    root = project_root or PROJECT_ROOT
    return root / "data" / "user" / "settings"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    深度合并两个字典，override 中的值会覆盖 base 中的值

    Args:
        base: 基础配置
        override: 覆盖配置

    Returns:
        合并后的配置
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # 递归合并字典
            result[key] = _deep_merge(result[key], value)
        else:
            # 直接覆盖
            result[key] = value

    return result


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """加载 YAML 文件并以字典形式返回其内容。"""
    with open(file_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _inject_runtime_paths(config: dict[str, Any]) -> dict[str, Any]:
    """暴露标准运行时路径，同时不将 YAML 路径视为用户可编辑的状态。"""
    path_service = get_path_service()
    normalized = dict(config or {})
    tools = dict(normalized.get("tools", {}) or {})
    run_code = dict(tools.get("run_code", {}) or {})
    run_code["workspace"] = str(path_service.get_chat_feature_dir("_detached_code_execution"))
    tools["run_code"] = run_code
    normalized["tools"] = tools
    normalized["paths"] = {
        "user_data_dir": str(path_service.get_user_root()),
        "knowledge_bases_dir": str(path_service.get_knowledge_bases_root()),
        "user_log_dir": str(path_service.get_logs_dir()),
        "performance_log_dir": str(path_service.get_logs_dir() / "performance"),
        "question_output_dir": str(path_service.get_chat_feature_dir("deep_question")),
        "research_output_dir": str(path_service.get_research_dir()),
        "research_reports_dir": str(path_service.get_research_reports_dir()),
        "solve_output_dir": str(path_service.get_chat_feature_dir("deep_solve")),
    }
    return normalized


async def _load_yaml_file_async(file_path: Path) -> dict[str, Any]:
    """_load_yaml_file 的异步版本。"""
    return await asyncio.to_thread(_load_yaml_file, file_path)


def resolve_config_path(
    config_file: str,
    project_root: Path | None = None,
) -> tuple[Path, bool]:
    """
    在 ``data/user/settings/`` 中解析 *config_file*。

    Returns:
        ``(path, False)``

    Raises:
        FileNotFoundError: 如果请求的配置不存在。
    """
    if project_root is None:
        project_root = PROJECT_ROOT

    settings_dir = get_runtime_settings_dir(project_root)
    config_path = settings_dir / config_file
    if config_path.exists():
        return config_path, False
    raise FileNotFoundError(
        f"Configuration file not found: {config_file} (expected under {settings_dir})"
    )


def load_config_with_main(config_file: str, project_root: Path | None = None) -> dict[str, Any]:
    """
    加载配置文件，自动与 main.yaml 通用配置合并

    Args:
        config_file: 配置文件名（如 "main.yaml"）
        project_root: 项目根目录（如果为 None，将尝试自动检测）

    Returns:
        合并后的配置字典
    """
    if project_root is None:
        project_root = PROJECT_ROOT

    config_path, _ = resolve_config_path(config_file, project_root)
    return _inject_runtime_paths(_load_yaml_file(config_path))


async def load_config_with_main_async(
    config_file: str, project_root: Path | None = None
) -> dict[str, Any]:
    """
    load_config_with_main 的异步版本，用于非阻塞文件操作。

    加载配置文件，自动与 main.yaml 通用配置合并

    Args:
        config_file: 配置文件名（如 "main.yaml"）
        project_root: 项目根目录（如果为 None，将尝试自动检测）

    Returns:
        合并后的配置字典
    """
    if project_root is None:
        project_root = PROJECT_ROOT

    config_path, _ = resolve_config_path(config_file, project_root)
    return _inject_runtime_paths(await _load_yaml_file_async(config_path))


def get_path_from_config(config: dict[str, Any], path_key: str, default: str = None) -> str:
    """
    从配置中获取路径。

    Args:
        config: 配置字典
        path_key: 路径键名（如 "log_dir", "workspace"）
        default: 默认值

    Returns:
        路径字符串
    """
    injected = _inject_runtime_paths(config)
    if "paths" in injected and path_key in injected["paths"]:
        return injected["paths"][path_key]
    if path_key == "workspace":
        return injected.get("tools", {}).get("run_code", {}).get("workspace", default)
    return default


def parse_language(language: Any) -> str:
    """
    统一的语言配置解析器，支持多种输入格式

    支持的语言表示：
    - 英文: "en", "english", "English"
    - 中文: "zh", "chinese", "Chinese"

    Args:
        language: 语言配置值（可以是 "zh"/"en"/"Chinese"/"English" 等）

    Returns:
        标准化语言代码：'zh' 或 'en'，默认为 'zh'
    """
    if not language:
        return "zh"

    if isinstance(language, str):
        lang_lower = language.lower()
        if lang_lower in ["en", "english"]:
            return "en"
        if lang_lower in ["zh", "chinese", "cn"]:
            return "zh"

    return "zh"  # 默认中文


def get_agent_params(module_name: str) -> dict:
    """
    获取特定模块的 Agent 参数（temperature, max_tokens）。

    此函数从 config/agents.yaml 加载参数，该文件是所有 Agent
    temperature 和 max_tokens 设置的唯一数据源。

    Args:
        module_name: 模块名称，可选值：
            - "solve": 解题模块 Agent
            - "research": 研究模块 Agent
            - "question": 出题模块 Agent
            - "brainstorm": 头脑风暴工具设置
            - "co_writer": 协同写作模块 Agent
            - "narrator": 叙述 Agent（独立，用于 TTS）
            - "llm_probe": 设置 → LLM 诊断探测

    Returns:
        dict: 包含以下字段的字典：
            - temperature: float, 默认 0.5
            - max_tokens: int, 默认 4096

    Example:
        >>> params = get_agent_params("solve")
        >>> params["temperature"]  # 0.3
        >>> params["max_tokens"]   # 8192
    """
    defaults = {
        "temperature": 0.5,
        "max_tokens": 4096,
    }
    section_map = {
        "solve": ("capabilities", "solve"),
        "research": ("capabilities", "research"),
        "question": ("capabilities", "question"),
        "co_writer": ("capabilities", "co_writer"),
        "brainstorm": ("tools", "brainstorm"),
        "llm_probe": ("diagnostics", "llm_probe"),
    }
    path = get_runtime_settings_dir(PROJECT_ROOT) / "agents.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing required configuration file: {path}")
    section = section_map.get(module_name)
    if section is None:
        return defaults
    with open(path, encoding="utf-8") as f:
        agents_config = yaml.safe_load(f) or {}
    module_config: dict[str, Any] = agents_config
    for key in section:
        module_config = module_config.get(key, {})
    return {
        "temperature": module_config.get("temperature", defaults["temperature"]),
        "max_tokens": module_config.get("max_tokens", defaults["max_tokens"]),
    }


DEFAULT_CHAT_PARAMS: dict[str, Any] = {
    "temperature": 0.5,
    "max_iterations": 20,
    "responding": {"max_tokens": 8192},
    "answer_now": {"max_tokens": 8192},
}


def get_chat_params() -> dict[str, Any]:
    """
    从 agents.yaml 读取 ``capabilities.chat`` 并与默认值深度合并。

    与 :func:`get_agent_params` 不同，chat 能力有按阶段划分的
    子节（``responding``、``answer_now``），每个子节有独立的
    ``max_tokens``。单个 ``temperature`` 和 ``max_iterations`` 值
    在整个聊天循环中共享。

    Returns:
        dict: 深度合并后的 chat 配置。始终包含 :data:`DEFAULT_CHAT_PARAMS`
        中的每个阶段键，以便调用方无需检查即可索引。
    """
    path = get_runtime_settings_dir(PROJECT_ROOT) / "agents.yaml"
    cfg: dict[str, Any] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            agents_config = yaml.safe_load(f) or {}
        cfg = (agents_config.get("capabilities", {}) or {}).get("chat", {}) or {}
    return _deep_merge(DEFAULT_CHAT_PARAMS, cfg)


__all__ = [
    "PROJECT_ROOT",
    "get_runtime_settings_dir",
    "load_config_with_main",
    "get_path_from_config",
    "parse_language",
    "get_agent_params",
    "get_chat_params",
    "DEFAULT_CHAT_PARAMS",
    "_deep_merge",
]
