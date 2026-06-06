"""
Agent Module - Code Review Agent Implementation
=================================================

Yeh module Code Review Agent ka core implementation contain karta hai.
ReACT loop (Think -> Act -> Observe -> Reflect) ke through code review
tasks automate karta hai using LLMs aur custom tools.

Main Components:
    - CodeReviewAgent: Main ReACT loop orchestrator
    - AgentMemory: Conversation history aur tool result storage
    - ToolOrchestrator: Tool execution with retry/timeout/stats
    - ReviewRequest/ReviewResult: API contract types
    - ToolCall/ToolResult/AgentStep: Internal data types
    - StepType/AgentStatus: State enums

USAGE EXAMPLES:

    Example 1: Import main agent
    ```python
    from agent import CodeReviewAgent, ReviewRequest
    ```

    Example 2: Use agent with LLM and tools
    ```python
    agent = CodeReviewAgent(llm_client=my_llm, tools_registry={...})
    request = ReviewRequest(github_url="https://github.com/user/repo")
    result = await agent.run(request)
    print(f"Score: {result.quality_score}/10")
    print(result.report)
    ```

    Example 3: Access types and enums
    ```python
    from agent import ReviewResult, AgentStatus, StepType
    if agent.get_status() == AgentStatus.COMPLETED:
        print("Done!")
    ```

    Example 4: Use constants
    ```python
    from agent import MAX_STEPS, TOOLS, LOG_LEVEL
    print(f"Max iterations: {MAX_STEPS}")
    print(f"Available tools: {list(TOOLS.values())}")
    ```

    Example 5: Use utility functions
    ```python
    from agent import format_memory_for_llm, validate_review_request
    is_valid, error = validate_review_request(my_request)
    context = format_memory_for_llm(memory)
    ```

ARCHITECTURE:

    User Request
        |
        v
    CodeReviewAgent.run()
        |
        v
    +--- ReACT Loop (max MAX_STEPS iterations) ---+
    |  THINK    -> LLM decides next tool          |
    |  ACT      -> Extract tool + params          |
    |  OBSERVE  -> Execute via ToolOrchestrator   |
    |  REFLECT  -> Evaluate result                |
    +---------------------------------------------+
        |
        v
    ReviewResult (score, issues, markdown report)

TEAM STRUCTURE:
    - Person 1 (Agent Architect): Yeh module - core agent architecture
    - Person 2 (Tool Engineer): Tools that agent invokes
    - Person 3 (LLM Engineer): LLM clients (Gemini/OpenAI)
    - Person 4 (Backend Engineer): FastAPI endpoints around this
    - Person 5 (Frontend Engineer): Streamlit UI on top
"""

# =============================================================================
# MODULE METADATA
# =============================================================================
__version__ = "1.0.0"
__author__ = "Person 1 (Agent Architect)"
__team__ = "Code Review Agent - 5 Person Team"

# =============================================================================
# PUBLIC API - __all__ controls what `from agent import *` exports
# =============================================================================
__all__ = [
    # --- Main Classes ---
    "CodeReviewAgent",
    "AgentMemory",
    "ToolOrchestrator",

    # --- Type Definitions (dataclasses + enums) ---
    "StepType",
    "AgentStatus",
    "ToolCall",
    "ToolResult",
    "AgentStep",
    "ReviewRequest",
    "ReviewResult",

    # --- Constants ---
    "AGENT_STATES",
    "TOOLS",
    "MAX_STEPS",
    "TOOL_TIMEOUT",
    "RETRY_ATTEMPTS",
    "LOG_LEVEL",
    "MEMORY_MAX_SIZE",
    "DEFAULT_ANALYSIS_TYPE",
    "STEP_TYPES",
    "VERSION",

    # --- Utility Functions ---
    "format_memory_for_llm",
    "extract_tool_name_from_thought",
    "extract_tool_params_from_response",
    "format_tool_result_for_llm",
    "validate_github_url",
    "validate_review_request",
]


# =============================================================================
# IMPORTS - organized by category for clarity
# =============================================================================
# Main classes - the three core components
from .agent_core import CodeReviewAgent
from .agent_memory import AgentMemory
from .agent_orchestrator import ToolOrchestrator

# Type definitions - dataclasses and enums used in API contract
from .agent_types import (
    AgentStatus,    # Agent lifecycle states (IDLE, THINKING, etc.)
    AgentStep,      # Single ReACT cycle step with thought/action/observation
    ReviewRequest,  # User's input - github URL or code + analysis type
    ReviewResult,   # Final output - score, issues, markdown report
    StepType,       # ReACT phase (THINK, ACT, OBSERVE, REFLECT)
    ToolCall,       # Tool execution request with params
    ToolResult,     # Tool execution result with success/data/error
)

# Configuration constants - all tunable values in one place
from .constants import (
    AGENT_STATES,           # Dict of state name -> description
    DEFAULT_ANALYSIS_TYPE,  # Default analysis mode ("full")
    LOG_LEVEL,              # Logging level ("INFO")
    MAX_STEPS,              # Max ReACT iterations per task
    MEMORY_MAX_SIZE,        # Max steps to retain in AgentMemory
    RETRY_ATTEMPTS,         # Retry count for failed tool calls
    STEP_TYPES,             # List of valid step type names
    TOOL_TIMEOUT,           # Per-tool execution timeout (seconds)
    TOOLS,                  # Dict of tool identifier -> tool name
    VERSION,                # Agent version string
)

# Utility functions - pure helpers used throughout the module
from .utils import (
    extract_tool_name_from_thought,    # Parse LLM thought for tool name
    extract_tool_params_from_response,  # Parse LLM response for tool params
    format_memory_for_llm,             # Format AgentMemory as LLM context
    format_tool_result_for_llm,        # Format ToolResult as readable text
    validate_github_url,               # Check if URL is valid GitHub repo
    validate_review_request,           # Validate ReviewRequest object
)


# =============================================================================
# MODULE INITIALIZATION LOGGING
# =============================================================================
# Debug log on import - useful for verifying package loaded correctly
import logging

logger = logging.getLogger(__name__)
logger.debug(
    "Agent module v%s loaded by %s | %d public exports",
    __version__, __author__, len(__all__),
)
