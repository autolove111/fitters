#!/usr/bin/env python
"""
系统设置和初始化
结合用户目录初始化和端口配置管理。
"""

import json
import logging
from pathlib import Path

import yaml

from aidlearning.services.path_service import get_path_service

# 初始化设置操作的日志记录器
_setup_logger = None

DEFAULT_INTERFACE_SETTINGS = {
    "theme": "light",
    "language": "en",
    "sidebar_description": "✨ Data Intelligence Lab @ HKU",
    "sidebar_nav_order": {
        "start": ["/", "/history", "/knowledge", "/notebook"],
        "learnResearch": ["/question", "/solver", "/research"],
    },
}

DEFAULT_MAIN_SETTINGS = {
    "system": {
        "language": "en",
    },
    "logging": {
        "level": "WARNING",
        "save_to_file": True,
        "console_output": True,
    },
    "tools": {
        "run_code": {
            "allowed_roots": ["./data/user"],
        },
        "web_search": {
            "enabled": True,
        },
    },
    "capabilities": {
        "solve": {
            "max_iterations_per_step": 7,
            "max_replans": 2,
        },
        "research": {
            "researching": {
                "note_agent_mode": "auto",
                "tool_timeout": 60,
                "tool_max_retries": 2,
                "paper_search_years_limit": 3,
            },
        },
        "question": {
            "exploring": {
                "max_iterations": 8,
                "tool_summarizer": {
                    "enabled": True,
                    "max_tokens": 800,
                },
            },
        },
    },
}

DEFAULT_AGENTS_SETTINGS = {
    "capabilities": {
        "solve": {"temperature": 0.3, "max_tokens": 8192},
        "research": {"temperature": 0.5, "max_tokens": 12000},
        "question": {"temperature": 0.7, "max_tokens": 4096},
        "chat": {
            "temperature": 0.2,
            "responding": {"max_tokens": 8000},
            "answer_now": {"max_tokens": 8000},
        },
    },
    "tools": {
        "brainstorm": {"temperature": 0.8, "max_tokens": 2048},
    },
    "services": {
        "personalization": {"temperature": 0.5, "max_tokens": 8192},
    },
}


def _get_setup_logger():
    """获取设置操作的日志记录器"""
    global _setup_logger
    if _setup_logger is None:
        _setup_logger = logging.getLogger(__name__)
    return _setup_logger


# ============================================================================
# 用户目录初始化
# ============================================================================


def init_user_directories(project_root: Path | None = None) -> None:
    """
    初始化必要的用户数据文件（如果不存在）。

    此函数使用延迟初始化 - 目录在文件保存时按需创建，
    而非在启动时预创建所有目录。

    仅在启动时创建必要的配置文件（如 settings/interface.json）。

    目录结构（由各模块按需创建）：
    data/user/
    ├── chat_history.db
    ├── logs/
    ├── settings/
    │   ├── interface.json
    │   ├── main.yaml
    │   └── agents.yaml
    └── workspace/
        ├── notebook/
        ├── memory/
        └── chat/
            ├── chat/
            ├── deep_solve/
            ├── deep_question/
            ├── deep_research/
            └── _detached_code_execution/

    Args:
        project_root: 项目根目录（已忽略，保留以兼容 API）
    """
    # 使用 PathService 获取所有路径
    path_service = get_path_service()
    path_service.ensure_all_directories()

    # 仅初始化必要的配置文件
    # 目录将在文件保存时按需创建
    _ensure_essential_settings(path_service)


def _ensure_essential_settings(path_service) -> None:
    """
    确保必要的设置文件存在。

    这是启动时所需的最小初始化。
    其他所有目录将在文件保存时按需创建。
    """
    interface_file = path_service.get_settings_file("interface")
    _write_json_if_missing(interface_file, DEFAULT_INTERFACE_SETTINGS)

    main_file = path_service.get_runtime_config_file("main")
    _write_yaml_if_missing(main_file, DEFAULT_MAIN_SETTINGS)

    agents_file = path_service.get_runtime_config_file("agents")
    _write_yaml_if_missing(agents_file, DEFAULT_AGENTS_SETTINGS)

    try:
        from aidlearning.services.config import ensure_runtime_settings_files

        ensure_runtime_settings_files()
    except Exception as e:
        _get_setup_logger().warning(f"Failed to initialise runtime JSON settings: {e}")


def _write_json_if_missing(file_path: Path, payload: dict) -> None:
    """写入 JSON 默认值（仅一次）；不覆盖用户管理的文件。"""
    if file_path.exists():
        return
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        _get_setup_logger().info(f"Created default settings: {file_path}")
    except Exception as e:
        _get_setup_logger().warning(f"Failed to create default JSON file {file_path}: {e}")


def _write_yaml_if_missing(file_path: Path, payload: dict) -> None:
    """写入 YAML 默认值（仅一次）；不覆盖用户管理的文件。"""
    if file_path.exists():
        return
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
        _get_setup_logger().info(f"Created default settings: {file_path}")
    except Exception as e:
        _get_setup_logger().warning(f"Failed to create default YAML file {file_path}: {e}")


# ============================================================================
# 端口配置管理
# ============================================================================
# 端口通过 data/user/settings/system.json 配置。
# ============================================================================


def get_backend_port(project_root: Path | None = None) -> int:
    """
    从运行时设置获取后端端口。

    Returns:
        后端端口号（默认：8001）
    """
    try:
        from aidlearning.services.config.launch_settings import load_launch_settings

        return load_launch_settings(project_root).backend_port
    except Exception as exc:
        logger = _get_setup_logger()
        logger.warning(f"Failed to load backend port from runtime settings: {exc}")
        return 8001


def get_frontend_port(project_root: Path | None = None) -> int:
    """
    从运行时设置获取前端端口。

    Returns:
        前端端口号（默认：3782）
    """
    try:
        from aidlearning.services.config.launch_settings import load_launch_settings

        return load_launch_settings(project_root).frontend_port
    except Exception as exc:
        logger = _get_setup_logger()
        logger.warning(f"Failed to load frontend port from runtime settings: {exc}")
        return 3782


def get_ports(project_root: Path | None = None) -> tuple[int, int]:
    """
    从配置获取后端和前端端口。

    Args:
        project_root: 项目根目录（如果为 None，将尝试自动检测）

    Returns:
        (backend_port, frontend_port) 元组

    Raises:
        SystemExit: 如果端口未配置
    """
    backend_port = get_backend_port(project_root)
    frontend_port = get_frontend_port(project_root)
    return (backend_port, frontend_port)


__all__ = [
    # 用户目录初始化
    "init_user_directories",
    # 端口配置
    "get_backend_port",
    "get_frontend_port",
    "get_ports",
]
