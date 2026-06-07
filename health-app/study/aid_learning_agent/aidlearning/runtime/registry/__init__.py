"""Runtime registries for capabilities and tools."""

from .capability_registry import CapabilityRegistry, get_capability_registry
from aidlearning.tools.registry import ToolRegistry, get_tool_registry

__all__ = [
    "CapabilityRegistry",
    "ToolRegistry",
    "get_capability_registry",
    "get_tool_registry",
]
