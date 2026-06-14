"""AidLearning 的可选多用户支持。

该包刻意与旧版单用户服务隔离。现有代码仅在 auth.json 启用认证时通过薄适配器进入。

后端支持矩阵
----------------------

默认的 JSON/SQLite 后端（``integrations.pocketbase_url`` 为空）是受支持的多用户路径：
``multi-user/<uid>/`` 下的每用户工作区、每用户 SQLite 会话数据库，以及基于 JWT 的认证。

PocketBase 模式（设置了 ``integrations.pocketbase_url``）目前**仅支持单用户**：
PocketBase 的 ``users`` 集合默认没有 ``role`` 字段（每次登录都解析为 ``role="user"``，无法创建管理员），
且 ``sessions`` / ``messages`` / ``turns`` 集合在查询中未按 ``user_id`` 过滤。
在更新 schema 和查询之前，请将 PocketBase 部署视为单用户模式。
"""

from .models import CurrentUser, UserRecord, UserScope

__all__ = ["CurrentUser", "UserRecord", "UserScope"]
