"""Time-based decay scoring for memory entries.

Each memory entry carries three metadata fields that feed into the decay
formula:

- ``created_at``   — when the entry was first written (Unix timestamp)
- ``last_accessed`` — when the entry was last retrieved by a search
- ``access_count``  — total retrieval hits

The decay score is computed on-the-fly (never persisted) so it always
reflects the current time.  The formula is a weighted blend of four
signals:

    base_decay   0.5  — exponential fade from creation time
    recency      0.2  — boost from last retrieval
    frequency    0.1  — log-scale access count
    importance   0.2  — LLM-assessed importance [0, 1]

All four components are in [0, 1] and the weights sum to 1.0.
"""

from __future__ import annotations

import math
import time

# ── Defaults ───────────────────────────────────────────────────────────

_DEFAULT_HALF_LIFE_DAYS = 90.0
_DEFAULT_ACCESS_BOOST = 0.1

# Weights
_W_BASE = 0.5
_W_RECENCY = 0.2
_W_FREQUENCY = 0.1
_W_IMPORTANCE = 0.2


def compute_decay_score(
    created_at: float,
    last_accessed: float,
    access_count: int,
    importance: float = 0.5,
    *,
    half_life_days: float = _DEFAULT_HALF_LIFE_DAYS,
    access_boost: float = _DEFAULT_ACCESS_BOOST,
    now: float | None = None,
) -> float:
    """Return a decay multiplier in [0.0, 1.0].

    Parameters
    ----------
    created_at : float
        Unix timestamp when the entry was first written.
    last_accessed : float
        Unix timestamp of the last retrieval hit.
    access_count : int
        Total number of times this entry has been retrieved.
    importance : float
        LLM-assessed importance in [0, 1].  Defaults to 0.5 (neutral).
    half_life_days : float
        Days until an untouched entry decays to 0.5.  Default 90 (~3 months).
    access_boost : float
        Scaling factor for the frequency bonus.  Higher = more weight on
        frequently accessed entries.
    now : float | None
        Override for the current time (useful in tests).  Defaults to
        ``time.time()``.
    """
    if now is None:
        now = time.time()

    _sec_per_day = 86400.0

    # ── Base decay: exponential from creation ──────────────────────────
    age_days = max(0.0, (now - created_at) / _sec_per_day)
    base_decay = math.pow(2.0, -age_days / half_life_days)

    # ── Recency: boost from last access ───────────────────────────────
    recency_days = max(0.0, (now - last_accessed) / _sec_per_day)
    recency = math.pow(2.0, -recency_days / (half_life_days * 2.0))

    # ── Frequency: log-scale access count ─────────────────────────────
    frequency = 1.0 - (1.0 / (1.0 + access_boost * max(0, access_count)))

    # ── Importance: direct from caller ────────────────────────────────
    imp = max(0.0, min(1.0, importance))

    # ── Weighted blend ────────────────────────────────────────────────
    score = (
        _W_BASE * base_decay
        + _W_RECENCY * recency
        + _W_FREQUENCY * frequency
        + _W_IMPORTANCE * imp
    )
    return max(0.0, min(1.0, score))


def is_stale(
    created_at: float,
    last_accessed: float,
    access_count: int,
    importance: float = 0.5,
    *,
    threshold: float = 0.05,
    half_life_days: float = _DEFAULT_HALF_LIFE_DAYS,
    now: float | None = None,
) -> bool:
    """Return True if the entry's decay score falls below *threshold*."""
    score = compute_decay_score(
        created_at,
        last_accessed,
        access_count,
        importance,
        half_life_days=half_life_days,
        now=now,
    )
    return score < threshold


__all__ = ["compute_decay_score", "is_stale"]
