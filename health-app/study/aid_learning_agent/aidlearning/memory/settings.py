"""记忆整合器的用户可调参数。

唯一数据源是 ``data/user/settings/main.yaml`` 中 ``memory:`` 子树。
默认值定义在此处。前端 ``/settings/memory`` 页面通过 API 读写同一子树。

与算法代码解耦：每个模式通过 :func:`load_memory_settings` 获取参数值，
而不是通过模块级常量。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Literal

from aidlearning.utils.config_manager import ConfigManager

_SETTINGS_KEY = "memory"


@dataclass(frozen=True)
class UpdateSettings:
    l2_budget: int = 20
    l3_budget: int = 10


@dataclass(frozen=True)
class AuditSettings:
    l2_budget: int = 20
    l3_budget: int = 10


@dataclass(frozen=True)
class DedupSettings:
    iterations: int = 3
    auto_after_update: bool = True


@dataclass(frozen=True)
class MergeSettings:
    """无需 LLM 的脚注合并（将重复引用合并为每个一个脚注）。"""

    auto_after_update: bool = True
    auto_after_audit: bool = True
    auto_after_dedup: bool = True


@dataclass(frozen=True)
class ChunkingSettings:
    overlap_ratio: float = 0.10
    boundary: Literal["paragraph", "sentence"] = "paragraph"
    min_chunk_chars: int = 1000
    max_chunk_chars: int = 64000


@dataclass(frozen=True)
class ReferenceSettings:
    enforce_required: bool = True
    drop_invalid_refs: bool = True


@dataclass(frozen=True)
class DecaySettings:
    """基于时间的记忆衰减参数。"""
    half_life_days: float = 90.0
    auto_cleanup_enabled: bool = True
    cleanup_threshold: float = 0.05
    archive_before_delete: bool = True


@dataclass(frozen=True)
class RetrievalSettings:
    """中期+长期记忆的智能检索参数。"""
    enabled: bool = True
    top_k: int = 10
    token_budget: int = 2000
    weight_similarity: float = 0.55
    weight_decay: float = 0.20
    weight_importance: float = 0.15
    weight_recency: float = 0.10


@dataclass(frozen=True)
class MemorySettings:
    update: UpdateSettings = field(default_factory=UpdateSettings)
    audit: AuditSettings = field(default_factory=AuditSettings)
    dedup: DedupSettings = field(default_factory=DedupSettings)
    merge: MergeSettings = field(default_factory=MergeSettings)
    chunking: ChunkingSettings = field(default_factory=ChunkingSettings)
    reference: ReferenceSettings = field(default_factory=ReferenceSettings)
    decay: DecaySettings = field(default_factory=DecaySettings)
    retrieval: RetrievalSettings = field(default_factory=RetrievalSettings)


def load_memory_settings() -> MemorySettings:
    """返回当前 ``memory:`` 子树与默认值合并后的结果。

    缺失的键回退到默认值。超出范围的数值会被钳制到安全范围内，
    以防止格式错误的 YAML 导致运行崩溃。
    """
    raw = ConfigManager().load_config().get(_SETTINGS_KEY) or {}
    return _from_dict(MemorySettings, raw)


def save_memory_settings(payload: dict[str, Any]) -> MemorySettings:
    """将 ``payload`` 合并到磁盘上的 ``memory:`` 子树中。

    未知键会被丢弃；值会被强制转换为模式定义的类型，
    以防止 YAML 中出现垃圾数据。返回合并后的设置。
    """
    merged = _from_dict(MemorySettings, payload)
    coerced = asdict(merged)
    ConfigManager().save_config({_SETTINGS_KEY: coerced})
    return merged


def memory_settings_dict() -> dict[str, Any]:
    """以普通字典形式返回设置 — JSON 安全，适用于 API 响应。"""
    return asdict(load_memory_settings())


# ── 类型转换 + 钳制 ─────────────────────────────────────────────────


_MIN_BUDGET = 1
_MAX_BUDGET = 200
_MIN_DEDUP_ITER = 1
_MAX_DEDUP_ITER = 20
_MIN_OVERLAP = 0.0
_MAX_OVERLAP = 0.5
_MIN_CHUNK_CHARS = 200
_MAX_CHUNK_CHARS = 64000
_BOUNDARIES = ("paragraph", "sentence")


def _from_dict(cls: type, raw: Any) -> Any:
    """从部分字典构建冻结 dataclass。

    策略：遍历字段，如果字段本身是 dataclass 且输入中有匹配的字典，
    则递归处理。否则进行类型转换+钳制。默认值填充所有缺失字段。
    """
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    instance_defaults = cls()  # type: ignore[call-arg]
    if not isinstance(raw, dict):
        return instance_defaults

    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        provided = raw.get(f.name)
        default = getattr(instance_defaults, f.name)
        if isinstance(f.type, type) and is_dataclass(f.type):
            kwargs[f.name] = _from_dict(f.type, provided) if provided is not None else default
            continue
        # 通过实际默认类型检测嵌套 dataclass
        if is_dataclass(default):
            kwargs[f.name] = (
                _from_dict(type(default), provided) if provided is not None else default
            )
            continue
        kwargs[f.name] = _coerce_scalar(f.name, provided, default)
    return cls(**kwargs)


def _coerce_scalar(name: str, raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(default, bool):
        return bool(raw)
    if isinstance(default, int):
        try:
            int_value = int(raw)
        except (TypeError, ValueError):
            return default
        return _clamp_int(name, int_value, default)
    if isinstance(default, float):
        try:
            float_value = float(raw)
        except (TypeError, ValueError):
            return default
        return _clamp_float(name, float_value, default)
    if isinstance(default, str):
        str_value = str(raw)
        if name == "boundary" and str_value not in _BOUNDARIES:
            return default
        return str_value
    return raw


def _clamp_int(name: str, value: int, default: int) -> int:
    if name.endswith("budget"):
        return max(_MIN_BUDGET, min(_MAX_BUDGET, value))
    if name == "iterations":
        return max(_MIN_DEDUP_ITER, min(_MAX_DEDUP_ITER, value))
    if name == "min_chunk_chars":
        return max(_MIN_CHUNK_CHARS, min(_MAX_CHUNK_CHARS, value))
    if name == "max_chunk_chars":
        return max(_MIN_CHUNK_CHARS, min(_MAX_CHUNK_CHARS, value))
    return max(0, value)


def _clamp_float(name: str, value: float, default: float) -> float:
    if name == "overlap_ratio":
        return max(_MIN_OVERLAP, min(_MAX_OVERLAP, value))
    if name == "half_life_days":
        return max(1.0, min(3650.0, value))  # 1 天到 10 年
    if name == "cleanup_threshold":
        return max(0.0, min(1.0, value))
    if name in ("weight_similarity", "weight_decay", "weight_importance", "weight_recency"):
        return max(0.0, min(1.0, value))
    if name == "token_budget":
        return max(256, min(32000, value))
    if name == "top_k":
        return max(1, min(100, value))
    return value


__all__ = [
    "AuditSettings",
    "ChunkingSettings",
    "DecaySettings",
    "DedupSettings",
    "MemorySettings",
    "MergeSettings",
    "ReferenceSettings",
    "RetrievalSettings",
    "UpdateSettings",
    "load_memory_settings",
    "memory_settings_dict",
    "save_memory_settings",
]
