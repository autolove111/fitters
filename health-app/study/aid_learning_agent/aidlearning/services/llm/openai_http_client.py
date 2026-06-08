"""OpenAI 兼容 SDK Provider 的 HTTP 客户端辅助函数。"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

import httpx

from aidlearning.services.config import load_system_settings
from aidlearning.services.llm.exceptions import LLMConfigError

logger = logging.getLogger(__name__)

_warning_lock = threading.Lock()
_warning_logged = False


def disable_ssl_verify_enabled() -> bool:
    """返回是否应禁用出站 TLS 验证。"""
    if not load_system_settings()["disable_ssl_verify"]:
        return False
    if os.getenv("ENVIRONMENT", "").strip().lower() in {"prod", "production"}:
        raise LLMConfigError("DISABLE_SSL_VERIFY is not allowed in production")
    global _warning_logged
    with _warning_lock:
        if not _warning_logged:
            logger.warning(
                "SSL verification is disabled via DISABLE_SSL_VERIFY. This is unsafe "
                "and must not be used in production environments."
            )
            _warning_logged = True
    return True


def build_openai_http_client(**kwargs: Any) -> httpx.AsyncClient | None:
    """当 DISABLE_SSL_VERIFY 启用时构建自定义 SDK httpx 客户端。"""
    if not disable_ssl_verify_enabled():
        return None
    return httpx.AsyncClient(verify=False, **kwargs)  # nosec B501


def openai_client_kwargs(**httpx_kwargs: Any) -> dict[str, httpx.AsyncClient]:
    """返回传递给 ``AsyncOpenAI`` 的 kwargs 以实现自定义 HTTP 行为。"""
    client = build_openai_http_client(**httpx_kwargs)
    return {"http_client": client} if client is not None else {}


__all__ = [
    "build_openai_http_client",
    "disable_ssl_verify_enabled",
    "openai_client_kwargs",
]
