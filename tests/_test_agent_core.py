"""End-to-end test for CodeReviewAgent."""
import asyncio
import sys

sys.path.insert(0, "G:/Ai-Agents/Code-Review-Agent")

from agent.agent_core import CodeReviewAgent
from agent.agent_types import ReviewRequest, ToolResult
from agent.llm.client import LLMResponse


# -----------------------------------------------------------------------------
# Mock LLM that returns scripted ReACT responses
# -----------------------------------------------------------------------------
class ScriptedLLM:
    """LLM jo pre-scripted responses return karta hai."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    async def generate(self, prompt):
        if self.call_count < len(self.responses):
            content = self.responses[self.call_count]
        else:
            content = "NEXT_TOOL: DONE\nREASON: All done"
        self.call_count += 1
        return LLMResponse(
            content=content, provider="mock", model="scripted"
        )


# -----------------------------------------------------------------------------
# Mock Tools
# -----------------------------------------------------------------------------
class FetchRepoTool:
    name = "fetch_repository"

    async def run(self, params):
        return ToolResult(
            tool_name="fetch_repository",
            success=True,
            data={"files": ["main.py", "utils.py"], "count": 2},
            execution_time=0.5,
        )


class AnalyzeCodeTool:
    name = "analyze_code_structure"

    async def run(self, params):
        return ToolResult(
            tool_name="analyze_code_structure",
            success=True,
            data={
                "issues": [
                    {"severity": "medium", "title": "Long function", "line": 42, "file": "main.py"},
                    {"severity": "low", "title": "Missing docstring", "line": 15, "file": "utils.py"},
                ]
            },
            execution_time=0.3,
        )


class SecurityTool:
    name = "security_audit"

    async def run(self, params):
        return ToolResult(
            tool_name="security_audit",
            success=True,
            data={
                "issues": [
                    {"severity": "high", "title": "SQL injection risk", "line": 88, "file": "main.py"},
                ]
            },
            execution_time=0.4,
        )


class PerformanceTool:
    name = "performance_analysis"

    async def run(self, params):
        return ToolResult(
            tool_name="performance_analysis",
            success=True,
            data={"issues": []},
            execution_time=0.2,
        )


class GenerateReportTool:
    name = "generate_report"

    async def run(self, params):
        return ToolResult(
            tool_name="generate_report",
            success=True,
            data={"report_generated": True},
            execution_time=0.1,
        )


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
async def test_full_react_loop():
    """Full ReACT loop with all 4 steps (think, act, observe, reflect)."""
    print("=== Test 1: Full ReACT loop ===")

    # Script: fetch -> analyze -> security -> performance -> report -> DONE
    scripted_responses = [
        "NEXT_TOOL: fetch_repository\nREASON: Need to download code first",
        "NEXT_TOOL: analyze_code_structure\nREASON: Now analyze the structure",
        "NEXT_TOOL: security_audit\nREASON: Check security",
        "NEXT_TOOL: performance_analysis\nREASON: Check performance",
        "NEXT_TOOL: generate_report\nREASON: Compile findings",
        "NEXT_TOOL: DONE\nREASON: Report generated, task complete",
    ]

    llm = ScriptedLLM(scripted_responses)
    tools = {
        "fetch_repository": FetchRepoTool(),
        "analyze_code_structure": AnalyzeCodeTool(),
        "security_audit": SecurityTool(),
        "performance_analysis": PerformanceTool(),
        "generate_report": GenerateReportTool(),
    }

    agent = CodeReviewAgent(llm_client=llm, tools_registry=tools)
    print(f"Agent: {agent}")

    request = ReviewRequest(
        github_url="https://github.com/user/test-repo",
        analysis_type="full",
    )

    result = await agent.run(request, max_steps=10)

    print(f"\nStatus: {agent.status.value}")
    print(f"Steps taken: {result.steps_taken}")
    print(f"Quality score: {result.quality_score}")
    print(f"Success: {result.success}")
    print(f"Issues found: {len(result.issues)}")
    print(f"Execution time: {result.execution_time:.3f}s")
    print(f"LLM calls: {llm.call_count}")

    assert result.success is True
    assert result.steps_taken == 5
    assert len(result.issues) == 3  # 2 from analyze + 1 from security
    assert result.quality_score == 7.0  # 10 - 3 issues
    assert llm.call_count == 6  # 5 actions + 1 DONE
    print("Full ReACT loop test PASSED!")


async def test_early_done():
    """Test when LLM says DONE immediately."""
    print("\n=== Test 2: Early DONE ===")

    llm = ScriptedLLM(["NEXT_TOOL: DONE\nREASON: Nothing to do"])
    tools = {"fetch_repository": FetchRepoTool()}

    agent = CodeReviewAgent(llm_client=llm, tools_registry=tools)
    request = ReviewRequest(code_content="print('hello')", analysis_type="full")
    result = await agent.run(request)

    print(f"Steps: {result.steps_taken}, Issues: {len(result.issues)}, Score: {result.quality_score}")
    assert result.steps_taken == 0
    assert len(result.issues) == 0
    assert result.quality_score == 10.0
    print("Early DONE test PASSED!")


async def test_invalid_request():
    """Test with invalid request (no source)."""
    print("\n=== Test 3: Invalid request ===")

    llm = ScriptedLLM([])
    agent = CodeReviewAgent(llm_client=llm, tools_registry={})
    request = ReviewRequest()  # no github_url, no code_content
    result = await agent.run(request)

    print(f"Success: {result.success}, Report: {result.report[:60]}")
    assert result.success is False
    assert "empty" in result.report.lower() or "invalid" in result.report.lower()
    print("Invalid request test PASSED!")


async def test_tool_failure_recovery():
    """Test when a tool fails but agent continues."""
    print("\n=== Test 4: Tool failure recovery ===")

    class FailingTool:
        name = "fetch_repository"

        async def run(self, params):
            return ToolResult(
                tool_name="fetch_repository",
                success=False,
                data={},
                error="Network timeout",
                execution_time=1.0,
            )

    scripted_responses = [
        "NEXT_TOOL: fetch_repository\nREASON: Try to fetch",
        "NEXT_TOOL: analyze_code_structure\nREASON: Try anyway",
        "NEXT_TOOL: DONE\nREASON: Done",
    ]

    llm = ScriptedLLM(scripted_responses)
    tools = {
        "fetch_repository": FailingTool(),
        "analyze_code_structure": AnalyzeCodeTool(),
    }
    agent = CodeReviewAgent(llm_client=llm, tools_registry=tools)
    request = ReviewRequest(code_content="x = 1", analysis_type="full")
    result = await agent.run(request)

    print(f"Steps: {result.steps_taken}, Success: {result.success}")
    # Critical failure (fetch) should mark result as failed
    assert result.success is False
    assert result.steps_taken == 2
    print("Tool failure recovery test PASSED!")


async def test_status_transitions():
    """Test that agent status transitions correctly."""
    print("\n=== Test 5: Status transitions ===")

    llm = ScriptedLLM([
        "NEXT_TOOL: analyze_code_structure\nREASON: Go",
        "NEXT_TOOL: DONE\nREASON: Stop",
    ])
    tools = {"analyze_code_structure": AnalyzeCodeTool()}
    agent = CodeReviewAgent(llm_client=llm, tools_registry=tools)

    print(f"Initial status: {agent.status.value}")
    assert agent.status.value == "idle"

    request = ReviewRequest(code_content="x", analysis_type="full")
    result = await agent.run(request)

    print(f"Final status: {agent.status.value}")
    assert agent.status.value == "completed"
    print("Status transitions test PASSED!")


async def test_report_format():
    """Test that the report is properly formatted markdown."""
    print("\n=== Test 6: Report format ===")

    llm = ScriptedLLM([
        "NEXT_TOOL: analyze_code_structure\nREASON: Go",
        "NEXT_TOOL: DONE\nREASON: Stop",
    ])
    tools = {"analyze_code_structure": AnalyzeCodeTool()}
    agent = CodeReviewAgent(llm_client=llm, tools_registry=tools)
    request = ReviewRequest(github_url="https://github.com/x/y", analysis_type="security")
    result = await agent.run(request)

    print("\n--- Report (first 500 chars) ---")
    print(result.report[:500])
    print("---")
    assert "# Code Review Report" in result.report
    assert "## Quality Score" in result.report
    assert "## Issues Found" in result.report
    assert "## Tool Executions" in result.report
    print("Report format test PASSED!")


async def test_multiple_requests():
    """Test that agent can handle multiple requests in sequence."""
    print("\n=== Test 7: Multiple sequential requests ===")

    llm = ScriptedLLM([
        "NEXT_TOOL: DONE\nREASON: Stop",
        "NEXT_TOOL: DONE\nREASON: Stop",
    ])
    tools = {"analyze_code_structure": AnalyzeCodeTool()}
    agent = CodeReviewAgent(llm_client=llm, tools_registry=tools)

    # First request
    r1 = await agent.run(ReviewRequest(code_content="x = 1"))
    print(f"Request 1: steps={r1.steps_taken}, memory cleared properly")

    # Second request - should start fresh
    r2 = await agent.run(ReviewRequest(code_content="y = 2"))
    print(f"Request 2: steps={r2.steps_taken}, memory cleared properly")

    assert r1.steps_taken == 0
    assert r2.steps_taken == 0
    print("Multiple requests test PASSED!")


async def main():
    await test_full_react_loop()
    await test_early_done()
    await test_invalid_request()
    await test_tool_failure_recovery()
    await test_status_transitions()
    await test_report_format()
    await test_multiple_requests()
    print("\n" + "=" * 60)
    print("All 7 tests PASSED!")
    print("=" * 60)


asyncio.run(main())
