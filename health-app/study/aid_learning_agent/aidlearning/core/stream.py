"""
流式事件协议
=====================

定义所有工具、能力和插件用于向消费者（CLI、WebSocket、SDK）
传达进度和结果的统一流式事件格式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any


class StreamEventType(str, Enum):
    """流式会话中所有可能的事件类型。"""

    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    THINKING = "thinking"
    OBSERVATION = "observation"
    CONTENT = "content"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PROGRESS = "progress"
    SOURCES = "sources"
    RESULT = "result"
    ERROR = "error"
    SESSION = "session"
    SESSION_META = "session_meta"
    DONE = "done"


@dataclass
class StreamEvent:
    """
    聊天轮次中发出的单个流式事件。

    属性：
        type: 此事件的语义类型。
        source: 产生该事件的工具/能力/插件（如 "deep_solve"）。
        stage: 来源中的当前阶段（如 "planning"）。
        content: 人类可读的文本负载。
        metadata: 任意结构化数据（工具参数、来源、指标等）。
        timestamp: 事件创建时的 Unix 纪元秒数。
    """

    type: StreamEventType
    source: str = ""
    stage: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    turn_id: str = ""
    seq: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "source": self.source,
            "stage": self.stage,
            "content": self.content,
            "metadata": self.metadata,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
        }
