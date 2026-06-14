"""多用户层中资源访问和管理员操作的审计日志。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from .context import get_current_user
from .paths import SYSTEM_ROOT, ensure_system_dirs


def _audit_file():
    # 每次调用时解析，以便在测试中通过猴子补丁修改的 SYSTEM_ROOT 无需重新加载模块即可生效。
    return SYSTEM_ROOT / "audit" / "usage.jsonl"


def _write(payload: dict[str, Any]) -> None:
    try:
        ensure_system_dirs()
        with _audit_file().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # 审计操作绝不能中断请求。
        return


def log_usage(
    resource_type: str,
    resource_id: str,
    action: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """记录普通用户对管理员管理资源的访问。

    此处有意不记录管理员的自身访问（管理员会频繁操作自己的工作区，记录每次读取会稀释信号）。
    管理员端的写入事件请使用 :func:`log_admin_action`。
    """
    user = get_current_user()
    if user.is_admin:
        return
    payload: dict[str, Any] = {
        "time": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id,
        "username": user.username,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "action": action,
    }
    if extra:
        payload["extra"] = extra
    _write(payload)


def log_admin_action(
    action: str,
    target_user_id: str | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    """记录管理员端的写入操作（授权变更、用户增删改查等）。

    当前用户（操作者）会被自动捕获；``target_user_id`` 标识操作影响的目标用户（如果有）。
    ``summary`` 可携带简短的非敏感信息描述变更内容。
    """
    user = get_current_user()
    payload: dict[str, Any] = {
        "time": datetime.now(timezone.utc).isoformat(),
        "actor_id": user.id,
        "actor_username": user.username,
        "actor_role": user.role,
        "action": action,
    }
    if target_user_id:
        payload["target_user_id"] = target_user_id
    if summary:
        payload["summary"] = summary
    _write(payload)
