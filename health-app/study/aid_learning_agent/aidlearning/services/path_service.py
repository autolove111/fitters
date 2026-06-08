#!/usr/bin/env python
"""
PathService — 运行时路径管理器

【调用链路位置】BaseSessionManager → PathService → 文件系统

统一管理所有运行时数据路径：
  data/user/
  ├── settings/          — 配置文件（model_catalog.json 等）
  ├── logs/              — 日志
  └── workspace/
      ├── memory/        — 记忆文件
      ├── notebook/      — 笔记
      └── chat/
          ├── chat/            — 对话会话（sessions.json）
          ├── deep_solve/      — 解题会话
          ├── deep_question/   — 出题会话
          └── deep_research/   — 研究会话

支持多用户隔离：多用户模式下 workspace_root 指向 multi-user/<uid>/
"""

from pathlib import Path
from typing import Literal, cast

from aidlearning.runtime.home import PACKAGE_ROOT, get_runtime_data_root

AgentModule = Literal[
    "solve",
    "chat",
    "question",
    "research",
    "run_code_workspace",
    "logs",
]

ChatWorkspaceFeature = Literal[
    "chat",
    "deep_solve",
    "deep_question",
    "deep_research",
    "_detached_code_execution",
]

WorkspaceFeature = Literal[
    "memory",
    "notebook",
    "chat",
]


class PathService:
    """Runtime path manager rooted at a workspace root.

    The default root is the historical ``data/`` directory.  The optional
    multi-user layer instantiates this class with ``multi-user/<uid>/`` so the
    public API can stay the same while disk writes become scoped per user.
    """

    _instance: "PathService | None" = None

    _AGENT_TO_WORKSPACE: dict[str, tuple[str, str | None]] = {
        "solve": ("chat", "deep_solve"),
        "chat": ("chat", "chat"),
        "question": ("chat", "deep_question"),
        "research": ("chat", "deep_research"),
        "run_code_workspace": ("chat", "_detached_code_execution"),
    }
    _PRIVATE_SUFFIXES = {".json", ".sqlite", ".db", ".md", ".yaml", ".yml", ".py", ".log"}

    def __init__(self, workspace_root: Path | None = None):
        self._package_root = PACKAGE_ROOT
        self._uses_default_workspace_root = workspace_root is None
        self._workspace_root = (workspace_root or get_runtime_data_root()).resolve()
        self._project_root = self._workspace_root.parent.resolve()
        self._user_data_dir = (self._workspace_root / "user").resolve()

    @classmethod
    def get_instance(cls) -> "PathService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def user_data_dir(self) -> Path:
        return self._user_data_dir

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    @property
    def package_root(self) -> Path:
        return self._package_root

    def get_user_root(self) -> Path:
        return self._user_data_dir

    def get_knowledge_bases_root(self) -> Path:
        return self._workspace_root / "knowledge_bases"

    def get_chat_history_db(self) -> Path:
        return self._user_data_dir / "chat_history.db"

    def get_public_outputs_root(self) -> Path:
        return self._user_data_dir

    def is_public_output_path(self, path: str | Path) -> bool:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (self.get_public_outputs_root() / candidate).resolve()
        else:
            candidate = candidate.resolve()

        root = self.get_public_outputs_root().resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            return False

        if not candidate.is_file():
            return False
        if candidate.suffix.lower() in self._PRIVATE_SUFFIXES:
            return False

        parts = relative.parts
        if (
            len(parts) >= 5
            and parts[:3] == ("workspace", "chat", "deep_solve")
            and "artifacts" in parts[4:]
        ):
            return True

        if len(parts) >= 5 and parts[:2] == ("workspace", "chat") and "code_runs" in parts[3:]:
            return True

        if len(parts) >= 4 and parts[:3] == ("workspace", "chat", "_detached_code_execution"):
            return True

        return False

    def get_workspace_dir(self) -> Path:
        return self._user_data_dir / "workspace"

    def get_settings_dir(self) -> Path:
        return self._user_data_dir / "settings"

    def get_settings_file(self, name: str) -> Path:
        if "." not in name:
            name = f"{name}.json"
        return self.get_settings_dir() / name

    def get_runtime_config_file(self, name: str) -> Path:
        if not name.endswith(".yaml"):
            name = f"{name}.yaml"
        return self.get_settings_dir() / name

    def get_workspace_feature_dir(self, feature: WorkspaceFeature) -> Path:
        return self.get_workspace_dir() / feature

    def get_chat_workspace_root(self) -> Path:
        return self.get_workspace_feature_dir("chat")

    def get_chat_feature_dir(self, feature: ChatWorkspaceFeature) -> Path:
        return self.get_chat_workspace_root() / feature

    def get_task_workspace(self, feature: str, task_id: str) -> Path:
        task_root = self._resolve_feature_root(feature)
        return task_root / task_id

    def get_session_workspace(self, feature: str, session_id: str) -> Path:
        session_root = self._resolve_feature_root(feature)
        return session_root / session_id

    def _resolve_feature_root(self, feature: str) -> Path:
        if feature in {
            "chat",
            "deep_solve",
            "deep_question",
            "deep_research",
            "_detached_code_execution",
        }:
            return self.get_chat_feature_dir(cast(ChatWorkspaceFeature, feature))
        if feature in {"memory", "notebook"}:
            return self.get_workspace_feature_dir(cast(WorkspaceFeature, feature))
        raise ValueError(f"Unknown workspace feature: {feature}")

    def get_agent_base_dir(self) -> Path:
        return self.get_workspace_dir()

    def get_agent_dir(self, module: str) -> Path:
        if module == "logs":
            return self.get_logs_dir()
        root_name, child_name = self._AGENT_TO_WORKSPACE[module]
        base = self.get_workspace_feature_dir(cast(WorkspaceFeature, root_name))
        return base / child_name if child_name else base

    def get_session_file(self, module: str) -> Path:
        return self.get_agent_dir(module) / "sessions.json"

    def get_task_dir(self, module: str, task_id: str) -> Path:
        return self.get_agent_dir(module) / task_id

    def get_notebook_dir(self) -> Path:
        return self.get_workspace_feature_dir("notebook")

    def get_notebook_file(self, notebook_id: str) -> Path:
        return self.get_notebook_dir() / f"{notebook_id}.json"

    def get_notebook_index_file(self) -> Path:
        return self.get_notebook_dir() / "notebooks_index.json"

    def get_memory_dir(self) -> Path:
        new_dir = self.workspace_root / "memory"
        old_dir = self.get_workspace_feature_dir("memory")
        if self.workspace_root == (self.project_root / "data").resolve() and old_dir.exists():
            new_dir.mkdir(parents=True, exist_ok=True)
            for f in old_dir.iterdir():
                if f.is_file() and f.suffix == ".md":
                    target = new_dir / f.name
                    if not target.exists():
                        import shutil

                        shutil.copy2(f, target)
        return new_dir

    def get_solve_dir(self) -> Path:
        return self.get_chat_feature_dir("deep_solve")

    def get_solve_session_file(self) -> Path:
        return self.get_session_file("solve")

    def get_solve_task_dir(self, task_id: str) -> Path:
        return self.get_task_dir("solve", task_id)

    def get_chat_dir(self) -> Path:
        return self.get_chat_feature_dir("chat")

    def get_chat_session_file(self) -> Path:
        return self.get_session_file("chat")

    def get_question_dir(self) -> Path:
        return self.get_chat_feature_dir("deep_question")

    def get_question_batch_dir(self, batch_id: str) -> Path:
        return self.get_task_dir("question", batch_id)

    def get_research_dir(self) -> Path:
        return self.get_chat_feature_dir("deep_research")

    def get_research_reports_dir(self) -> Path:
        return self.get_research_dir() / "reports"

    def get_run_code_workspace_dir(self) -> Path:
        return self.get_chat_feature_dir("_detached_code_execution")

    def get_logs_dir(self) -> Path:
        return self.get_user_root() / "logs"

    def ensure_agent_dir(self, module: str) -> Path:
        path = self.get_agent_dir(module)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_task_dir(self, module: str, task_id: str) -> Path:
        path = self.get_task_dir(module, task_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_workspace_dir(self) -> Path:
        path = self.get_workspace_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_notebook_dir(self) -> Path:
        path = self.get_notebook_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_memory_dir(self) -> Path:
        path = self.get_memory_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_settings_dir(self) -> Path:
        path = self.get_settings_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_all_directories(self) -> None:
        self.ensure_settings_dir()
        self.ensure_workspace_dir()
        self.ensure_memory_dir()
        self.ensure_notebook_dir()
        self.get_logs_dir().mkdir(parents=True, exist_ok=True)
        for chat_feature in cast(
            tuple[ChatWorkspaceFeature, ...],
            (
                "chat",
                "deep_solve",
                "deep_question",
                "deep_research",
                "_detached_code_execution",
            ),
        ):
            self.get_chat_feature_dir(chat_feature).mkdir(parents=True, exist_ok=True)
        self.get_research_reports_dir().mkdir(parents=True, exist_ok=True)


def get_path_service() -> PathService:
    try:
        from aidlearning.multi_user.paths import get_current_path_service

        return get_current_path_service()
    except Exception:
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "get_path_service() 回退到默认实例；多用户路径解析失败",
            exc_info=True,
        )
        return PathService.get_instance()


__all__ = [
    "AgentModule",
    "ChatWorkspaceFeature",
    "PathService",
    "WorkspaceFeature",
    "get_path_service",
]
