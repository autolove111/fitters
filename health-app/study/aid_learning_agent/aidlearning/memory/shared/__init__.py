"""所有记忆层共享的基础。

- ``ids``   : ULID 风格的追踪和条目 id 生成器
- ``paths`` : 每用户路径解析 (Surface, L3Slot)
- ``trace`` : L1 原始事件捕获（每个 surface 每天仅追加 JSONL）
"""

from .ids import is_entry_id, is_trace_id, new_entry_id, new_trace_id
from .paths import L3_SLOTS, SURFACES, L3Slot, Surface
from .trace import TraceEvent

__all__ = [
    "L3_SLOTS",
    "L3Slot",
    "SURFACES",
    "Surface",
    "TraceEvent",
    "is_entry_id",
    "is_trace_id",
    "new_entry_id",
    "new_trace_id",
]
