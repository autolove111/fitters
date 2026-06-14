"""聊天会话工件的可插拔存储后端。

目前仅暴露 :mod:`attachment_store`，将用户上传的聊天附件持久化到磁盘，
以便在原始 base64 载荷从消息记录中丢弃后，前端仍可预览它们。
"""

from aidlearning.services.storage.attachment_store import (
    AttachmentStore,
    LocalDiskAttachmentStore,
    get_attachment_store,
)

__all__ = [
    "AttachmentStore",
    "LocalDiskAttachmentStore",
    "get_attachment_store",
]
