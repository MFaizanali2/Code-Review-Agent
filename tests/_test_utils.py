"""Verification test for utils.py - all 12 functions."""
from datetime import datetime, timezone
from agent.agent_types import (
    AgentStep, ReviewRequest, StepType, ToolCall, ToolResult
)
from agent.agent_memory import AgentMemory
from agent import utils


def test_format_memory_for_llm():
    print("=== T1: format_memory_for_llm ===")
    mem = AgentMemory()
    print(utils.format_memory_for_llm(mem)[:50])

    # Add some steps
    mem.add_step(AgentStep(
        step_number=1, step_type=StepType.THINK,
        thought="Need to analyze this Python code"
    ))
    mem.add_step(AgentStep(
        step_number=2, step_type=StepType.ACT,
        action=ToolCall(tool_name="analyze_code", params={"lang": "python"}),
        thought="Calling analyze_code"
    ))
    mem.add_step(AgentStep(
        step_number=3, step_type=StepType.OBSERVE,
        observation=ToolResult(
            tool_name="analyze_code", success=True,
            data={"issues": 5}, execution_time=1.2
        )
    ))
    print(utils.format_memory_for_llm(mem))


def test_format_step_summary():
    print("\n=== T2: format_step_summary ===")
    step_ok = AgentStep(
        step_number=3, step_type=StepType.ACT,
        action=ToolCall(tool_name="fetch_repository", params={}),
        observation=ToolResult(
            tool_name="fetch_repository", success=True,
            data={}, execution_time=2.1
        )
    )
    print(utils.format_step_summary(step_ok))

    step_fail = AgentStep(
        step_number=5, step_type=StepType.ACT,
        action=ToolCall(tool_name="analyze_code", params={}),
        observation=ToolResult(
            tool_name="analyze_code", success=False,
            error="Timeout after 120s", execution_time=120.0
        )
    )
    print(utils.format_step_summary(step_fail))


def test_extract_tool_name():
    print("\n=== T3: extract_tool_name_from_thought ===")
    tools = ["fetch_repository", "analyze_code", "security_audit"]

    # Exact match
    r1 = utils.extract_tool_name_from_thought("I should use fetch_repository", tools)
    print(f"1. {r1!r}")
    assert r1 == "fetch_repository"

    # Case-insensitive
    r2 = utils.extract_tool_name_from_thought("Use ANALYZE_CODE tool", tools)
    print(f"2. {r2!r}")
    assert r2 == "analyze_code"

    # No match
    r3 = utils.extract_tool_name_from_thought("Just thinking", tools)
    print(f"3. {r3!r}")
    assert r3 is None

    # Empty
    r4 = utils.extract_tool_name_from_thought("", tools)
    print(f"4. {r4!r}")
    assert r4 is None


def test_extract_tool_params():
    print("\n=== T4: extract_tool_params_from_response ===")
    # JSON
    r1 = utils.extract_tool_params_from_response(
        '{"github_url": "https://github.com/x/y"}', "fetch_repository"
    )
    print(f"1. JSON: {r1}")
    assert r1["github_url"] == "https://github.com/x/y"

    # key=value pairs
    r2 = utils.extract_tool_params_from_response(
        'fetch_repository with github_url="https://github.com/x/y" language="python"',
        "fetch_repository"
    )
    print(f"2. kv: {r2}")
    assert r2["github_url"] == "https://github.com/x/y"

    # Empty
    r3 = utils.extract_tool_params_from_response("", "x")
    print(f"3. empty: {r3}")
    assert r3 == {}


def test_create_tool_call():
    print("\n=== T5: create_tool_call_from_response ===")
    response = 'analyze_code with language="python"'
    call = utils.create_tool_call_from_response(response, "analyze_code", ["analyze_code", "fetch_repository"])
    print(f"1. {call}")
    assert call is not None
    assert call.tool_name == "analyze_code"
    assert call.params["language"] == "python"

    # Invalid tool
    call2 = utils.create_tool_call_from_response(response, "invalid_tool", ["analyze_code"])
    print(f"2. invalid: {call2}")
    assert call2 is None


def test_format_tool_result():
    print("\n=== T6: format_tool_result_for_llm ===")
    ok = ToolResult(tool_name="pylint", success=True, data={"issues": 5}, execution_time=2.5)
    print(utils.format_tool_result_for_llm(ok))

    fail = ToolResult(tool_name="bandit", success=False, error="Tool not found", execution_time=0.1)
    print(utils.format_tool_result_for_llm(fail))


def test_should_continue_loop():
    print("\n=== T7: should_continue_loop ===")
    # Max steps reached
    r1 = utils.should_continue_loop(10, 10, "thinking...")
    print(f"1. max reached: {r1}")
    assert r1 is False

    # Task complete
    r2 = utils.should_continue_loop(3, 10, "TASK COMPLETE - all done")
    print(f"2. complete: {r2}")
    assert r2 is False

    # "DONE" keyword
    r3 = utils.should_continue_loop(3, 10, "I think we're DONE here")
    print(f"3. done: {r3}")
    assert r3 is False

    # Should continue
    r4 = utils.should_continue_loop(3, 10, "Need more analysis")
    print(f"4. continue: {r4}")
    assert r4 is True

    # Empty reflection
    r5 = utils.should_continue_loop(3, 10, "")
    print(f"5. empty: {r5}")
    assert r5 is True


def test_retry_with_backoff():
    print("\n=== T8: retry_with_backoff ===")
    assert utils.retry_with_backoff(0) == 1.0
    assert utils.retry_with_backoff(1) == 2.0
    assert utils.retry_with_backoff(2) == 4.0
    assert utils.retry_with_backoff(3) == 8.0
    # Cap test
    assert utils.retry_with_backoff(10) == 30.0
    assert utils.retry_with_backoff(100) == 30.0
    # Custom base
    assert utils.retry_with_backoff(2, base_delay=2) == 8.0
    # Negative attempt
    assert utils.retry_with_backoff(-1) == 1.0
    print("All backoff values correct")


def test_validate_github_url():
    print("\n=== T9: validate_github_url ===")
    valid = [
        "https://github.com/user/repo",
        "https://github.com/user-name/repo-name",
        "https://github.com/user/repo/",
        "https://github.com/user_name/repo.js",
    ]
    invalid = [
        "",
        "not-a-url",
        "https://gitlab.com/user/repo",
        "github.com/user/repo",  # no https
        "https://github.com/user",  # no repo
        None,
    ]
    for url in valid:
        r = utils.validate_github_url(url)
        print(f"  {url!r}: {r}")
        assert r is True, f"Should be valid: {url}"
    for url in invalid:
        r = utils.validate_github_url(url)
        print(f"  {url!r}: {r}")
        assert r is False, f"Should be invalid: {url}"


def test_validate_review_request():
    print("\n=== T10: validate_review_request ===")
    # Valid: GitHub URL
    r1 = ReviewRequest(github_url="https://github.com/user/repo", analysis_type="full")
    v, e = utils.validate_review_request(r1)
    print(f"1. valid URL: {v}, {e}")
    assert v is True

    # Valid: code content
    r2 = ReviewRequest(code_content="def foo(): pass", analysis_type="security")
    v, e = utils.validate_review_request(r2)
    print(f"2. valid code: {v}, {e}")
    assert v is True

    # Invalid: no source
    r3 = ReviewRequest(analysis_type="full")
    v, e = utils.validate_review_request(r3)
    print(f"3. no source: {v}, {e}")
    assert v is False
    assert "empty" in e.lower()

    # Invalid: bad analysis type
    r4 = ReviewRequest(code_content="x", analysis_type="invalid_type")
    v, e = utils.validate_review_request(r4)
    print(f"4. bad type: {v}, {e}")
    assert v is False
    assert "analysis_type" in e.lower()

    # Invalid: bad URL
    r5 = ReviewRequest(github_url="https://gitlab.com/x/y", analysis_type="full")
    v, e = utils.validate_review_request(r5)
    print(f"5. bad url: {v}, {e}")
    assert v is False
    assert "github" in e.lower()


def test_get_current_timestamp():
    print("\n=== T11: get_current_timestamp ===")
    ts = utils.get_current_timestamp()
    print(f"  {ts}")
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None  # timezone-aware
    assert ts.tzinfo == timezone.utc


def test_parse_tool_error_message():
    print("\n=== T12: parse_tool_error_message ===")
    # Standard format
    t, d = utils.parse_tool_error_message("TimeoutError: Tool exceeded 120s")
    print(f"1. {t!r}, {d!r}")
    assert t == "TimeoutError"
    assert d == "Tool exceeded 120s"

    # No colon
    t, d = utils.parse_tool_error_message("Some error without colon")
    print(f"2. {t!r}, {d!r}")
    assert t == "Some error without colon"
    assert d == ""

    # Empty
    t, d = utils.parse_tool_error_message("")
    print(f"3. {t!r}, {d!r}")
    assert t == "" and d == ""

    # Multiple colons
    t, d = utils.parse_tool_error_message("ValueError: bad: input: here")
    print(f"4. {t!r}, {d!r}")
    assert t == "ValueError"
    assert d == "bad: input: here"  # only first split


if __name__ == "__main__":
    test_format_memory_for_llm()
    test_format_step_summary()
    test_extract_tool_name()
    test_extract_tool_params()
    test_create_tool_call()
    test_format_tool_result()
    test_should_continue_loop()
    test_retry_with_backoff()
    test_validate_github_url()
    test_validate_review_request()
    test_get_current_timestamp()
    test_parse_tool_error_message()
    print("\n" + "=" * 50)
    print("All 12 utils functions verified!")
    print("=" * 50)
