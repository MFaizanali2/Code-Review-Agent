"""
Tools package - base interface aur registry yahan hain.
Person 2 apne custom tools (linter, security scanner, etc.) is interface ke against banayega.
"""

from agent.tools.base import BaseTool, ToolResult, ToolSchema
from agent.tools.registry import ToolRegistry

__all__ = ["BaseTool", "ToolResult", "ToolSchema", "ToolRegistry"]
