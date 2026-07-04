from __future__ import annotations

import os

import pytest

from agent.tools.base import ToolResult
from agent.tools.builtin import (
    GitHubTool,
    CodeAnalyzerTool,
    SecurityCheckerTool,
    PerformanceCheckerTool,
    ReportGeneratorTool,
)

SAMPLE_GOOD_CODE = """
def add(a: int, b: int) -> int:
    \"\"\"Two numbers add karo.\"\"\"
    return a + b

def multiply(a: int, b: int) -> int:
    \"\"\"Multiply karo.\"\"\"
    return a * b
"""

SAMPLE_BAD_CODE = """
import os
password = "admin123"

def run_cmd(user_input):
    os.system(user_input)
    eval(user_input)
    result = []
    for i in range(100):
        for j in range(100):
            result.append(i * j)
"""


@pytest.fixture
def good_file(tmp_path):
    f = tmp_path / "good_code.py"
    f.write_text(SAMPLE_GOOD_CODE)
    return str(f)


@pytest.fixture
def bad_file(tmp_path):
    f = tmp_path / "bad_code.py"
    f.write_text(SAMPLE_BAD_CODE)
    return str(f)


def test_tool_schema():
    tool = CodeAnalyzerTool()
    schema = tool.schema()
    assert schema.name == "analyze_code_structure"
    assert schema.description
    assert "code_path" in schema.parameters


@pytest.mark.asyncio
async def test_code_analyzer_good(good_file):
    tool = CodeAnalyzerTool()
    result: ToolResult = await tool.run({"code_path": good_file})
    assert result.success
    assert len(result.data["data"]["functions"]) == 2
    assert result.data["data"]["lines_of_code"] > 0


@pytest.mark.asyncio
async def test_code_analyzer_missing_path():
    tool = CodeAnalyzerTool()
    result: ToolResult = await tool.run({})
    assert not result.success
    assert "required" in result.error.lower()


@pytest.mark.asyncio
async def test_code_analyzer_not_found():
    tool = CodeAnalyzerTool()
    result: ToolResult = await tool.run({"code_path": "/nonexistent/file.py"})
    assert not result.success


@pytest.mark.asyncio
async def test_security_checker_bad(bad_file):
    tool = SecurityCheckerTool()
    result: ToolResult = await tool.run({"code_path": bad_file})
    assert result.success
    assert result.data["total_issues"] > 0
    assert result.data["risk_level"] in ["HIGH", "CRITICAL"]


@pytest.mark.asyncio
async def test_performance_checker_bad(bad_file):
    tool = PerformanceCheckerTool()
    result: ToolResult = await tool.run({"code_path": bad_file})
    assert result.success
    assert result.data["total_issues"] > 0


@pytest.mark.asyncio
async def test_security_checker_good(good_file):
    tool = SecurityCheckerTool()
    result: ToolResult = await tool.run({"code_path": good_file})
    assert result.success
    assert result.data["risk_level"] == "SAFE"


@pytest.mark.asyncio
async def test_performance_checker_good(good_file):
    tool = PerformanceCheckerTool()
    result: ToolResult = await tool.run({"code_path": good_file})
    assert result.success
    assert result.data["total_issues"] == 0


@pytest.mark.asyncio
async def test_report_generator():
    tool = ReportGeneratorTool()
    mock_data = {
        "github": {"file_count": 5, "python_file_count": 3, "languages": {".py": 3}},
        "code": {
            "data": {
                "functions": [{"name": "f"}],
                "classes": [],
                "lines_of_code": 50,
                "complexity": 3,
                "has_docstrings": True,
            }
        },
        "security": {"total_issues": 0, "risk_level": "SAFE", "vulnerabilities": []},
        "performance": {
            "total_issues": 0,
            "performance_score": 100,
            "issues": [],
        },
    }
    result: ToolResult = await tool.run({"analysis_data": mock_data})
    assert result.success
    assert result.data["report"]["scores"]["overall"] >= 80


@pytest.mark.asyncio
async def test_report_generator_invalid_input():
    tool = ReportGeneratorTool()
    result: ToolResult = await tool.run({"analysis_data": "not a dict"})
    assert not result.success


@pytest.mark.asyncio
async def test_github_tool_invalid_url():
    tool = GitHubTool()
    result: ToolResult = await tool.run(
        {"github_url": "https://github.com/fake/nonexistent-repo-xyz"}
    )
    assert not result.success


@pytest.mark.asyncio
async def test_github_tool_missing_url():
    tool = GitHubTool()
    result: ToolResult = await tool.run({})
    assert not result.success


@pytest.mark.asyncio
async def test_security_checker_missing_path():
    tool = SecurityCheckerTool()
    result: ToolResult = await tool.run({})
    assert not result.success


@pytest.mark.asyncio
async def test_performance_checker_missing_path():
    tool = PerformanceCheckerTool()
    result: ToolResult = await tool.run({})
    assert not result.success


@pytest.mark.asyncio
async def test_all_tools_have_schema():
    for tool_cls in [GitHubTool, CodeAnalyzerTool, SecurityCheckerTool, PerformanceCheckerTool, ReportGeneratorTool]:
        tool = tool_cls()
        schema = tool.schema()
        assert schema.name == tool.name
        assert schema.description == tool.description


@pytest.mark.asyncio
async def test_code_analyzer_syntax_error(tmp_path):
    f = tmp_path / "bad_syntax.py"
    f.write_text("def foo( broken syntax")
    tool = CodeAnalyzerTool()
    result: ToolResult = await tool.run({"code_path": str(f)})
    assert not result.success


@pytest.mark.asyncio
async def test_code_analyzer_complexity(good_file):
    tool = CodeAnalyzerTool()
    result: ToolResult = await tool.run({"code_path": good_file})
    assert result.data["data"]["complexity"] >= 1


@pytest.mark.asyncio
async def test_report_generator_poor_score():
    tool = ReportGeneratorTool()
    mock_data = {
        "github": {"file_count": 1, "python_file_count": 0, "languages": {}},
        "code": {
            "data": {
                "functions": [],
                "classes": [],
                "lines_of_code": 10,
                "complexity": 15,
                "has_docstrings": False,
            }
        },
        "security": {"total_issues": 5, "risk_level": "CRITICAL", "vulnerabilities": [{"line": 1}]},
        "performance": {"total_issues": 3, "performance_score": 70, "issues": [{"line": 2}]},
    }
    result: ToolResult = await tool.run({"analysis_data": mock_data})
    assert result.success
    assert result.data["report"]["scores"]["overall"] < 80


def test_tool_utils_import():
    from agent.tools.builtin.tool_utils import (
        cleanup_temp_dir,
        get_python_files,
        is_valid_github_url,
        safe_read_file,
        severity_rank,
    )
    assert is_valid_github_url("https://github.com/owner/repo")
    assert not is_valid_github_url("https://example.com")
    assert severity_rank("CRITICAL") == 4
    assert severity_rank("SAFE") == 0
