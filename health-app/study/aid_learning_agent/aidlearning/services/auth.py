"""
AidLearning 认证服务。

默认禁用（auth.enabled=false），本地用户不受影响。
启用后，所有 API 路由均通过 JWT Bearer Token 进行保护。

快速配置（单用户，通过 data/user/settings/auth.json）：
    1. 设置 enabled=true
    2. 设置 username=<你的用户名>
    3. 生成密码哈希：
           python -c "from aidlearning.services.auth import hash_password; print(hash_password('yourpassword'))"
       将输出粘贴到 password_hash=<hash>

多用户配置（推荐）：
    启用认证并将 username/password_hash 留空。
    在浏览器中访问 /register，第一个注册的用户将获得管理员权限，
    并可在 /admin/users 管理其他用户。

    用户数据存储在 data/user/auth_users.json 中：
        {
            "alice": {"hash": "$2b$12$...", "role": "admin", "created_at": "2026-..."},
            "bob":   {"hash": "$2b$12$...", "role": "user",  "created_at": "2026-..."}
        }
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from aidlearning.services.config import load_auth_settings, load_integrations_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置 — 在模块导入时从运行时 JSON 配置中读取
# ---------------------------------------------------------------------------

_AUTH_SETTINGS = load_auth_settings()
_INTEGRATIONS_SETTINGS = load_integrations_settings()

AUTH_ENABLED: bool = bool(_AUTH_SETTINGS["enabled"])
AUTH_USERNAME: str = str(_AUTH_SETTINGS["username"])
AUTH_PASSWORD_HASH: str = str(_AUTH_SETTINGS["password_hash"])
AUTH_SECRET: str = ""
TOKEN_EXPIRE_HOURS: int = int(_AUTH_SETTINGS["token_expire_hours"])

# PocketBase 认证模式 — 当 integrations.pocketbase_url 已配置且认证已启用时激活。
# 启用后，登录/注册代理到 PocketBase，Token 验证使用
# PocketBase 的 auth-refresh 端点（结果缓存在内存中，无需静态密钥）。
POCKETBASE_BASE_URL: str = str(_INTEGRATIONS_SETTINGS["pocketbase_url"]).rstrip("/")
POCKETBASE_ENABLED: bool = bool(POCKETBASE_BASE_URL) and AUTH_ENABLED

_ALGORITHM = "HS256"


if AUTH_ENABLED and not POCKETBASE_ENABLED and not AUTH_SECRET:
    from aidlearning.multi_user.identity import load_or_create_auth_secret

    AUTH_SECRET = load_or_create_auth_secret()


# ---------------------------------------------------------------------------
# Token 载荷
# ---------------------------------------------------------------------------


@dataclass
class TokenPayload:
    """解码后的 JWT 载荷。"""

    username: str
    role: str
    user_id: str = ""


# ---------------------------------------------------------------------------
# 密码哈希 — 直接使用 bcrypt（passlib 对 bcrypt 4+ 已停止维护）
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """对明文密码进行哈希。使用此函数生成密码哈希。"""
    import bcrypt

    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码是否与存储的 bcrypt 哈希匹配。"""
    import bcrypt

    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 用户存储 — 多用户 JSON 存储，附带可选的 auth.json 引导用户
# ---------------------------------------------------------------------------


def _make_user_record(hashed: str, role: str = "user", created_at: str = "") -> dict[str, Any]:
    """为旧版调用方/测试构建标准用户记录字典。"""
    from aidlearning.multi_user.identity import new_user_id

    return {
        "id": new_user_id(),
        "hash": hashed,
        "role": role,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "disabled": False,
    }


def _load_users() -> dict[str, dict]:
    """
    加载用户存储，如有需要则迁移旧的扁平格式。

    优先级：
      1. 多用户身份存储
      2. auth.json 中的 username + password_hash — 单用户引导用户

    旧格式：{"alice": "$2b$12$..."}
    新格式：{"alice": {"hash": "...", "role": "admin", "created_at": "..."}}
    """
    from aidlearning.multi_user.identity import load_users

    return load_users(AUTH_USERNAME, AUTH_PASSWORD_HASH)


def is_first_user() -> bool:
    """当尚无用户存在时返回 True（第一个注册的用户将成为管理员）。"""
    return len(_load_users()) == 0


def add_user(username: str, plain_password: str, role: str = "user") -> None:
    """
    在 data/user/auth_users.json 中添加或更新用户。

    角色默认为 'user'，传入 role='admin' 可提升权限。当存储为空时，
    第一个用户会自动升级为 'admin'，无论 role 参数如何设置。

    如果文件（及父目录）不存在，会自动创建。
    """
    from aidlearning.multi_user.identity import save_user

    record = save_user(username, hash_password(plain_password), role=role)  # type: ignore[arg-type]
    logger.info("User '%s' saved with role=%r", username, record.get("role", "user"))


def list_users() -> list[dict]:
    """返回用户信息字典列表（username, role, created_at），不包含哈希值。"""
    from aidlearning.multi_user.identity import list_user_info

    return list_user_info(AUTH_USERNAME, AUTH_PASSWORD_HASH)


def delete_user(username: str) -> bool:
    """
    从存储中删除用户。如果用户存在则返回 True。

    """
    from aidlearning.multi_user.identity import delete_user as _delete_user

    if not _delete_user(username):
        return False
    logger.info("User '%s' deleted", username)
    return True


def set_role(username: str, role: str) -> bool:
    """
    更改已有用户的角色。成功时返回 True。

    有效角色：'admin', 'user'。
    """
    if role not in ("admin", "user"):
        raise ValueError(f"Invalid role: {role!r}. Must be 'admin' or 'user'.")

    from aidlearning.multi_user.identity import set_role as _set_role

    if not _set_role(username, role):  # type: ignore[arg-type]
        return False
    logger.info(f"User '{username}' role updated to {role!r}")
    return True


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_token(username: str, role: str = "user", user_id: str | None = None) -> str:
    """为指定用户名和角色创建签名 JWT。"""
    from jose import jwt

    if not user_id:
        record = _load_users().get(username) or {}
        user_id = str(record.get("id") or "")

    payload = {
        "sub": username,
        "role": role,
        "uid": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, AUTH_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> TokenPayload | None:
    """
    验证 Token 并返回 TokenPayload，无效时返回 None。

    - PocketBase 模式：调用 PocketBase 的 auth-refresh 端点（结果缓存在
      内存中 60 秒，因此每个 Token 每分钟仅首次请求会产生网络调用）。
      无需静态 JWT 密钥。
    - 标准模式：使用 AUTH_SECRET 进行本地内存 jwt.decode() — 零网络调用，
      与之前行为一致。
    """
    if not token:
        return None

    if POCKETBASE_ENABLED:
        from aidlearning.services.pocketbase_client import validate_pb_token

        payload = validate_pb_token(token)
        if payload is None:
            return None
        return TokenPayload(
            username=payload["username"],
            role=payload.get("role", "user"),
            user_id=str(payload.get("id") or payload.get("uid") or payload.get("user_id") or ""),
        )

    # 标准 JWT + bcrypt 模式
    from jose import JWTError, jwt

    if not AUTH_SECRET:
        return None

    try:
        payload = jwt.decode(token, AUTH_SECRET, algorithms=[_ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        user_id = str(payload.get("uid") or "")
        if not user_id:
            record = _load_users().get(str(username)) or {}
            user_id = str(record.get("id") or "")
        return TokenPayload(username=username, role=payload.get("role", "user"), user_id=user_id)
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# PocketBase 认证辅助函数
# ---------------------------------------------------------------------------


def authenticate_pb(username: str, password: str) -> tuple[TokenPayload, str] | None:
    """
    通过 PocketBase 进行认证，返回 (TokenPayload, raw_pb_token)。

    仅在 POCKETBASE_ENABLED=True 时调用。
    失败时返回 None。
    raw token 是 PocketBase JWT 字符串，用于存储在 Cookie 中。

    PocketBase 需要邮箱地址；纯用户名会被映射为
    <username>@aidlearning.local 以匹配注册时使用的邮箱。
    """
    try:
        from aidlearning.services.pocketbase_client import get_pb_client

        pb = get_pb_client()
        result = pb.collection("users").auth_with_password(username, password)
        token: str = result.token
        record = result.record
        username = (
            getattr(record, "email", None)
            or getattr(record, "name", None)
            or getattr(record, "id", "unknown")
        )
        # PocketBase 默认没有内置的 "role" 字段；全部视为 "user"。
        # 通过 PocketBase 管理面板认证的管理员使用单独的端点。
        role = getattr(record, "role", "user") or "user"
        user_id = str(getattr(record, "id", "") or "")
        return TokenPayload(username=str(username), role=str(role), user_id=user_id), token
    except Exception as exc:
        logger.warning(f"PocketBase authentication failed: {exc}")
        return None


def register_pb(username: str, email: str, password: str) -> dict | None:
    """
    在 PocketBase 中创建新用户。

    返回创建的用户记录字典，失败时返回 None。
    """
    try:
        from aidlearning.services.pocketbase_client import get_pb_client

        pb = get_pb_client()
        record = pb.collection("users").create(
            {
                "username": username,
                "email": email,
                "password": password,
                "passwordConfirm": password,
            }
        )
        return {"id": record.id, "username": username, "email": email}
    except Exception as exc:
        logger.warning(f"PocketBase registration failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# 认证主入口
# ---------------------------------------------------------------------------


def authenticate(username: str, password: str) -> TokenPayload | None:
    """
    验证凭据。成功时返回 TokenPayload，失败时返回 None。

    当认证被禁用时，始终返回一个虚拟的管理员载荷，
    以便调用方无需特殊处理禁用状态。
    """
    if not AUTH_ENABLED:
        return TokenPayload(username=username or "local", role="admin", user_id="local-admin")

    users = _load_users()
    if not users:
        logger.warning(
            "未配置用户 — 登录将始终失败。"
            "请访问 /register 创建第一个账户。"
        )
        return None

    record = users.get(username)
    if not record:
        return None

    hashed = record.get("hash", "") if isinstance(record, dict) else record
    if not verify_password(password, hashed):
        return None

    role = record.get("role", "user") if isinstance(record, dict) else "user"
    user_id = str(record.get("id") or "") if isinstance(record, dict) else ""
    return TokenPayload(username=username, role=role, user_id=user_id)
