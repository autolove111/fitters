"""记忆条目的基于时间的衰减评分。

每个记忆条目携带三个元数据字段用于衰减公式：

- ``created_at``   — 条目首次写入的时间（Unix 时间戳）
- ``last_accessed`` — 条目上次被检索的时间
- ``access_count``  — 总检索命中次数

衰减分数是实时计算的（从不持久化），因此始终反映当前时间。
公式是四个信号的加权混合：

    base_decay   0.5  — 从创建时间的指数衰减
    recency      0.2  — 上次检索的加成
    frequency    0.1  — 对数尺度的访问次数
    importance   0.2  — LLM 评估的重要性 [0, 1]

四个分量均在 [0, 1] 范围内，权重之和为 1.0。
"""

from __future__ import annotations

import math
import time

# ── 默认值 ───────────────────────────────────────────────────────────

_DEFAULT_HALF_LIFE_DAYS = 90.0
_DEFAULT_ACCESS_BOOST = 0.1

# 权重
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
    """返回 [0.0, 1.0] 范围内的衰减乘数。

    参数
    ----------
    created_at : float
        条目首次写入时的 Unix 时间戳。
    last_accessed : float
        上次检索命中的 Unix 时间戳。
    access_count : int
        此条目被检索的总次数。
    importance : float
        LLM 评估的重要性，范围 [0, 1]。默认 0.5（中性）。
    half_life_days : float
        未被触碰的条目衰减到 0.5 所需的天数。默认 90（约 3 个月）。
    access_boost : float
        频率加成的缩放因子。值越高 = 频繁访问的条目权重越大。
    now : float | None
        当前时间的覆盖（用于测试）。默认为 ``time.time()``。
    """
    if now is None:
        now = time.time()

    _sec_per_day = 86400.0

    # ── 基础衰减：从创建时间的指数衰减 ──────────────────────────
    age_days = max(0.0, (now - created_at) / _sec_per_day)
    base_decay = math.pow(2.0, -age_days / half_life_days)

    # ── 新近度：上次访问的加成 ───────────────────────────────
    recency_days = max(0.0, (now - last_accessed) / _sec_per_day)
    recency = math.pow(2.0, -recency_days / (half_life_days * 2.0))

    # ── 频率：对数尺度访问次数 ─────────────────────────────
    frequency = 1.0 - (1.0 / (1.0 + access_boost * max(0, access_count)))

    # ── 重要性：直接来自调用方 ────────────────────────────────
    imp = max(0.0, min(1.0, importance))

    # ── 加权混合 ────────────────────────────────────────────────
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
    """如果条目的衰减分数低于 *threshold* 则返回 True。"""
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
