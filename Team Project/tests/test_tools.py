import pytest
import asyncio
import os

from tools import (
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

def test_base_tool_schema():
    tool = CodeAnalyzerTool()
    schema = tool.to_schema()
    assert "name" in schema
    assert "description" in schema

@pytest.mark.asyncio
async def test_code_analyzer_good(good_file):
    tool = CodeAnalyzerTool()
    result = await tool.execute(code_path=good_file)
    assert result["status"] == "success"
    assert len(result["data"]["functions"]) == 2
    assert result["data"]["lines_of_code"] > 0

@pytest.mark.asyncio
async def test_security_checker_bad(bad_file):
    tool = SecurityCheckerTool()
    result = await tool.execute(code_path=bad_file)
    assert result["status"] == "success"
    assert result["total_issues"] > 0
    assert result["risk_level"] in ["HIGH", "CRITICAL"]

@pytest.mark.asyncio
async def test_performance_checker_bad(bad_file):
    tool = PerformanceCheckerTool()
    result = await tool.execute(code_path=bad_file)
    assert result["status"] == "success"
    assert result["total_issues"] > 0

@pytest.mark.asyncio
async def test_security_checker_good(good_file):
    tool = SecurityCheckerTool()
    result = await tool.execute(code_path=good_file)
    assert result["status"] == "success"
    assert result["risk_level"] == "SAFE"

@pytest.mark.asyncio
async def test_report_generator():
    tool = ReportGeneratorTool()
    mock_data = {
        "github": {"file_count": 5, "python_file_count": 3, "languages": {".py": 3}},
        "code": {"data": {"functions": [{"name": "f"}], "classes": [],
                          "lines_of_code": 50, "complexity": 3, "has_docstrings": True}},
        "security": {"total_issues": 0, "risk_level": "SAFE", "vulnerabilities": []},
        "performance": {"total_issues": 0, "performance_score": 100, "issues": []}
    }
    result = await tool.execute(analysis_data=mock_data)
    assert result["status"] == "success"
    assert result["report"]["scores"]["overall"] >= 80

@pytest.mark.asyncio
async def test_github_tool_invalid_url():
    tool = GitHubTool()
    result = await tool.execute(github_url="https://github.com/fake/nonexistent-repo-xyz")
    assert result["status"] == "error"
