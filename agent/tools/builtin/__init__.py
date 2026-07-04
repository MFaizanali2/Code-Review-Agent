from agent.tools.builtin.github_tool import GitHubTool
from agent.tools.builtin.code_analyzer import CodeAnalyzerTool
from agent.tools.builtin.security_checker import SecurityCheckerTool
from agent.tools.builtin.performance_checker import PerformanceCheckerTool
from agent.tools.builtin.report_generator import ReportGeneratorTool

ALL_TOOLS = [
    GitHubTool(),
    CodeAnalyzerTool(),
    SecurityCheckerTool(),
    PerformanceCheckerTool(),
    ReportGeneratorTool(),
]

__all__ = [
    "GitHubTool",
    "CodeAnalyzerTool",
    "SecurityCheckerTool",
    "PerformanceCheckerTool",
    "ReportGeneratorTool",
    "ALL_TOOLS",
]
