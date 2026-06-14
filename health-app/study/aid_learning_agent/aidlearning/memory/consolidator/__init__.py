"""记忆整合器 — 基于分块的更新/审计/去重。

公共接口（从 API 路由/存储/测试中调用）：

* :class:`ConsolidateResult`, :data:`OnEvent` — 为 :mod:`aidlearning.memory.store` 保留的旧类型。
* :func:`consolidate_l2`, :func:`consolidate_l3` — 委托给 :func:`run_update` 的旧兼容层。
* :func:`run_update`, :func:`run_audit`, :func:`run_dedup` — 工作台直接驱动的三种模式。
* :func:`_parse_ops_response`, :func:`_filter_banned`,
  :func:`_has_banned` — 为 :meth:`store.MemoryStore.apply_ops_payload`
  和现有测试套件保留。

子模块布局：

    chunker.py         纯字符分块器，带边界扩展
    line_doc.py        行号视图 + 替换/删除/插入编辑
    meta.py            *.meta.json 读写，用于"已见 id"差异
    references.py      引用池验证 + 原始追踪标注
    guards.py          禁用短语过滤器（旧版 + L3 强制）
    parse.py           旧版操作数组解析器 (apply_ops_payload)
    modes/
      _runtime.py      共享提示词加载 + LLM + 原子写入
      _shims.py        旧版 consolidate_l2/l3 → run_update
      update.py        基于分块的增量事实提取
      audit.py         基于分块的行级编辑 vs 原始证据
      dedup.py         全文档迭代行级去重
    prompts/
      {en,zh}/{update_l2,update_l3,audit_l2,audit_l3,dedup,_meta}.yaml
"""

from __future__ import annotations

from aidlearning.memory.consolidator.guards import _filter_banned, _has_banned
from aidlearning.memory.consolidator.modes import (
    consolidate_l2,
    consolidate_l3,
    run_audit,
    run_cleanup,
    run_dedup,
    run_merge,
    run_update,
)
from aidlearning.memory.consolidator.modes._shims import (
    ConsolidateResult,
    OnEvent,
)
from aidlearning.memory.consolidator.parse import _parse_ops_response

__all__ = [
    "ConsolidateResult",
    "OnEvent",
    "_filter_banned",
    "_has_banned",
    "_parse_ops_response",
    "consolidate_l2",
    "consolidate_l3",
    "run_audit",
    "run_cleanup",
    "run_dedup",
    "run_merge",
    "run_update",
]
