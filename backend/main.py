"""FastAPI application entry point for the Code Review Agent backend."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings

settings = get_settings()
settings.configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - startup and shutdown events."""
    logger.info("Starting Code Review Agent API...")
    from backend.database import init_db

    init_db()
    logger.info("Database initialized")

    errors = settings.validate()
    if errors:
        logger.warning("Configuration issues: %s", errors)
    else:
        logger.info(
            "Server running on %s:%d with provider=%s",
            settings.api_host,
            settings.api_port,
            settings.llm_provider,
        )

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="Code Review Agent API",
    description="AI-powered code review using ReACT loop architecture",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.api.routes import router  # noqa: E402

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Service info endpoint."""
    return {
        "name": "Code Review Agent API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Server is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
    )
