"""能力和工具的运行时注册表。"""

from .capability_registry import CapabilityRegistry, get_capability_registry
from aidlearning.tools.registry import ToolRegistry, get_tool_registry

__all__ = [
    "CapabilityRegistry",
    "ToolRegistry",
    "get_capability_registry",
    "get_tool_registry",
]
