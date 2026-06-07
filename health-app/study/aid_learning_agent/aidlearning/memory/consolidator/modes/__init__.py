"""Five user-visible consolidation modes.

* :func:`run_update`  — chunk-based incremental fact extraction.
* :func:`run_audit`   — chunk-based line-level edits against raw evidence.
* :func:`run_dedup`   — iterative line-level dedup over the full doc.
* :func:`run_merge`   — no-LLM footnote consolidation (collapse duplicate refs).
* :func:`run_cleanup` — decay-based stale entry removal.

Plus thin shims (:func:`consolidate_l2`, :func:`consolidate_l3`) kept
for :mod:`aidlearning.memory.store` so the public API surface
stays stable while the implementation switches under the hood.
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
