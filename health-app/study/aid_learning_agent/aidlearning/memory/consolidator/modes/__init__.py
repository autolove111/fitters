"""五种用户可见的整合模式。

* :func:`run_update`  — 基于分块的增量事实提取。
* :func:`run_audit`   — 基于分块的行级编辑对照原始证据检查。
* :func:`run_dedup`   — 全文档迭代行级去重。
* :func:`run_merge`   — 无需 LLM 的脚注合并（折叠重复引用）。
* :func:`run_cleanup` — 基于衰减的过时条目移除。

加上为 :mod:`aidlearning.memory.store` 保留的薄兼容层
（:func:`consolidate_l2`、:func:`consolidate_l3`），
使公共 API 接口在底层实现切换时保持稳定。
"""

from __future__ import annotations

from aidlearning.memory.consolidator.modes._shims import (
    consolidate_l2,
    consolidate_l3,
)
from aidlearning.memory.consolidator.modes.audit import run_audit
from aidlearning.memory.consolidator.modes.cleanup import CleanupResult, run_cleanup
from aidlearning.memory.consolidator.modes.dedup import run_dedup
from aidlearning.memory.consolidator.modes.merge import run_merge
from aidlearning.memory.consolidator.modes.update import run_update

__all__ = [
    "CleanupResult",
    "consolidate_l2",
    "consolidate_l3",
    "run_audit",
    "run_cleanup",
    "run_dedup",
    "run_merge",
    "run_update",
]
