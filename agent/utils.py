"""
utils.py - Agent module ke liye pure helper functions.
Yeh functions stateless hain - input lete hain, output dete hain, koi side effects nahi.
agent_core.py aur doosre modules inhe extensively use karte hain.

Design principles:
- Pure functions (no class state, no I/O)
- Robust error handling (bad input pe crash nahi karte)
- Clear naming (har function ka kaam obvious)
- Comprehensive docstrings with examples
"""

# =============================================================================
# IMPORTS
# =============================================================================
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Note: AgentMemory agent_types mein nahi, agent_memory module mein hai.
# Spec ke mutabiq code chahiye tha, actual location use kar rahe hain.
from agent.agent_memory import AgentMemory
from agent.agent_types import AgentStep, ReviewRequest, StepType, ToolCall, ToolResult
from agent.constants import DEFAULT_ANALYSIS_TYPE, TOOLS

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS USED IN UTILS
# =============================================================================
# Valid analysis types for ReviewRequest - validation ke liye
VALID_ANALYSIS_TYPES: frozenset[str] = frozenset({"full", "security", "performance", "style"})

# Max backoff delay cap (seconds) - retry storms se bachne ke liye
MAX_BACKOFF_SECONDS: int = 30

# GitHub URL pattern - username/repo format
GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$"
)

# Available tool names list (derived from constants.TOOLS)
AVAILABLE_TOOL_NAMES: List[str] = list(TOOLS.values())


# =============================================================================
# MEMORY AND STEP FORMATTING
# =============================================================================
def format_memory_for_llm(memory: AgentMemory) -> str:
    """
    AgentMemory ko readable text format mein convert karo for LLM consumption.
    Last 7 steps include karta hai with type, thought, action, aur result.

    Yeh function LLM ko "ab tak kya hua" summarize karke dikhata hai.
    Agent_core ReACT loop mein isse use karta hai.

    Args:
        memory: AgentMemory instance jisko format karna hai.

    Returns:
        Formatted string with recent steps. Empty memory pe "No activity yet."

    Example:
        >>> memory = AgentMemory()
        >>> context = format_memory_for_llm(memory)
        >>> print(context)
        === Recent Agent Activity ===

        No activity yet.
    """
    try:
        # Last 7 steps le lo (memory helper method use karke)
        recent_steps = memory.get_recent_steps(7)

        if not recent_steps:
            return "=== Recent Agent Activity ===\n\nNo activity yet."

        lines: List[str] = ["=== Recent Agent Activity ===", ""]

        for step in recent_steps:
            # Step number aur type header
            lines.append(f"Step {step.step_number} [{step.step_type.value.upper()}]:")

            # Thought - LLM ka reasoning
            if step.thought:
                lines.append(f"  Thought: {step.thought}")

            # Action - tool call details
            if step.action:
                lines.append(f"  Action: {step.action.tool_name}")
                if step.action.params:
                    params_str = ", ".join(f"{k}={v}" for k, v in step.action.params.items())
                    lines.append(f"  Params: {params_str}")

            # Observation - tool ka result
            if step.observation:
                if step.observation.success:
                    data_preview = str(step.observation.data)[:100]
                    lines.append(f"  Result: SUCCESS ({data_preview})")
                else:
                    err = step.observation.error or "Unknown error"
                    lines.append(f"  Result: FAILED ({err})")

            # Reflection - LLM ka self-evaluation
            if step.reflection:
                lines.append(f"  Reflection: {step.reflection}")

            lines.append("")  # Blank line between steps

        return "\n".join(lines).rstrip()
    except Exception as exc:
        logger.exception("Failed to format memory: %s", exc)
        return f"=== Recent Agent Activity ===\n\nError formatting: {exc}"


def format_step_summary(step: AgentStep) -> str:
    """
    AgentStep ka one-line summary banao.
    Format: "Step 3: THINK → fetch_repository (Success in 2.1s)"

    Logs aur quick UI display ke liye useful.

    Args:
        step: AgentStep instance to summarize.

    Returns:
        One-line string summary.

    Example:
        >>> step = AgentStep(step_number=5, step_type=StepType.ACT, action=call)
        >>> print(format_step_summary(step))
        Step 5: ACT → fetch_repository
    """
    try:
        parts: List[str] = [f"Step {step.step_number}: {step.step_type.value.upper()}"]

        # Tool name show karo agar action hai
        if step.action:
            parts.append(f"→ {step.action.tool_name}")

        # Result status with timing
        if step.observation:
            if step.observation.success:
                parts.append(f"(Success in {step.observation.execution_time:.1f}s)")
            else:
                err = step.observation.error or "Unknown"
                # Long error truncate karo
                if len(err) > 40:
                    err = err[:37] + "..."
                parts.append(f"(Failed: {err})")

        return " ".join(parts)
    except Exception as exc:
        logger.exception("Failed to format step summary: %s", exc)
        return f"Step {step.step_number}: <format error: {exc}>"


# =============================================================================
# TOOL NAME AND PARAMETER EXTRACTION
# =============================================================================
def extract_tool_name_from_thought(
    thought: str, available_tools: List[str]
) -> Optional[str]:
    """
    LLM ke thought text se tool name extract karo.
    Case-insensitive matching use karta hai aur pehle match return karta hai.

    Args:
        thought: LLM ka reasoning text jismein tool mention hai.
        available_tools: List of valid tool names to match against.

    Returns:
        Matched tool name (original case mein), ya None agar koi match nahi mila.

    Example:
        >>> thought = "I should use fetch_repository to download code"
        >>> tool = extract_tool_name_from_thought(thought, ["fetch_repository", "analyze_code"])
        >>> print(tool)
        fetch_repository
    """
    if not thought or not available_tools:
        return None

    try:
        # Case-insensitive matching ke liye lowercase compare
        thought_lower = thought.lower()

        # Pehle exact match dhundho (word boundaries ke saath)
        for tool in available_tools:
            # Pattern: tool name as whole word, case-insensitive
            pattern = r"\b" + re.escape(tool.lower()) + r"\b"
            if re.search(pattern, thought_lower):
                return tool  # Original case wapas karo

        # Fallback: simple substring match (less strict)
        for tool in available_tools:
            if tool.lower() in thought_lower:
                return tool

        return None
    except Exception as exc:
        logger.exception("Failed to extract tool name: %s", exc)
        return None


def extract_tool_params_from_response(
    response_text: str, tool_name: str
) -> Dict[str, Any]:
    """
    LLM ke response text se tool parameters extract karo.
    Pehle JSON block try karta hai, phir key=value pairs.

    Args:
        response_text: LLM ka response text.
        tool_name: Tool jiske params extract karne hain (logging ke liye).

    Returns:
        Dict of extracted parameters. Empty dict agar kuch nahi mila.

    Example:
        >>> response = 'fetch_repository with github_url="https://github.com/x/y"'
        >>> params = extract_tool_params_from_response(response, "fetch_repository")
        >>> print(params)
        {'github_url': 'https://github.com/x/y'}
    """
    if not response_text:
        return {}

    try:
        # Strategy 1: JSON block extract karo
        json_match = re.search(r"\{[\s\S]*?\}", response_text)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass  # JSON nahi mila, next strategy try karo

        # Strategy 2: key=value pairs (handle both quoted and unquoted values)
        params: Dict[str, Any] = {}
        # Pattern: key="value" ya key='value' ya key=value
        kv_pattern = re.compile(
            r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))'
        )
        for match in kv_pattern.finditer(response_text):
            key = match.group(1)
            # First non-None group is the value
            value = match.group(2) or match.group(3) or match.group(4)
            if value is not None:
                params[key] = value

        if params:
            logger.debug("Extracted %d params for %s", len(params), tool_name)
        return params
    except Exception as exc:
        logger.exception("Failed to extract params for %s: %s", tool_name, exc)
        return {}


def create_tool_call_from_response(
    llm_response: str, tool_name: str, tools_available: List[str]
) -> Optional[ToolCall]:
    """
    LLM response se ToolCall object banao.
    Tool name validate karta hai aur parameters extract karta hai.

    Args:
        llm_response: LLM ka raw response text.
        tool_name: Tool ka naam jisko call karna hai.
        tools_available: List of valid tool names for validation.

    Returns:
        ToolCall instance agar valid hai, None agar tool name invalid hai.

    Example:
        >>> response = 'analyze_code with language="python"'
        >>> call = create_tool_call_from_response(response, "analyze_code", ["analyze_code"])
        >>> if call:
        ...     print(call.params)
        {'language': 'python'}
    """
    try:
        # Validate tool exists in available list
        if tool_name not in tools_available:
            logger.warning("Tool '%s' not in available tools: %s", tool_name, tools_available)
            return None

        # Extract parameters from response
        params = extract_tool_params_from_response(llm_response, tool_name)

        return ToolCall(tool_name=tool_name, params=params)
    except Exception as exc:
        logger.exception("Failed to create tool call: %s", exc)
        return None


# =============================================================================
# TOOL RESULT FORMATTING
# =============================================================================
def format_tool_result_for_llm(result: ToolResult) -> str:
    """
    ToolResult ko LLM-friendly text mein format karo.
    Success/failure status, timing, aur key data points include karta hai.

    Args:
        result: ToolResult instance to format.

    Returns:
        Human-readable formatted string with emoji indicators.

    Example:
        >>> result = ToolResult(tool_name="pylint", success=True,
        ...                     data={"files": 150}, execution_time=2.5)
        >>> print(format_tool_result_for_llm(result))
        OK Tool 'pylint' succeeded in 2.5s. Data: {'files': 150}
    """
    try:
        tool_name = result.tool_name
        exec_time = result.execution_time

        if result.success:
            # Success path - green check + summary
            data_str = str(result.data) if result.data else "no data"
            # Data preview truncate for long results
            if len(data_str) > 200:
                data_str = data_str[:197] + "..."
            return f"OK Tool '{tool_name}' succeeded in {exec_time:.1f}s. Data: {data_str}"
        else:
            # Failure path - red X + error details
            error_msg = result.error or "Unknown error"
            return f"FAIL Tool '{tool_name}' failed in {exec_time:.1f}s. Error: {error_msg}"
    except Exception as exc:
        logger.exception("Failed to format tool result: %s", exc)
        return f"ERROR formatting result: {exc}"


# =============================================================================
# REACT LOOP CONTROL
# =============================================================================
def should_continue_loop(
    current_step: int, max_steps: int, last_reflection: str
) -> bool:
    """
    Decide karo ke ReACT loop continue karna chahiye ya stop.
    Multiple conditions check karta hai:
    - Max steps reached
    - Reflection indicates completion

    Args:
        current_step: Current iteration number (0-indexed or 1-indexed).
        max_steps: Maximum allowed iterations.
        last_reflection: Latest reflection text from LLM (can be empty).

    Returns:
        True if loop should continue, False if should stop.

    Example:
        >>> if should_continue_loop(step=5, max_steps=10, last_reflection="TASK COMPLETE"):
        ...     print("Continue")
        ... else:
        ...     print("Stop")
        Stop
    """
    try:
        # Max steps reached - must stop
        if current_step >= max_steps:
            logger.info("Loop stopping: reached max_steps=%d (current=%d)", max_steps, current_step)
            return False

        # Check reflection for completion signals
        if last_reflection:
            reflection_lower = last_reflection.lower()
            # "DONE" ya "COMPLETE" keywords - multiple variants support
            completion_signals = [
                "task complete", "task completed", "tack complete",
                "done", "finished", "no more steps",
                "sufficient information", "ready to answer",
            ]
            for signal in completion_signals:
                if signal in reflection_lower:
                    logger.info("Loop stopping: reflection signals completion ('%s')", signal)
                    return False

        return True
    except Exception as exc:
        logger.exception("Error in should_continue_loop: %s", exc)
        # On error, default to continuing (safe side)
        return True


# =============================================================================
# RETRY LOGIC
# =============================================================================
def retry_with_backoff(attempt: int, base_delay: int = 1) -> float:
    """
    Exponential backoff delay calculate karo for retry attempts.
    delay = base_delay * (2 ** attempt), capped at 30 seconds.

    Args:
        attempt: Current attempt number (0 = first retry, 1 = second, ...).
        base_delay: Base delay in seconds (default 1).

    Returns:
        Delay in seconds (float). Always between base_delay and MAX_BACKOFF_SECONDS.

    Example:
        >>> retry_with_backoff(0)  # 1 * 1 = 1.0
        1.0
        >>> retry_with_backoff(1)  # 1 * 2 = 2.0
        2.0
        >>> retry_with_backoff(2)  # 1 * 4 = 4.0
        4.0
        >>> retry_with_backoff(10) # capped at 30
        30
    """
    try:
        # Negative attempt ko 0 treat karo (safety)
        if attempt < 0:
            attempt = 0

        # Exponential: base * 2^attempt
        delay = base_delay * (2 ** attempt)

        # Cap at MAX_BACKOFF_SECONDS
        delay = min(float(delay), float(MAX_BACKOFF_SECONDS))

        return delay
    except Exception as exc:
        logger.exception("Failed to calculate backoff: %s", exc)
        return float(base_delay)  # Safe fallback


# =============================================================================
# VALIDATION HELPERS
# =============================================================================
def validate_github_url(url: str) -> bool:
    """
    Check karo ke URL valid GitHub repository URL hai ya nahi.
    Must match: https://github.com/username/repo pattern.

    Args:
        url: URL string to validate.

    Returns:
        True if valid GitHub repo URL, False otherwise.

    Example:
        >>> validate_github_url("https://github.com/user/repo")
        True
        >>> validate_github_url("https://gitlab.com/user/repo")
        False
        >>> validate_github_url("not-a-url")
        False
    """
    if not url or not isinstance(url, str):
        return False

    try:
        return bool(GITHUB_URL_PATTERN.match(url))
    except Exception as exc:
        logger.exception("Failed to validate GitHub URL: %s", exc)
        return False


def validate_review_request(
    request: ReviewRequest,
) -> Tuple[bool, Optional[str]]:
    """
    ReviewRequest object validate karo.
    Checks: source provided, valid analysis type, valid GitHub URL.

    Args:
        request: ReviewRequest instance to validate.

    Returns:
        Tuple of (is_valid, error_message).
        - is_valid: True agar sab checks pass
        - error_message: None if valid, string describing issue if invalid

    Example:
        >>> req = ReviewRequest(github_url="https://github.com/x/y")
        >>> is_valid, err = validate_review_request(req)
        >>> print(is_valid, err)
        True None

        >>> bad_req = ReviewRequest()  # no source
        >>> is_valid, err = validate_review_request(bad_req)
        >>> print(is_valid, err)
        False Both github_url and code_content are empty
    """
    try:
        # Check 1: Kam az kam ek source hona chahiye
        if not request.github_url and not request.code_content:
            return False, "Both github_url and code_content are empty"

        # Check 2: Valid analysis type
        if request.analysis_type not in VALID_ANALYSIS_TYPES:
            valid_str = ", ".join(sorted(VALID_ANALYSIS_TYPES))
            return False, (
                f"Invalid analysis_type: '{request.analysis_type}'. "
                f"Valid options: {valid_str}"
            )

        # Check 3: Agar GitHub URL diya hai to valid hona chahiye
        if request.github_url and not validate_github_url(request.github_url):
            return False, f"Invalid GitHub URL: '{request.github_url}'"

        # All checks passed
        return True, None
    except Exception as exc:
        logger.exception("Review request validation failed: %s", exc)
        return False, f"Validation error: {exc}"


# =============================================================================
# TIMESTAMP AND ERROR HELPERS
# =============================================================================
def get_current_timestamp() -> datetime:
    """
    Current UTC timestamp return karo with timezone awareness.
    Wrapper around datetime.now(timezone.utc) for consistent behavior.

    Returns:
        Timezone-aware datetime in UTC.

    Example:
        >>> ts = get_current_timestamp()
        >>> ts.tzinfo is not None
        True
        >>> ts.year >= 2024
        True
    """
    return datetime.now(timezone.utc)


def parse_tool_error_message(error: str) -> Tuple[str, str]:
    """
    Error message ko (error_type, error_detail) mein parse karo.
    Format expected: "TypeName: detail message"

    Args:
        error: Raw error string.

    Returns:
        Tuple of (error_type, error_detail).
        Agar colon nahi mila to (full_error, "") return.

    Example:
        >>> parse_tool_error_message("TimeoutError: Tool exceeded 120s")
        ('TimeoutError', 'Tool exceeded 120s')
        >>> parse_tool_error_message("Some error without colon")
        ('Some error without colon', '')
    """
    if not error:
        return "", ""

    try:
        # First colon pe split karo (baaki sab detail)
        if ":" in error:
            parts = error.split(":", 1)
            error_type = parts[0].strip()
            error_detail = parts[1].strip() if len(parts) > 1 else ""
            return error_type, error_detail

        # No colon - return whole as type, empty detail
        return error.strip(), ""
    except Exception as exc:
        logger.exception("Failed to parse error message: %s", exc)
        return error, ""
