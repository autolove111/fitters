"""Shared foundations used by all memory layers.

- ``ids``   : ULID-style trace and entry id generators
- ``paths`` : per-user path resolution (Surface, L3Slot)
- ``trace`` : L1 raw event capture (append-only JSONL per surface per day)
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
