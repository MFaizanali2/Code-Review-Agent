"""
Tool Loader - dynamic tool discovery, validation, and registration.

Provides:
- discover_tools(): Scan directories for BaseTool subclasses
- validate_tool(): Check tool implements required interface
- load_builtin_tools(): Auto-load built-in tools (Team Project bridge)
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
import sys
from pathlib import Path
from typing import Any

from agent.tools.base import BaseTool
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def validate_tool(tool: Any) -> tuple[bool, str | None]:
    """Validate that a tool implements the BaseTool interface correctly.

    Checks:
    - Has .name property (non-empty string)
    - Has .description property (non-empty string)
    - Has async .run() method
    - run() returns ToolResult
    - Has .schema() returning ToolSchema

    Returns: (is_valid, error_message)
    """
    if not isinstance(tool, BaseTool):
        return False, f"Tool must be a BaseTool instance, got {type(tool).__name__}"

    if not tool.name:
        return False, "Tool name cannot be empty"

    if not tool.description:
        return False, "Tool description cannot be empty"

    if not hasattr(tool, "run") or not inspect.iscoroutinefunction(tool.run):
        return False, f"Tool '{tool.name}' is missing async run() method"

    if not hasattr(tool, "schema"):
        return False, f"Tool '{tool.name}' is missing schema() method"

    schema = tool.schema()
    if schema.name != tool.name:
        return False, (
            f"Tool name mismatch: '{tool.name}' vs schema name '{schema.name}'"
        )

    return True, None


def validate_all_tools(registry: ToolRegistry) -> dict[str, str | None]:
    """Validate all tools in the registry.

    Returns: {tool_name: error_message_or_None}
    """
    results: dict[str, str | None] = {}
    for tool in registry.list_tools():
        is_valid, error = validate_tool(tool)
        results[tool.name] = None if is_valid else error
    return results


def discover_tools(
    package_paths: list[str] | None = None,
) -> list[type[BaseTool]]:
    """Dynamically discover BaseTool subclasses from installed packages.

    Scans packages listed in package_paths (or all importable packages)
    for classes that inherit from BaseTool (but are not BaseTool itself).

    Returns: List of BaseTool subclass references (not instances).
    """
    discovered: list[type[BaseTool]] = []

    if package_paths is None:
        package_paths = ["agent.tools", "agent.tools.builtin"]

    for package_name in package_paths:
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.debug("Package %s not found, skipping", package_name)
            continue

        package_path = getattr(package, "__path__", None)
        if not package_path:
            continue

        for _importer, modname, _ispkg in pkgutil.iter_modules(package_path):
            full_name = f"{package_name}.{modname}"
            try:
                module = importlib.import_module(full_name)
            except Exception as exc:
                logger.warning("Failed to import %s: %s", full_name, exc)
                continue

            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and obj.__module__ == full_name
                ):
                    if obj not in discovered:
                        discovered.append(obj)
                        logger.debug("Discovered tool: %s from %s", obj.__name__, full_name)

    return discovered


def instantiate_tools(tool_classes: list[type[BaseTool]]) -> list[BaseTool]:
    """Instantiate tool classes, skipping those that fail."""
    tools: list[BaseTool] = []
    for cls in tool_classes:
        try:
            instance = cls()
            tools.append(instance)
        except Exception as exc:
            logger.warning("Failed to instantiate %s: %s", cls.__name__, exc)
    return tools


def load_builtin_tools(
    registry: ToolRegistry | None = None,
    skip_team_project: bool = False,
) -> ToolRegistry:
    """Load all built-in tools into a (new or existing) registry.

    Loads:
    1. Team Project tools via bridge adapter (unless skip_team_project)
    2. Any tools discovered in agent.tools.builtin package

    Args:
        registry: Existing registry to populate (creates new one if None)
        skip_team_project: Skip loading Team Project tools

    Returns:
        ToolRegistry with all loaded tools
    """
    if registry is None:
        from agent.tools.registry import ToolRegistry
        registry = ToolRegistry()

    if not skip_team_project:
        try:
            from agent.tools.builtin.github_tool import GitHubTool
            from agent.tools.builtin.code_analyzer import CodeAnalyzerTool
            from agent.tools.builtin.security_checker import SecurityCheckerTool
            from agent.tools.builtin.performance_checker import PerformanceCheckerTool
            from agent.tools.builtin.report_generator import ReportGeneratorTool

            builtin_tools: list[BaseTool] = [
                GitHubTool(),
                CodeAnalyzerTool(),
                SecurityCheckerTool(),
                PerformanceCheckerTool(),
                ReportGeneratorTool(),
            ]

            for tool in builtin_tools:
                is_valid, error = validate_tool(tool)
                if is_valid:
                    registry.register(tool)
                else:
                    logger.warning("Skipping invalid built-in tool: %s", error)
        except ImportError:
            logger.info("Built-in tools not available")

    # Load any tools from agent.tools.builtin if the package exists
    discovered = discover_tools(["agent.tools.builtin"])
    for tool_instance in instantiate_tools(discovered):
        registry.register(tool_instance)

    return registry


def load_tools_into_agent(
    agent: Any,
    skip_team_project: bool = False,
) -> int:
    """Convenience: load all built-in tools into an agent instance.

    Works with both modern CodeReviewAgent (has register_tool) and
    any object with a register_tool or register_tools method.

    Args:
        agent: Agent instance to load tools into
        skip_team_project: Skip loading Team Project tools

    Returns:
        Number of tools loaded
    """
    registry = load_builtin_tools(skip_team_project=skip_team_project)
    tools = registry.list_tools()

    if hasattr(agent, "register_tools"):
        agent.register_tools(tools)
    elif hasattr(agent, "register_tool"):
        for tool in tools:
            agent.register_tool(tool)
    else:
        raise TypeError("Agent has no register_tool(s) method")

    return len(tools)
