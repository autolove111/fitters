"""聊天附件的持久化存储。

聊天轮次运行时在文档提取器运行*之前*将每个上传附件的字节写入此处。
持久化后，URL 被记录到消息上，内存中的 base64 被丢弃
（提取器仍会清除 Office 文档的 base64 以节省数据库空间）。
前端随后通过 :mod:`aidlearning.api.routers.attachments` 端点获取原始文件以渲染预览。

设计目标
--------

* **默认本地磁盘**：适用于单容器 Docker 部署（``data/user`` 卷已挂载）
  和纯 Linux 服务器，无需额外基础设施。
* **可插拔**：精简的 :class:`AttachmentStore` 协议为 S3 / MinIO / GCS
  后端留出空间，无需修改调用点。
* **路径安全**：通过 WS 传入的文件名会被清理；解析后的路径必须保持在
  配置的根目录内。

磁盘布局为::

    {root}/{session_id}/{attachment_id}_{filename}

``attachment_id`` 前缀防止同一会话中上传同名文件时的冲突。
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import quote

from aidlearning.services.config import load_system_settings
from aidlearning.services.path_service import get_path_service

logger = logging.getLogger(__name__)


_DEFAULT_SUBPATH = ("workspace", "chat", "attachments")
# 由 aidlearning.api.routers.attachments 提供的公共路由前缀
_PUBLIC_URL_PREFIX = "/api/attachments"


def safe_filename(name: str) -> str:
    """将文件系统不安全的字符替换为下划线。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip(". ")


def _coerce_filename(filename: str) -> str:
    """将文件名缩减为安全的基本名称。

    * 去除任何目录组件（防止 ``../`` 遍历攻击）。
    * 替换文件系统不安全的字符。
    * 如果结果为空则回退为 ``"file"``。
    """
    base = os.path.basename(filename or "")
    cleaned = safe_filename(base)
    return cleaned or "file"


@runtime_checkable
class AttachmentStore(Protocol):
    """聊天附件的存储后端。

    实现必须可以从 asyncio 上下文中安全调用。
    默认的 :class:`LocalDiskAttachmentStore` 使用 ``run_in_executor``
    将阻塞磁盘 I/O 移出事件循环。
    """

    async def put(
        self,
        *,
        session_id: str,
        attachment_id: str,
        filename: str,
        data: bytes,
        mime_type: str = "",
    ) -> str:
        """持久化 *data* 并返回前端可获取的公共 URL。

        返回的 URL 相对于 API 源（如 ``"/api/attachments/<sid>/<aid>/<name>"``）。
        失败时抛出异常是可以的 —— 调用方会记录错误并在没有 ``url`` 的情况下继续。
        """

    async def delete_session(self, session_id: str) -> None:
        """尽力清理 *session_id* 的所有附件。"""

    async def delete_attachment(self, session_id: str, attachment_id: str) -> None:
        """尽力清理由 *attachment_id* 标识的单个附件。"""

    def resolve_path(self, *, session_id: str, attachment_id: str, filename: str) -> Path | None:
        """返回附件在磁盘上的绝对路径，如果不存在或超出存储根目录则返回 ``None``。

        由静态路由器用于提供文件服务；远程存储后端可以返回 ``None``，
        路由器将回退到重定向。
        """


class LocalDiskAttachmentStore:
    """默认的 :class:`AttachmentStore` 后端，写入本地磁盘。

    根目录默认为项目根目录下的 ``data/user/workspace/chat/attachments``
    （与 :class:`PathService` 的公开输出匹配）。
    可通过 ``data/user/settings/system.json`` 的 ``chat_attachment_dir`` 覆盖。
    """

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = _attachment_root()
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def _stored_filename(self, attachment_id: str, filename: str) -> str:
        return f"{attachment_id}_{_coerce_filename(filename)}"

    def _session_dir(self, session_id: str) -> Path:
        sid = _coerce_filename(session_id)
        return (self._root / sid).resolve()

    def _safe_join(self, session_id: str, name: str) -> Path | None:
        """将 *name* 连接到会话目录下，并确认结果保持在 ``self._root`` 内。
        如果检测到路径遍历则返回 ``None``。
        """
        session_dir = self._session_dir(session_id)
        # 即使候选路径尚不存在也进行解析 —— 防止基于符号链接的攻击，
        # 该攻击可能在创建后指向根目录之外。
        candidate = (session_dir / name).resolve()
        try:
            candidate.relative_to(self._root.resolve())
        except ValueError:
            return None
        return candidate

    async def put(
        self,
        *,
        session_id: str,
        attachment_id: str,
        filename: str,
        data: bytes,
        mime_type: str = "",
    ) -> str:
        del mime_type  # 本地磁盘不需要
        stored = self._stored_filename(attachment_id, filename)
        target = self._safe_join(session_id, stored)
        if target is None:
            raise ValueError(f"refusing to write attachment outside storage root: {stored!r}")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_sync, target, data)

        # 路由器使用相同的 _coerce_filename 规则查找文件，
        # 因此公共 URL 必须使用清理后的片段。每个路径段都经过百分比编码，
        # 使文件名中的空格/Unicode/标点符号在各浏览器的 fetch / <iframe> 中一致传递。
        sid = quote(_coerce_filename(session_id), safe="")
        aid = quote(attachment_id, safe="")
        name = quote(_coerce_filename(filename), safe="")
        return f"{_PUBLIC_URL_PREFIX}/{sid}/{aid}/{name}"

    @staticmethod
    def _write_sync(target: Path, data: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        # 原子写入：先写入 .tmp 再重命名。避免通过静态处理器暴露写入一半的文件。
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            with tmp.open("wb") as fh:
                fh.write(data)
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    async def delete_session(self, session_id: str) -> None:
        session_dir = self._session_dir(session_id)
        if not session_dir.exists():
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._rmtree_sync, session_dir)

    async def delete_attachment(self, session_id: str, attachment_id: str) -> None:
        session_dir = self._session_dir(session_id)
        if not session_dir.exists():
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._delete_attachment_sync, session_dir, attachment_id)

    @staticmethod
    def _rmtree_sync(path: Path) -> None:
        import shutil

        try:
            shutil.rmtree(path)
        except OSError as exc:
            logger.warning("failed to clean up attachment dir %s: %s", path, exc)

    @staticmethod
    def _delete_attachment_sync(session_dir: Path, attachment_id: str) -> None:
        prefix = f"{attachment_id}_"
        for entry in session_dir.iterdir():
            if entry.name.startswith(prefix):
                try:
                    entry.unlink()
                except OSError as exc:
                    logger.warning("failed to delete attachment file %s: %s", entry, exc)
        try:
            if session_dir.exists() and not any(session_dir.iterdir()):
                session_dir.rmdir()
        except OSError as exc:
            logger.warning("failed to remove empty attachment dir %s: %s", session_dir, exc)

    def resolve_path(self, *, session_id: str, attachment_id: str, filename: str) -> Path | None:
        stored = self._stored_filename(attachment_id, filename)
        target = self._safe_join(session_id, stored)
        if target is None or not target.is_file():
            return None
        return target


_stores: dict[str, AttachmentStore] = {}


def get_attachment_store() -> AttachmentStore:
    """返回进程范围的 :class:`AttachmentStore`。

    目前始终是 :class:`LocalDiskAttachmentStore`；
    未来的 S3/MinIO 后端可在此基于环境变量选择。
    """
    root = _attachment_root()
    key = str(root)
    if key not in _stores:
        _stores[key] = LocalDiskAttachmentStore(root=root)
    return _stores[key]


def _attachment_root() -> Path:
    override = str(load_system_settings().get("chat_attachment_dir") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return get_path_service().get_user_root().joinpath(*_DEFAULT_SUBPATH).resolve()


def reset_attachment_store() -> None:
    """重置单例 —— 仅用于测试。"""
    _stores.clear()
