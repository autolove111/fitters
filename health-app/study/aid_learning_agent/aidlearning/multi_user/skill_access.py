"""非管理员用户的技能可见性守卫。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .context import get_current_user
from .grants import load_grant
from .paths import get_admin_path_service


def assigned_skill_ids(user_id: str | None = None) -> set[str]:
    user = get_current_user()
    uid = user_id or user.id
    return {
        str(item.get("skill_id") or item.get("id") or "").strip()
        for item in load_grant(uid).get("skills", []) or []
        if str(item.get("skill_id") or item.get("id") or "").strip()
    }


def _admin_skill_service():
    """返回以管理员工作区为根目录的 SkillService（用于加载已分配的技能）。"""
    from aidlearning.services.skill.service import SkillService

    return SkillService(root=get_admin_path_service().get_workspace_dir() / "skills")


def assigned_skill_infos(user_id: str | None = None) -> list[dict[str, Any]]:
    """返回分配给用户的管理员技能的 SkillInfo 格式字典。

    每个字典都标注了 ``source="admin"`` 和 ``assigned=True``，以便 UI 将其与用户自己的技能并列显示。
    """
    allowed = assigned_skill_ids(user_id)
    if not allowed:
        return []
    out: list[dict[str, Any]] = []
    for info in _admin_skill_service().list_skills():
        if info.name in allowed:
            entry = info.to_dict()
            entry.update({"source": "admin", "assigned": True, "read_only": True})
            out.append(entry)
    return out


def assigned_skill_detail(name: str) -> dict[str, Any] | None:
    """返回管理员分配技能的 SkillDetail 格式字典，或 None。

    调用方应已验证该技能已分配给当前用户（例如通过 ``assert_skill_allowed``）。
    """
    try:
        detail = _admin_skill_service().get_detail(name)
    except Exception:
        return None
    payload = detail.to_dict()
    payload.update({"source": "admin", "assigned": True, "read_only": True})
    return payload


def assert_skill_allowed(name: str) -> None:
    """当非管理员用户尝试读取非自己拥有且未被管理员授权的技能时，抛出 403 错误。

    ``user_owns_skill`` 由调用方单独传入（技能路由器已知该名称是否存在于用户自己的工作区中）。
    """
    user = get_current_user()
    if user.is_admin:
        return
    if name not in assigned_skill_ids(user.id):
        raise HTTPException(status_code=403, detail="Skill is not assigned to you")
