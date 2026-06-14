#!/usr/bin/env python
"""
Prompt Manager — 统一 Prompt 加载管理器

【调用链路位置】BaseAgent.__init__() → get_prompt_manager().load_prompts()

职责：
  - 从 YAML 文件加载 Agent 的 prompt 模板（system prompt、context 模板等）
  - 支持多语言（zh/en），带 fallback 链
  - 内存缓存，避免重复读取文件
  - 支持子目录组织（如 agents/chat/prompts/zh/chat_agent.yaml）
"""

from pathlib import Path
from typing import Any

import yaml

from aidlearning.runtime.home import PACKAGE_ROOT
from aidlearning.services.config import parse_language


class PromptManager:
    """使用单例模式和全局缓存的统一提示词管理器。"""

    _instance: "PromptManager | None" = None
    _cache: dict[str, dict[str, Any]] = {}

    # 语言回退链：如果主语言未找到，尝试替代语言
    LANGUAGE_FALLBACKS = {
        "zh": ["zh", "cn", "en"],
        "en": ["en", "zh", "cn"],
    }

    # 支持的模块
    MODULES = [
        "research",
        "solve",
        "question",
        "co_writer",
        "book",
        "notebook",
        "chat",
    ]

    # 不在 aidlearning/agents/ 目录下的模块
    # 映射 module_name -> aidlearning/ 下的磁盘路径组件
    NON_AGENT_MODULES: dict[str, str] = {
        "book": "book",
        "co_writer": "co_writer",
        "capabilities": "capabilities",
    }

    def __new__(cls) -> "PromptManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_prompts(
        self,
        module_name: str,
        agent_name: str,
        language: str = "zh",
        subdirectory: str | None = None,
    ) -> dict[str, Any]:
        """
        加载 Agent 的提示词。

        Args:
            module_name: 模块名称（research、solve、question、co_writer）
            agent_name: Agent 名称（不含 .yaml 的文件名）
            language: 语言代码（'zh' 或 'en'）
            subdirectory: 可选子目录（如 solve 模块的 'solve_loop'）

        Returns:
            加载的提示词配置字典
        """
        lang_code = parse_language(language)
        cache_key = self._build_cache_key(module_name, agent_name, lang_code, subdirectory)

        if cache_key in self._cache:
            return self._cache[cache_key]

        prompts = self._load_with_fallback(module_name, agent_name, lang_code, subdirectory)
        self._cache[cache_key] = prompts
        return prompts

    def _build_cache_key(
        self,
        module_name: str,
        agent_name: str,
        lang_code: str,
        subdirectory: str | None,
    ) -> str:
        """构建唯一的缓存键。"""
        subdir_part = f"_{subdirectory}" if subdirectory else ""
        return f"{module_name}_{agent_name}_{lang_code}{subdir_part}"

    def _load_with_fallback(
        self,
        module_name: str,
        agent_name: str,
        lang_code: str,
        subdirectory: str | None,
    ) -> dict[str, Any]:
        """加载提示词文件，支持语言回退。"""
        prompt_dirs = self._candidate_prompt_dirs(module_name)
        fallback_chain = self.LANGUAGE_FALLBACKS.get(lang_code, ["en"])

        for prompts_dir in prompt_dirs:
            for lang in fallback_chain:
                prompt_file = self._resolve_prompt_path(prompts_dir, lang, agent_name, subdirectory)
                if prompt_file and prompt_file.exists():
                    try:
                        with open(prompt_file, encoding="utf-8") as f:
                            return yaml.safe_load(f) or {}
                    except Exception as e:
                        print(f"Warning: Failed to load {prompt_file}: {e}")
                        continue

        print(f"Warning: No prompt file found for {module_name}/{agent_name}")
        return {}

    def _candidate_prompt_dirs(self, module_name: str) -> list[Path]:
        """返回模块的旧版和当前提示词根目录。"""
        if module_name in self.NON_AGENT_MODULES:
            legacy_dir = PACKAGE_ROOT / "src" / module_name / "prompts"
            current_dir = PACKAGE_ROOT / "aidlearning" / module_name / "prompts"
            return [legacy_dir, current_dir]

        legacy_dir = PACKAGE_ROOT / "src" / "agents" / module_name / "prompts"
        current_dir = PACKAGE_ROOT / "aidlearning" / "agents" / module_name / "prompts"
        return [legacy_dir, current_dir]

    def _resolve_prompt_path(
        self,
        prompts_dir: Path,
        lang: str,
        agent_name: str,
        subdirectory: str | None,
    ) -> Path | None:
        """解析提示词文件路径，支持子目录和递归搜索。"""
        lang_dir = prompts_dir / lang

        if not lang_dir.exists():
            return None

        # 如果指定了子目录，先在其中查找
        if subdirectory:
            direct_path = lang_dir / subdirectory / f"{agent_name}.yaml"
            if direct_path.exists():
                return direct_path

        # 尝试直接路径
        direct_path = lang_dir / f"{agent_name}.yaml"
        if direct_path.exists():
            return direct_path

        # 在子目录中递归搜索
        found = list(lang_dir.rglob(f"{agent_name}.yaml"))
        if found:
            return found[0]

        return None

    def get_prompt(
        self,
        prompts: dict[str, Any],
        section: str,
        field: str | None = None,
        fallback: str = "",
    ) -> str:
        """
        从已加载配置中安全获取提示词。

        Args:
            prompts: 已加载的提示词字典
            section: 顶层节名称
            field: 可选的嵌套字段名称
            fallback: 未找到时的默认值

        Returns:
            提示词字符串或回退值
        """
        if section not in prompts:
            return fallback

        value = prompts[section]

        if field is None:
            return value if isinstance(value, str) else fallback

        if isinstance(value, dict) and field in value:
            result = value[field]
            return result if isinstance(result, str) else fallback

        return fallback

    def clear_cache(self, module_name: str | None = None) -> None:
        """
        清除缓存的提示词。

        Args:
            module_name: 如果提供，仅清除该模块的缓存
        """
        if module_name:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{module_name}_")]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()

    def reload_prompts(
        self,
        module_name: str,
        agent_name: str,
        language: str = "zh",
        subdirectory: str | None = None,
    ) -> dict[str, Any]:
        """强制重新加载提示词，绕过缓存。"""
        lang_code = parse_language(language)
        cache_key = self._build_cache_key(module_name, agent_name, lang_code, subdirectory)

        if cache_key in self._cache:
            del self._cache[cache_key]

        return self.load_prompts(module_name, agent_name, language, subdirectory)


# 全局单例实例
_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """获取全局 PromptManager 实例。"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


__all__ = ["PromptManager", "get_prompt_manager"]
