"""
LLM Provider 注册表
=================

LLM Provider 的简单注册系统。
"""

from collections.abc import Callable

# LLM Provider 全局注册表
_provider_registry: dict[str, type] = {}


def register_provider(name: str) -> Callable[[type], type]:
    """
    注册 LLM Provider 类的装饰器。

    Args:
        name: 注册 Provider 使用的名称

    Returns:
        装饰器函数
    """

    def decorator(cls: type) -> type:
        if name in _provider_registry:
            raise ValueError(f"Provider '{name}' is already registered")
        _provider_registry[name] = cls
        setattr(cls, "__provider_name__", name)
        return cls

    return decorator


def get_provider_class(name: str) -> type:
    """
    按名称获取已注册的 Provider 类。

    Args:
        name: Provider 名称

    Returns:
        Provider 类

    Raises:
        KeyError: 如果 Provider 未注册
    """
    return _provider_registry[name]


def list_providers() -> list[str]:
    """
    列出所有已注册的 Provider 名称。

    Returns:
        Provider 名称列表
    """
    return list(_provider_registry.keys())


def is_provider_registered(name: str) -> bool:
    """
    检查 Provider 是否已注册。

    Args:
        name: Provider 名称

    Returns:
        如果已注册返回 True，否则返回 False
    """
    return name in _provider_registry
