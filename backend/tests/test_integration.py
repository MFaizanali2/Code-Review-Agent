"""
End-to-end integration tests across all system layers.

Covers 5 flow categories:
1. Agent + ReACT Loop (think -> act -> observe -> reflect)
2. Tool orchestration (single, parallel, sequential)
3. API endpoints (sync review, async review, history)
4. Database persistence (save, retrieve, history)
5. Error handling across all layers
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent.agent import CodeReviewAgent
from agent.core.react_loop import LoopResult, LoopStatus, ReACTConfig
from agent.core.state import AgentState, StateManager, StepType
from agent.llm.client import LLMClient, LLMProvider, LLMResponse, MockLLMClient
from agent.memory.conversation import ConversationMemory, MessageRole
from agent.tools.base import BaseTool, ToolResult, ToolSchema
from agent.tools.loader import load_builtin_tools, validate_tool
from agent.tools.registry import ToolRegistry


# =============================================================================
# HELPER: Test tools for controlled integration testing
# =============================================================================

class FetchRepoMockTool(BaseTool):
    """Mock tool that simulates fetching a GitHub repository."""

    @property
    def name(self) -> str:
        return "fetch_repository"

    @property
    def description(self) -> str:
        return "GitHub repository clone karo aur files list karo"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        url = tool_input.get("github_url", "")
        if not url:
            return ToolResult(success=False, data={}, error="No URL provided")
        return ToolResult(success=True, data={
            "status": "success",
            "repo_path": "/tmp/test_repo",
            "file_count": 10,
            "python_file_count": 5,
            "files": ["main.py", "utils.py", "test_main.py"],
        })


class AnalyzeCodeMockTool(BaseTool):
    """Mock tool that simulates code analysis."""

    @property
    def name(self) -> str:
        return "analyze_code_structure"

    @property
    def description(self) -> str:
        return "Python file ka structure analyze karo"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, data={
            "status": "success",
            "file": tool_input.get("code_path", "unknown.py"),
            "functions": ["process_data", "validate_input"],
            "classes": ["DataProcessor"],
            "lines_of_code": 150,
            "complexity": 5,
        })


class SecurityCheckMockTool(BaseTool):
    """Mock tool that simulates security scanning."""

    @property
    def name(self) -> str:
        return "check_security"

    @property
    def description(self) -> str:
        return "Python file mein security vulnerabilities scan karo"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, data={
            "status": "success",
            "vulnerabilities": [
                {"line": 42, "issue": "Hardcoded password", "severity": "HIGH"},
            ],
            "total_issues": 1,
            "risk_level": "HIGH",
        })


class PerformanceCheckMockTool(BaseTool):
    """Mock tool that simulates performance checking."""

    @property
    def name(self) -> str:
        return "check_performance"

    @property
    def description(self) -> str:
        return "Python code mein performance issues detect karo"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, data={
            "status": "success",
            "issues": [
                {"line": 15, "issue": "Nested loop O(n\u00b2)", "severity": "MEDIUM"},
            ],
            "total_issues": 1,
            "performance_score": 85,
        })


class CrashTool(BaseTool):
    """Tool that always crashes - tests error handling."""

    @property
    def name(self) -> str:
        return "crash_tool"

    @property
    def description(self) -> str:
        return "Always crashes when run"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        raise RuntimeError("Simulated crash")


def make_registry_with_mock_tools() -> ToolRegistry:
    """Create a ToolRegistry populated with mock tools for testing."""
    registry = ToolRegistry()
    registry.register(FetchRepoMockTool())
    registry.register(AnalyzeCodeMockTool())
    registry.register(SecurityCheckMockTool())
    registry.register(PerformanceCheckMockTool())
    return registry


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_llm() -> MockLLMClient:
    """Mock LLM client with a default safe response."""
    return MockLLMClient(
        default_response='{"type": "final_answer", "answer": "Code review complete. Found 2 issues."}'
    )


@pytest.fixture
def llm_with_tool_decision() -> MockLLMClient:
    """Mock LLM that decides to use tools before answering."""
    responses = iter([
        # Think 1: decide to fetch repo
        '{"type": "tool_call", "tool": "fetch_repository", "input": {"github_url": "https://github.com/test/repo"}}',
        # Reflect 1: more analysis needed
        "More analysis needed. Task not complete yet.",
        # Think 2: decide to analyze
        '{"type": "tool_call", "tool": "analyze_code_structure", "input": {"code_path": "main.py"}}',
        # Reflect 2: more analysis needed
        "Still need more information.",
        # Think 3: decide to check security
        '{"type": "tool_call", "tool": "check_security", "input": {"code_path": "main.py"}}',
        # Reflect 3: task complete
        "TASK COMPLETE. Sufficient information gathered.",
        # Final answer request
        "The code has 1 security issue and is mostly well-structured.",
    ])

    class IterMockLLM(MockLLMClient):
        async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
            self.call_count += 1
            try:
                content = next(responses)
            except StopIteration:
                content = "Final answer: Code review done."
            return LLMResponse(
                success=True,
                text=content,
            )

    return IterMockLLM()


@pytest.fixture
def llm_with_error_recovery() -> MockLLMClient:
    """Mock LLM that recovers from tool errors."""
    responses = iter([
        # Think 1: try the crash tool
        '{"type": "tool_call", "tool": "crash_tool", "input": {}}',
        # Reflect 1: tool failed, try something else
        "The crash_tool failed. Trying with fetch_repository instead.",
        # Think 2: use the working tool
        '{"type": "tool_call", "tool": "fetch_repository", "input": {"github_url": "https://github.com/test/repo"}}',
        # Reflect 2: got data
        "Sufficient. Task COMPLETE.",
        # Final answer
        "Completed with fallback.",
    ])

    class RecoveryMockLLM(MockLLMClient):
        async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
            self.call_count += 1
            try:
                content = next(responses)
            except StopIteration:
                content = "Done."
            return LLMResponse(
                success=True,
                text=content,
            )

    return RecoveryMockLLM()


@pytest.fixture
def registry_with_mock_tools() -> ToolRegistry:
    """ToolRegistry with all mock tools + the crash tool."""
    return make_registry_with_mock_tools()


@pytest.fixture
def registry_with_crash_tool() -> ToolRegistry:
    """ToolRegistry with the crash tool included."""
    registry = make_registry_with_mock_tools()
    registry.register(CrashTool())
    return registry


@pytest.fixture
def agent(mock_llm: MockLLMClient) -> CodeReviewAgent:
    """CodeReviewAgent with mock LLM and no auto-loaded tools."""
    agent = CodeReviewAgent(llm=mock_llm, auto_load_tools=False)
    registry = make_registry_with_mock_tools()
    # Replace the empty registry with our controlled one
    agent.tool_registry = registry
    agent.orchestrator.registry = registry
    agent.react_loop.registry = registry
    return agent


@pytest.fixture
def agent_with_tool_decisions(llm_with_tool_decision: MockLLMClient) -> CodeReviewAgent:
    """Agent configured with an LLM that makes multi-step tool decisions."""
    agent = CodeReviewAgent(llm=llm_with_tool_decision, auto_load_tools=False)
    registry = make_registry_with_mock_tools()
    agent.tool_registry = registry
    agent.orchestrator.registry = registry
    agent.react_loop.registry = registry
    return agent


@pytest.fixture
def agent_with_error_recovery(llm_with_error_recovery: MockLLMClient, registry_with_crash_tool: ToolRegistry) -> CodeReviewAgent:
    """Agent configured with an LLM that recovers from tool errors."""
    agent = CodeReviewAgent(llm=llm_with_error_recovery, auto_load_tools=False)
    agent.tool_registry = registry_with_crash_tool
    agent.orchestrator.registry = registry_with_crash_tool
    agent.react_loop.registry = registry_with_crash_tool
    return agent


@pytest.fixture
def test_app(agent: CodeReviewAgent) -> TestClient:
    """FastAPI TestClient with the agent dependency overridden."""
    from backend.main import app
    from backend.api.dependencies import get_agent
    from backend.database import Base, engine, init_db

    # Create fresh in-memory DB tables
    Base.metadata.drop_all(bind=engine)
    init_db()

    # Override agent dependency
    app.dependency_overrides[get_agent] = lambda: agent

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def test_db() -> Any:
    """In-memory SQLite database session for direct DB testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# =============================================================================
# CATEGORY 1: AGENT + ReACT LOOP INTEGRATION
# =============================================================================

class TestAgentReACTLoop:
    """Agent with full ReACT loop: think -> act -> observe -> reflect."""

    @pytest.mark.asyncio
    async def test_agent_initializes_with_tools(self, agent: CodeReviewAgent):
        """Agent should initialize with tools accessible via the registry."""
        assert len(agent.tool_registry) == 4
        assert agent.tool_registry.get("fetch_repository") is not None
        assert agent.tool_registry.get("analyze_code_structure") is not None

    @pytest.mark.asyncio
    async def test_agent_review_returns_loop_result(self, agent: CodeReviewAgent):
        """agent.review() should return a LoopResult."""
        result = await agent.review("Check my code for bugs")
        assert isinstance(result, LoopResult)
        assert result.final_answer is not None

    @pytest.mark.asyncio
    async def test_agent_review_success_status(self, agent: CodeReviewAgent):
        """Agent with mock LLM returning final_answer should complete with SUCCESS."""
        result = await agent.review("Find bugs in this Python code")
        assert result.status == LoopStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_agent_memory_tracks_conversation(self, agent: CodeReviewAgent):
        """Agent should add messages to memory during review."""
        session_id = "test-session"
        await agent.review("Check my code", session_id=session_id)
        history = agent.get_session_history(session_id)
        assert len(history) > 0
        # Should have at least a user message
        assert any(m["role"] == "user" for m in history)

    @pytest.mark.asyncio
    async def test_agent_state_tracks_progress(self, agent: CodeReviewAgent):
        """Agent should update state during review."""
        session_id = "state-test"
        await agent.review("Analyze main.py", session_id=session_id)
        state = agent.get_session_state(session_id)
        assert state is not None
        assert state.final_answer is not None

    @pytest.mark.asyncio
    async def test_agent_multi_step_tool_decisions(
        self, agent_with_tool_decisions: CodeReviewAgent
    ):
        """Agent should use multiple tools across iterations."""
        result = await agent_with_tool_decisions.review(
            "Review https://github.com/test/repo"
        )
        assert result.status == LoopStatus.SUCCESS
        # Should have made at least one tool call
        assert len(result.tool_calls) > 0
        # Track used tools
        tool_names = [tc["tool"] for tc in result.tool_calls]
        assert "fetch_repository" in tool_names

    @pytest.mark.asyncio
    async def test_agent_error_recovery(
        self, agent_with_error_recovery: CodeReviewAgent
    ):
        """Agent should recover from tool crashes and continue."""
        result = await agent_with_error_recovery.review("Review my repo")
        assert result.status == LoopStatus.SUCCESS
        # Should have called crash_tool but recovered
        tool_names = [tc["tool"] for tc in result.tool_calls]
        assert "crash_tool" in tool_names
        assert "fetch_repository" in tool_names

    @pytest.mark.asyncio
    async def test_agent_stats_reflects_tools(self, agent: CodeReviewAgent):
        """get_stats() should show registered tools."""
        stats = agent.get_stats()
        assert stats["tool_count"] == 4
        assert "fetch_repository" in stats["registered_tools"]

    @pytest.mark.asyncio
    async def test_chat_mode_works(self, agent: CodeReviewAgent):
        """Simple chat mode should work without ReACT loop."""
        result = await agent.chat("Hello, what can you do?")
        assert result.status == LoopStatus.SUCCESS
        assert result.final_answer is not None

    @pytest.mark.asyncio
    async def test_session_management(self, agent: CodeReviewAgent):
        """Agent should manage multiple sessions independently."""
        await agent.review("Check code A", session_id="session-a")
        await agent.review("Check code B", session_id="session-b")

        state_a = agent.get_session_state("session-a")
        state_b = agent.get_session_state("session-b")
        assert state_a is not None
        assert state_b is not None
        assert state_a.user_input != state_b.user_input

    @pytest.mark.asyncio
    async def test_clear_session_works(self, agent: CodeReviewAgent):
        """Clearing a session should remove its history and state."""
        await agent.review("Test code", session_id="clear-test")
        assert agent.get_session_state("clear-test") is not None
        agent.clear_session("clear-test")
        assert agent.get_session_state("clear-test") is None


# =============================================================================
# CATEGORY 2: TOOL ORCHESTRATION INTEGRATION
# =============================================================================

class TestToolOrchestration:
    """Tool execution patterns: single, parallel, sequential."""

    @pytest.mark.asyncio
    async def test_single_tool_execution(self, registry_with_mock_tools: ToolRegistry):
        """A single tool should execute and return ToolResult."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        result = await orchestrator.call_single(
            "fetch_repository", {"github_url": "https://github.com/test/repo"}
        )
        assert result.success is True
        assert result.data["file_count"] == 10

    @pytest.mark.asyncio
    async def test_parallel_tool_execution(self, registry_with_mock_tools: ToolRegistry):
        """Multiple tools should execute in parallel."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        calls = [
            ("fetch_repository", {"github_url": "https://github.com/test/repo"}),
            ("analyze_code_structure", {"code_path": "main.py"}),
            ("check_security", {"code_path": "main.py"}),
        ]
        result = await orchestrator.call_parallel(calls)
        assert result.all_succeeded
        assert "fetch_repository" in result.results
        assert "analyze_code_structure" in result.results
        assert "check_security" in result.results
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_sequential_tool_execution(self, registry_with_mock_tools: ToolRegistry):
        """Tools should execute sequentially in order."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        calls = [
            ("fetch_repository", {"github_url": "https://github.com/test/repo"}),
            ("analyze_code_structure", {"code_path": "main.py"}),
        ]
        result = await orchestrator.call_sequential(calls)
        assert result.all_succeeded
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_missing_tool_graceful(self, registry_with_mock_tools: ToolRegistry):
        """Calling a non-existent tool should return failure, not crash."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        result = await orchestrator.call_single("non_existent_tool", {})
        assert result.success is False
        assert "not registered" in result.error

    @pytest.mark.asyncio
    async def test_tool_crash_returns_error(self, registry_with_crash_tool: ToolRegistry):
        """A tool that raises an exception should return a graceful error."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_crash_tool)
        result = await orchestrator.call_single("crash_tool", {})
        assert result.success is False
        assert "Simulated crash" in result.error

    @pytest.mark.asyncio
    async def test_parallel_empty_calls(self, registry_with_mock_tools: ToolRegistry):
        """Parallel execution with no calls should return empty result."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        result = await orchestrator.call_parallel([])
        assert result.all_succeeded
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_execution_logging(self, registry_with_mock_tools: ToolRegistry):
        """Tool executions should be logged."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        await orchestrator.call_single("fetch_repository", {"github_url": "https://github.com/test/repo"})
        logs = orchestrator.get_recent_logs()
        assert len(logs) == 1
        assert logs[0]["tool"] == "fetch_repository"
        assert logs[0]["success"] is True

    @pytest.mark.asyncio
    async def test_tool_validate_all(self, registry_with_mock_tools: ToolRegistry):
        """validate_all() should pass for all mock tools."""
        results = registry_with_mock_tools.validate_all()
        invalid = [name for name, err in results.items() if err is not None]
        assert len(invalid) == 0, f"Invalid tools: {invalid}"


# =============================================================================
# CATEGORY 3: API ENDPOINT INTEGRATION
# =============================================================================

class TestAPIEndpointIntegration:
    """API endpoints with real agent and database."""

    def test_sync_review_with_code(self, test_app: TestClient):
        """POST /api/review with code content should return 200."""
        response = test_app.post("/api/review", json={
            "code_content": "def hello(): pass",
            "analysis_type": "full",
        })
        assert response.status_code == 200

    def test_sync_review_response_shape(self, test_app: TestClient):
        """POST /api/review response should have all required fields."""
        response = test_app.post("/api/review", json={
            "code_content": "x = 1",
        })
        data = response.json()
        assert "status" in data
        assert "review_id" in data
        assert "quality_score" in data
        assert "total_issues" in data
        assert "issues" in data
        assert "report" in data
        assert "timestamp" in data

    def test_sync_review_with_github_url(self, test_app: TestClient):
        """POST /api/review with GitHub URL should work."""
        response = test_app.post("/api/review", json={
            "github_url": "https://github.com/test/repo",
        })
        assert response.status_code == 200

    def test_sync_review_missing_input_returns_400(self, test_app: TestClient):
        """POST /api/review with no input should return 400."""
        response = test_app.post("/api/review", json={
            "analysis_type": "full",
        })
        assert response.status_code == 400
        assert "required" in response.json()["detail"]

    def test_get_review_after_creation(self, test_app: TestClient):
        """GET /api/review/{id} should return the created review."""
        create_resp = test_app.post("/api/review", json={
            "code_content": "test code",
        })
        review_id = create_resp.json()["review_id"]

        get_resp = test_app.get(f"/api/review/{review_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["review_id"] == review_id

    def test_get_nonexistent_review_returns_404(self, test_app: TestClient):
        """GET /api/review/{id} with bad ID should return 404."""
        response = test_app.get("/api/review/nonexistent-id")
        assert response.status_code == 404

    def test_review_history(self, test_app: TestClient):
        """GET /api/reviews/history should return a list."""
        # Create a review first so history is non-empty
        test_app.post("/api/review", json={"code_content": "history test"})

        response = test_app.get("/api/reviews/history")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_review_history_items_have_required_fields(self, test_app: TestClient):
        """History items should have the required fields."""
        test_app.post("/api/review", json={"code_content": "history fields test"})

        response = test_app.get("/api/reviews/history")
        item = response.json()[0]
        assert "review_id" in item
        assert "code_source" in item
        assert "quality_score" in item
        assert "total_issues" in item
        assert "timestamp" in item

    def test_async_review_returns_processing(self, test_app: TestClient):
        """POST /api/review/async should return processing status."""
        response = test_app.post("/api/review/async", json={
            "code_content": "async test",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert "review_id" in data

    def test_async_review_missing_input_returns_400(self, test_app: TestClient):
        """POST /api/review/async with no input should return 400."""
        response = test_app.post("/api/review/async", json={})
        assert response.status_code == 400

    def test_root_endpoint(self, test_app: TestClient):
        """GET / should return service info."""
        response = test_app.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Code Review Agent API"
        assert "version" in data

    def test_health_endpoint(self, test_app: TestClient):
        """GET /health should return ok."""
        response = test_app.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# =============================================================================
# CATEGORY 4: DATABASE INTEGRATION
# =============================================================================

class TestDatabaseIntegration:
    """Database persistence across the review lifecycle."""

    def test_save_review_to_db(self, test_db: Any):
        """ReviewRecord should be savable to the database."""
        from backend.database import ReviewRecord

        record = ReviewRecord(
            id=str(uuid.uuid4()),
            code_source="direct",
            quality_score=8.5,
            total_issues=3,
            critical_issues=1,
            security_issues=1,
            performance_issues=1,
            report="# Test Report",
            timestamp=datetime.now(timezone.utc),
        )
        test_db.add(record)
        test_db.commit()

        saved = test_db.query(ReviewRecord).filter(ReviewRecord.id == record.id).first()
        assert saved is not None
        assert saved.quality_score == 8.5

    def test_retrieve_review_from_db(self, test_db: Any):
        """Saved review should be retrievable by ID."""
        from backend.database import ReviewRecord

        review_id = str(uuid.uuid4())
        test_db.add(ReviewRecord(
            id=review_id,
            code_source="github",
            github_url="https://github.com/test/repo",
            quality_score=7.0,
            total_issues=2,
            critical_issues=0,
            security_issues=1,
            performance_issues=1,
            report="# Report",
            timestamp=datetime.now(timezone.utc),
        ))
        test_db.commit()

        found = test_db.query(ReviewRecord).filter(ReviewRecord.id == review_id).first()
        assert found is not None
        assert found.github_url == "https://github.com/test/repo"

    def test_review_history_ordered(self, test_db: Any):
        """Reviews should be queryable in descending timestamp order."""
        from backend.database import ReviewRecord

        for i in range(3):
            test_db.add(ReviewRecord(
                id=str(uuid.uuid4()),
                code_source="direct",
                quality_score=float(10 - i),
                total_issues=i,
                critical_issues=0,
                security_issues=0,
                performance_issues=0,
                report=f"Report {i}",
                timestamp=datetime.now(timezone.utc),
            ))
        test_db.commit()

        reviews = (
            test_db.query(ReviewRecord)
            .order_by(ReviewRecord.timestamp.desc())
            .limit(20)
            .all()
        )
        assert len(reviews) == 3
        # Most recent first
        # Newest first (i=2, score=8), oldest last (i=0, score=10)
        assert reviews[0].quality_score <= reviews[-1].quality_score

    def test_nonexistent_review_returns_none(self, test_db: Any):
        """Querying a non-existent review ID should return None."""
        from backend.database import ReviewRecord

        found = test_db.query(ReviewRecord).filter(ReviewRecord.id == "fake-id").first()
        assert found is None

    def test_multiple_reviews_can_be_saved(self, test_db: Any):
        """Multiple reviews should be independently savable."""
        from backend.database import ReviewRecord

        for i in range(5):
            test_db.add(ReviewRecord(
                id=str(uuid.uuid4()),
                code_source="direct",
                quality_score=8.0,
                total_issues=i,
                critical_issues=0,
                security_issues=0,
                performance_issues=0,
                report=f"Report {i}",
                timestamp=datetime.now(timezone.utc),
            ))
        test_db.commit()

        count = test_db.query(ReviewRecord).count()
        assert count == 5

    def test_review_record_fields(self, test_db: Any):
        """ReviewRecord should have all expected fields."""
        from backend.database import ReviewRecord

        record = ReviewRecord(
            id="field-test-id",
            code_source="github",
            github_url="https://github.com/test/repo",
            quality_score=6.5,
            total_issues=4,
            critical_issues=2,
            security_issues=1,
            performance_issues=1,
            report="Detailed report with findings",
            timestamp=datetime.now(timezone.utc),
        )
        for col in ReviewRecord.__table__.columns:
            assert hasattr(record, col.name), f"Missing field: {col.name}"


# =============================================================================
# CATEGORY 5: ERROR HANDLING
# =============================================================================

class TestErrorHandling:
    """Error handling across all layers."""

    @pytest.mark.asyncio
    async def test_missing_tool_in_loop(self, registry_with_mock_tools: ToolRegistry):
        """ReACT loop should handle missing tool names gracefully."""
        from agent.core.react_loop import ReACTLoop
        from agent.llm.client import MockLLMClient

        llm = MockLLMClient(
            default_response='{"type": "tool_call", "tool": "ghost_tool", "input": {}}'
        )
        memory = ConversationMemory()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry_with_mock_tools)

        result = await loop.run("Use the ghost tool")
        # LLM keeps requesting missing tool -> loop exhausts max_iterations
        assert result.status == LoopStatus.MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_empty_registry_does_not_crash(self):
        """Agent with empty tool registry should still work."""
        llm = MockLLMClient(default_response="Final answer: No tools available.")
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)

        result = await agent.review("Do something")
        assert result.status == LoopStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_tool_with_bad_input(self, registry_with_mock_tools: ToolRegistry):
        """Tool should handle missing required input gracefully."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        result = await orchestrator.call_single("fetch_repository", {})
        assert result.success is False
        assert "No URL" in result.error

    @pytest.mark.asyncio
    async def test_parallel_tool_failure(self, registry_with_crash_tool: ToolRegistry):
        """Parallel execution should handle individual tool failures."""
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_crash_tool)
        calls = [
            ("fetch_repository", {"github_url": "https://github.com/test/repo"}),
            ("crash_tool", {}),
        ]
        result = await orchestrator.call_parallel(calls)
        # fetch_repository should succeed
        assert "fetch_repository" in result.results
        # crash_tool should fail
        assert "crash_tool" in result.errors

    def test_api_500_handling(self, test_app: TestClient):
        """API should return 500 for unexpected errors."""
        from backend.api import routes as api_routes

        original = api_routes._execute_review

        async def broken_execute(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Unexpected system failure")

        api_routes._execute_review = broken_execute  # type: ignore[assignment]
        try:
            response = test_app.post("/api/review", json={
                "code_content": "will break",
            })
            assert response.status_code == 500
        finally:
            api_routes._execute_review = original

    def test_api_invalid_json_returns_422(self, test_app: TestClient):
        """API should return 422 for malformed JSON."""
        response = test_app.post(
            "/api/review",
            data="not json at all",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self):
        """Agent should stop after max iterations and return best effort."""
        # LLM that never says "done" so loop hits max iterations
        never_done_llm = MockLLMClient(
            default_response='{"type": "tool_call", "tool": "", "input": {}}'
        )
        config = ReACTConfig(max_iterations=2, reflection_enabled=False)
        agent = CodeReviewAgent(llm=never_done_llm, config=config, auto_load_tools=False)
        registry = make_registry_with_mock_tools()
        agent.tool_registry = registry
        agent.orchestrator.registry = registry
        agent.react_loop.registry = registry

        result = await agent.review("Test max iterations")
        assert result.status in (LoopStatus.MAX_ITERATIONS, LoopStatus.SUCCESS)
        assert result.iterations_used <= 2


# =============================================================================
# CATEGORY 6: PERFORMANCE & COMPATIBILITY
# =============================================================================

class TestPerformanceConstraints:
    """Performance sanity checks."""

    @pytest.mark.asyncio
    async def test_agent_completes_within_reasonable_time(self, agent: CodeReviewAgent):
        """Agent should complete a simple review quickly (under 5s)."""
        import time

        start = time.time()
        await agent.review("Quick check")
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Agent took {elapsed:.2f}s (expected < 5s)"

    @pytest.mark.asyncio
    async def test_tool_execution_fast(self, registry_with_mock_tools: ToolRegistry):
        """Mock tool execution should be near-instant."""
        import time
        from agent.core.orchestrator import ToolOrchestrator

        orchestrator = ToolOrchestrator(registry_with_mock_tools)
        start = time.time()
        await orchestrator.call_single("fetch_repository", {"github_url": "https://github.com/test/repo"})
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Tool took {elapsed:.2f}s (expected < 1s)"

    def test_api_response_fast(self, test_app: TestClient):
        """API sync review should respond quickly."""
        import time

        start = time.time()
        response = test_app.post("/api/review", json={
            "code_content": "performance test",
        })
        elapsed = time.time() - start
        assert elapsed < 5.0, f"API took {elapsed:.2f}s (expected < 5s)"
        assert response.status_code == 200

    def test_database_query_fast(self, test_db: Any):
        """Database queries should be fast."""
        import time
        from backend.database import ReviewRecord

        # Insert a test record
        test_db.add(ReviewRecord(
            id="perf-test",
            code_source="direct",
            quality_score=9.0,
            total_issues=1,
            critical_issues=0,
            security_issues=0,
            performance_issues=0,
            report="Perf test",
            timestamp=datetime.now(timezone.utc),
        ))
        test_db.commit()

        start = time.time()
        for _ in range(100):
            test_db.query(ReviewRecord).filter(ReviewRecord.id == "perf-test").first()
        elapsed = time.time() - start
        assert elapsed < 2.0, f"100 queries took {elapsed:.2f}s (expected < 2s)"


class TestCompatibility:
    """Python version and async compatibility."""

    def test_python_version(self):
        """Code should run on Python 3.10+."""
        import sys
        assert sys.version_info >= (3, 10), f"Python {sys.version} is too old"

    def test_type_hints_available(self):
        """Modern type hints (| syntax) should be available."""
        # Python 3.10+ supports X | Y syntax for unions
        x: int | None = None
        assert x is None

    @pytest.mark.asyncio
    async def test_async_operations_correct(self):
        """Basic async operations should work correctly."""
        async def sample():
            return 42

        result = await sample()
        assert result == 42

    @pytest.mark.asyncio
    async def test_agent_is_async(self):
        """Agent should be fully async."""
        from inspect import iscoroutinefunction
        agent = CodeReviewAgent(llm=MockLLMClient(), auto_load_tools=False)
        assert iscoroutinefunction(agent.review)
        assert iscoroutinefunction(agent.chat)


# =============================================================================
# CATEGORY 7: END-TO-END FULL FLOW
# =============================================================================

class TestEndToEnd:
    """Complete end-to-end flow: API -> Agent -> Tools -> DB -> Response."""

    def test_api_to_db_to_response(self, test_app: TestClient, test_db: Any):
        """Full round-trip: POST review, GET review, verify DB has it."""
        from backend.database import ReviewRecord

        # Step 1: Submit a review via API
        post_resp = test_app.post("/api/review", json={
            "code_content": "def add(a, b): return a + b",
        })
        assert post_resp.status_code == 200
        review_id = post_resp.json()["review_id"]

        # Step 2: Retrieve by ID from API
        get_resp = test_app.get(f"/api/review/{review_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["review_id"] == review_id

        # Step 3: Verify DB has the record (using the test_db fixture
        # which is a separate in-memory DB; the API uses the real DB.
        # We verify through the API instead.)

    def test_multiple_reviews_round_trip(self, test_app: TestClient):
        """Multiple reviews should be independently accessible."""
        ids = []
        for i in range(3):
            resp = test_app.post("/api/review", json={
                "code_content": f"code block {i}",
            })
            assert resp.status_code == 200
            ids.append(resp.json()["review_id"])

        # Each review should be independently retrievable
        for rid in ids:
            resp = test_app.get(f"/api/review/{rid}")
            assert resp.status_code == 200
            assert resp.json()["review_id"] == rid

    def test_history_includes_created_reviews(self, test_app: TestClient):
        """Review history should reflect created reviews."""
        # Create 3 reviews
        for i in range(3):
            test_app.post("/api/review", json={
                "code_content": f"history item {i}",
            })

        history_resp = test_app.get("/api/reviews/history")
        assert history_resp.status_code == 200
        items = history_resp.json()
        assert len(items) >= 3

    def test_sync_then_async_workflow(self, test_app: TestClient):
        """Sync and async endpoints should both work."""
        # Sync review
        sync_resp = test_app.post("/api/review", json={
            "code_content": "sync test",
        })
        assert sync_resp.status_code == 200

        # Async review
        async_resp = test_app.post("/api/review/async", json={
            "code_content": "async test",
        })
        assert async_resp.status_code == 200
        assert async_resp.json()["status"] == "processing"

    @pytest.mark.asyncio
    async def test_agent_tools_db_integration(self, agent: CodeReviewAgent, test_db: Any):
        """Agent executes tools, results can be stored and retrieved."""
        from backend.database import ReviewRecord
        from backend.models import ReviewRequest as ReviewRequestModel

        # Run agent
        result = await agent.review("Analyze my Python code")
        assert result.final_answer is not None

        # Store in DB directly
        record = ReviewRecord(
            id=str(uuid.uuid4()),
            code_source="direct",
            quality_score=8.0,
            total_issues=2,
            critical_issues=0,
            security_issues=0,
            performance_issues=0,
            report=result.final_answer,
            timestamp=datetime.now(timezone.utc),
        )
        test_db.add(record)
        test_db.commit()

        # Retrieve and verify
        saved = test_db.query(ReviewRecord).filter(ReviewRecord.id == record.id).first()
        assert saved is not None
        assert saved.report == result.final_answer

    def test_frontend_api_compatibility(self, test_app: TestClient):
        """Frontend API client should be compatible with the backend."""
        # Frontend sends: {"github_url": "...", "code_content": "...", "model": "...", "depth": "..."}
        response = test_app.post("/api/review", json={
            "code_content": "x = 1",
            "analysis_type": "full",
        })
        assert response.status_code == 200
        data = response.json()

        # Frontend expects these fields
        frontend_expected = [
            "status", "review_id", "quality_score", "total_issues",
            "critical_issues", "issues", "report", "timestamp",
        ]
        for field in frontend_expected:
            assert field in data, f"Frontend needs field: {field}"

        # Frontend also expects fields via the mock result format
        # Check that quality_score is a number
        assert isinstance(data["quality_score"], (int, float))
        assert isinstance(data["issues"], list)
