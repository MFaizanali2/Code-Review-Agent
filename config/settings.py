"""
Application settings - environment variables aur configuration yahan load hoti hai.
Centralized config - 12-factor app principle follow karta hai.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field


def _get_env(key: str, default: str = "") -> str:
    """Env var read karo with fallback - case insensitive Windows par bhi kaam karta hai."""
    return os.environ.get(key, os.environ.get(key.upper(), default))


def _get_int(key: str, default: int) -> int:
    """Env var ko int mein convert karo with safe fallback."""
    try:
        return int(_get_env(key, str(default)))
    except ValueError:
        return default


def _get_bool(key: str, default: bool) -> bool:
    """Env var ko bool mein convert karo. Truthy values: 1, true, yes, on."""
    val = _get_env(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


@dataclass
class Settings:
    """
    Application ki saari configuration yahan.
    Override karne ke liye .env file ya system env vars use karo.
    """

    # LLM Provider settings
    llm_provider: str = field(default_factory=lambda: _get_env("LLM_PROVIDER", "mock"))
    gemini_api_key: str = field(default_factory=lambda: _get_env("GEMINI_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: _get_env("OPENAI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: _get_env("GEMINI_MODEL", "gemini-2.0-flash"))
    openai_model: str = field(default_factory=lambda: _get_env("OPENAI_MODEL", "gpt-4o-mini"))

    # Agent settings
    max_react_iterations: int = field(default_factory=lambda: _get_int("MAX_REACT_ITERATIONS", 8))
    agent_timeout_seconds: int = field(default_factory=lambda: _get_int("AGENT_TIMEOUT_SECONDS", 120))
    max_context_tokens: int = field(default_factory=lambda: _get_int("MAX_CONTEXT_TOKENS", 32000))

    # API settings
    api_host: str = field(default_factory=lambda: _get_env("API_HOST", "127.0.0.1"))
    api_port: int = field(default_factory=lambda: _get_int("API_PORT", 8000))
    api_debug: bool = field(default_factory=lambda: _get_bool("API_DEBUG", False))

    # Logging
    log_level: str = field(default_factory=lambda: _get_env("LOG_LEVEL", "INFO"))

    def configure_logging(self) -> None:
        """Application-wide logging configure karo - once at startup."""
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def validate(self) -> list[str]:
        """
        Required settings check karo. Returns list of missing/wrong keys.
        Production mein deployment se pehle yeh run karna chahiye.
        """
        errors: list[str] = []
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            errors.append("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        if self.llm_provider == "openai" and not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if self.llm_provider not in ("gemini", "openai", "mock"):
            errors.append(f"Unknown LLM_PROVIDER: {self.llm_provider}")
        return errors


_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Singleton settings instance - lazy load.
    Multiple imports se same instance milega.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
