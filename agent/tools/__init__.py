"""
Tools package - base interface, registry, and tool loader.
Person 2 apne custom tools (linter, security scanner, etc.) is interface ke against banayega.
"""

from agent.tools.base import BaseTool, ToolResult, ToolSchema
from agent.tools.loader import (
    discover_tools,
    instantiate_tools,
    load_builtin_tools,
    load_tools_into_agent,
    validate_tool,
    validate_all_tools,
)
from agent.tools.registry import ToolRegistry

__all__ = [
    "BaseTool", "ToolResult", "ToolSchema", "ToolRegistry",
    "discover_tools", "instantiate_tools", "load_builtin_tools",
    "load_tools_into_agent", "validate_tool", "validate_all_tools",
]
