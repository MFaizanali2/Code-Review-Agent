"""
Agent Module - Code Review Agent Implementation
=================================================

ReACT loop (Think -> Act -> Observe -> Reflect) ke through code review
tasks automate karta hai using LLMs aur custom tools.

Architecture:
    agent/                    # Package root
    ├── agent.py             # High-level CodeReviewAgent (primary API)
    ├── core/                # ReACT loop, state, tool orchestration
    ├── llm/                 # LLM client interface (ABC + Mock)
    ├── memory/              # Conversation memory + context window
    ├── tools/               # BaseTool ABC + ToolRegistry
    └── prompts/             # System prompt templates

TEAM STRUCTURE:
    - Person 1 (Agent Architect): Core agent architecture
    - Person 2 (Tool Engineer): Tools that agent invokes
    - Person 3 (LLM Engineer): LLM clients (Gemini/OpenAI)
    - Person 4 (Backend Engineer): FastAPI endpoints around this
    - Person 5 (Frontend Engineer): Streamlit UI on top
"""

__version__ = "2.0.0"
__author__ = "Code Review Agent Team"

from .agent import CodeReviewAgent
from .core.react_loop import ReACTLoop, ReACTConfig, LoopResult, LoopStatus
from .core.state import AgentState, StateManager, Step as AgentStepRecord
from .core.orchestrator import ToolOrchestrator
from .llm.client import LLMClient, LLMResponse, LLMProvider, MockLLMClient
from .memory.conversation import ConversationMemory, MessageRole, Message
from .memory.context import ContextWindow, TokenBudget
from .tools.base import BaseTool, ToolSchema
from .tools.registry import ToolRegistry
from .prompts.system import SYSTEM_PROMPT, build_react_prompt, build_reflection_prompt, build_tool_selection_prompt

from .agent_types import (
    AgentStatus, AgentStep, ReviewRequest, ReviewResult,
    StepType, ToolCall, ToolResult,
)

__all__ = [
    "CodeReviewAgent", "ToolOrchestrator",
    "ReACTLoop", "ReACTConfig", "LoopResult", "LoopStatus",
    "AgentState", "StateManager", "AgentStepRecord",
    "LLMClient", "LLMResponse", "LLMProvider", "MockLLMClient",
    "ConversationMemory", "MessageRole", "Message",
    "ContextWindow", "TokenBudget",
    "BaseTool", "ToolSchema", "ToolRegistry",
    "SYSTEM_PROMPT", "build_react_prompt", "build_reflection_prompt", "build_tool_selection_prompt",
    "AgentStatus", "AgentStep", "ReviewRequest", "ReviewResult",
    "StepType", "ToolCall", "ToolResult",
]

import logging
logger = logging.getLogger(__name__)
logger.debug("Agent module v%s loaded", __version__)
