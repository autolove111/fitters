"""Auth router — 认证路由

提供登录、登出、注册、用户管理等接口。
WebSocket 和 HTTP 路由共用同一套鉴权逻辑。

鉴权方式：
  - HTTP: 从 Cookie (dt_token) 或 Authorization: Bearer <token> 头提取 JWT
  - WebSocket: 从 query param ?token= 或 Cookie 提取 JWT
"""

from contextvars import Token as _CtxToken
import logging

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Response,
    WebSocket,
    status,
)
from pydantic import BaseModel, field_validator

from aidlearning.services.config import load_auth_settings

# SameSite=None 允许 cookie 在浏览器通过 127.0.0.1 访问前端、通过 localhost
# 访问后端（同一机器上的不同源）时正常工作。
# 浏览器要求 SameSite=None 时必须设置 Secure=True，但这需要 HTTPS——
# 因此在本地开发中回退为 SameSite=Lax，并提示用户使用 localhost:// URL。
_SECURE = bool(load_auth_settings()["cookie_secure"])
_SAMESITE = "none" if _SECURE else "lax"

from aidlearning.services.auth import (
    AUTH_ENABLED,
    POCKETBASE_ENABLED,
    TOKEN_EXPIRE_HOURS,
    TokenPayload,
    add_user,
    authenticate,
    authenticate_pb,
    create_token,
    decode_token,
    delete_user,
    is_first_user,
    list_users,
    register_pb,
    set_role,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_COOKIE_NAME = "dt_token"
_COOKIE_MAX_AGE = TOKEN_EXPIRE_HOURS * 3600


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """POST /login 端点的请求体。"""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """POST /register 端点的请求体。"""

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        import re

        v = v.strip()
        if not v:
            raise ValueError("Email cannot be empty")
        # 接受标准邮箱地址（PocketBase 模式使用）或纯用户名（内置 SQLite/JSON 认证模式使用）。
        email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        plain_re = re.compile(r"^[A-Za-z0-9_\-.]{3,64}$")
        if not email_re.match(v) and not plain_re.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SetRoleRequest(BaseModel):
    """PUT /users/{username}/role 端点的请求体。"""

    role: str

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in ("admin", "user"):
            raise ValueError("Role must be 'admin' or 'user'")
        return v


class AuthStatusResponse(BaseModel):
    """GET /status 端点的响应体。"""

    enabled: bool
    authenticated: bool
    user_id: str | None = None
    username: str | None = None
    role: str | None = None
    is_admin: bool = False


class UserInfo(BaseModel):
    """GET /users 端点返回的单条用户记录。"""

    id: str = ""
    username: str
    role: str
    created_at: str
    disabled: bool = False


# ---------------------------------------------------------------------------
# 共享辅助函数 — 从 cookie 或 Bearer 头提取 token
# ---------------------------------------------------------------------------


def _bearer_token_from_header(authorization: str | None) -> str | None:
    """解析 Authorization: Bearer <token>，不使用 HTTPBearer。

    HTTPBearer 是基于类的依赖，其 __call__ 注解了 request: Request。
    FastAPI 不会向 WebSocket 依赖解析注入 Request，这会导致使用此依赖的
    路由在挂载 WS 端点时抛出 TypeError。手动解析可保持 require_auth 的
    HTTP/WS 对称性。
    """
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        return token or None
    return None


def _extract_token(authorization: str | None, dt_token: str | None) -> str | None:
    return _bearer_token_from_header(authorization) or dt_token


# ---------------------------------------------------------------------------
# 依赖注入 — 可复用的鉴权守卫，供其他路由使用
# ---------------------------------------------------------------------------


def require_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
    dt_token: str | None = Cookie(default=None),
) -> TokenPayload | None:
    """
    HTTP 路由鉴权依赖 — FastAPI Depends 注入。

    从 Cookie 或 Authorization 头提取 JWT，解码后返回 TokenPayload。
    AUTH_ENABLED=false 时跳过鉴权，返回 None。
    供其他路由通过 Depends(require_auth) 使用。
    """
    if not AUTH_ENABLED:
        from aidlearning.multi_user.context import set_current_user
        from aidlearning.multi_user.paths import local_admin_user

        set_current_user(local_admin_user())
        return None

    token = _extract_token(authorization, dt_token)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from aidlearning.multi_user.context import set_current_user, user_from_token_payload

    set_current_user(user_from_token_payload(payload))
    return payload


class _WsAuthFailed:
    """哨兵对象：ws_require_auth 鉴权失败并已关闭 WebSocket。"""


ws_auth_failed: _WsAuthFailed = _WsAuthFailed()


async def ws_require_auth(ws: WebSocket) -> _CtxToken | _WsAuthFailed:
    """
    WebSocket 鉴权 — 在 ws.accept() 之前调用。

    从 query param ?token= 或 Cookie 提取 JWT，解码后设置用户上下文。
    失败则关闭连接(4001)并返回 ws_auth_failed，调用方应立即 return。
    成功返回 ContextVar reset token，用完后需 reset_current_user(token)。

    调用方式见 chat.py websocket_chat()。
    """
    from aidlearning.multi_user.context import set_current_user, user_from_token_payload
    from aidlearning.multi_user.paths import local_admin_user
    from aidlearning.services.auth import AUTH_ENABLED, decode_token

    if not AUTH_ENABLED:
        return set_current_user(local_admin_user())

    token = ws.query_params.get("token") or ws.cookies.get("dt_token")
    payload = decode_token(token) if token else None
    if not payload:
        await ws.close(code=4001)
        return ws_auth_failed

    return set_current_user(user_from_token_payload(payload))


def require_admin(
    payload: TokenPayload | None = Depends(require_auth),
) -> TokenPayload:
    """
    要求调用者为管理员的 FastAPI 依赖。

    当认证用户不是管理员时抛出 HTTP 403。
    当 AUTH_ENABLED=false 时，所有请求均视为管理员。
    """
    if not AUTH_ENABLED:
        from aidlearning.services.auth import TokenPayload as TP

        return TP(username="local", role="admin", user_id="local-admin")

    if payload is None or payload.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return payload


# ---------------------------------------------------------------------------
# 公开端点（无需认证）
# ---------------------------------------------------------------------------


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    authorization: str | None = Header(default=None, alias="Authorization"),
    dt_token: str | None = Cookie(default=None),
) -> AuthStatusResponse:
    """返回认证是否启用以及当前请求是否已认证。"""
    if not AUTH_ENABLED:
        return AuthStatusResponse(
            enabled=False,
            authenticated=True,
            user_id="local-admin",
            username="local",
            role="admin",
            is_admin=True,
        )

    token = _extract_token(authorization, dt_token)
    payload = decode_token(token) if token else None
    return AuthStatusResponse(
        enabled=True,
        authenticated=payload is not None,
        user_id=payload.user_id if payload else None,
        username=payload.username if payload else None,
        role=payload.role if payload else None,
        is_admin=payload.role == "admin" if payload else False,
    )


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> dict:
    """验证凭据并设置 JWT cookie。"""
    if not AUTH_ENABLED:
        return {"ok": True, "message": "Auth is disabled — no login required."}

    if POCKETBASE_ENABLED:
        # PocketBase 模式：邮箱 = username 字段，为兼容现有的 LoginRequest 模式；
        # 用户可以将邮箱作为 "username" 传入。
        pb_result = authenticate_pb(body.username, body.password)
        if not pb_result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        payload, pb_token = pb_result
        response.set_cookie(
            key=_COOKIE_NAME,
            value=pb_token,
            httponly=True,
            samesite=_SAMESITE,
            max_age=_COOKIE_MAX_AGE,
            secure=_SECURE,
        )
        logger.info(f"User '{payload.username}' logged in via PocketBase (role={payload.role!r})")
        return {
            "ok": True,
            "user_id": payload.user_id,
            "username": payload.username,
            "role": payload.role,
            "is_admin": payload.role == "admin",
        }

    # 标准 JWT + bcrypt 模式
    result = authenticate(body.username, body.password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_token(result.username, result.role, result.user_id)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=_SAMESITE,
        max_age=_COOKIE_MAX_AGE,
        secure=_SECURE,
    )

    logger.info(f"User '{result.username}' logged in (role={result.role!r})")
    return {
        "ok": True,
        "user_id": result.user_id,
        "username": result.username,
        "role": result.role,
        "is_admin": result.role == "admin",
    }


@router.post("/logout")
async def logout(response: Response) -> dict:
    """清除 JWT cookie。"""
    response.delete_cookie(key=_COOKIE_NAME, samesite=_SAMESITE)
    return {"ok": True}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest) -> dict:
    """
    仅限引导注册。

    公开端点，在用户存储为空时创建第一个管理员账户。
    一旦管理员存在，此端点将关闭；后续账户必须由管理员通过
    POST /api/v1/auth/users 创建。

    仅在 AUTH_ENABLED=true 时可用。
    """
    if not AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth is disabled — registration is not available.",
        )

    if POCKETBASE_ENABLED:
        # PocketBase 部署文档定义为单用户模式。保持注册关闭，
        # 要求管理员在 PocketBase 管理界面中配置用户。
        if not is_first_user():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-registration is closed. Ask an administrator to create your account.",
            )
        result = register_pb(username=body.username, email=body.username, password=body.password)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Registration failed — username or email may already be taken.",
            )
        logger.info(f"First user registered via PocketBase: '{body.username}'")
        return {
            "ok": True,
            "user_id": result.get("id", ""),
            "username": body.username,
            "role": "user",
            "is_first_user": True,
            "is_admin": False,
        }

    # 标准模式——仅在第一个管理员创建之前允许。
    if not is_first_user():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is closed. Ask an administrator to create your account.",
        )

    existing = {u["username"] for u in list_users()}
    if body.username in existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    add_user(body.username, body.password)
    user_id = ""
    role = "user"
    for item in list_users():
        if item.get("username") == body.username:
            user_id = str(item.get("id") or "")
            role = str(item.get("role") or "user")
            break
    logger.info(f"First user (admin) registered: '{body.username}'")
    return {
        "ok": True,
        "user_id": user_id,
        "username": body.username,
        "role": role,
        "is_first_user": True,
        "is_admin": role == "admin",
    }


@router.get("/is_first_user")
async def check_is_first_user() -> dict:
    """返回用户存储是否为空（注册界面使用）。"""
    return {"is_first_user": is_first_user() if AUTH_ENABLED else False}


# ---------------------------------------------------------------------------
# 仅限管理员的端点
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserInfo])
async def get_users(_: TokenPayload = Depends(require_admin)) -> list[UserInfo]:
    """列出所有已注册用户。需要管理员角色。"""
    return [UserInfo(**u) for u in list_users()]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: RegisterRequest,
    current: TokenPayload = Depends(require_admin),
) -> dict:
    """仅限管理员：创建新用户账户。

    在第一个管理员存在后，替代公开的 /register 流程。
    新账户始终以 role=user 创建；管理员可稍后通过
    PUT /users/{username}/role 进行角色提升。
    """
    if not AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth is disabled — user creation is not available.",
        )

    if POCKETBASE_ENABLED:
        result = register_pb(username=body.username, email=body.username, password=body.password)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Failed to create user — username may already be taken.",
            )
        logger.info(
            f"Admin '{current.username if current else 'local'}' created PocketBase user "
            f"'{body.username}'"
        )
        return {
            "ok": True,
            "user_id": result.get("id", ""),
            "username": body.username,
            "role": "user",
            "is_admin": False,
        }

    existing = {u["username"] for u in list_users()}
    if body.username in existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    add_user(body.username, body.password)
    user_id = ""
    role = "user"
    for item in list_users():
        if item.get("username") == body.username:
            user_id = str(item.get("id") or "")
            role = str(item.get("role") or "user")
            break
    logger.info(
        f"Admin '{current.username if current else 'local'}' created user '{body.username}' "
        f"(role={role!r})"
    )
    return {
        "ok": True,
        "user_id": user_id,
        "username": body.username,
        "role": role,
        "is_admin": role == "admin",
    }


@router.delete("/users/{username}", status_code=status.HTTP_200_OK)
async def remove_user(
    username: str,
    current: TokenPayload = Depends(require_admin),
) -> dict:
    """删除用户。管理员不能删除自己的账户。"""
    if current and username == current.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    removed = delete_user(username)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    logger.info(f"Admin '{current.username if current else 'local'}' deleted user '{username}'")
    return {"ok": True}


@router.put("/users/{username}/role", status_code=status.HTTP_200_OK)
async def update_user_role(
    username: str,
    body: SetRoleRequest,
    current: TokenPayload = Depends(require_admin),
) -> dict:
    """更改用户角色。管理员不能更改自己的角色。"""
    if current and username == current.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )

    updated = set_role(username, body.role)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    logger.info(
        f"Admin '{current.username if current else 'local'}' set '{username}' role to {body.role!r}"
    )
    return {"ok": True, "username": username, "role": body.role}
