"""Demo outputs of utils functions."""
from agent import utils
from agent.agent_types import ToolResult, AgentStep, StepType, ToolCall

print("--- format_step_summary ---")
print(utils.format_step_summary(AgentStep(
    step_number=3, step_type=StepType.ACT,
    action=ToolCall(tool_name="fetch_repository", params={}),
    observation=ToolResult(
        tool_name="fetch_repository", success=True,
        data={}, execution_time=2.1
    )
)))
print(utils.format_step_summary(AgentStep(
    step_number=5, step_type=StepType.ACT,
    action=ToolCall(tool_name="analyze_code", params={}),
    observation=ToolResult(
        tool_name="analyze_code", success=False,
        error="Timeout after 120s", execution_time=120.0
    )
)))

print()
print("--- format_tool_result_for_llm ---")
print(utils.format_tool_result_for_llm(ToolResult(
    tool_name="pylint", success=True,
    data={"issues": 5, "score": 8.5}, execution_time=2.5
)))
print(utils.format_tool_result_for_llm(ToolResult(
    tool_name="bandit", success=False,
    error="Tool not found", execution_time=0.1
)))

print()
print("--- retry_with_backoff ---")
for i in range(7):
    print(f"  attempt {i}: {utils.retry_with_backoff(i)}s")

print()
print("--- extract_tool_params (JSON) ---")
print(utils.extract_tool_params_from_response(
    '{"github_url": "https://github.com/x/y", "branch": "main"}',
    "fetch_repository"
))

print("--- extract_tool_params (key=value) ---")
print(utils.extract_tool_params_from_response(
    'fetch_repository with github_url="https://github.com/x/y" branch=main',
    "fetch_repository"
))

print()
print("--- should_continue_loop ---")
for case in [
    (3, 10, "Need more analysis"),
    (10, 10, "thinking"),
    (3, 10, "TASK COMPLETE"),
    (3, 10, "I think we're DONE here"),
]:
    print(f"  step={case[0]}, max={case[1]}, reflection='{case[2]}' -> {utils.should_continue_loop(*case)}")

print()
print("--- parse_tool_error_message ---")
for err in [
    "TimeoutError: Tool exceeded 120s",
    "ValueError: bad: input: here",
    "No colon here",
    "",
]:
    t, d = utils.parse_tool_error_message(err)
    print(f"  {err!r:50} -> ({t!r}, {d!r})")
