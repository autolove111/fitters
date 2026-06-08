"""聊天附件下载/预览的 HTTP 端点。

对话轮次运行时会将每个上传的附件持久化到
AttachmentStore，并在消息上记录公开 URL。
前端预览抽屉通过此路由加载文件，该路由仅提供存储层返回的路径——每个组件都经过净化处理以防御目录遍历攻击。

URL 格式::

    GET /api/attachments/{session_id}/{attachment_id}/{filename}

session_id 作为 ACL 边界，与应用当前对会话的处理方式一致（单租户，会话归属基于本地信任）。
待多用户认证上线后，应改用签名 URL。
"""

from __future__ import annotations

import logging
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from aidlearning.services.storage import (
    LocalDiskAttachmentStore,
    get_attachment_store,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _content_disposition(filename: str, *, disposition: str = "inline") -> str:
    """构建能正确处理非 ASCII 文件名的 Content-Disposition 头。

    HTTP/1.1 头部使用 latin-1 编码，直接将中文/带重音符号的文件名放入
    filename="..." 会抛出 UnicodeEncodeError。RFC 6266 / RFC 5987 对此有解决方案：
    输出 filename*=UTF-8''<百分比编码> 并在 filename= 上为旧版客户端提供 ASCII 回退。
    """
    ascii_fallback = filename.encode("ascii", errors="replace").decode("ascii")
    # 引号和反斜杠会破坏简单引号字符串格式，需要替换掉。
    ascii_fallback = ascii_fallback.replace('"', "_").replace("\\", "_")
    encoded = quote(filename, safe="")
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


@router.get("/{session_id}/{attachment_id}/{filename:path}")
async def get_attachment(
    session_id: str,
    attachment_id: str,
    filename: str,
):
    """提供之前上传的聊天附件。

    响应使用 Content-Disposition: inline，使浏览器可在 iframe / img 中
    直接预览 PDF 和图片。对于未知类型，浏览器会回退到下载模式，
    这对抽屉的"下载"按钮路径来说是可以接受的。
    """
    store = get_attachment_store()
    if not isinstance(store, LocalDiskAttachmentStore):
        # 未来的远程后端应在此处重定向到签名 URL。
        # 目前本地磁盘是唯一的后端，此分支仅用于防御意外配置。
        raise HTTPException(status_code=501, detail="Attachment backend not servable")

    target = store.resolve_path(
        session_id=session_id,
        attachment_id=attachment_id,
        filename=filename,
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    media_type, _ = mimetypes.guess_type(target.name)
    if not media_type:
        media_type = "application/octet-stream"

    # inline 使浏览器在可能的情况下预览文件，同时保留建议的文件名供抽屉下载操作使用。
    headers = {
        "Content-Disposition": _content_disposition(target.name),
        # 用户上传的数据，不允许中间层缓存。
        "Cache-Control": "private, max-age=0, must-revalidate",
    }
    return FileResponse(path=str(target), media_type=media_type, headers=headers)
