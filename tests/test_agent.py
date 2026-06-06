"""
test_agent.py - Comprehensive unit tests for all agent components.
Pytest-based with auto async support (asyncio_mode=auto in pyproject.toml).
5 test classes, 50+ test cases covering happy paths, errors, and edge cases.

Test structure:
    TestAgentTypes       - Dataclasses and enums
    TestAgentMemory      - Memory management
    TestToolOrchestrator - Tool execution
    TestAgentUtils       - Pure helper functions
    TestCodeReviewAgent  - Main ReACT loop (most important)

Run with:
    pytest tests/test_agent.py -v
"""

# =============================================================================
# IMPORTS
# Note: User's spec shows flat imports but actual paths use agent.X package
# =============================================================================
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agent.agent_core import CodeReviewAgent
from agent.agent_memory import AgentMemory
from agent.agent_orchestrator import ToolOrchestrator
from agent.agent_types import (
    AgentStatus,
    AgentStep,
    ReviewRequest,
    ReviewResult,
    StepType,
    ToolCall,
    ToolResult,
)
from agent.constants import (
    AGENT_STATES,
    DEFAULT_ANALYSIS_TYPE,
    MAX_STEPS,
    MEMORY_MAX_SIZE,
    TOOLS,
)
from agent.llm.client import LLMProvider, LLMResponse
from agent.utils import (
    AVAILABLE_TOOL_NAMES,
    create_tool_call_from_response,
    extract_tool_name_from_thought,
    extract_tool_params_from_response,
    format_memory_for_llm,
    format_step_summary,
    format_tool_result_for_llm,
    get_current_timestamp,
    parse_tool_error_message,
    retry_with_backoff,
    should_continue_loop,
    validate_github_url,
    validate_review_request,
)


# =============================================================================
# MOCK CLASSES - reusable across all tests
# =============================================================================
class MockLLMClient:
    """
    Mock LLM client that returns scripted ReACT responses.
    Compatible with LLMClient interface (returns LLMResponse with .content).

    Usage:
        llm = MockLLMClient(["NEXT_TOOL: fetch_repository", "NEXT_TOOL: DONE"])
    """

    def __init__(self, responses: List[str] = None) -> None:
        self.responses = list(responses or [])
        self.call_count = 0
        self.prompts_received: List[str] = []

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Return next scripted response, or DONE if exhausted."""
        self.prompts_received.append(prompt)
        if self.call_count < len(self.responses):
            content = self.responses[self.call_count]
        else:
            content = "NEXT_TOOL: DONE\nREASON: No more responses scripted"
        self.call_count += 1
        return LLMResponse(
            content=content,
            provider=LLMProvider.MOCK,
            model="mock-test",
        )


class MockTool:
    """
    Mock tool with async run(params) method.
    Configurable: name, result, failure behavior, delay.

    Usage:
        tool = MockTool(name="pylint", result={"issues": 3})
    """

    def __init__(
        self,
        name: str = "mock_tool",
        result: Any = None,
        should_fail: bool = False,
        error_message: str = "Mock failure",
        delay: float = 0.0,
    ) -> None:
        self._name = name
        self._result = result if result is not None else {"status": "success"}
        self._should_fail = should_fail
        self._error_message = error_message
        self._delay = delay
        self.call_count = 0
        self.calls_received: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    async def run(self, params: Dict[str, Any]) -> Any:
        """Execute mock tool - configurable behavior."""
        self.call_count += 1
        self.calls_received.append(params)
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._should_fail:
            raise ValueError(self._error_message)
        return self._result


class FlakyMockTool:
    """
    Mock tool that fails N times then succeeds.
    Used to test retry logic.

    Usage:
        tool = FlakyMockTool(name="pylint", fail_count=2)
        # First 2 calls fail, 3rd succeeds
    """

    def __init__(self, name: str = "flaky", fail_count: int = 1) -> None:
        self._name = name
        self._fail_count = fail_count
        self.attempts = 0

    @property
    def name(self) -> str:
        return self._name

    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fails first N attempts, then succeeds."""
        self.attempts += 1
        if self.attempts <= self._fail_count:
            raise ValueError(f"Flaky failure on attempt {self.attempts}")
        return {"succeeded": True, "attempts": self.attempts}


# =============================================================================
# PYTEST FIXTURES
# =============================================================================
@pytest.fixture
def mock_llm() -> MockLLMClient:
    """Default mock LLM with DONE response."""
    return MockLLMClient()


@pytest.fixture
def scripted_llm() -> MockLLMClient:
    """LLM with a typical ReACT flow scripted."""
    return MockLLMClient([
        "NEXT_TOOL: fetch_repository\nREASON: Need to download",
        "NEXT_TOOL: analyze_code_structure\nREASON: Analyze it",
        "NEXT_TOOL: DONE\nREASON: All done",
    ])


@pytest.fixture
def mock_tools_registry() -> Dict[str, MockTool]:
    """Standard set of mock tools for testing."""
    return {
        "fetch_repository": MockTool(
            name="fetch_repository",
            result={"files": ["main.py", "utils.py"], "count": 2},
        ),
        "analyze_code_structure": MockTool(
            name="analyze_code_structure",
            result={"issues": [{"severity": "low", "title": "test issue"}]},
        ),
        "security_audit": MockTool(
            name="security_audit",
            result={"issues": []},
        ),
        "performance_analysis": MockTool(
            name="performance_analysis",
            result={"issues": []},
        ),
        "generate_report": MockTool(
            name="generate_report",
            result={"report_generated": True},
        ),
    }


@pytest.fixture
def agent(scripted_llm, mock_tools_registry) -> CodeReviewAgent:
    """Fully wired agent with mock LLM and tools."""
    return CodeReviewAgent(llm_client=scripted_llm, tools_registry=mock_tools_registry)


@pytest.fixture
def fresh_memory() -> AgentMemory:
    """Empty memory instance."""
    return AgentMemory()


# =============================================================================
# TEST CLASS 1: AGENT TYPES
# =============================================================================
class TestAgentTypes:
    """Tests for agent_types.py - dataclasses and enums."""

    def test_step_type_enum_values(self):
        """StepType enum should have THINK, ACT, OBSERVE, REFLECT values."""
        # Sab expected values present hain
        assert StepType.THINK.value == "think"
        assert StepType.ACT.value == "act"
        assert StepType.OBSERVE.value == "observe"
        assert StepType.REFLECT.value == "reflect"
        # Total 4 values
        assert len(list(StepType)) == 4

    def test_agent_status_enum_values(self):
        """AgentStatus enum should have all lifecycle states."""
        statuses = [s.value for s in AgentStatus]
        assert "idle" in statuses
        assert "thinking" in statuses
        assert "acting" in statuses
        assert "observing" in statuses
        assert "reflecting" in statuses
        assert "completed" in statuses
        assert "failed" in statuses

    def test_tool_call_creation(self):
        """ToolCall should store all fields and auto-set timestamp."""
        before = datetime.now(timezone.utc)
        call = ToolCall(tool_name="pylint", params={"file": "main.py"})
        after = datetime.now(timezone.utc)

        # Fields set correctly
        assert call.tool_name == "pylint"
        assert call.params == {"file": "main.py"}
        # Timestamp auto-set within reasonable window
        assert before <= call.timestamp <= after
        # call_id auto-generated UUID
        assert call.call_id is not None
        assert len(call.call_id) > 0

    def test_tool_call_with_empty_params(self):
        """ToolCall with no params should have empty dict, not None."""
        call = ToolCall(tool_name="simple")
        assert call.params == {}
        assert isinstance(call.params, dict)

    def test_tool_result_creation_success(self):
        """Successful ToolResult should have success=True and data."""
        result = ToolResult(
            tool_name="pylint",
            success=True,
            data={"issues": 3, "score": 8.5},
            execution_time=1.5,
        )
        assert result.success is True
        assert result.data == {"issues": 3, "score": 8.5}
        assert result.error is None
        assert result.execution_time == 1.5

    def test_tool_result_creation_failure(self):
        """Failed ToolResult should have success=False and error message."""
        result = ToolResult(
            tool_name="bandit",
            success=False,
            data={},
            error="Connection timeout",
            execution_time=30.0,
        )
        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.data == {}

    def test_agent_step_creation(self):
        """AgentStep should accept all fields and auto-set timestamp."""
        before = datetime.now(timezone.utc)
        step = AgentStep(
            step_number=1,
            step_type=StepType.THINK,
            thought="Need to analyze this code",
            action=ToolCall(tool_name="pylint", params={}),
            reflection="All good",
        )
        after = datetime.now(timezone.utc)

        assert step.step_number == 1
        assert step.step_type == StepType.THINK
        assert step.thought == "Need to analyze this code"
        assert step.action is not None
        assert step.action.tool_name == "pylint"
        assert step.reflection == "All good"
        assert before <= step.timestamp <= after

    def test_agent_step_optional_fields(self):
        """AgentStep with only required fields should work."""
        step = AgentStep(step_number=5, step_type=StepType.ACT)
        assert step.thought is None
        assert step.action is None
        assert step.observation is None
        assert step.reflection is None

    def test_review_request_with_github_url(self):
        """ReviewRequest with github_url should auto-set request_time."""
        before = datetime.now(timezone.utc)
        req = ReviewRequest(github_url="https://github.com/user/repo")
        after = datetime.now(timezone.utc)

        assert req.github_url == "https://github.com/user/repo"
        assert req.code_content is None
        assert req.analysis_type == "full"  # default
        assert req.request_time is not None
        assert before <= req.request_time <= after
        assert req.request_id is not None  # auto-generated UUID

    def test_review_request_with_code_content(self):
        """ReviewRequest with code_content should work."""
        req = ReviewRequest(code_content="def foo(): pass", analysis_type="security")
        assert req.code_content == "def foo(): pass"
        assert req.github_url is None
        assert req.analysis_type == "security"

    def test_review_result_creation(self):
        """ReviewResult should hold all output fields."""
        result = ReviewResult(
            success=True,
            quality_score=8.5,
            issues=[{"severity": "low", "title": "test"}],
            report="# Report\n\nAll good",
            steps_taken=5,
            execution_time=12.3,
        )
        assert result.success is True
        assert result.quality_score == 8.5
        assert len(result.issues) == 1
        assert result.report.startswith("# Report")
        assert result.steps_taken == 5
        assert result.execution_time == 12.3
        assert result.errors is None  # default

    def test_review_result_to_dict(self):
        """ReviewResult.to_dict() should return API-friendly dict."""
        result = ReviewResult(
            success=True,
            quality_score=7.0,
            issues=[],
            report="test",
            steps_taken=3,
            execution_time=5.0,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["success"] is True
        assert d["quality_score"] == 7.0
        assert d["steps_taken"] == 3
        assert "timestamp" in d


# =============================================================================
# TEST CLASS 2: AGENT MEMORY
# =============================================================================
class TestAgentMemory:
    """Tests for AgentMemory class - memory management system."""

    def test_memory_initialization(self, fresh_memory):
        """New memory should be empty with default max_history."""
        assert len(fresh_memory) == 0
        assert fresh_memory.max_history == MEMORY_MAX_SIZE
        assert fresh_memory.step_count == 0
        assert fresh_memory.tool_count == 0
        assert fresh_memory.is_full is False

    def test_memory_custom_max_history(self):
        """Memory should accept custom max_history parameter."""
        mem = AgentMemory(max_history=10)
        assert mem.max_history == 10
        assert mem.is_full is False

    def test_add_step(self, fresh_memory):
        """Adding a step should increase step_count."""
        step = AgentStep(step_number=1, step_type=StepType.THINK, thought="test")
        fresh_memory.add_step(step)

        assert fresh_memory.step_count == 1
        assert len(fresh_memory) == 1

    def test_add_multiple_steps(self, fresh_memory):
        """Multiple steps should be stored in order."""
        for i in range(5):
            fresh_memory.add_step(
                AgentStep(step_number=i + 1, step_type=StepType.THINK, thought=f"step {i}")
            )
        assert fresh_memory.step_count == 5

    def test_memory_max_history_limit(self):
        """Memory should evict oldest steps when max exceeded (FIFO)."""
        mem = AgentMemory(max_history=3)
        # Add 5 steps with max=3
        for i in range(5):
            mem.add_step(AgentStep(step_number=i + 1, step_type=StepType.THINK))
        # Should keep only last 3 (steps 3, 4, 5)
        assert mem.step_count == 3
        # Verify oldest are evicted
        recent = mem.get_recent_steps(10)
        step_numbers = [s.step_number for s in recent]
        assert 1 not in step_numbers
        assert 2 not in step_numbers
        assert 3 in step_numbers
        assert 5 in step_numbers

    def test_add_tool_result(self, fresh_memory):
        """Tool result should be stored in tool_results dict."""
        result = ToolResult(tool_name="pylint", success=True, data={})
        fresh_memory.add_tool_result("pylint", result)

        assert fresh_memory.tool_count == 1
        assert fresh_memory.get_last_tool_result("pylint") == result

    def test_add_multiple_results_same_tool(self, fresh_memory):
        """Multiple results for same tool should be stored in list."""
        for i in range(3):
            fresh_memory.add_tool_result(
                "pylint",
                ToolResult(tool_name="pylint", success=True, data={"i": i}),
            )
        all_results = fresh_memory.get_all_tool_results("pylint")
        assert len(all_results) == 3
        # Verify order preserved
        assert all_results[0].data["i"] == 0
        assert all_results[2].data["i"] == 2

    def test_get_last_tool_result(self, fresh_memory):
        """get_last_tool_result should return most recent."""
        r1 = ToolResult(tool_name="x", success=True, data={"v": 1})
        r2 = ToolResult(tool_name="x", success=True, data={"v": 2})
        r3 = ToolResult(tool_name="x", success=True, data={"v": 3})
        fresh_memory.add_tool_result("x", r1)
        fresh_memory.add_tool_result("x", r2)
        fresh_memory.add_tool_result("x", r3)

        last = fresh_memory.get_last_tool_result("x")
        assert last == r3
        assert last.data["v"] == 3

    def test_get_last_tool_result_not_found(self, fresh_memory):
        """get_last_tool_result should return None for unknown tool."""
        assert fresh_memory.get_last_tool_result("never_used") is None

    def test_get_context_for_llm(self, fresh_memory):
        """get_context_for_llm should return formatted string with recent steps."""
        for i in range(5):
            fresh_memory.add_step(
                AgentStep(
                    step_number=i + 1,
                    step_type=StepType.THINK,
                    thought=f"step {i} thought",
                )
            )
        context = fresh_memory.get_context_for_llm()
        assert isinstance(context, str)
        assert "AGENT MEMORY CONTEXT" in context
        # Last step's thought should be in context
        assert "step 4 thought" in context

    def test_get_context_for_llm_empty(self, fresh_memory):
        """get_context_for_llm on empty memory should return sensible string."""
        context = fresh_memory.get_context_for_llm()
        assert "No steps yet" in context

    def test_clear_memory(self, fresh_memory):
        """clear() should remove all steps and tool results."""
        fresh_memory.add_step(AgentStep(step_number=1, step_type=StepType.THINK))
        fresh_memory.add_tool_result("x", ToolResult(tool_name="x", success=True, data={}))
        assert fresh_memory.step_count == 1
        assert fresh_memory.tool_count == 1

        fresh_memory.clear()
        assert fresh_memory.step_count == 0
        assert fresh_memory.tool_count == 0

    def test_memory_to_dict(self, fresh_memory):
        """to_dict() should return dict with counts and metadata."""
        fresh_memory.add_step(AgentStep(step_number=1, step_type=StepType.THINK))
        fresh_memory.add_tool_result("pylint", ToolResult(tool_name="pylint", success=True, data={}))

        d = fresh_memory.to_dict()
        assert isinstance(d, dict)
        assert d["step_count"] == 1
        assert d["tool_results_count"] == 1
        assert d["unique_tools_used"] == 1
        assert "created_at" in d
        assert "last_updated" in d

    def test_memory_repr(self, fresh_memory):
        """__repr__ should return descriptive string."""
        fresh_memory.add_step(AgentStep(step_number=1, step_type=StepType.THINK))
        fresh_memory.add_step(AgentStep(step_number=2, step_type=StepType.ACT))
        fresh_memory.add_tool_result("x", ToolResult(tool_name="x", success=True, data={}))

        r = repr(fresh_memory)
        assert "AgentMemory" in r
        assert "steps=2" in r
        assert "tools=1" in r

    def test_get_steps_by_type(self, fresh_memory):
        """get_steps_by_type should filter steps correctly."""
        fresh_memory.add_step(AgentStep(step_number=1, step_type=StepType.THINK))
        fresh_memory.add_step(AgentStep(step_number=2, step_type=StepType.ACT))
        fresh_memory.add_step(AgentStep(step_number=3, step_type=StepType.THINK))

        think_steps = fresh_memory.get_steps_by_type(StepType.THINK)
        act_steps = fresh_memory.get_steps_by_type(StepType.ACT)
        assert len(think_steps) == 2
        assert len(act_steps) == 1

    def test_get_recent_steps(self, fresh_memory):
        """get_recent_steps should return last N steps in order."""
        for i in range(10):
            fresh_memory.add_step(AgentStep(step_number=i + 1, step_type=StepType.THINK))
        recent = fresh_memory.get_recent_steps(3)
        assert len(recent) == 3
        assert recent[0].step_number == 8
        assert recent[2].step_number == 10


# =============================================================================
# TEST CLASS 3: TOOL ORCHESTRATOR
# =============================================================================
class TestToolOrchestrator:
    """Tests for ToolOrchestrator - tool execution management."""

    def test_orchestrator_initialization(self, mock_tools_registry):
        """Orchestrator should store tools and initialize empty state."""
        orch = ToolOrchestrator(mock_tools_registry)
        assert orch.tool_count == 5
        assert "fetch_repository" in orch.registered_tools

    def test_orchestrator_empty_registry(self):
        """Orchestrator should handle empty registry."""
        orch = ToolOrchestrator({})
        assert orch.tool_count == 0
        assert orch.registered_tools == []

    def test_validate_tool_exists(self, mock_tools_registry):
        """Orchestrator should correctly check tool availability."""
        orch = ToolOrchestrator(mock_tools_registry)
        assert orch._is_tool_available("fetch_repository") is True
        assert orch._is_tool_available("nonexistent") is False

    def test_get_tool(self, mock_tools_registry):
        """_get_tool should return tool instance or None."""
        orch = ToolOrchestrator(mock_tools_registry)
        tool = orch._get_tool("fetch_repository")
        assert tool is not None
        assert orch._get_tool("nonexistent") is None

    async def test_execute_tool_success(self, mock_tools_registry):
        """Successful tool execution should return success ToolResult."""
        orch = ToolOrchestrator(mock_tools_registry)
        result = await orch.execute_tool("fetch_repository", {}, timeout=5, retries=0)
        assert result.success is True
        assert result.tool_name == "fetch_repository"
        assert result.execution_time > 0
        assert "files" in result.data

    async def test_execute_tool_failure(self):
        """Failing tool should return failure ToolResult after retries."""
        tools = {"bad": MockTool(name="bad", should_fail=True, error_message="oops")}
        orch = ToolOrchestrator(tools)
        result = await orch.execute_tool("bad", {}, timeout=5, retries=0)
        assert result.success is False
        assert "oops" in result.error

    async def test_execute_tool_timeout(self):
        """Tool that takes too long should timeout gracefully."""
        tools = {"slow": MockTool(name="slow", delay=2.0)}
        orch = ToolOrchestrator(tools)
        result = await orch.execute_tool("slow", {}, timeout=1, retries=0)
        assert result.success is False
        assert "Timeout" in result.error

    async def test_execute_tool_retry_then_success(self):
        """Tool that fails N times then succeeds should eventually work."""
        # 2s total backoff (1s between 2 retries) + tool execution
        tools = {"flaky": FlakyMockTool(name="flaky", fail_count=1)}
        orch = ToolOrchestrator(tools)
        result = await orch.execute_tool("flaky", {}, timeout=5, retries=2)
        assert result.success is True
        # Original + 2 retries; first attempt fails, second succeeds
        assert orch._get_tool("flaky").attempts == 2

    async def test_execute_tool_max_retries_exceeded(self):
        """Tool that always fails should fail after all retries."""
        tools = {"bad": MockTool(name="bad", should_fail=True)}
        orch = ToolOrchestrator(tools)
        result = await orch.execute_tool("bad", {}, timeout=5, retries=2)
        assert result.success is False
        # 3 total attempts (1 + 2 retries)
        assert orch.get_failed_tools()["bad"] == 3

    async def test_execute_tool_not_found(self, mock_tools_registry):
        """Non-existent tool should return error result, not crash."""
        orch = ToolOrchestrator(mock_tools_registry)
        result = await orch.execute_tool("nonexistent", {}, timeout=5, retries=0)
        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_execute_tools_parallel(self):
        """Parallel execution should run all tools simultaneously."""
        tools = {
            "a": MockTool(name="a", result={"v": "a"}, delay=0.05),
            "b": MockTool(name="b", result={"v": "b"}, delay=0.05),
            "c": MockTool(name="c", result={"v": "c"}, delay=0.05),
        }
        orch = ToolOrchestrator(tools)
        start = asyncio.get_event_loop().time()
        results = await orch.execute_tools_parallel([
            ("a", {}), ("b", {}), ("c", {}),
        ])
        elapsed = asyncio.get_event_loop().time() - start
        # Parallel: should take ~0.05s, not 0.15s
        assert elapsed < 0.12
        assert len(results) == 3
        # Order preserved
        assert results[0].data["v"] == "a"
        assert results[1].data["v"] == "b"
        assert results[2].data["v"] == "c"

    async def test_execute_tools_parallel_empty(self, mock_tools_registry):
        """Parallel with empty list should return empty list."""
        orch = ToolOrchestrator(mock_tools_registry)
        results = await orch.execute_tools_parallel([])
        assert results == []

    async def test_get_execution_history(self, mock_tools_registry):
        """get_execution_history should return all results in order."""
        orch = ToolOrchestrator(mock_tools_registry)
        await orch.execute_tool("fetch_repository", {}, timeout=5, retries=0)
        await orch.execute_tool("analyze_code_structure", {}, timeout=5, retries=0)
        await orch.execute_tool("generate_report", {}, timeout=5, retries=0)

        history = orch.get_execution_history()
        assert len(history) == 3
        assert history[0].tool_name == "fetch_repository"
        assert history[2].tool_name == "generate_report"

    async def test_get_tool_stats(self, mock_tools_registry):
        """get_tool_stats should return counts and timing in new spec format."""
        orch = ToolOrchestrator(mock_tools_registry)
        # Run 3 executions: 2 success, 1 failure
        await orch.execute_tool("fetch_repository", {}, timeout=5, retries=0)
        await orch.execute_tool("fetch_repository", {}, timeout=5, retries=0)
        await orch.execute_tool("bad_tool", {}, timeout=5, retries=0)  # not in registry

        stats = orch.get_tool_stats()
        # New spec format
        assert "total_executions" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "average_time" in stats
        assert "tools" in stats
        # Per-tool: executions, success, avg_time
        assert "fetch_repository" in stats["tools"]
        fr_stats = stats["tools"]["fetch_repository"]
        assert "executions" in fr_stats
        assert "success" in fr_stats
        assert "avg_time" in fr_stats

    async def test_reset_history(self, mock_tools_registry):
        """reset_history should clear all execution state."""
        orch = ToolOrchestrator(mock_tools_registry)
        await orch.execute_tool("fetch_repository", {}, timeout=5, retries=0)
        assert len(orch.get_execution_history()) == 1

        orch.reset_history()
        assert len(orch.get_execution_history()) == 0
        stats = orch.get_tool_stats()
        assert stats["total_executions"] == 0

    async def test_should_retry_tool(self, mock_tools_registry):
        """should_retry_tool should respect RETRY_ATTEMPTS limit."""
        orch = ToolOrchestrator(mock_tools_registry)
        # No failures yet - should be retryable
        assert orch.should_retry_tool("fetch_repository") is True

        # Cause failures (1 + 2 retries = 3 attempts)
        tools_with_fail = {"bad": MockTool(name="bad", should_fail=True)}
        orch2 = ToolOrchestrator(tools_with_fail)
        await orch2.execute_tool("bad", {}, timeout=5, retries=2)
        # 3 failures, max is 2, so no more retries
        assert orch2.should_retry_tool("bad") is False

    async def test_reset_tool_failures(self):
        """reset_tool_failures should clear specific tool's failure count."""
        # Create orchestrator with directly-failing tool (no dict replacement)
        failing_tool = MockTool(name="fetch_repository", should_fail=True)
        orch = ToolOrchestrator({"fetch_repository": failing_tool})
        await orch.execute_tool("fetch_repository", {}, timeout=5, retries=0)
        assert orch.get_failed_tools().get("fetch_repository", 0) > 0

        # Reset
        orch.reset_tool_failures("fetch_repository")
        assert orch.get_failed_tools()["fetch_repository"] == 0

    def test_orchestrator_repr(self, mock_tools_registry):
        """__repr__ should return descriptive string."""
        orch = ToolOrchestrator(mock_tools_registry)
        r = repr(orch)
        assert "ToolOrchestrator" in r
        assert "tools=5" in r


# =============================================================================
# TEST CLASS 4: AGENT UTILS
# =============================================================================
class TestAgentUtils:
    """Tests for utils.py - pure helper functions."""

    def test_format_memory_for_llm(self, fresh_memory):
        """format_memory_for_llm should return readable string."""
        for i in range(3):
            fresh_memory.add_step(
                AgentStep(
                    step_number=i + 1,
                    step_type=StepType.THINK,
                    thought=f"thought {i}",
                )
            )
        result = format_memory_for_llm(fresh_memory)
        assert "Recent Agent Activity" in result
        assert "thought 0" in result

    def test_format_memory_for_llm_empty(self, fresh_memory):
        """Empty memory should return 'No activity yet' message."""
        result = format_memory_for_llm(fresh_memory)
        assert "No activity yet" in result

    def test_extract_tool_name_from_thought(self):
        """Should extract tool name from thought text."""
        thought = "I should use fetch_repository to download the code"
        tool = extract_tool_name_from_thought(thought, ["fetch_repository", "analyze_code"])
        assert tool == "fetch_repository"

    def test_extract_tool_name_case_insensitive(self):
        """Tool name extraction should be case-insensitive."""
        thought = "Use ANALYZE_CODE for analysis"
        tool = extract_tool_name_from_thought(thought, ["analyze_code"])
        assert tool == "analyze_code"

    def test_extract_tool_name_not_found(self):
        """Should return None when no tool name in thought."""
        thought = "Just thinking about the problem"
        tool = extract_tool_name_from_thought(thought, ["fetch_repository"])
        assert tool is None

    def test_extract_tool_name_empty_inputs(self):
        """Empty inputs should return None, not crash."""
        assert extract_tool_name_from_thought("", ["x"]) is None
        assert extract_tool_name_from_thought("text", []) is None

    def test_extract_tool_params_from_response_json(self):
        """Should extract params from JSON in response."""
        response = '{"github_url": "https://github.com/x/y", "branch": "main"}'
        params = extract_tool_params_from_response(response, "fetch_repository")
        assert params["github_url"] == "https://github.com/x/y"
        assert params["branch"] == "main"

    def test_extract_tool_params_from_response_kv(self):
        """Should extract params from key=value pairs."""
        response = 'fetch_repository with github_url="https://github.com/x/y" language="python"'
        params = extract_tool_params_from_response(response, "fetch_repository")
        assert params["github_url"] == "https://github.com/x/y"
        assert params["language"] == "python"

    def test_extract_tool_params_empty(self):
        """Empty response should return empty dict."""
        assert extract_tool_params_from_response("", "x") == {}

    def test_format_tool_result_for_llm_success(self):
        """Successful result should show OK + time + data."""
        result = ToolResult(
            tool_name="pylint", success=True,
            data={"issues": 5}, execution_time=2.5,
        )
        formatted = format_tool_result_for_llm(result)
        assert "pylint" in formatted
        assert "2.5" in formatted
        assert "issues" in formatted

    def test_format_tool_result_for_llm_failure(self):
        """Failed result should show FAIL + error."""
        result = ToolResult(
            tool_name="bandit", success=False,
            error="Connection error", execution_time=0.1,
        )
        formatted = format_tool_result_for_llm(result)
        assert "bandit" in formatted
        assert "Connection error" in formatted

    def test_should_continue_loop_max_steps(self):
        """Should return False when max_steps reached."""
        assert should_continue_loop(10, 10, "thinking") is False
        assert should_continue_loop(11, 10, "thinking") is False

    def test_should_continue_loop_done_keyword(self):
        """Should return False when reflection contains DONE."""
        assert should_continue_loop(3, 10, "TASK COMPLETE - DONE") is False
        assert should_continue_loop(3, 10, "I think we're done here") is False
        assert should_continue_loop(3, 10, "task completed successfully") is False

    def test_should_continue_loop_continue(self):
        """Should return True when no completion signal."""
        assert should_continue_loop(3, 10, "Need more analysis") is True
        assert should_continue_loop(3, 10, "") is True

    def test_validate_github_url_valid(self):
        """Valid GitHub URLs should return True."""
        valid_urls = [
            "https://github.com/user/repo",
            "https://github.com/user-name/repo-name",
            "https://github.com/user/repo/",
            "https://github.com/user_name/repo.js",
        ]
        for url in valid_urls:
            assert validate_github_url(url) is True, f"Should be valid: {url}"

    def test_validate_github_url_invalid(self):
        """Invalid URLs should return False."""
        invalid_urls = [
            "",
            "not-a-url",
            "https://gitlab.com/user/repo",
            "github.com/user/repo",  # missing https://
            "https://github.com/user",  # missing repo
            None,
        ]
        for url in invalid_urls:
            assert validate_github_url(url) is False, f"Should be invalid: {url}"

    def test_validate_review_request_valid(self):
        """Valid request with github_url should pass validation."""
        req = ReviewRequest(github_url="https://github.com/user/repo", analysis_type="full")
        is_valid, error = validate_review_request(req)
        assert is_valid is True
        assert error is None

    def test_validate_review_request_with_code(self):
        """Valid request with code_content should also pass."""
        req = ReviewRequest(code_content="print('hi')", analysis_type="security")
        is_valid, error = validate_review_request(req)
        assert is_valid is True

    def test_validate_review_request_both_empty(self):
        """Request with no source should fail with empty error."""
        req = ReviewRequest(analysis_type="full")
        is_valid, error = validate_review_request(req)
        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_review_request_invalid_type(self):
        """Request with invalid analysis_type should fail."""
        req = ReviewRequest(code_content="x", analysis_type="invalid_type")
        is_valid, error = validate_review_request(req)
        assert is_valid is False
        assert "analysis_type" in error.lower()

    def test_validate_review_request_invalid_url(self):
        """Request with malformed GitHub URL should fail."""
        req = ReviewRequest(github_url="https://gitlab.com/x/y", analysis_type="full")
        is_valid, error = validate_review_request(req)
        assert is_valid is False
        assert "github" in error.lower()

    def test_create_tool_call_from_response(self):
        """Should create ToolCall from response with valid tool."""
        response = 'analyze_code with language="python"'
        call = create_tool_call_from_response(
            response, "analyze_code", ["analyze_code", "fetch_repository"]
        )
        assert call is not None
        assert call.tool_name == "analyze_code"
        assert call.params.get("language") == "python"

    def test_create_tool_call_invalid_tool(self):
        """Should return None for invalid tool name."""
        response = "some response"
        call = create_tool_call_from_response(
            response, "nonexistent_tool", ["fetch_repository"]
        )
        assert call is None

    def test_format_step_summary(self):
        """format_step_summary should return one-line string."""
        step = AgentStep(
            step_number=3,
            step_type=StepType.ACT,
            action=ToolCall(tool_name="pylint", params={}),
            observation=ToolResult(
                tool_name="pylint", success=True, data={}, execution_time=2.1
            ),
        )
        summary = format_step_summary(step)
        assert "Step 3" in summary
        assert "pylint" in summary

    def test_get_current_timestamp(self):
        """get_current_timestamp should return timezone-aware UTC datetime."""
        ts = get_current_timestamp()
        assert isinstance(ts, datetime)
        assert ts.tzinfo is not None
        assert ts.tzinfo == timezone.utc

    def test_parse_tool_error_message(self):
        """Should split 'Type: detail' into tuple."""
        err_type, err_detail = parse_tool_error_message("TimeoutError: Tool exceeded 120s")
        assert err_type == "TimeoutError"
        assert err_detail == "Tool exceeded 120s"

    def test_parse_tool_error_message_no_colon(self):
        """No colon should return whole as type, empty detail."""
        err_type, err_detail = parse_tool_error_message("Some error")
        assert err_type == "Some error"
        assert err_detail == ""

    def test_parse_tool_error_message_empty(self):
        """Empty input should return empty tuple."""
        err_type, err_detail = parse_tool_error_message("")
        assert err_type == ""
        assert err_detail == ""

    def test_retry_with_backoff(self):
        """retry_with_backoff should follow exponential pattern."""
        assert retry_with_backoff(0) == 1.0
        assert retry_with_backoff(1) == 2.0
        assert retry_with_backoff(2) == 4.0
        assert retry_with_backoff(3) == 8.0
        # Cap at 30s
        assert retry_with_backoff(10) == 30.0


# =============================================================================
# TEST CLASS 5: CODE REVIEW AGENT (Main - most important)
# =============================================================================
class TestCodeReviewAgent:
    """Tests for CodeReviewAgent - the main ReACT loop."""

    def test_agent_initialization(self, mock_tools_registry):
        """Agent should initialize with IDLE status and proper components."""
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)

        assert agent.status == AgentStatus.IDLE
        assert agent.current_step == 0
        assert agent.memory is not None
        assert agent.orchestrator is not None
        assert len(agent.available_tools) == 5

    def test_agent_initialization_empty_registry(self):
        """Agent should handle empty tools registry."""
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm_client=llm, tools_registry={})
        assert agent.tool_count == 0

    def test_agent_repr(self, agent):
        """__repr__ should return descriptive string."""
        r = repr(agent)
        assert "CodeReviewAgent" in r
        assert "status=idle" in r

    async def test_agent_think_step(self, agent):
        """_think_step should return (thought, should_continue) tuple."""
        request = ReviewRequest(code_content="x = 1", analysis_type="full")
        # Mock LLM returns "NEXT_TOOL: analyze_code_structure\n..."
        thought, should_continue = await agent._think_step(request)

        assert isinstance(thought, str)
        assert "NEXT_TOOL" in thought
        assert should_continue is True

    async def test_agent_think_step_done(self, mock_tools_registry):
        """_think_step should return False when LLM says DONE."""
        llm = MockLLMClient(["NEXT_TOOL: DONE\nREASON: All done"])
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)
        request = ReviewRequest(code_content="x", analysis_type="full")

        thought, should_continue = await agent._think_step(request)
        assert should_continue is False

    async def test_agent_act_step(self, agent):
        """_act_step should return ToolCall for valid thought."""
        # _act_step uses self.current_request for params; set it for test
        agent.current_request = ReviewRequest(github_url="https://github.com/x/y")
        thought = "I need to use fetch_repository to download the code"
        tool_call = await agent._act_step(thought, 1)
        assert tool_call is not None
        assert tool_call.tool_name == "fetch_repository"

    async def test_agent_act_step_no_tool(self, agent):
        """_act_step should return None when no tool found in thought."""
        thought = "Just thinking about the problem"
        tool_call = await agent._act_step(thought, 1)
        assert tool_call is None

    async def test_agent_observe_step(self, agent):
        """_observe_step should execute tool and return result."""
        tool_call = ToolCall(tool_name="fetch_repository", params={"github_url": "x"})
        result = await agent._observe_step(tool_call)
        assert isinstance(result, ToolResult)
        assert result.tool_name == "fetch_repository"
        # Should be stored in memory
        assert agent.memory.get_last_tool_result("fetch_repository") is not None

    async def test_agent_reflect_step_success(self, agent):
        """_reflect_step should return reflection string on success."""
        result = ToolResult(tool_name="pylint", success=True, data={}, execution_time=1.0)
        reflection = await agent._reflect_step(result, 1)
        assert isinstance(reflection, str)
        assert "Step 1" in reflection

    async def test_agent_reflect_step_failure(self, agent):
        """_reflect_step should handle failure case."""
        result = ToolResult(
            tool_name="pylint", success=False,
            error="timeout", execution_time=30.0,
        )
        reflection = await agent._reflect_step(result, 1)
        assert "failed" in reflection.lower() or "fail" in reflection.lower()

    async def test_agent_complete_run(self, scripted_llm, mock_tools_registry):
        """⭐ Most important: full agent run should produce ReviewResult."""
        agent = CodeReviewAgent(
            llm_client=scripted_llm, tools_registry=mock_tools_registry
        )
        request = ReviewRequest(
            github_url="https://github.com/user/repo", analysis_type="full"
        )

        result = await agent.run(request, max_steps=10)

        # Returns ReviewResult
        assert isinstance(result, ReviewResult)
        # Status COMPLETED
        assert agent.status == AgentStatus.COMPLETED
        # Steps taken > 0 (scripted 2 actions before DONE)
        assert result.steps_taken > 0
        # Quality score set
        assert isinstance(result.quality_score, float)
        # Report generated
        assert isinstance(result.report, str)
        assert len(result.report) > 0
        # Execution time tracked
        assert result.execution_time > 0

    async def test_agent_run_with_github_url(self, scripted_llm, mock_tools_registry):
        """Agent should pass github_url to fetch_repository tool."""
        agent = CodeReviewAgent(
            llm_client=scripted_llm, tools_registry=mock_tools_registry
        )
        request = ReviewRequest(
            github_url="https://github.com/user/repo", analysis_type="full"
        )
        await agent.run(request, max_steps=10)

        # fetch_repository tool was called with github_url in params
        fetch_tool = mock_tools_registry["fetch_repository"]
        assert fetch_tool.call_count > 0
        # Check that github_url was passed in at least one call
        all_params = fetch_tool.calls_received
        github_url_passed = any(
            "github_url" in str(p) for p in all_params
        )
        assert github_url_passed

    async def test_agent_run_with_direct_code(self, mock_tools_registry):
        """Agent should handle ReviewRequest with direct code_content."""
        llm = MockLLMClient([
            "NEXT_TOOL: analyze_code_structure\nREASON: Direct code analysis",
            "NEXT_TOOL: DONE\nREASON: Done",
        ])
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)
        request = ReviewRequest(
            code_content="def hello():\n    print('hi')",
            analysis_type="full",
        )

        result = await agent.run(request, max_steps=5)
        assert result.success is True
        # analyze_code_structure was called
        assert mock_tools_registry["analyze_code_structure"].call_count > 0

    async def test_agent_run_max_steps_limit(self, mock_tools_registry):
        """Agent should stop at max_steps even if LLM keeps going."""
        # LLM never says DONE - keep requesting tools
        llm = MockLLMClient([
            "NEXT_TOOL: analyze_code_structure\nREASON: keep going",
            "NEXT_TOOL: security_audit\nREASON: keep going",
            "NEXT_TOOL: performance_analysis\nREASON: keep going",
            "NEXT_TOOL: analyze_code_structure\nREASON: keep going",
            "NEXT_TOOL: analyze_code_structure\nREASON: keep going",
        ])
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)
        request = ReviewRequest(code_content="x", analysis_type="full")

        result = await agent.run(request, max_steps=3)
        # Should stop at 3 steps, not run forever
        assert result.steps_taken == 3
        # Status is still COMPLETED (just hit limit)
        assert agent.status == AgentStatus.COMPLETED

    async def test_agent_run_invalid_request(self, mock_tools_registry):
        """Invalid request (no source) should return failure result gracefully."""
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)
        # Empty request - no github_url, no code_content
        request = ReviewRequest(analysis_type="full")

        result = await agent.run(request)
        assert result.success is False
        assert result.steps_taken == 0
        # No LLM calls made for invalid request
        assert llm.call_count == 0

    async def test_agent_run_early_done(self, mock_tools_registry):
        """Agent should exit early when LLM signals DONE immediately."""
        llm = MockLLMClient(["NEXT_TOOL: DONE\nREASON: Nothing to do"])
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)
        request = ReviewRequest(code_content="x", analysis_type="full")

        result = await agent.run(request)
        assert result.steps_taken == 0
        # No tool calls made
        assert result.quality_score == 10.0  # no issues = perfect

    async def test_agent_memory_tracking(self, scripted_llm, mock_tools_registry):
        """Agent should track all steps and tool results in memory."""
        agent = CodeReviewAgent(
            llm_client=scripted_llm, tools_registry=mock_tools_registry
        )
        request = ReviewRequest(github_url="https://github.com/x/y", analysis_type="full")
        await agent.run(request, max_steps=10)

        # Memory has steps recorded
        assert agent.memory.step_count > 0
        # Tool results stored
        assert agent.memory.tool_count > 0
        # Summary works
        summary = agent.get_memory_summary()
        assert "steps completed" in summary

    async def test_agent_error_handling(self, mock_tools_registry):
        """Agent should handle tool failures gracefully without crashing."""
        # Make fetch_repository fail
        mock_tools_registry["fetch_repository"] = MockTool(
            name="fetch_repository", should_fail=True, error_message="network down"
        )
        llm = MockLLMClient([
            "NEXT_TOOL: fetch_repository\nREASON: try fetch",
            "NEXT_TOOL: analyze_code_structure\nREASON: try analyze",
            "NEXT_TOOL: DONE\nREASON: stop",
        ])
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)
        request = ReviewRequest(code_content="x", analysis_type="full")

        # Should not raise exception
        result = await agent.run(request, max_steps=5)
        # Status should be COMPLETED (not FAILED) - we handled the tool error
        assert agent.status == AgentStatus.COMPLETED
        # Result exists (even if critical tool failed)
        assert result is not None

    async def test_agent_status_transitions(self, scripted_llm, mock_tools_registry):
        """Agent status should transition through ReACT phases."""
        agent = CodeReviewAgent(
            llm_client=scripted_llm, tools_registry=mock_tools_registry
        )
        assert agent.status == AgentStatus.IDLE

        request = ReviewRequest(code_content="x", analysis_type="full")
        await agent.run(request, max_steps=10)

        # After completion, status should be COMPLETED
        assert agent.status == AgentStatus.COMPLETED

    async def test_agent_multiple_sequential_runs(self, mock_tools_registry):
        """Agent should handle multiple runs by resetting state."""
        # 6 responses: 2 runs × 3 LLM calls each (action, action, DONE)
        llm = MockLLMClient([
            "NEXT_TOOL: analyze_code_structure\nREASON: run 1",
            "NEXT_TOOL: DONE\nREASON: end run 1",
            "NEXT_TOOL: analyze_code_structure\nREASON: run 2",
            "NEXT_TOOL: DONE\nREASON: end run 2",
            "NEXT_TOOL: DONE\nREASON: extra",
            "NEXT_TOOL: DONE\nREASON: extra",
        ])
        agent = CodeReviewAgent(llm_client=llm, tools_registry=mock_tools_registry)

        # First run
        r1 = await agent.run(ReviewRequest(code_content="x = 1"))
        first_step = agent.current_step
        # Second run - state should reset
        r2 = await agent.run(ReviewRequest(code_content="y = 2"))

        # Both runs should complete successfully
        assert r1.success is True
        assert r2.success is True
        # Memory cleared between runs - now has run 2's steps
        assert agent.memory.step_count > 0  # has new run's steps
        # current_step reflects last run
        assert agent.current_step == first_step

    def test_agent_get_memory_summary(self, agent):
        """get_memory_summary should return string summary."""
        summary = agent.get_memory_summary()
        assert "steps completed" in summary
