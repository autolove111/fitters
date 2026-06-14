"""
PocketBase 客户端单例。

仅在 integrations.pocketbase_url 已配置时才会初始化。
其他代码在调用 ``get_pb_client()`` 前应先检查 ``is_pocketbase_enabled()``，
以避免在 PocketBase 未配置时出现导入时错误。

Token 验证使用 PocketBase 的 auth-refresh 端点而非本地 JWT 解码
（PocketBase 不暴露静态 JWT 密钥）。结果缓存在内存中 60 秒，
因此每个 Token 每分钟仅首次请求会产生网络调用（约 5-10 毫秒）；
TTL 内的所有后续请求均在 1 毫秒内从本地缓存解析。

用法：
    from aidlearning.services.pocketbase_client import get_pb_client, is_pocketbase_enabled

    if is_pocketbase_enabled():
        pb = get_pb_client()
        result = pb.collection("sessions").get_list(1, 50)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aidlearning.services.config import load_integrations_settings

logger = logging.getLogger(__name__)

_client = None
_client_initialised = False
_client_key = ""

# Token 验证缓存：token -> (payload_dict, expires_at)
_TOKEN_CACHE: dict[str, tuple[dict[str, Any], float]] = {}
_TOKEN_CACHE_TTL: float = 60.0  # 秒


def is_pocketbase_enabled() -> bool:
    """当 integrations.pocketbase_url 已配置时返回 True。"""
    return bool(_pocketbase_settings()["url"])


def _pocketbase_settings() -> dict[str, str]:
    settings = load_integrations_settings()
    return {
        "url": str(settings["pocketbase_url"]).rstrip("/"),
        "admin_email": str(settings["pocketbase_admin_email"]),
        "admin_password": str(settings["pocketbase_admin_password"]),
    }


def get_pb_client():
    """
    返回经过管理员认证的 PocketBase SDK 客户端（缓存单例）。

    如果 integrations.pocketbase_url 未设置则抛出 RuntimeError。
    认证失败时抛出异常。
    """
    global _client, _client_initialised, _client_key

    settings = _pocketbase_settings()
    pocketbase_url = settings["url"]
    admin_email = settings["admin_email"]
    admin_password = settings["admin_password"]

    if not pocketbase_url:
        raise RuntimeError(
            "PocketBase 未配置。请设置 integrations.pocketbase_url 以启用。"
        )

    cache_key = f"{pocketbase_url}|{admin_email}"
    if _client_initialised and _client_key == cache_key:
        return _client

    try:
        from pocketbase import PocketBase  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "'pocketbase' 包未安装。请运行：pip install pocketbase"
        ) from exc

    pb = PocketBase(pocketbase_url)

    if admin_email and admin_password:
        try:
            pb.admins.auth_with_password(admin_email, admin_password)
            logger.info(f"PocketBase admin authenticated at {pocketbase_url}")
        except Exception as exc:
            logger.error(
                f"PocketBase 管理员认证失败：{exc}。"
                "请检查 integrations.pocketbase_admin_email 和 integrations.pocketbase_admin_password。"
            )
            raise
    else:
        logger.warning(
            "integrations.json 中未设置 PocketBase 管理员邮箱/密码。"
            "后端将以无管理员权限连接 PocketBase。"
            "集合管理（scripts/pb_setup.py）将无法工作。"
        )

    _client = pb
    _client_initialised = True
    _client_key = cache_key
    return _client


def validate_pb_token(token: str) -> dict[str, Any] | None:
    """
    验证 PocketBase 用户 Token 并返回用户载荷字典。

    使用 PocketBase 的 /api/collections/users/auth-refresh 端点。
    结果缓存 ``_TOKEN_CACHE_TTL`` 秒，因此每个 Token 每分钟
    仅首次调用会产生网络往返。

    返回至少包含 ``username`` 和 ``role`` 键的字典，
    如果 Token 无效/已过期则返回 None。
    """
    settings = _pocketbase_settings()
    pocketbase_url = settings["url"]
    if not pocketbase_url:
        return None

    now = time.monotonic()

    # 缓存命中
    cached = _TOKEN_CACHE.get(token)
    if cached is not None:
        payload, expires_at = cached
        if now < expires_at:
            return payload
        del _TOKEN_CACHE[token]

    # 缓存未命中 — 调用 PocketBase
    try:
        from pocketbase import PocketBase  # type: ignore[import]

        pb = PocketBase(pocketbase_url)
        # 注入用户 Token 以便 auth_refresh 进行验证
        pb.auth_store.save(token, None)
        result = pb.collection("users").auth_refresh()

        record = result.record
        username = (
            getattr(record, "email", None)
            or getattr(record, "name", None)
            or getattr(record, "username", None)
            or getattr(record, "id", "unknown")
        )
        role = str(getattr(record, "role", "user") or "user")

        payload = {"username": str(username), "role": role}
        _TOKEN_CACHE[token] = (payload, now + _TOKEN_CACHE_TTL)
        return payload

    except Exception as exc:
        logger.debug(f"PocketBase token validation failed: {exc}")
        return None


async def ping_pocketbase() -> bool:
    """
    FastAPI 生命周期启动时调用的异步健康检查。

    如果 PocketBase 可达则返回 True，否则返回 False。
    记录明确的警告（而非异常），使服务器在 PocketBase 已配置但
    暂时不可用时仍能正常启动。
    """
    settings = _pocketbase_settings()
    pocketbase_url = settings["url"]
    if not pocketbase_url:
        return False

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{pocketbase_url}/api/health")
            if resp.status_code == 200:
                logger.info(f"PocketBase health check passed at {pocketbase_url}")
                return True
            logger.warning(
                f"PocketBase 健康检查在 {pocketbase_url} 返回 HTTP {resp.status_code}。"
                "在 PocketBase 恢复正常之前，会话将无法工作。"
            )
            return False
    except Exception as exc:
        logger.warning(
            f"PocketBase 在 {pocketbase_url} 不可达（{exc}）。"
            "会话和认证将回退到 SQLite，直到 PocketBase 可用。"
            "请检查 pocketbase 容器是否正在运行以及 integrations.pocketbase_url 是否正确。"
        )
        return False
