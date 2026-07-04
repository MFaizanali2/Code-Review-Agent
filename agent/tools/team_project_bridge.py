"""
Team Project Tools Bridge - adapts Team Project BaseTool to modern BaseTool.

Usage:
    from agent.tools.team_project_bridge import TeamProjectToolAdapter, register_team_project_tools

    registry = ToolRegistry()
    register_team_project_tools(registry)
    # or manually:
    # from agent.tools.builtin.github_tool import GitHubTool
    # registry.register(TeamProjectToolAdapter(GitHubTool()))
"""

from __future__ import annotations

from typing import Any

from agent.tools.base import BaseTool, ToolResult, ToolSchema


class TeamProjectToolAdapter(BaseTool):
    """Wraps a Team Project BaseTool to conform to the modern BaseTool interface.

    Bridges execute(**kwargs) -> dict to run(tool_input: dict) -> ToolResult.
    """

    def __init__(self, team_tool: Any) -> None:
        self._tool = team_tool

    @property
    def name(self) -> str:
        return self._tool.name

    @property
    def description(self) -> str:
        return self._tool.description

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        try:
            result = await self._tool.execute(**tool_input)
            if isinstance(result, dict) and result.get("status") == "error":
                return ToolResult(
                    success=False,
                    data=result,
                    error=result.get("message", "Unknown error"),
                )
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, data={}, error=str(e))

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self._tool.name,
            description=self._tool.description,
            parameters={},
            required=[],
        )


def register_team_project_tools(registry: Any) -> None:
    """Register all Team Project tools into a ToolRegistry.

    Safe to call if the Team Project package is not installed.
    """
    try:
        from agent.tools.builtin.github_tool import GitHubTool
        from agent.tools.builtin.code_analyzer import CodeAnalyzerTool
        from agent.tools.builtin.security_checker import SecurityCheckerTool
        from agent.tools.builtin.performance_checker import PerformanceCheckerTool
        from agent.tools.builtin.report_generator import ReportGeneratorTool

        registry.register_many([
            TeamProjectToolAdapter(GitHubTool()),
            TeamProjectToolAdapter(CodeAnalyzerTool()),
            TeamProjectToolAdapter(SecurityCheckerTool()),
            TeamProjectToolAdapter(PerformanceCheckerTool()),
            TeamProjectToolAdapter(ReportGeneratorTool()),
        ])
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "Built-in tools not available (package not installed)"
        )
