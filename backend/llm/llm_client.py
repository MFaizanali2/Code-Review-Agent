import asyncio
import json
import logging
import os
import time
from typing import Optional

from .llm_types import (
    LLMConfig, LLMResponse, Message, Role,
    ToolCall, TokenUsage, Provider, PROVIDER_CONFIGS,
    auto_detect_provider, get_provider_for_model,
)

logger = logging.getLogger(__name__)

# ========================================================================
# COST TABLES — 2026 Pricing (per 1M tokens in USD)
# ========================================================================
COST_TABLES = {
    "gemini": {
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        "gemini-2.0-flash-lite": {"input": 0.000075, "output": 0.0003},
        "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.01},
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
    },
    "openai": {
        "gpt-4.1": {"input": 0.002, "output": 0.008},
        "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
        "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.0015, "output": 0.006},
        "o3-mini": {"input": 0.0011, "output": 0.0044},
        "o4-mini": {"input": 0.0011, "output": 0.0044},
    },
    "groq": {
        "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
        "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
        "llama-4-scout": {"input": 0.00011, "output": 0.00034},
        "mixtral-8x7b-32768": {"input": 0.00024, "output": 0.00024},
        "gemma2-9b-it": {"input": 0.00007, "output": 0.00007},
    },
    "anthropic": {
        "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
        "claude-haiku-3-5-20241022": {"input": 0.0008, "output": 0.004},
    },
    "openrouter": {},
    "together": {},
    "deepseek": {
        "deepseek-chat": {"input": 0.00014, "output": 0.00028},
        "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
    },
}


class LLMClient:
    """
    Universal LLM Client — 10+ providers, auto-detect, custom base URL.

    Supported Providers:
        gemini, openai, groq, anthropic, openrouter,
        together, deepseek, ollama, azure, custom

    Features:
    - Auto-detect provider from API key format
    - Custom base URL (Ollama, local LLMs, etc.)
    - Automatic retry with exponential backoff
    - Token usage tracking + cost estimation
    - Response caching
    - Streaming support
    """

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.provider = self.config.provider
        self.model = self.config.model
        self._client = None
        self._cache: dict[str, LLMResponse] = {}
        self._total_usage = TokenUsage()
        self._default_base_urls: dict[str, Optional[str]] = {}

        # Store default base URLs from PROVIDER_CONFIGS
        for p in Provider:
            cfg = PROVIDER_CONFIGS.get(p, {})
            self._default_base_urls[p.value] = cfg.get("base_url")

        # Auto-detect provider from API key if not explicitly set
        resolved_key = api_key or self.config.api_key or ""
        if not resolved_key:
            resolved_key = self._find_api_key_from_env()

        if self.provider == "gemini" and auto_detect_provider(resolved_key):
            detected = auto_detect_provider(resolved_key)
            if detected and detected.value != "gemini":
                logger.info(f"Auto-detected provider: {detected.value}")
                self.provider = detected.value
                self.config.provider = detected.value
                self._apply_provider_defaults()

        self.config.api_key = resolved_key
        self._apply_provider_defaults()
        self._init_client()

    def _find_api_key_from_env(self) -> str:
        provider_key_map = {
            Provider.GEMINI: "GEMINI_API_KEY",
            Provider.OPENAI: "OPENAI_API_KEY",
            Provider.GROQ: "GROQ_API_KEY",
            Provider.ANTHROPIC: "ANTHROPIC_API_KEY",
            Provider.OPENROUTER: "OPENROUTER_API_KEY",
            Provider.TOGETHER: "TOGETHER_API_KEY",
            Provider.DEEPSEEK: "DEEPSEEK_API_KEY",
        }
        for p, env_var in provider_key_map.items():
            val = os.getenv(env_var)
            if val:
                if not self.config.provider or self.config.provider == "gemini":
                    detected = auto_detect_provider(val)
                    if detected:
                        self.provider = detected.value
                        self.config.provider = detected.value
                return val

        for p, cfg in PROVIDER_CONFIGS.items():
            env_key = cfg.get("env_key")
            if env_key:
                val = os.getenv(env_key)
                if val:
                    return val
        return ""

    def _apply_provider_defaults(self):
        provider_enum = None
        for p in Provider:
            if p.value == self.provider:
                provider_enum = p
                break
        if provider_enum and provider_enum in PROVIDER_CONFIGS:
            cfg = PROVIDER_CONFIGS[provider_enum]
            if self.model == "gemini-2.0-flash" or not self.model or self.model == "unknown":
                self.model = cfg.get("default_model", self.model)
                self.config.model = self.model
            if not self.config.base_url:
                self.config.base_url = cfg.get("base_url")

    def _init_client(self):
        try:
            if self.provider == Provider.GEMINI.value:
                try:
                    from google import genai as genai_new
                    self._client = genai_new.Client(api_key=self.config.api_key)
                    self._gemini_model = self.model
                    self._gemini_use_new = True
                except ImportError:
                    import google.generativeai as genai
                    genai.configure(api_key=self.config.api_key)
                    self._client = genai.GenerativeModel(self.model, system_instruction=None)
                    self._gemini_use_new = False

            elif self.provider in (
                Provider.OPENAI.value, Provider.GROQ.value,
                Provider.OPENROUTER.value, Provider.TOGETHER.value,
                Provider.DEEPSEEK.value, Provider.OLLAMA.value,
                Provider.CUSTOM.value,
            ):
                from openai import AsyncOpenAI
                client_kwargs = {"api_key": self.config.api_key, "timeout": self.config.timeout}
                if self.config.base_url:
                    client_kwargs["base_url"] = self.config.base_url
                if self.config.extra_headers:
                    client_kwargs["default_headers"] = self.config.extra_headers
                self._client = AsyncOpenAI(**client_kwargs)

            elif self.provider == Provider.ANTHROPIC.value:
                from anthropic import AsyncAnthropic
                client_kwargs = {"api_key": self.config.api_key, "timeout": self.config.timeout}
                if self.config.base_url:
                    client_kwargs["base_url"] = self.config.base_url
                self._client = AsyncAnthropic(**client_kwargs)

            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            logger.info(
                f"LLM Client initialized | provider={self.provider} "
                f"model={self.model} base_url={self.config.base_url or 'default'}"
            )

        except ImportError as e:
            pkg = PROVIDER_CONFIGS.get(
                next((p for p in Provider if p.value == self.provider), None), {}
            ).get("package", "openai")
            raise ImportError(
                f"{self.provider} ke liye package install nahi hai. "
                f"Run: pip install {pkg}"
            ) from e

    def _get_cache_key(self, messages: list, tools: Optional[list] = None) -> str:
        import hashlib
        data = json.dumps(
            [[{"role": m.role.value, "content": m.content} for m in messages], tools],
            sort_keys=True, default=str,
        )
        return hashlib.md5(data.encode()).hexdigest()

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4 + 1

    def _estimate_cost(self, usage_obj: TokenUsage, model: str) -> float:
        model_cost = COST_TABLES.get(self.provider, {}).get(
            model, {"input": 0.001, "output": 0.002}
        )
        input_cost = (usage_obj.prompt_tokens / 1000) * model_cost["input"]
        output_cost = (usage_obj.completion_tokens / 1000) * model_cost["output"]
        return round(input_cost + output_cost, 6)

    # ---- Agent Interface (generate/chat/generate_with_tools) ----

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        """Agent interface — single-turn generation."""
        messages = []
        if system:
            messages.append(Message(role=Role.SYSTEM, content=system))
        messages.append(Message(role=Role.USER, content=prompt))
        return await self.call_with_tools(messages, tools=None)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        """Agent interface — multi-turn chat."""
        converted: list[Message] = []
        for msg in messages:
            role_map = {"user": Role.USER, "assistant": Role.ASSISTANT, "system": Role.SYSTEM}
            converted.append(Message(
                role=role_map.get(msg.get("role", "user"), Role.USER),
                content=msg.get("content", ""),
            ))
        return await self.call_with_tools(converted, tools=None)

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system: str | None = None,
        temperature: float = 0.3,
        **kwargs,
    ) -> LLMResponse:
        """Agent interface — generation with tool definitions."""
        messages = []
        if system:
            messages.append(Message(role=Role.SYSTEM, content=system))
        messages.append(Message(role=Role.USER, content=prompt))
        return await self.call_with_tools(messages, tools=tools)

    # ---- Message Conversion ----

    def _convert_messages_for_gemini(self, messages: list[Message]) -> list[dict]:
        contents = []
        system_text = None
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_text = msg.content
                continue
            role = "model" if msg.role == Role.ASSISTANT else "user"
            if msg.role == Role.TOOL:
                contents.append({
                    "role": "function",
                    "parts": [{"function_response": {"name": msg.name or "unknown", "response": {"result": msg.content}}}],
                })
                continue
            contents.append({"role": role, "parts": [{"text": msg.content}]})
        if system_text:
            self._client._system_instruction = system_text
        return contents

    def _convert_messages_for_openai(self, messages: list[Message]) -> list[dict]:
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

    def _convert_messages_for_anthropic(self, messages: list[Message]) -> tuple[list[dict], Optional[str]]:
        system_text = None
        converted = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_text = msg.content
                continue
            role_map = {Role.USER: "user", Role.ASSISTANT: "assistant", Role.TOOL: "user"}
            entry = {"role": role_map.get(msg.role, "user"), "content": msg.content}
            converted.append(entry)
        return converted, system_text

    # ---- Response Parsing ----

    def _parse_gemini_response(self, response) -> LLMResponse:
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
            usage = TokenUsage()
            if hasattr(response, "usage_metadata"):
                usage.prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
                usage.completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            return LLMResponse(success=True, text=text, tool_calls=tool_calls, usage=usage.__dict__)
        except Exception as e:
            logger.error(f"Gemini parse error: {e}")
            return LLMResponse(success=False, error=f"Parse error: {str(e)}")

    def _parse_openai_response(self, response) -> LLMResponse:
        try:
            message = response.choices[0].message
            text = message.content or ""
            tool_calls = []
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id, name=tc.function.name,
                        args=json.loads(tc.function.arguments),
                    ))
            usage = TokenUsage()
            if hasattr(response, "usage") and response.usage:
                usage.prompt_tokens = response.usage.prompt_tokens or 0
                usage.completion_tokens = response.usage.completion_tokens or 0
                usage.total_tokens = response.usage.total_tokens or 0
            return LLMResponse(success=True, text=text, tool_calls=tool_calls, usage=usage.__dict__)
        except Exception as e:
            logger.error(f"OpenAI parse error: {e}")
            return LLMResponse(success=False, error=f"Parse error: {str(e)}")

    def _parse_anthropic_response(self, response) -> LLMResponse:
        try:
            text = ""
            tool_calls = []
            if hasattr(response, "content"):
                for block in response.content:
                    if block.type == "text":
                        text = block.text
                    elif block.type == "tool_use":
                        tool_calls.append(ToolCall(
                            id=block.id, name=block.name,
                            args=block.input if isinstance(block.input, dict) else json.loads(block.input),
                        ))
            usage = TokenUsage()
            if hasattr(response, "usage"):
                usage.prompt_tokens = response.usage.input_tokens or 0
                usage.completion_tokens = response.usage.output_tokens or 0
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            return LLMResponse(success=True, text=text, tool_calls=tool_calls, usage=usage.__dict__)
        except Exception as e:
            logger.error(f"Anthropic parse error: {e}")
            return LLMResponse(success=False, error=f"Parse error: {str(e)}")

    # ---- Core API Methods ----

    async def call_with_tools(
        self,
        messages: list[Message],
        tools: Optional[list[dict]] = None,
        use_cache: bool = True,
    ) -> LLMResponse:
        start_time = time.time()

        if use_cache:
            cache_key = self._get_cache_key(messages, tools)
            if cache_key in self._cache:
                logger.debug("Cache hit")
                return self._cache[cache_key]

        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = await self._call_llm(messages, tools)

                if response.usage:
                    usage = TokenUsage(**response.usage)
                    usage.estimated_cost_usd = self._estimate_cost(usage, self.model)
                    response.usage = usage.__dict__
                    self._total_usage.prompt_tokens += usage.prompt_tokens
                    self._total_usage.completion_tokens += usage.completion_tokens
                    self._total_usage.total_tokens += usage.total_tokens
                    self._total_usage.estimated_cost_usd += usage.estimated_cost_usd

                response.latency_ms = round((time.time() - start_time) * 1000, 2)

                if use_cache and response.success:
                    self._cache[self._get_cache_key(messages, tools)] = response

                return response

            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait = self.config.retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"Attempt {attempt}/{self.config.max_retries} failed: {e}. Retry in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"All {self.config.max_retries} attempts failed")

        return LLMResponse(
            success=False,
            error=f"Max retries exceeded: {last_error}",
            latency_ms=round((time.time() - start_time) * 1000, 2),
        )

    async def _call_llm(self, messages: list[Message], tools: Optional[list[dict]]) -> LLMResponse:
        if self.provider == Provider.GEMINI.value:
            return await self._call_gemini(messages, tools)
        elif self.provider == Provider.ANTHROPIC.value:
            return await self._call_anthropic(messages, tools)
        else:
            return await self._call_openai_compat(messages, tools)

    async def _call_gemini(self, messages: list[Message], tools: Optional[list[dict]]) -> LLMResponse:
        if getattr(self, "_gemini_use_new", False):
            return await self._call_gemini_new_api(messages, tools)
        contents = self._convert_messages_for_gemini(messages)
        gc = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "max_output_tokens": self.config.max_output_tokens,
        }
        kwargs = {"contents": contents, "generation_config": gc}
        if tools:
            kwargs["tools"] = tools
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._client.generate_content(**kwargs)
        )
        return self._parse_gemini_response(response)

    async def _call_gemini_new_api(self, messages: list[Message], tools: Optional[list[dict]]) -> LLMResponse:
        from google.genai import types as genai_types
        gemini_messages = self._convert_messages_for_gemini(messages)
        system_prompt = None
        filtered = []
        for msg in gemini_messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                system_prompt = msg["parts"][0]["text"]
            else:
                filtered.append(msg)
        config_kwargs = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_output_tokens": self.config.max_output_tokens,
        }
        if tools:
            config_kwargs["tools"] = [
                genai_types.Tool(function_declarations=[
                    genai_types.FunctionDeclaration(
                        name=t["name"],
                        description=t.get("description", ""),
                        parameters=t.get("input_schema", {}),
                    ) for t in tools
                ])
            ]
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        gc = genai_types.GenerateContentConfig(**config_kwargs)
        response = self._client.models.generate_content(
            model=self._gemini_model,
            contents=filtered or gemini_messages,
            config=gc,
        )
        return self._parse_gemini_new_response(response)

    def _parse_gemini_new_response(self, response) -> LLMResponse:
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
                                args={k: v for k, v in part.function_call.args.items()},
                            ))
            usage = TokenUsage()
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage.prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
                usage.completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)
                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
            return LLMResponse(success=True, text=text, tool_calls=tool_calls, usage=usage.__dict__)
        except Exception as e:
            logger.error(f"Gemini new API parse error: {e}")
            return LLMResponse(success=False, error=f"Parse error: {str(e)}")

    async def _call_openai_compat(self, messages: list[Message], tools: Optional[list[dict]]) -> LLMResponse:
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
                {"type": "function", "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                }}
                for t in tools
            ]
            kwargs["tool_choice"] = "auto"
        response = await self._client.chat.completions.create(**kwargs)
        return self._parse_openai_response(response)

    async def _call_anthropic(self, messages: list[Message], tools: Optional[list[dict]]) -> LLMResponse:
        converted, system_text = self._convert_messages_for_anthropic(messages)
        kwargs = {
            "model": self.model,
            "messages": converted,
            "max_tokens": self.config.max_output_tokens,
            "temperature": self.config.temperature,
        }
        if system_text:
            kwargs["system"] = system_text
        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema", {}),
                }
                for t in tools
            ]
        response = await self._client.messages.create(**kwargs)
        return self._parse_anthropic_response(response)

    async def call_without_tools(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=system_prompt))
        messages.append(Message(role=Role.USER, content=prompt))
        return await self.call_with_tools(messages, tools=None)

    async def stream_response(self, messages: list[Message], system_prompt: Optional[str] = None):
        if self.provider == Provider.GEMINI.value:
            contents = self._convert_messages_for_gemini(messages)
            gc = {"temperature": self.config.temperature, "max_output_tokens": self.config.max_output_tokens}
            kwargs = {"contents": contents, "generation_config": gc}
            if system_prompt:
                kwargs["system_instruction"] = system_prompt
            response = self._client.generate_content(**kwargs, stream=True)
            for chunk in response:
                if hasattr(chunk, "text") and chunk.text:
                    yield chunk.text

        elif self.provider in (
            Provider.OPENAI.value, Provider.GROQ.value,
            Provider.OPENROUTER.value, Provider.TOGETHER.value,
            Provider.DEEPSEEK.value, Provider.OLLAMA.value,
            Provider.CUSTOM.value,
        ):
            openai_messages = self._convert_messages_for_openai(messages)
            if system_prompt and not any(m.role == Role.SYSTEM for m in messages):
                openai_messages.insert(0, {"role": "system", "content": system_prompt})
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_output_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        elif self.provider == Provider.ANTHROPIC.value:
            converted, system_text = self._convert_messages_for_anthropic(messages)
            kwargs = {
                "model": self.model,
                "messages": converted,
                "max_tokens": self.config.max_output_tokens,
                "stream": True,
            }
            if system_text or system_prompt:
                kwargs["system"] = system_text or system_prompt or ""
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

        else:
            raise NotImplementedError(f"Streaming not supported for {self.provider}")

    # ---- Provider Info & Utilities ----

    async def list_models(self) -> list[str]:
        try:
            if self.provider in (
                Provider.OPENAI.value, Provider.GROQ.value,
                Provider.OPENROUTER.value, Provider.TOGETHER.value,
                Provider.DEEPSEEK.value, Provider.CUSTOM.value,
            ):
                response = await self._client.models.list()
                return [m.id for m in response.data]
            elif self.provider == Provider.OLLAMA.value:
                import aiohttp
                base = (self.config.base_url or "http://localhost:11434/v1").rstrip("/v1") + "/api"
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{base}/tags") as resp:
                        data = await resp.json()
                        return [m["name"] for m in data.get("models", [])]
            elif self.provider == Provider.GEMINI.value:
                return ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"]
            elif self.provider == Provider.ANTHROPIC.value:
                return ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-haiku-3-5-20241022"]
            return []
        except Exception as e:
            logger.warning(f"Could not list models for {self.provider}: {e}")
            return []

    def get_total_usage(self) -> dict:
        return {
            "total_tokens": self._total_usage.total_tokens,
            "prompt_tokens": self._total_usage.prompt_tokens,
            "completion_tokens": self._total_usage.completion_tokens,
            "estimated_cost_usd": round(self._total_usage.estimated_cost_usd, 4),
        }

    def clear_cache(self):
        self._cache.clear()
        logger.info("LLM cache cleared")

    async def validate_api_key(self) -> bool:
        try:
            if self.provider == Provider.GEMINI.value:
                resp = await self.call_without_tools("Say 'ok' if you can read this.")
                return resp.success
            elif self.provider == Provider.ANTHROPIC.value:
                resp = await self.call_without_tools("Say 'ok'")
                return resp.success
            else:
                await self._client.models.list()
                return True
        except Exception:
            return False

    def get_provider_info(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.config.base_url or "default",
            "has_api_key": bool(self.config.api_key),
            "total_usage": self.get_total_usage(),
            "cache_size": len(self._cache),
            "max_retries": self.config.max_retries,
            "timeout": self.config.timeout,
        }


# ========================================================================
# FACTORY FUNCTIONS
# ========================================================================

def create_llm_client(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> LLMClient:
    """
    Smart factory — auto-detects provider if not specified.

    Examples:
        # Auto-detect from API key
        client = create_llm_client(api_key="sk-...")

        # Explicit provider
        client = create_llm_client(api_key="...", provider="groq")

        # Custom base URL (Ollama, local LLMs)
        client = create_llm_client(
            provider="custom",
            base_url="http://localhost:11434/v1",
            model="llama3",
            api_key="ignored"
        )

        # OpenRouter with extra headers
        client = create_llm_client(
            api_key="sk-or-...",
            extra_headers={"HTTP-Referer": "https://myapp.com"}
        )
    """
    if provider is None and api_key:
        detected = auto_detect_provider(api_key)
        if detected:
            provider = detected.value
            if model is None:
                cfg = PROVIDER_CONFIGS.get(detected, {})
                model = cfg.get("default_model")

    if provider is None and model:
        detected_prov = get_provider_for_model(model)
        if detected_prov:
            provider = detected_prov.value

    provider = provider or "gemini"
    model = model or PROVIDER_CONFIGS.get(
        next((p for p in Provider if p.value == provider), None), {}
    ).get("default_model", "gemini-2.0-flash")

    config = LLMConfig(provider=provider, model=model, base_url=base_url, **kwargs)
    return LLMClient(api_key=api_key, config=config)


def create_gemini_client(api_key: str, model: str = "gemini-2.0-flash") -> LLMClient:
    return create_llm_client(api_key=api_key, provider="gemini", model=model)


def create_openai_client(api_key: str, model: str = "gpt-4o-mini") -> LLMClient:
    return create_llm_client(api_key=api_key, provider="openai", model=model)


def create_groq_client(api_key: str, model: str = "llama-3.3-70b-versatile") -> LLMClient:
    return create_llm_client(api_key=api_key, provider="groq", model=model)


def create_anthropic_client(api_key: str, model: str = "claude-sonnet-4-20250514") -> LLMClient:
    return create_llm_client(api_key=api_key, provider="anthropic", model=model)


def create_openrouter_client(
    api_key: str,
    model: str = "openai/gpt-4o-mini",
    extra_headers: Optional[dict] = None,
) -> LLMClient:
    return create_llm_client(
        api_key=api_key, provider="openrouter", model=model,
        extra_headers=extra_headers or {"HTTP-Referer": "https://github.com/code-review-agent"},
    )


def create_deepseek_client(api_key: str, model: str = "deepseek-chat") -> LLMClient:
    return create_llm_client(api_key=api_key, provider="deepseek", model=model)


def create_ollama_client(model: str = "llama3", base_url: str = "http://localhost:11434/v1") -> LLMClient:
    return create_llm_client(
        api_key="ollama", provider="ollama", model=model, base_url=base_url,
    )


def create_custom_client(
    base_url: str,
    api_key: str = "",
    model: str = "custom-model",
    extra_headers: Optional[dict] = None,
) -> LLMClient:
    return create_llm_client(
        api_key=api_key, provider="custom", model=model,
        base_url=base_url, extra_headers=extra_headers,
    )


class MockLLMClient:
    """Testing ke liye mock — uses no real API keys.
    
    Implements the same interface as LLMClient but purely in-memory.
    """

    provider: str = "mock"

    def __init__(self, default_response: str = "Mock response"):
        self.default_response = default_response
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(success=True, text=self.default_response)

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        return await self.generate("")

    async def generate_with_tools(self, prompt: str, tools: list[dict], **kwargs) -> LLMResponse:
        return await self.generate(prompt)

    async def call_with_tools(self, messages=None, tools=None, use_cache=False) -> LLMResponse:
        return await self.generate("")

    async def call_without_tools(self, prompt: str = "", system_prompt: str = None) -> LLMResponse:
        return await self.generate(prompt or self.default_response)

    def estimate_cost(self, response: LLMResponse) -> float:
        return 0.0
