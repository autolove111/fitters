"""
任务 ID 管理器 - 为每个后台任务分配唯一 ID
"""

from datetime import datetime, timedelta
import threading
from typing import Optional
import uuid


class TaskIDManager:
    """任务 ID 管理的单例类"""

    _instance: Optional["TaskIDManager"] = None
    _lock = threading.Lock()
    _task_ids: dict[str, str] = {}  # 任务键 -> 任务 ID
    _task_metadata: dict[str, dict] = {}  # 任务 ID -> 元数据

    @classmethod
    def get_instance(cls) -> "TaskIDManager":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def generate_task_id(self, task_type: str, task_key: str) -> str:
        """
        为任务生成唯一 ID

        Args:
            task_type: 任务类型（如 'kb_init'、'kb_upload'、'question_gen'、'solve'、'research'）
            task_key: 任务唯一标识（如知识库名称、问题 ID 等）

        Returns:
            任务 ID（格式：{task_type}_{timestamp}_{uuid})
        """
        with self._lock:
            # 如果任务已存在，返回已有的 ID
            if task_key in self._task_ids:
                return self._task_ids[task_key]

            # 生成新 ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            task_id = f"{task_type}_{timestamp}_{unique_id}"

            # 保存映射和元数据
            self._task_ids[task_key] = task_id
            self._task_metadata[task_id] = {
                "task_type": task_type,
                "task_key": task_key,
                "created_at": datetime.now().isoformat(),
                "status": "running",
            }

            return task_id

    def get_task_id(self, task_key: str) -> str | None:
        """获取任务 ID"""
        with self._lock:
            return self._task_ids.get(task_key)

    def update_task_status(self, task_id: str, status: str, **kwargs):
        """更新任务状态"""
        with self._lock:
            if task_id in self._task_metadata:
                self._task_metadata[task_id]["status"] = status
                self._task_metadata[task_id].update(kwargs)
                if status in ["completed", "error", "cancelled"]:
                    self._task_metadata[task_id]["finished_at"] = datetime.now().isoformat()

    def get_task_metadata(self, task_id: str) -> dict | None:
        """获取任务元数据"""
        with self._lock:
            return self._task_metadata.get(task_id, {}).copy()

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务（已完成且超过指定小时数的任务）"""
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)

            to_remove = []
            for task_id, metadata in self._task_metadata.items():
                if metadata.get("status") in ["completed", "error", "cancelled"]:
                    finished_at = metadata.get("finished_at")
                    if finished_at:
                        try:
                            finished_time = datetime.fromisoformat(finished_at)
                            if finished_time < cutoff:
                                to_remove.append(task_id)
                        except:
                            pass

            for task_id in to_remove:
                metadata = self._task_metadata.pop(task_id, {})
                task_key = metadata.get("task_key")
                if task_key:
                    self._task_ids.pop(task_key, None)
