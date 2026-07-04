"""
System Prompts - LLM ko guide karne ke liye saari instructions yahan hain.
Centralized prompts - easy to update aur version control.
"""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT = """You are CodeReviewAgent, an expert AI code reviewer.

Your capabilities:
- Analyze code for bugs, security issues, and performance problems
- Suggest improvements following best practices
- Use available tools to perform deep analysis
- Communicate clearly in both English and Roman Urdu

Rules:
1. Always think step-by-step before acting
2. Use tools when you need concrete data (linting, security scans, etc.)
3. When confident in your answer, output it as a JSON with "type": "final_answer"
4. Never guess - if unsure, use a tool to verify
5. Be concise but thorough
6. Respect user's language preference (English or Roman Urdu)
"""


def build_react_prompt(
    user_input: str,
    history: list[dict],
    available_tools: list[dict[str, Any]],
    observations: str,
    iteration: int,
) -> str:
    """
    ReACT cycle ke THINK step ke liye prompt banao.
    LLM ko current state aur options dikhata hai.
    """
    tools_text = "\n".join(
        f"- {t['name']}: {t['description']}"
        for t in available_tools
    ) or "No tools available"

    history_text = "\n".join(
        f"[{getattr(m, 'role', 'unknown')}] {getattr(m, 'content', '')}"
        for m in history[-5:]
    ) or "No prior history"

    return f"""You are in iteration {iteration} of a reasoning loop.

USER REQUEST: {user_input}

CONVERSATION HISTORY:
{history_text}

OBSERVATIONS SO FAR:
{observations}

AVAILABLE TOOLS:
{tools_text}

INSTRUCTIONS:
1. Reason about what to do next
2. If you have enough info, respond with JSON: {{"type": "final_answer", "answer": "..."}}
3. If you need a tool, respond with JSON: {{"type": "tool_call", "tool": "tool_name", "input": {{...}}}}
4. Keep your thinking concise

Your response:"""


def build_reflection_prompt(
    user_input: str,
    observation: str,
    iteration: int,
    steps_so_far: int,
) -> str:
    """
    REFLECT step ke liye prompt - LLM se poocho "kya task complete hua?"
    Yeh unnecessary iterations rokta hai.
    """
    return f"""Reflect on the latest observation.

USER REQUEST: {user_input}
LATEST OBSERVATION: {observation}
ITERATION: {iteration}
TOTAL STEPS: {steps_so_far}

Questions to answer:
1. Does this observation address the user's request?
2. Do we have enough information to provide a final answer?
3. What (if anything) is still missing?

If you believe the task is complete, say "TASK COMPLETE" in your response.
Otherwise, briefly describe what's still needed.

Your reflection:"""


def build_tool_selection_prompt(
    user_input: str,
    observations: str,
    history: list[dict],
) -> str:
    """
    Jab max iterations hit ho jaye ya timeout ho jaye, final answer banane ka prompt.
    Best-effort answer generate karta hai.
    """
    history_text = "\n".join(
        f"[{getattr(m, 'role', 'unknown')}] {getattr(m, 'content', '')}"
        for m in history[-5:]
    )

    return f"""Based on all information gathered, provide a final answer.

USER REQUEST: {user_input}

CONVERSATION:
{history_text}

OBSERVATIONS:
{observations}

Provide a clear, well-structured answer based on the available data.
If information is incomplete, acknowledge limitations and provide best-effort guidance.

Your final answer:"""
