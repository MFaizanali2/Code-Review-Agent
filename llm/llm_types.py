import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Provider(Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    TOGETHER = "together"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    AZURE = "azure"
    CUSTOM = "custom"


PROVIDER_CONFIGS = {
    Provider.GEMINI: {
        "default_model": "gemini-2.0-flash",
        "package": "google-generativeai",
        "base_url": None,
    },
    Provider.OPENAI: {
        "default_model": "gpt-4o-mini",
        "package": "openai",
        "base_url": "https://api.openai.com/v1",
    },
    Provider.GROQ: {
        "default_model": "llama-3.3-70b-versatile",
        "package": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
    },
    Provider.ANTHROPIC: {
        "default_model": "claude-sonnet-4-20250514",
        "package": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
    },
    Provider.OPENROUTER: {
        "default_model": "openai/gpt-4o-mini",
        "package": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
    },
    Provider.TOGETHER: {
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "package": "openai",
        "base_url": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
    },
    Provider.DEEPSEEK: {
        "default_model": "deepseek-chat",
        "package": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
    },
    Provider.OLLAMA: {
        "default_model": "llama3",
        "package": "openai",
        "base_url": "http://localhost:11434/v1",
        "env_key": None,
    },
    Provider.CUSTOM: {
        "default_model": "custom-model",
        "package": "openai",
        "base_url": None,
        "env_key": "CUSTOM_API_KEY",
    },
}


API_KEY_PATTERNS = [
    (re.compile(r"^AIzaSy[A-Za-z0-9_-]{10,}$"), Provider.GEMINI),
    (re.compile(r"^sk-proj-[A-Za-z0-9_-]{20,}$"), Provider.OPENAI),
    (re.compile(r"^sk-[A-Za-z0-9]{20,}$"), Provider.OPENAI),
    (re.compile(r"^gsk_[A-Za-z0-9]{20,}$"), Provider.GROQ),
    (re.compile(r"^sk-ant-[a-z0-9]{20,}$"), Provider.ANTHROPIC),
    (re.compile(r"^sk-or-v1-[a-z0-9_-]{20,}$"), Provider.OPENROUTER),
    (re.compile(r"^sk-or-[a-z0-9_-]{10,}$"), Provider.OPENROUTER),
    (re.compile(r"^tgp-[a-z0-9_-]{20,}$"), Provider.TOGETHER),
    (re.compile(r"^[a-f0-9]{32,}$"), Provider.DEEPSEEK),
]

def auto_detect_provider(api_key: str) -> Optional[Provider]:
    for pattern, provider in API_KEY_PATTERNS:
        if pattern.match(api_key):
            return provider
    return None


def get_provider_for_model(model_name: str) -> Optional[Provider]:
    model_lower = model_name.lower()
    if "gemini" in model_lower:
        return Provider.GEMINI
    if model_lower.startswith("gpt") or model_lower.startswith("o3") or model_lower.startswith("o4"):
        return Provider.OPENAI
    if "claude" in model_lower:
        return Provider.ANTHROPIC
    if "llama" in model_lower or "mixtral" in model_lower or "gemma" in model_lower:
        return Provider.GROQ
    if "deepseek" in model_lower:
        return Provider.DEEPSEEK
    return None


@dataclass
class Message:
    role: Role
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class ContentBlock:
    type: str
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
    model: str = "gemini-2.0-flash"
    temperature: float = 0.3
    top_p: float = 0.9
    top_k: int = 40
    max_output_tokens: int = 4096
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    provider: str = "gemini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_headers: Optional[dict] = None


@dataclass
class LLMResponse:
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
