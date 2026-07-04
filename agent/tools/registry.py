"""
Tool Registry - tools ko register, lookup, aur manage karo.
Centralized jagah jahan saare available tools track hote hain.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    In-memory tool registry.
    Tools yahan register hote hain aur LLM ke liye discoverable bante hain.

    Usage:
        registry = ToolRegistry()
        registry.register(MyTool())
        tool = registry.get("tool_name")
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Tool ko register karo. Agar same naam ka pehle se hai to overwrite hoga."""
        if not tool.name:
            raise ValueError("Tool name cannot be empty")
        if tool.name in self._tools:
            logger.warning("Tool '%s' already registered, overwriting", tool.name)
        self._tools[tool.name] = tool
        logger.info("Tool registered: %s", tool.name)

    def register_many(self, tools: list[BaseTool]) -> None:
        """Bulk registration - multiple tools ek saath register karo."""
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> bool:
        """Tool ko registry se hatao. Returns True agar tha aur hata diya."""
        if name in self._tools:
            del self._tools[name]
            logger.info("Tool unregistered: %s", name)
            return True
        return False

    def get(self, name: str) -> BaseTool | None:
        """Naam se tool retrieve karo. Na mile to None."""
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """Saare registered tool names return karo."""
        return list(self._tools.keys())

    def list_tools(self) -> list[BaseTool]:
        """Saare tool instances return karo."""
        return list(self._tools.values())

    def describe_all(self) -> list[dict[str, Any]]:
        """
        Saare tools ke schemas return karo - LLM ko available tools dikhane ke liye.
        """
        descriptions = []
        for tool in self._tools.values():
            schema = tool.schema()
            descriptions.append({
                "name": schema.name,
                "description": schema.description,
                "parameters": schema.parameters,
                "required": schema.required,
            })
        return descriptions

    def clear(self) -> None:
        """Registry khali karo - testing ke liye useful."""
        self._tools.clear()

    def validate_all(self) -> dict[str, str | None]:
        """Validate every registered tool.

        Returns: {tool_name: error_message_or_None}
        """
        from agent.tools.loader import validate_tool

        results: dict[str, str | None] = {}
        for name, tool in self._tools.items():
            is_valid, error = validate_tool(tool)
            results[name] = None if is_valid else error
        return results

    def get_safe(self, name: str) -> BaseTool | None:
        """Get tool with additional runtime validation.

        Same as get(), but logs a warning if tool is missing.
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("Tool '%s' not found in registry", name)
        return tool

    def __contains__(self, name: str) -> bool:
        """'tool_name' in registry syntax support karo."""
        return name in self._tools

    def __len__(self) -> int:
        """len(registry) se tool count pata karo."""
        return len(self._tools)
