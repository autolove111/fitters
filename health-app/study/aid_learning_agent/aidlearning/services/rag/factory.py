"""RAG 管线工厂。

项目附带一个基于 LlamaIndex 的管线。以下辅助函数保留是因为多个调用点导入了它们；
它们已全部合并为操作单一支持的管线。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_PROVIDER = "llamaindex"

# 以 kb_base_dir 为键缓存的管线实例。
_PIPELINE_CACHE: Dict[Optional[str], Any] = {}


def normalize_provider_name(_name: Optional[str] = None) -> str:
    """始终返回规范的提供商名称。

    较旧的配置/迁移可能携带旧版提供商字符串（如 ``lightrag``）；
    它们都被视为唯一支持的管线。
    """
    return DEFAULT_PROVIDER


def get_pipeline(
    name: str = DEFAULT_PROVIDER,
    kb_base_dir: Optional[str] = None,
    **kwargs: Any,
):
    """返回（缓存的）LlamaIndex 管线实例。

    ``name`` 参数为向后兼容而接受，但会被忽略 —— 仅支持 LlamaIndex 管线。
    """
    from .pipelines.llamaindex.pipeline import LlamaIndexPipeline

    if kwargs:
        # 当提供自定义参数时，构建新实例并跳过缓存以尊重覆盖。
        if kb_base_dir is not None:
            kwargs.setdefault("kb_base_dir", kb_base_dir)
        return LlamaIndexPipeline(**kwargs)

    if kb_base_dir not in _PIPELINE_CACHE:
        _PIPELINE_CACHE[kb_base_dir] = LlamaIndexPipeline(kb_base_dir=kb_base_dir)
    return _PIPELINE_CACHE[kb_base_dir]


def list_pipelines() -> List[Dict[str, str]]:
    """返回唯一可用的管线（保留给仍在使用的调用方）。"""
    return [
        {
            "id": DEFAULT_PROVIDER,
            "name": "LlamaIndex",
            "description": "LlamaIndex retrieval with hybrid BM25/vector fusion when available.",
        }
    ]


__all__ = [
    "DEFAULT_PROVIDER",
    "get_pipeline",
    "list_pipelines",
    "normalize_provider_name",
]
