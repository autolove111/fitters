"""能力 ``run()`` 端点的共享基础设施。

所有能力最终汇聚到相同的最终发射：

    await stream.result({"response": ..., ...}, source="<cap>")

基础聊天能力还会附带每轮的 ``cost_summary``，使前端能在消息底部
渲染 ``$cost · tokens · calls``。其他几个能力以前会重复该合并逻辑
（solve、research、question followup），其余则完全跳过，
导致底部信息只对部分能力可见。本模块集中了合并+发射逻辑，
使每个能力发出相同的信封结构。
"""

from __future__ import annotations

from typing import Any

from aidlearning.core.agentic.usage import UsageTracker
from aidlearning.core.stream_bus import StreamBus


async def emit_capability_result(
    stream: StreamBus,
    payload: dict[str, Any],
    *,
    source: str,
    usage: UsageTracker | None = None,
) -> None:
    """发射最终的能力结果，附带费用摘要（如果可用）。

    ``payload`` 会被就地修改：当 ``usage`` 至少有一次已记录的调用时，
    其 ``summary()`` 会被合并到 ``payload["metadata"]["cost_summary"]``。
    任何已有的 ``payload["metadata"]`` 字典会被保留。
    """
    if usage is not None:
        cs = usage.summary()
        if cs:
            meta = payload.get("metadata")
            if not isinstance(meta, dict):
                meta = {}
                payload["metadata"] = meta
            meta["cost_summary"] = cs
    await stream.result(payload, source=source)


__all__ = ["emit_capability_result"]
