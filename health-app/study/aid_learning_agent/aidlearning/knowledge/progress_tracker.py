"""
进度跟踪器 - 跟踪知识库初始化进度
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from enum import Enum
import json
import logging
from pathlib import Path

# 使用统一日志系统

_logger = logging.getLogger(__name__)


def _logger_instance():
    return _logger


class ProgressStage(Enum):
    """初始化阶段"""

    INITIALIZING = "initializing"  # 初始化中
    PROCESSING_DOCUMENTS = "processing_documents"  # 处理文档
    PROCESSING_FILE = "processing_file"  # 处理单个文件
    COMPLETED = "completed"  # 已完成
    ERROR = "error"  # 错误


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self, kb_name: str, base_dir: Path):
        self.kb_name = kb_name
        self.base_dir = base_dir
        self.kb_dir = base_dir / kb_name
        self.progress_file = self.kb_dir / ".progress.json"
        self._callbacks: list = []  # 支持多个回调
        self.task_id: str | None = None  # 任务 ID（用于日志标识）

    def set_callback(self, callback: Callable[[dict], None]):
        """设置进度回调函数（可多次调用以添加多个回调）"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[dict], None]):
        """移除进度回调函数"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify(self, progress: dict):
        """通知进度更新（调用所有回调）"""
        from aidlearning.runtime.mode import is_server

        if is_server():
            try:
                from aidlearning.api.utils.progress_broadcaster import ProgressBroadcaster

                broadcaster = ProgressBroadcaster.get_instance()

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(broadcaster.broadcast(self.kb_name, progress))
                except RuntimeError:
                    pass
            except (ImportError, Exception):
                pass

        for callback in self._callbacks:
            try:
                callback(progress)
            except Exception as e:
                _logger_instance().debug("Progress callback error: %s", e)

    def _save_progress(self, progress: dict):
        """将进度保存到 kb_config.json 和本地 .progress.json 文件"""
        # 保存到 kb_config.json（集中配置）
        try:
            from aidlearning.knowledge.manager import KnowledgeBaseManager

            manager = KnowledgeBaseManager(base_dir=str(self.base_dir))

            # 根据阶段确定状态
            stage = progress.get("stage", "")
            if stage == "completed":
                status = "ready"
            elif stage == "error":
                status = "error"
            elif stage in [
                "initializing",
                "processing_documents",
                "processing_file",
            ]:
                status = "processing"
            else:
                status = "initializing"

            # 更新 kb_config.json 的状态和进度
            manager.update_kb_status(
                name=self.kb_name,
                status=status,
                progress={
                    "stage": progress.get("stage"),
                    "message": progress.get("message"),
                    "percent": progress.get("progress_percent", 0),
                    "current": progress.get("current", 0),
                    "total": progress.get("total", 0),
                    "file_name": progress.get("file_name"),
                    "error": progress.get("error"),
                    "timestamp": progress.get("timestamp"),
                    "task_id": progress.get("task_id"),
                    "indexed_count": progress.get("indexed_count"),
                    "index_changed": progress.get("index_changed"),
                    "index_action": progress.get("index_action"),
                },
            )
        except Exception as e:
            _logger_instance().warning("Failed to save progress to kb_config.json: %s", e)

        # 持久化最近的进度快照，以便 websocket 订阅者和页面重新加载
        # 可以恢复实时状态，而不依赖内存中的回调。
        try:
            self.kb_dir.mkdir(parents=True, exist_ok=True)
            temp_progress_file = self.progress_file.parent / f"{self.progress_file.name}.tmp"
            with open(temp_progress_file, "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
                f.flush()
            temp_progress_file.replace(self.progress_file)
        except Exception as e:
            _logger_instance().warning(
                "Failed to persist progress snapshot for '%s': %s", self.kb_name, e
            )

    def update(
        self,
        stage: ProgressStage,
        message: str = "",
        current: int = 0,
        total: int = 0,
        file_name: str = "",
        error: str | None = None,
        indexed_count: int | None = None,
        index_changed: bool | None = None,
        index_action: str | None = None,
    ):
        """更新进度"""
        progress = {
            "kb_name": self.kb_name,
            "task_id": self.task_id,
            "stage": stage.value,
            "message": message,
            "current": current,
            "total": total,
            "file_name": file_name,
            "progress_percent": int(current / total * 100) if total > 0 else 0,
            "timestamp": datetime.now().isoformat(),
        }
        if indexed_count is not None:
            progress["indexed_count"] = indexed_count
        if index_changed is not None:
            progress["index_changed"] = index_changed
        if index_action:
            progress["index_action"] = index_action

        if error:
            progress["error"] = error
            progress["stage"] = ProgressStage.ERROR.value

        # 输出到日志记录器（终端和日志文件）
        try:
            logger = _logger_instance()
            prefix = f"[{self.task_id}]" if self.task_id else ""

            if total > 0:
                percent = progress["progress_percent"]
                progress_msg = f"{prefix} {message} ({current}/{total}, {percent}%)"
                if file_name:
                    progress_msg += f" - File: {file_name}"
            else:
                progress_msg = f"{prefix} {message}"
                if file_name:
                    progress_msg += f" - File: {file_name}"

            if error:
                logger.error(f"{progress_msg} - Error: {error}")
            else:
                logger.info(progress_msg)
        except Exception:
            # 如果统一日志意外失败，使用标准库日志记录器作为回退。
            fallback_logger = logging.getLogger("aidlearning.ProgressTracker")
            prefix = f"[{self.task_id}]" if self.task_id else ""
            fallback_logger.warning(
                "%s [ProgressTracker] %s (%s/%s)",
                prefix,
                message,
                current,
                total if total > 0 else "?",
            )
            if error:
                fallback_logger.error("%s [ProgressTracker] Error: %s", prefix, error)

        self._save_progress(progress)

        if self.task_id:
            try:
                from aidlearning.api.utils.task_log_stream import get_task_stream_manager

                get_task_stream_manager().emit(self.task_id, "progress", progress)
            except Exception as e:
                _logger_instance().debug("Failed to emit task progress event: %s", e)

        self._notify(progress)

    def get_progress(self) -> dict | None:
        """获取当前进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                _logger_instance().debug(f"Failed to read progress file for '{self.kb_name}': {e}")

        try:
            from aidlearning.knowledge.manager import KnowledgeBaseManager

            manager = KnowledgeBaseManager(base_dir=str(self.base_dir))
            status = manager.get_kb_status(self.kb_name)
            if status and status.get("progress"):
                return status.get("progress")
        except Exception as e:
            _logger_instance().debug(
                "Failed to recover progress snapshot from kb_config for '%s': %s",
                self.kb_name,
                e,
            )

        return None

    def clear(self):
        """清除进度文件"""
        if self.progress_file.exists():
            try:
                self.progress_file.unlink()
            except Exception as e:
                _logger_instance().debug(f"Failed to clear progress file for '{self.kb_name}': {e}")
