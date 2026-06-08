"""技能服务：加载用户编写的 SKILL.md 文件并注入到聊天系统提示中。"""

from aidlearning.services.skill.service import SkillService, get_skill_service

__all__ = ["SkillService", "get_skill_service"]
