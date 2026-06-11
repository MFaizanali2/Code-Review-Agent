# 👤 Person 3: LLM Integration Specialist — Complete Implementation Plan

**Role:** LLM Integration Specialist  
**Status:** Ready for Implementation  
**Priority:** HIGH  

---

## 📌 Overview

Tumhara kaam hai **Gemini/OpenAI LLM ko agent se connect karna**, prompts optimize karna, tool definitions banana, aur response parsing handle karna. Yeh project ka **brain** hai — LLM hi sochega ke konsa tool use karna hai.

---

## 🗂️ Files to Create (6 files)

```
llm/
├── __init__.py              ← Package init
├── llm_client.py            ← LLM API client (Gemini + OpenAI both)
├── llm_types.py             ← Type definitions, dataclasses
├── prompts.py               ← System prompts + few-shot examples
├── tool_schemas.py          ← Tool definitions for LLM
└── response_parser.py       ← Parse LLM responses into structured format
```

---

## 📅 Day-wise Execution Plan

### Day 1: Foundation (Types + Schemas)

| Time | Task | File |
|------|------|------|
| 2 hrs | `llm_types.py` — All dataclasses/types | ✅ Done |
| 3 hrs | `tool_schemas.py` — Enhanced tool definitions | ✅ Done |
| 2 hrs | Testing types & schemas | ✅ Done |

### Day 2: LLM Client Core

| Time | Task | File |
|------|------|------|
| 3 hrs | `llm_client.py` — Main client (both Gemini + OpenAI) | ✅ Done |
| 2 hrs | Retry logic + error handling | ✅ Done |
| 2 hrs | Token counting + cost estimation | ✅ Done |

### Day 3: Prompts + Response Parsing

| Time | Task | File |
|------|------|------|
| 3 hrs | `prompts.py` — System prompt + few-shot examples | ✅ Done |
| 3 hrs | `response_parser.py` — Robust parsing | ✅ Done |
| 1 hr | Cross-format support (JSON + Markdown) | ✅ Done |

### Day 4: Testing + Integration

| Time | Task |
|------|------|
| 3 hrs | Unit tests for all files |
| 2 hrs | Integration with Person 1 (Agent) |
| 2 hrs | Integration with Person 2 (Tools) |

### Day 5: Polish + Optimization

| Time | Task |
|------|------|
| 2 hrs | Token optimization |
| 2 hrs | Caching strategy |
| 2 hrs | Documentation |
| 1 hr | Final review |

---

## 🔧 File-by-File Implementation Details

---

### 📄 File 1: `llm/__init__.py`

```python
from .llm_client import LLMClient
from .llm_types import (
    LLMConfig, ToolCall, LLMResponse,
    Message, Role, ContentBlock
)
from .prompts import SYSTEM_PROMPT, get_review_prompt
from .tool_schemas import get_tool_schemas
from .response_parser import parse_llm_response

__all__ = [
    "LLMClient",
    "LLMConfig", "ToolCall", "LLMResponse",
    "Message", "Role", "ContentBlock",
    "SYSTEM_PROMPT", "get_review_prompt",
    "get_tool_schemas",
    "parse_llm_response",
]
```

---

### 📄 File 2: `llm/llm_types.py` — Type Definitions

**Kyun banaya?** — Saare types ek jagah define honge taake consistency rahe aur type hints ka sahi use ho.

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: Role
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class ContentBlock:
    type: str  # "text" or "tool_use" or "tool_result"
    text: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_result: Optional[dict] = None


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LLMConfig:
    """LLM configuration with sensible defaults"""
    model: str = "gemini-2.0-flash"
    temperature: float = 0.3
    top_p: float = 0.9
    top_k: int = 40
    max_output_tokens: int = 4096
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    provider: str = "gemini"  # "gemini" or "openai"
    api_key: Optional[str] = None


@dataclass
class LLMResponse:
    """Standardized LLM response"""
    success: bool
    text: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: Optional[str] = None
    usage: Optional[dict] = None
    latency_ms: float = 0.0


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
```

---

### 📄 File 3: `llm/tool_schemas.py` — Enhanced Tool Definitions

**Kyun improved?** — Har tool ka ab detailed schema hai with examples, constraints, aur proper typing. Yeh LLM ko better decisions lene mein help karega.

```python
"""
LLM ke liye tool definitions — JSON schema format mein.
Yeh Gemini/OpenAI function calling ke liye ready hai.

Key improvements over original:
1. Detailed field descriptions with examples
2. Input validation constraints (min/max, patterns)
3. Return type hints in descriptions
4. Consistent naming conventions
5. Tool categories for better organization
6. Required vs optional clearly marked
7. Enums where applicable
"""

def get_tool_schemas() -> list[dict]:
    """
    Saare tools ka schema return karta hai.
    LLM ko batata hai ke kaunse tools available hain aur unkaise use karne hain.
    """
    return [
        _github_tool_schema(),
        _code_analyzer_schema(),
        _security_checker_schema(),
        _performance_checker_schema(),
        _report_generator_schema(),
        _file_reader_schema(),
    ]


def _github_tool_schema() -> dict:
    return {
        "name": "fetch_repository",
        "description": (
            "GitHub se repository clone karta hai aur file list return karta hai. "
            "Sirf PUBLIC repositories support hain. "
            "Repository URL full hona chahiye (https://github.com/username/repo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "github_url": {
                    "type": "string",
                    "description": (
                        "Full GitHub repository URL. "
                        "Example: 'https://github.com/psf/black'"
                    ),
                    "pattern": r"^https://github\.com/[\w.-]+/[\w.-]+/?$",
                },
                "branch": {
                    "type": "string",
                    "description": (
                        "Branch ya tag name (default: main ya master auto-detect). "
                        "Example: 'main', 'develop', 'v1.0.0'"
                    ),
                    "default": "main",
                },
                "depth": {
                    "type": "integer",
                    "description": "Clone depth for faster cloning. 0 = full clone.",
                    "default": 1,
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "required": ["github_url"],
        },
    }


def _code_analyzer_schema() -> dict:
    return {
        "name": "analyze_code_structure",
        "description": (
            "Kisi bhi Python file ka structure analyze karta hai. "
            "Functions, classes, imports, aur complexity nikalta hai. "
            "Sirf .py files support hain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Analyze karne ke liye file ka relative path. "
                        "Example: 'src/main.py', 'utils/helpers.py'"
                    ),
                },
                "include_ast": {
                    "type": "boolean",
                    "description": "AST details bhi include karein? (default: false)",
                    "default": False,
                },
            },
            "required": ["file_path"],
        },
    }


def _security_checker_schema() -> dict:
    return {
        "name": "security_audit",
        "description": (
            "Code mein security vulnerabilities detect karta hai. "
            "Checks: SQL injection, hardcoded secrets, eval/exec usage, "
            "command injection, path traversal, unsafe deserialization."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File ka path jiska security audit karna hai.",
                },
                "severity_threshold": {
                    "type": "string",
                    "description": (
                        "Minimum severity to report. "
                        "Options: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'"
                    ),
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    "default": "LOW",
                },
            },
            "required": ["file_path"],
        },
    }


def _performance_checker_schema() -> dict:
    return {
        "name": "performance_analysis",
        "description": (
            "Performance bottlenecks identify karta hai. "
            "Checks: nested loops, O(n²) complexity, "
            "memory leaks, string concat in loops, large allocations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File ka path jiska performance analysis karna hai.",
                },
                "detailed": {
                    "type": "boolean",
                    "description": "Detailed analysis with line numbers? (default: false)",
                    "default": False,
                },
            },
            "required": ["file_path"],
        },
    }


def _report_generator_schema() -> dict:
    return {
        "name": "generate_report",
        "description": (
            "Saare findings ko ek structured report mein convert karta hai. "
            "Report mein score, issues, recommendations, aur code examples hote hain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "description": "All findings from security, performance, and analysis tools.",
                    "items": {"type": "object"},
                },
                "format": {
                    "type": "string",
                    "description": "Report format. Options: 'markdown', 'json'",
                    "enum": ["markdown", "json"],
                    "default": "markdown",
                },
                "include_code_examples": {
                    "type": "boolean",
                    "description": "Fix examples include karein? (default: true)",
                    "default": True,
                },
            },
            "required": ["findings"],
        },
    }


def _file_reader_schema() -> dict:
    return {
        "name": "read_file_content",
        "description": (
            "Kisi bhi file ka content read karta hai. "
            "Binary files skip ho jayenge. "
            "Sirf text files support hain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File ka path jo read karna hai.",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to read (0 = all).",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 5000,
                },
            },
            "required": ["file_path"],
        },
    }


TOOL_CATEGORIES = {
    "code_fetching": ["fetch_repository"],
    "code_analysis": ["analyze_code_structure", "read_file_content"],
    "security": ["security_audit"],
    "performance": ["performance_analysis"],
    "reporting": ["generate_report"],
}


def get_simplified_tools() -> list[dict]:
    """
    Kuch tools ka simplified version — jab LLM ko simple tasks karne hote hain.
    Isme extra details nahi hoti, bas basic fields hoti hain.
    """
    return [
        {
            "name": "fetch_repository",
            "description": "GitHub se code fetch karein",
            "input_schema": {
                "type": "object",
                "properties": {
                    "github_url": {"type": "string"}
                },
                "required": ["github_url"],
            },
        },
        {
            "name": "analyze_code_structure",
            "description": "Code structure analyze karein",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"}
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "security_audit",
            "description": "Security check karein",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"}
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "performance_analysis",
            "description": "Performance check karein",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"}
                },
                "required": ["file_path"],
            },
        },
    ]
```

---

### 📄 File 4: `llm/llm_client.py` — Improved LLM Client

**Key improvements over original:**

| Feature | Original | Improved |
|---------|----------|----------|
| Provider | Sirf Gemini | Gemini + OpenAI both |
| Retry logic | ❌ Nahi hai | ✅ Exponential backoff |
| Token counting | ❌ Nahi hai | ✅ Token usage tracking |
| Cost estimation | ❌ Nahi hai | ✅ Cost calculator |
| Caching | ❌ Nahi hai | ✅ Response caching |
| Streaming | ❌ Nahi hai | ✅ Streaming support |
| Timeout | ❌ Nahi hai | ✅ Configurable timeout |
| Logging | ❌ Nahi hai | ✅ Structured logging |

```python
"""
LLM Client — Gemini aur OpenAI dono ko support karta hai.

Usage:
    client = LLMClient(api_key="...", provider="gemini")
    # ya
    client = LLMClient(api_key="...", provider="openai")

    response = await client.call_with_tools(
        messages=[Message(role=Role.USER, content="Review this code")],
        tools=get_tool_schemas()
    )
"""

import asyncio
import json
import logging
import time
from typing import Optional

from .llm_types import (
    LLMConfig, LLMResponse, Message, Role,
    ToolCall, TokenUsage
)

logger = logging.getLogger(__name__)


# --- Cost tables (per 1K tokens in USD) ---
COST_TABLES = {
    "gemini": {
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        "gemini-2.0-flash-lite": {"input": 0.000075, "output": 0.0003},
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
    },
    "openai": {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.0015, "output": 0.006},
        "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
    },
}


class LLMClient:
    """
    Main LLM client — Gemini aur OpenAI dono ka common interface.

    Features:
    - Automatic retry with exponential backoff
    - Token usage tracking
    - Cost estimation
    - Streaming support
    - Response caching
    """

    def __init__(
        self,
        api_key: str,
        config: Optional[LLMConfig] = None,
    ):
        self.config = config or LLMConfig()
        self.config.api_key = api_key
        self.provider = self.config.provider
        self.model = self.config.model
        self._client = None
        self._cache: dict[str, LLMResponse] = {}
        self._total_usage = TokenUsage()

        self._init_client()

    def _init_client(self):
        """Provider ke hisaab se client initialize karo"""
        try:
            if self.provider == "gemini":
                import google.generativeai as genai
                genai.configure(api_key=self.config.api_key)
                self._client = genai.GenerativeModel(self.model)

            elif self.provider == "openai":
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout,
                )

            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            logger.info(
                "LLM Client initialized",
                extra={
                    "provider": self.provider,
                    "model": self.model,
                },
            )

        except ImportError as e:
            raise ImportError(
                f"{self.provider} ke liye package install nahi hai. "
                f"Run: pip install google-generativeai ya openai"
            ) from e

    def _get_cache_key(self, messages: list, tools: Optional[list] = None) -> str:
        """Cache key generate karo — same request pe same response na aaye"""
        import hashlib
        data = json.dumps(
            [
                [{"role": m.role.value, "content": m.content} for m in messages],
                tools,
            ],
            sort_keys=True,
            default=str,
        )
        return hashlib.md5(data.encode()).hexdigest()

    def _estimate_tokens(self, text: str) -> int:
        """Approximately token count karo (4 chars ≈ 1 token)"""
        return len(text) // 4 + 1

    def _estimate_cost(self, usage: TokenUsage, model: str) -> float:
        """Cost estimate karo based on token usage"""
        model_cost = COST_TABLES.get(self.provider, {}).get(
            model, {"input": 0.001, "output": 0.002}
        )
        input_cost = (usage.prompt_tokens / 1000) * model_cost["input"]
        output_cost = (usage.completion_tokens / 1000) * model_cost["output"]
        return round(input_cost + output_cost, 6)

    def _convert_messages_for_gemini(self, messages: list[Message]) -> list[dict]:
        """Messages ko Gemini format mein convert karo"""
        contents = []
        for msg in messages:
            role = "model" if msg.role == Role.ASSISTANT else msg.role.value
            content = msg.content

            # Tool results ko alag format mein bhejo
            if msg.role == Role.TOOL:
                if not contents or contents[-1]["role"] != "function":
                    # Part of function response
                    if contents and contents[-1]["role"] == "model":
                        # Append as function response
                        contents.append({
                            "role": "function",
                            "parts": [{"function_response": {
                                "name": msg.name or "unknown",
                                "response": {"result": content},
                            }}],
                        })
                        continue
                else:
                    contents.append({
                        "role": "function",
                        "parts": [{"function_response": {
                            "name": msg.name or "unknown",
                            "response": {"result": content},
                        }}],
                    })
                    continue

            contents.append({
                "role": role,
                "parts": [{"text": content}],
            })

        return contents

    def _convert_messages_for_openai(self, messages: list[Message]) -> list[dict]:
        """Messages ko OpenAI format mein convert karo"""
        result = []
        for msg in messages:
            entry = {"role": msg.role.value}
            if msg.content:
                entry["content"] = msg.content
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    def _parse_gemini_response(self, response) -> LLMResponse:
        """Gemini response ko parse karo"""
        try:
            text = response.text if hasattr(response, "text") else ""
            tool_calls = []

            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call"):
                            tool_calls.append(ToolCall(
                                id=str(id(part)),
                                name=part.function_call.name,
                                args=dict(part.function_call.args),
                            ))

            # Token usage
            usage = TokenUsage()
            if hasattr(response, "usage_metadata"):
                usage.prompt_tokens = getattr(
                    response.usage_metadata, "prompt_token_count", 0
                )
                usage.completion_tokens = getattr(
                    response.usage_metadata, "candidates_token_count", 0
                )
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

            return LLMResponse(
                success=True,
                text=text,
                tool_calls=tool_calls,
                usage=usage.__dict__,
            )

        except Exception as e:
            logger.error(f"Gemini response parse error: {e}")
            return LLMResponse(
                success=False,
                error=f"Parse error: {str(e)}",
            )

    def _parse_openai_response(self, response) -> LLMResponse:
        """OpenAI response ko parse karo"""
        try:
            message = response.choices[0].message
            text = message.content or ""
            tool_calls = []

            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        args=json.loads(tc.function.arguments),
                    ))

            # Token usage
            usage = TokenUsage()
            if hasattr(response, "usage"):
                usage.prompt_tokens = response.usage.prompt_tokens or 0
                usage.completion_tokens = response.usage.completion_tokens or 0
                usage.total_tokens = response.usage.total_tokens or 0

            return LLMResponse(
                success=True,
                text=text,
                tool_calls=tool_calls,
                usage=usage.__dict__,
            )

        except Exception as e:
            logger.error(f"OpenAI response parse error: {e}")
            return LLMResponse(
                success=False,
                error=f"Parse error: {str(e)}",
            )

    async def call_with_tools(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        use_cache: bool = True,
    ) -> LLMResponse:
        """
        LLM ko call karo with tool definitions.

        Args:
            messages: Conversation history
            tools: Tool definitions (optional)
            use_cache: Cache use karna hai ya nahi

        Returns:
            LLMResponse with text and/or tool_calls
        """
        start_time = time.time()

        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(messages, tools)
            if cache_key in self._cache:
                logger.debug("Cache hit for request")
                return self._cache[cache_key]

        # Retry loop
        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = await self._call_llm_with_retry(
                    messages, tools, attempt
                )

                # Track usage
                if response.usage:
                    usage = TokenUsage(**response.usage)
                    usage.estimated_cost_usd = self._estimate_cost(
                        usage, self.model
                    )
                    response.usage = usage.__dict__

                    # Update total
                    self._total_usage.prompt_tokens += usage.prompt_tokens
                    self._total_usage.completion_tokens += usage.completion_tokens
                    self._total_usage.total_tokens += usage.total_tokens
                    self._total_usage.estimated_cost_usd += usage.estimated_cost_usd

                response.latency_ms = round((time.time() - start_time) * 1000, 2)

                # Cache response
                if use_cache and response.success:
                    cache_key = self._get_cache_key(messages, tools)
                    self._cache[cache_key] = response

                return response

            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait = self.config.retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Attempt {attempt} failed: {e}. "
                        f"Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"All {self.config.max_retries} attempts failed")

        return LLMResponse(
            success=False,
            error=f"Max retries exceeded: {last_error}",
            latency_ms=round((time.time() - start_time) * 1000, 2),
        )

    async def _call_llm_with_retry(
        self,
        messages: list[Message],
        tools: Optional[list[dict]],
        attempt: int,
    ):
        """Actual LLM API call — provider-specific"""
        if self.provider == "gemini":
            return await self._call_gemini(messages, tools)
        else:
            return await self._call_openai(messages, tools)

    async def _call_gemini(
        self, messages: list[Message], tools: Optional[list[dict]]
    ) -> LLMResponse:
        """Gemini API call"""
        try:
            contents = self._convert_messages_for_gemini(messages)

            generation_config = {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "top_k": self.config.top_k,
                "max_output_tokens": self.config.max_output_tokens,
            }

            # System prompt alag se bhejo
            system_prompt = None
            filtered_contents = []
            for msg in contents:
                if msg.get("role") == "system":
                    system_prompt = msg["parts"][0]["text"]
                else:
                    filtered_contents.append(msg)

            kwargs = {
                "contents": filtered_contents or contents,
                "generation_config": generation_config,
            }

            if system_prompt:
                kwargs["system_instruction"] = system_prompt

            if tools:
                kwargs["tools"] = tools

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.generate_content(**kwargs),
            )

            return self._parse_gemini_response(response)

        except Exception as e:
            logger.exception(f"Gemini API error: {e}")
            raise

    async def _call_openai(
        self, messages: list[Message], tools: Optional[list[dict]]
    ) -> LLMResponse:
        """OpenAI API call"""
        try:
            openai_messages = self._convert_messages_for_openai(messages)

            kwargs = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_output_tokens,
                "top_p": self.config.top_p,
            }

            if tools:
                kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": t.get("input_schema", {}),
                        },
                    }
                    for t in tools
                ]
                kwargs["tool_choice"] = "auto"

            response = await self._client.chat.completions.create(**kwargs)
            return self._parse_openai_response(response)

        except Exception as e:
            logger.exception(f"OpenAI API error: {e}")
            raise

    async def call_without_tools(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """Simple text generation — bina tools ke"""
        messages = []

        if system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=system_prompt))

        messages.append(Message(role=Role.USER, content=prompt))

        return await self.call_with_tools(messages, tools=None)

    async def stream_response(
        self, messages: list[Message], system_prompt: Optional[str] = None
    ):
        """Streaming response — Gemini ke saath"""
        if self.provider != "gemini":
            raise NotImplementedError("Streaming sirf Gemini ke saath hai abhi")

        contents = self._convert_messages_for_gemini(messages)

        generation_config = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
        }

        kwargs = {"contents": contents, "generation_config": generation_config}
        if system_prompt:
            kwargs["system_instruction"] = system_prompt

        response = self._client.generate_content(**kwargs, stream=True)

        for chunk in response:
            if hasattr(chunk, "text") and chunk.text:
                yield chunk.text

    def get_total_usage(self) -> dict:
        """Total token usage aur cost return karo"""
        return {
            "total_tokens": self._total_usage.total_tokens,
            "prompt_tokens": self._total_usage.prompt_tokens,
            "completion_tokens": self._total_usage.completion_tokens,
            "estimated_cost_usd": round(
                self._total_usage.estimated_cost_usd, 4
            ),
        }

    def clear_cache(self):
        """Cache clear karo"""
        self._cache.clear()
        logger.info("LLM cache cleared")

    async def validate_api_key(self) -> bool:
        """Check karo ke API key valid hai ya nahi"""
        try:
            if self.provider == "gemini":
                response = await self.call_without_tools(
                    "Say 'ok' if you can read this."
                )
                return response.success
            else:
                # OpenAI — list models se check karo
                await self._client.models.list()
                return True
        except Exception:
            return False


# Factory function
def create_llm_client(
    api_key: str,
    provider: str = "gemini",
    model: Optional[str] = None,
    **kwargs,
) -> LLMClient:
    """
    LLMClient banane ka easy tarika.

    Usage:
        client = create_llm_client("api-key-here")
        client = create_llm_client("api-key", provider="openai", model="gpt-4o")
    """
    config = LLMConfig(provider=provider, **kwargs)
    if model:
        config.model = model
    return LLMClient(api_key=api_key, config=config)
```

---

### 📄 File 5: `llm/prompts.py` — Advanced System Prompts

**Key improvements over original:**

| Feature | Original | Improved |
|---------|----------|----------|
| System prompt | ✅ Basic | ✅ Detailed with examples |
| Few-shot examples | ✅ 2 examples | ✅ 5 examples (all categories) |
| Dynamic prompting | ❌ Nahi hai | ✅ Custom prompt builder |
| Chain-of-thought | ❌ Nahi hai | ✅ Step-by-step reasoning |
| Output format | Basic text | ✅ Structured + JSON |
| Urdu/English mix | ✅ Basic | ✅ Better mix |

```python
"""
Prompts — System prompts, few-shot examples, aur dynamic prompt builder.
Saare prompts Urdu + English mix mein hain for better understanding.
"""

# ============================================================
# MAIN SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """You are an expert AI Code Reviewer Agent. Your job is to analyze code professionally.

## 🎯 Your Role
You are a senior developer jo code reviews karta hai. Tumhe har file ko carefully analyze karna hai aur detailed feedback dena hai.

## 🔧 Tools Available
You have these tools:
1. **fetch_repository** — GitHub se code download karo
2. **analyze_code_structure** — Code ka structure samjho (functions, classes)
3. **security_audit** — Security vulnerabilities check karo
4. **performance_analysis** — Performance issues find karo
5. **read_file_content** — Kisi bhi file ka content padho
6. **generate_report** — Final report banao

## 📋 Analysis Process (FOLLOW THIS ORDER)

### STEP 1: Fetch & Understand
- Pehle repository fetch karo
- File structure dekho aur main files identify karo
- Project ka purpose samjho

### STEP 2: Deep Analysis
- Har important file ko read karo
- Code structure analyze karo
- Functions, classes, imports note karo

### STEP 3: Security Review
- Security vulnerabilities check karo
- CRITICAL issues pe focus karo
- Hardcoded secrets, injections, unsafe code

### STEP 4: Performance Check
- Slow code patterns find karo
- Nested loops, memory issues, O(n²) complexity
- Optimization suggestions do

### STEP 5: Report Generation
- Saare findings ko compile karo
- Quality score do (0-100)
- Actionable recommendations do

## 📊 Scoring Guidelines
- **90-100**: Excellent — Production ready
- **70-89**: Good — Minor improvements needed
- **50-69**: Average — Major issues found
- **30-49**: Poor — Significant rework needed
- **0-29**: Critical — Complete rewrite recommended

## ⚠️ Critical Checks (ALWAYS DO THESE)
1. ❌ Hardcoded secrets (passwords, API keys, tokens)
2. ❌ SQL injection vulnerabilities
3. ❌ Unsafe eval()/exec() usage
4. ❌ Path traversal vulnerabilities
5. ❌ Command injection risks
6. ❌ Insecure deserialization

## ✅ Best Practices (RECOMMEND THESE)
1. 📁 Follow project conventions
2. 🔒 Use environment variables for secrets
3. ⚡ Optimize loops and data structures
4. 🧪 Add proper error handling
5. 📝 Use type hints
6. 🧹 Remove dead code and debug statements

## 📤 Output Format
Always structure your final report like this:

```
## 📊 Quality Score: XX/100

## 🚨 Critical Issues (X)
- [description with line numbers]

## ⚠️ Major Issues (X)
- [description with line numbers]

## 📝 Minor Issues (X)
- [description with line numbers]

## 💡 Recommendations
- [actionable suggestions]

## 🔧 Code Examples
- [before/after code snippets]
```

## 🚫 Rules
1. NEVER make up issues — only report real problems
2. NEVER suggest removing functionality
3. ALWAYS give constructive feedback
4. ALWAYS explain WHY something is an issue
5. Use line numbers where possible
6. Be specific, not vague
"""

# ============================================================
# FEW-SHOT EXAMPLES
# ============================================================

FEW_SHOT_EXAMPLES = [
    {
        "category": "Security",
        "code": """password = "admin123"
api_key = "sk-1234567890abcdef"
db.execute(f"SELECT * FROM users WHERE id = {user_input}")""",
        "analysis": {
            "issues": [
                {
                    "type": "Hardcoded Secrets",
                    "severity": "CRITICAL",
                    "line": 1,
                    "message": "Password hardcoded in source code",
                    "fix": "Use environment variables: os.getenv('DB_PASSWORD')"
                },
                {
                    "type": "Hardcoded Secrets",
                    "severity": "CRITICAL",
                    "line": 2,
                    "message": "API key exposed in code",
                    "fix": "Store in .env file and load with python-dotenv"
                },
                {
                    "type": "SQL Injection",
                    "severity": "CRITICAL",
                    "line": 3,
                    "message": "SQL injection vulnerability - f-string in query",
                    "fix": "Use parameterized queries: db.execute('SELECT * FROM users WHERE id = ?', (user_input,))"
                }
            ],
            "score_impact": -30
        }
    },
    {
        "category": "Performance",
        "code": """result = []
for i in range(len(data)):
    for j in range(len(data)):
        result.append(data[i] + data[j])

full_string = ""
for item in items:
    full_string += item + ","

big_list = list(range(1000000))""",
        "analysis": {
            "issues": [
                {
                    "type": "Nested Loops",
                    "severity": "HIGH",
                    "line": 2,
                    "message": "O(n²) complexity - nested loops",
                    "fix": "Use itertools.product() or numpy broadcasting"
                },
                {
                    "type": "String Concatenation",
                    "severity": "MEDIUM",
                    "line": 7,
                    "message": "String concatenation in loop creates new string each iteration",
                    "fix": "Use ','.join(items) - O(n) instead of O(n²)"
                },
                {
                    "type": "Memory Usage",
                    "severity": "LOW",
                    "line": 10,
                    "message": "Large list created in memory",
                    "fix": "Use range() directly or generator: (x for x in range(1000000))"
                }
            ],
            "score_impact": -15
        }
    },
    {
        "category": "Code Quality",
        "code": """def calc(a,b,c,d,e):
    x = a+b
    y = x*c
    z = y-d
    return z+e

def process():
    pass
    pass
    pass
    return None""",
        "analysis": {
            "issues": [
                {
                    "type": "Unclear Function",
                    "severity": "MEDIUM",
                    "line": 1,
                    "message": "Function name 'calc' is vague, too many parameters",
                    "fix": "Rename to 'calculate_discount' with specific params"
                },
                {
                    "type": "Dead Code",
                    "severity": "LOW",
                    "line": 7,
                    "message": "Unnecessary pass statements",
                    "fix": "Remove unused pass statements"
                },
                {
                    "type": "Missing Type Hints",
                    "severity": "LOW",
                    "line": 1,
                    "message": "No type hints on function parameters",
                    "fix": "def calc(a: int, b: int, c: int, d: int, e: int) -> int:"
                }
            ],
            "score_impact": -10
        }
    },
    {
        "category": "Error Handling",
        "code": """data = open("file.txt").read()
result = 100 / user_input
import requests
response = requests.get(url)""",
        "analysis": {
            "issues": [
                {
                    "type": "Missing Error Handling",
                    "severity": "HIGH",
                    "line": 1,
                    "message": "File not closed - resource leak, no exception handling",
                    "fix": "Use 'with open(\"file.txt\") as f: data = f.read()'"
                },
                {
                    "type": "Division by Zero",
                    "severity": "CRITICAL",
                    "line": 2,
                    "message": "Potential ZeroDivisionError",
                    "fix": "Check: if user_input != 0: result = 100 / user_input"
                },
                {
                    "type": "Network Error",
                    "severity": "MEDIUM",
                    "line": 4,
                    "message": "No try/except around network call",
                    "fix": "Wrap in try/except for ConnectionError, Timeout"
                }
            ],
            "score_impact": -20
        }
    },
    {
        "category": "Best Practices",
        "code": """import *
from module import *

MY_CONSTANT = 42
my_mixed_case = "bad"
MY_OTHER_CONSTANT = 56

def DoSomething():
    global MY_CONSTANT
    MY_CONSTANT = 100""",
        "analysis": {
            "issues": [
                {
                    "type": "Wildcard Import",
                    "severity": "MEDIUM",
                    "line": 1,
                    "message": "Wildcard import causes namespace pollution",
                    "fix": "Import specific names: from module import specific_function"
                },
                {
                    "type": "Naming Convention",
                    "severity": "LOW",
                    "line": 5,
                    "message": "Variable uses mixed_case instead of snake_case",
                    "fix": "Rename to: my_mixed_case_var"
                },
                {
                    "type": "Global Variable",
                    "severity": "MEDIUM",
                    "line": 10,
                    "message": "Modifying global variable in function",
                    "fix": "Pass as parameter and return new value"
                }
            ],
            "score_impact": -8
        }
    }
]


# ============================================================
# DYNAMIC PROMPT BUILDERS
# ============================================================

def get_review_prompt(
    repo_url: str = None,
    files_to_review: list[str] = None,
    focus_areas: list[str] = None,
) -> str:
    """
    Dynamic review prompt banata hai based on context.
    
    Args:
        repo_url: GitHub repository URL (optional)
        files_to_review: Specific files jinhe review karna hai
        focus_areas: Kis cheez pe focus karna hai (security, performance, quality)
    
    Returns:
        str: Review prompt
    """
    prompt_parts = ["## 📋 Code Review Request\n"]

    if repo_url:
        prompt_parts.append(f"**Repository:** {repo_url}\n")

    if files_to_review:
        prompt_parts.append(
            f"**Files to Review:** {', '.join(files_to_review)}\n"
        )

    if focus_areas:
        prompt_parts.append(
            f"**Focus Areas:** {', '.join(focus_areas)}\n"
        )

    prompt_parts.append("""
Please analyze the code and provide:
1. Quality score (0-100)
2. Critical issues (must fix)
3. Major issues (should fix)
4. Minor issues (nice to fix)
5. Specific recommendations
6. Code examples for fixes

Be thorough and constructive. Include line numbers.
    """)

    return "\n".join(prompt_parts)


def get_fix_prompt(error_message: str, code_snippet: str) -> str:
    """
    Specific error ke liye fix suggestion prompt.
    
    Args:
        error_message: Error message from tool/compiler
        code_snippet: Code jisme error hai
    
    Returns:
        str: Fix suggestion prompt
    """
    return f"""## 🔧 Code Fix Request

**Error:**
```
{error_message}
```

**Code:**
```
{code_snippet}
```

Please:
1. Identify the root cause
2. Provide the fix
3. Explain why this fix works
4. Show before/after code
"""


def get_summary_prompt(findings: list[dict]) -> str:
    """
    Saare findings ka summary banane ke liye prompt.
    
    Args:
        findings: List of findings from different tools
    
    Returns:
        str: Summary prompt
    """
    return f"""## 📊 Review Summary

**Findings: {json.dumps(findings, indent=2, default=str)}**

Please provide:
1. Overall quality score (0-100)
2. Top 3 most critical issues
3. Summary paragraph
4. 3 quick wins (easy fixes)
"""


import json  # noqa: E402 — for get_summary_prompt
```

---

### 📄 File 6: `llm/response_parser.py` — Robust Response Parser

**Key improvements over original:**

| Feature | Original | Improved |
|---------|----------|----------|
| JSON parsing | ❌ Nahi hai | ✅ JSON + Markdown both |
| Error recovery | ❌ Nahi hai | ✅ Graceful fallback |
| Score extraction | ✅ Basic regex | ✅ Multiple pattern matching |
| Issue extraction | ✅ Basic | ✅ Severity-based grouping |
| Recommendation extraction | ✅ Basic | ✅ Priority-sorted |
| Validation | ❌ Nahi hai | ✅ Output validation |
| Line numbers | ❌ Nahi hai | ✅ Line number extraction |

```python
"""
Response Parser — LLM ke response ko structured format mein convert karta hai.

Supports:
1. Markdown format (default)
2. JSON format
3. Mixed format
4. Error recovery for malformed responses
"""

import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ParsedReview:
    """
    Structured review output.
    Saari fields properly typed hain.
    """
    def __init__(self):
        self.quality_score: int = 0
        self.critical_issues: list[dict] = []
        self.major_issues: list[dict] = []
        self.minor_issues: list[dict] = []
        self.recommendations: list[str] = []
        self.summary: str = ""
        self.raw_text: str = ""
        self.parsing_method: str = "markdown"

    def to_dict(self) -> dict:
        return {
            "quality_score": self.quality_score,
            "critical_issues": self.critical_issues,
            "major_issues": self.major_issues,
            "minor_issues": self.minor_issues,
            "recommendations": self.recommendations,
            "summary": self.summary,
            "total_issues": (
                len(self.critical_issues)
                + len(self.major_issues)
                + len(self.minor_issues)
            ),
        }

    @property
    def all_issues(self) -> list[dict]:
        """Saare issues ek saath, severity sorted"""
        return (
            self.critical_issues
            + self.major_issues
            + self.minor_issues
        )


def parse_llm_response(response_text: str) -> ParsedReview:
    """
    Main parsing function — LLM response ko parse karta hai.

    Strategy:
    1. Pehle JSON format try karo
    2. Phir Markdown format try karo
    3. Agar kuch kaam na kare toh basic extraction karo
    """
    result = ParsedReview()
    result.raw_text = response_text

    if not response_text or not response_text.strip():
        logger.warning("Empty response received")
        result.summary = "No response received from LLM."
        return result

    # Strategy 1: JSON format
    if response_text.strip().startswith("{"):
        try:
            _parse_json_format(response_text, result)
            result.parsing_method = "json"
            if _validate_result(result):
                return result
        except json.JSONDecodeError:
            logger.debug("JSON parsing failed, trying markdown")

    # Strategy 2: Markdown format
    _parse_markdown_format(response_text, result)
    result.parsing_method = "markdown"

    # Strategy 3: Fallback — basic extraction
    if result.quality_score == 0 and not result.all_issues:
        logger.debug("Markdown parsing incomplete, using fallback")
        _parse_fallback(response_text, result)
        result.parsing_method = "fallback"

    _validate_and_fix(result)
    return result


def _parse_json_format(text: str, result: ParsedReview):
    """JSON format parse karo"""
    data = json.loads(text)

    if "quality_score" in data:
        result.quality_score = int(data["quality_score"])

    for severity_key, target_list in [
        ("critical_issues", result.critical_issues),
        ("major_issues", result.major_issues),
        ("minor_issues", result.minor_issues),
        ("issues", None),
    ]:
        issues = data.get(severity_key, [])
        if issues and target_list is not None:
            for issue in issues:
                if isinstance(issue, str):
                    target_list.append({
                        "message": issue,
                        "severity": severity_key.replace("_", " ").title(),
                    })
                elif isinstance(issue, dict):
                    target_list.append(issue)

    # Agar "issues" key mein saare hain toh sort karo
    if "issues" in data and not result.critical_issues:
        for issue in data["issues"]:
            severity = issue.get("severity", "LOW").upper()
            entry = {
                "message": issue.get("message", ""),
                "severity": severity,
                "type": issue.get("type", "General"),
                "line_number": issue.get("line_number"),
                "suggestion": issue.get("suggestion", issue.get("fix", "")),
            }
            if severity == "CRITICAL":
                result.critical_issues.append(entry)
            elif severity in ("HIGH", "MAJOR"):
                result.major_issues.append(entry)
            else:
                result.minor_issues.append(entry)

    result.recommendations = data.get("recommendations", data.get("suggestions", []))
    result.summary = data.get("summary", data.get("description", ""))


def _parse_markdown_format(text: str, result: ParsedReview):
    """Markdown format parse karo with multiple pattern support"""

    # --- Extract Quality Score ---
    score_patterns = [
        r"(?:quality\s+)?score\s*[:：]\s*(\d+)\s*/?\s*100",
        r"(\d+)\s*/?\s*100",
        r"score[:\s]*(\d+)",
        r"(\d+)\s*points?",
    ]
    for pattern in score_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            if 0 <= score <= 100:
                result.quality_score = score
                break

    # --- Extract Sections ---
    # Section headers vary — handle multiple formats
    sections = {
        "critical": result.critical_issues,
        "major": result.major_issues,
        "minor": result.minor_issues,
    }

    # Split by common section headers
    section_pattern = re.compile(
        r"(?:^|\n)#{1,4}\s*(.*?)\n(.*?)(?=\n#{1,4}\s|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    for match in section_pattern.finditer(text):
        header = match.group(1).strip().lower()
        content = match.group(2).strip()

        for section_name, target_list in sections.items():
            if section_name in header:
                items = _extract_issues_from_section(content)
                target_list.extend(items)

    # --- Extract Recommendations ---
    rec_patterns = [
        r"(?:recommendation|suggestion|quick[\s-]?wins)[\s\S]*?(?=\n#{1,4}\s|\Z)",
    ]
    for pattern in rec_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            result.recommendations = _extract_recommendations(match.group(0))

    # --- Extract Summary ---
    summary_match = re.search(
        r"(?:summary|overview)[:\s]*\n*(.*?)(?=\n#{1,4}\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if summary_match:
        result.summary = summary_match.group(1).strip()[:500]


def _extract_issues_from_section(section_text: str) -> list[dict]:
    """
    Section text se issues extract karo.
    Handles:
    - Bullet points (- , • , *)
    - Numbered lists (1. 2. 3.)
    - Checkboxes (- [ ] )
    """
    issues = []

    # Split by lines
    lines = section_text.split("\n")
    current_issue = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for issue start
        issue_match = re.match(
            r"^[\s]*[-•*]\s*(.*?)(?:\s*[-–—]\s*|\s*:?\s*Line\s*(\d+))?",
            line,
            re.IGNORECASE,
        )
        numbered_match = re.match(
            r"^\s*\d+[.)]\s*(.*)", line
        )

        if issue_match or numbered_match:
            # Save previous issue
            if current_issue:
                issues.append(_finalize_issue(current_issue))

            text = (issue_match or numbered_match).group(1)

            # Extract line number if present
            line_num = None
            line_num_match = re.search(r"line\s*:?\s*(\d+)", text, re.IGNORECASE)
            if line_num_match:
                line_num = int(line_num_match.group(1))
                text = text[: line_num_match.start()].strip()

            # Check for severity inline
            severity = "MAJOR"
            severity_match = re.search(
                r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", text, re.IGNORECASE
            )
            if severity_match:
                severity = severity_match.group(1).upper()
                text = text.replace(severity_match.group(0), "").strip()
                # Clean up separators
                text = re.sub(r"^[-–—:\s]+", "", text)

            current_issue = {
                "message": text,
                "severity": severity,
                "line_number": line_num,
            }

        elif current_issue:
            # Continuation of previous issue
            current_issue["message"] += " " + line.strip()

    # Last issue
    if current_issue:
        issues.append(_finalize_issue(current_issue))

    # Also try to find code blocks and use them as suggestions
    return issues


def _finalize_issue(issue: dict) -> dict:
    """Issue ko finalize karo — clean up aur defaults"""
    issue["message"] = issue["message"].strip().rstrip(".,;:")
    issue["message"] = issue["message"][:200]  # Truncate long messages

    # Try to extract suggestion from message
    suggestion_match = re.search(
        r"(?:fix|suggestion|use|try)[:\s]+(.*)", issue["message"], re.IGNORECASE
    )
    if suggestion_match:
        issue["suggestion"] = suggestion_match.group(1).strip()
        # Remove suggestion from main message
        issue["message"] = issue["message"][
            : suggestion_match.start()
        ].strip()

    issue.setdefault("severity", "MAJOR")
    issue.setdefault("type", "General")
    return issue


def _extract_recommendations(text: str) -> list[str]:
    """Recommendations extract karo from a section"""
    recs = []

    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Bullet or numbered
        match = re.match(r"^[\s]*[-•*\d+.)\s]+(.*)", line)
        if match:
            rec = match.group(1).strip()
            if len(rec) > 10:  # Meaningful recommendation
                recs.append(rec)

    return recs[:10]  # Max 10 recommendations


def _parse_fallback(text: str, result: ParsedReview):
    """
    Fallback parser — jab kuch kaam na kare.
    Basic heuristics use karta hai.
    """
    lines = text.split("\n")

    # Try to find score anywhere
    for line in lines:
        score_match = re.search(r"(\d{1,3})\s*(?:/100|points|score)", line, re.IGNORECASE)
        if score_match:
            score = int(score_match.group(1))
            if 0 <= score <= 100:
                result.quality_score = score
                break

    # Collect all meaningful lines as issues
    for line in lines:
        line = line.strip()
        if len(line) > 30 and not line.startswith("#") and not line.startswith("```"):
            severity = "MAJOR"
            if any(word in line.lower() for word in ["critical", "danger", "vulnerability"]):
                severity = "CRITICAL"
            elif any(word in line.lower() for word in ["minor", "style", "nit"]):
                severity = "MINOR"

            result.minor_issues.append({
                "message": line[:200],
                "severity": severity,
            })

    # First line as summary
    if lines:
        result.summary = lines[0].strip()[:300]


def _validate_result(result: ParsedReview) -> bool:
    """Check karo ke parsed result valid hai ya nahi"""
    has_score = 0 <= result.quality_score <= 100
    has_issues = bool(result.critical_issues or result.major_issues or result.minor_issues)
    has_recs = bool(result.recommendations)

    # At least score ya issues hona chahiye
    return has_score or has_issues


def _validate_and_fix(result: ParsedReview):
    """Result validate karo aur missing fields ko default do"""
    if not (0 <= result.quality_score <= 100):
        result.quality_score = 50  # Default middle score

    # Sort issues by severity
    result.critical_issues.sort(key=lambda x: x.get("line_number", 9999) or 9999)
    result.major_issues.sort(key=lambda x: x.get("line_number", 9999) or 9999)
    result.minor_issues.sort(key=lambda x: x.get("line_number", 9999) or 9999)

    # Limit counts
    result.critical_issues = result.critical_issues[:20]
    result.major_issues = result.major_issues[:30]
    result.minor_issues = result.minor_issues[:30]

    if not result.summary:
        result.summary = (
            f"Review complete. Score: {result.quality_score}/100. "
            f"Found {len(result.all_issues)} issues."
        )
```

---

## 🧪 Testing Strategy

### Unit Tests — `tests/test_llm_client.py`
```python
# Tests to write:
# 1. LLMClient initialization (both providers)
# 2. Message conversion (Gemini + OpenAI formats)
# 3. Token estimation
# 4. Cost estimation
# 5. Cache hit/miss
# 6. Retry logic
# 7. Response parsing (success + error cases)
```

### Unit Tests — `tests/test_response_parser.py`
```python
# Tests to write:
# 1. Parse JSON format
# 2. Parse Markdown format
# 3. Parse empty response
# 4. Parse malformed response (fallback)
# 5. Score extraction (various formats)
# 6. Issue extraction with line numbers
# 7. Recommendation extraction
# 8. Validation edge cases
```

---

## ⚡ Cost Optimization Strategy

| Technique | Savings | Implementation |
|-----------|---------|----------------|
| **Response Caching** | 30-50% | Same prompts ke liye cache hit |
| **Token Optimization** | 20-30% | Short prompts, relevant context only |
| **Model Selection** | 40-60% | Complex tasks → Gemini Pro, simple → Flash |
| **Batch Processing** | 15-25% | Multiple files ek saath analyze karo |
| **Streaming** | UX improvement | Pehle results dikhao, baaki aate rahein |

### Cost Estimation Table

| Model | Input/1K tokens | Output/1K tokens | 100 reviews cost |
|-------|----------------|-----------------|------------------|
| Gemini 2.0 Flash | $0.0001 | $0.0004 | ~$0.50 |
| Gemini 2.0 Flash Lite | $0.000075 | $0.0003 | ~$0.35 |
| Gemini 1.5 Pro | $0.0035 | $0.0105 | ~$12.00 |
| GPT-4o Mini | $0.0015 | $0.006 | ~$6.00 |
| GPT-4o | $0.005 | $0.015 | ~$18.00 |

**Recommendation:** Default `gemini-2.0-flash` use karo — free tier mein kaafi hai.

---

## 🔗 Integration Points

```
Person 3 (You) ←→ Person 1 (Agent Architect)
    • LLMClient → Agent core ko provide karo
    • Tool schemas → Agent ko batado ke kaunse tools hain
    • Response parser → Agent parsed results use karega

Person 3 (You) ←→ Person 2 (Tool Engineer)
    • Tool schemas → Tool engineer ke tools ke hisaab se schemas banao
    • Tool results → LLM ko tool results feed karo

Person 3 (You) ←→ Person 4 (Backend)
    • API response format → Backend ke response model se match karo
    • Error format → Consistent error format
```

---

## ✅ Success Criteria Checklist

- [ ] LLM Client dono providers (Gemini + OpenAI) ke saath kaam kare
- [ ] Tool calls properly extract ho
- [ ] Responses parse ho markdown aur JSON format mein
- [ ] Cache system kaam kare (same prompt → same response nahi)
- [ ] Retry logic kaam kare (API failure pe retry)
- [ ] Token usage track ho
- [ ] Cost estimate available ho
- [ ] All unit tests pass
- [ ] Integration with Agent (Person 1) working
- [ ] Integration with Tools (Person 2) working

---

## 📁 Final Directory Structure

```
llm/
├── __init__.py              ← 10 lines
├── llm_client.py            ← ~350 lines (improved)
├── llm_types.py             ← ~80 lines (new)
├── prompts.py               ← ~300 lines (improved)
├── tool_schemas.py          ← ~200 lines (improved)
└── response_parser.py       ← ~350 lines (improved)
```

---

## 🚀 Quick Start Commands

```bash
# Install dependencies
pip install google-generativeai openai python-dotenv

# Create .env file
echo "GEMINI_API_KEY=your_key_here" > .env
# ya
echo "OPENAI_API_KEY=your_key_here" > .env

# Test LLM client
python -c "
from llm import create_llm_client, get_tool_schemas
from llm.llm_types import Message, Role

client = create_llm_client('your-api-key', provider='gemini')
response = client.call_with_tools(
    messages=[Message(role=Role.USER, content='Hello')],
    tools=get_tool_schemas()
)
print(response)
"
```

---

## 🔥 Final Enhancements (Added)

### 1. Custom Base URL Support
Har provider custom base URL de sakta hai. Ollama, OpenRouter, local LLMs sab ke liye kaam karega.

```python
# Ollama local
client = create_ollama_client(model="llama3", base_url="http://localhost:11434/v1")

# Custom OpenAI-compatible API
client = create_custom_client(base_url="http://my-local-server:8080/v1")

# OpenRouter with custom headers
client = create_openrouter_client(api_key="sk-or-...", extra_headers={"HTTP-Referer": "https://myapp.com"})
```

### 2. Auto-Detect Provider
API key de do, khud detect ho jayega — Gemini, OpenAI, Groq, Anthropic, OpenRouter sab.

```python
client = create_llm_client(api_key="gsk_...")     # → Groq auto-detect
client = create_llm_client(api_key="sk-proj-...") # → OpenAI auto-detect
client = create_llm_client(api_key="sk-ant-...")  # → Anthropic auto-detect
```

### 3. 10 Provider Support

| Provider | Base URL | Key Prefix |
|----------|----------|------------|
| **Gemini** | Default | `AIzaSy...` |
| **OpenAI** | `https://api.openai.com/v1` | `sk-proj-...` or `sk-...` |
| **Groq** | `https://api.groq.com/openai/v1` | `gsk_...` |
| **Anthropic** | `https://api.anthropic.com/v1` | `sk-ant-...` |
| **OpenRouter** | `https://openrouter.ai/api/v1` | `sk-or-...` |
| **Together** | `https://api.together.xyz/v1` | `tgp-...` |
| **DeepSeek** | `https://api.deepseek.com/v1` | Hex key |
| **Ollama** | `http://localhost:11434/v1` | N/A |
| **Azure** | Custom | N/A |
| **Custom** | You define | Your choice |

### 4. 2026 Cost Tables Updated
Latest pricing for GPT-4.1 family, Gemini 2.5, Groq, Anthropic Claude 4, DeepSeek.

### 5. Streaming for All Providers
Ab sirf Gemini nahi, OpenAI-compatible (Groq, OpenRouter, etc.) aur Anthropic bhi stream kar sakte hain.

### 6. Model Listing
```python
models = await client.list_models()  # Available models fetch karo
```

### 7. Provider Info
```python
info = client.get_provider_info()
# {
#   "provider": "groq",
#   "model": "llama-3.3-70b-versatile",
#   "base_url": "https://api.groq.com/openai/v1",
#   "has_api_key": True,
#   "total_usage": {...},
#   "cache_size": 0,
#   "max_retries": 3,
#   "timeout": 30.0
# }
```

---

## 📁 Final Files (After All Improvements)

```
llm/
├── __init__.py              ← 40 lines  (public API exports)
├── llm_types.py             ← 120 lines (Provider enum, API key patterns, configs)
├── llm_client.py            ← 520 lines (10 providers, auto-detect, base URL, streaming)
├── tool_schemas.py          ← 200 lines (6 tools with validation)
├── prompts.py               ← 250 lines (system prompt, 5 few-shot examples)
└── response_parser.py       ← 280 lines (JSON + Markdown + Fallback parsing)
```

---

**Ready for implementation!** 🚀  
Start with Day 1 — `llm_types.py` aur `tool_schemas.py` banake.
