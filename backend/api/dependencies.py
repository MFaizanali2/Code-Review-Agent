"""Dependency injection for API routes."""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Generator

from sqlalchemy.orm import Session

from agent.agent import CodeReviewAgent
from agent.llm.client import LLMClient, MockLLMClient
from config.settings import get_settings

from backend.database import SessionLocal

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """Get database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_agent_instance: CodeReviewAgent | None = None


def _create_llm_client() -> LLMClient:
    """Create LLM client based on settings."""
    settings = get_settings()
    provider = settings.llm_provider

    if provider == "mock":
        logger.info("Using MockLLMClient for development")
        return MockLLMClient(default_response="Code review analysis completed.")

    if provider == "gemini":
        try:
            from agent.llm.gemini_client import GeminiClient

            return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
        except ImportError:
            logger.warning("Gemini client not available, falling back to mock")
            return MockLLMClient()

    if provider == "openai":
        try:
            from agent.llm.openai_client import OpenAIClient

            return OpenAIClient(api_key=settings.openai_api_key, model=settings.openai_model)
        except ImportError:
            logger.warning("OpenAI client not available, falling back to mock")
            return MockLLMClient()

    logger.warning("Unknown provider %s, using mock", provider)
    return MockLLMClient()


async def get_agent() -> AsyncGenerator[CodeReviewAgent, None]:
    """Dependency that provides a configured CodeReviewAgent instance."""
    global _agent_instance

    if _agent_instance is None:
        llm = _create_llm_client()
        _agent_instance = CodeReviewAgent(llm=llm)
        logger.info("CodeReviewAgent instance created with provider=%s", llm.provider)

    yield _agent_instance
