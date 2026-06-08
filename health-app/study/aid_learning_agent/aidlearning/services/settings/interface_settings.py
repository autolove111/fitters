"""
界面（UI）设置读取器。

这是用户选择的 UI 语言/主题的权威后端数据源，存储在：
  data/user/settings/interface.json
"""

from __future__ import annotations

import json
from typing import Any

from aidlearning.services.path_service import get_path_service

DEFAULT_UI_SETTINGS: dict[str, Any] = {
    "theme": "light",
    "language": "en",
}


def _interface_settings_file():
    # 每次调用时解析，以便每用户的 PathService（在认证后设置）
    # 将读取路由到调用方自己的 ``settings/interface.json``，
    # 而不是导入时冻结的管理员作用域。
    return get_path_service().get_settings_file("interface")


def _normalize_language(language: Any, default: str = "en") -> str:
    """
    标准化语言代码：
    - en/english -> en
    - zh/chinese/cn -> zh
    """
    if language is None or language == "":
        language = default

    if isinstance(language, str):
        s = language.lower().strip()
        if s in {"en", "english"}:
            return "en"
        if s in {"zh", "chinese", "cn"}:
            return "zh"

    # 回退到默认值
    if isinstance(default, str):
        return _normalize_language(default, "en")
    return "en"


def get_ui_settings() -> dict[str, Any]:
    """
    从 interface.json 读取 UI 设置并应用默认值。

    Returns:
        至少包含以下键的字典：{"theme": "...", "language": "..."}
    """
    settings_file = _interface_settings_file()
    if settings_file.exists():
        try:
            with open(settings_file, encoding="utf-8") as f:
                saved = json.load(f) or {}
            merged = {**DEFAULT_UI_SETTINGS, **saved}
            merged["language"] = _normalize_language(
                merged.get("language"), DEFAULT_UI_SETTINGS["language"]
            )
            return merged
        except Exception:
            # 任何解析错误时回退到默认值（安全）
            return DEFAULT_UI_SETTINGS.copy()

    return DEFAULT_UI_SETTINGS.copy()


def get_ui_language(default: str = "en") -> str:
    """
    获取当前 UI 语言。

    优先级：
    1) interface.json
    2) 提供的默认值
    3) 'en'
    """
    settings = get_ui_settings()
    return _normalize_language(settings.get("language"), default)
