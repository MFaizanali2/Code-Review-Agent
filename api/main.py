"""
FastAPI main application entry point.
Person 4 is file ko extend karke routes add karega.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from config.settings import get_settings

settings = get_settings()
settings.configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Code Review Agent API",
    description="AI-powered code review using ReACT loop architecture",
    version="0.1.0",
    debug=settings.api_debug,
)


@app.get("/")
async def root() -> dict[str, str]:
    """Basic health endpoint - Person 4 isko enhance karega."""
    return {
        "service": "Code Review Agent",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event() -> None:
    """App start hone par validation aur setup."""
    errors = settings.validate()
    if errors:
        logger.warning("Configuration issues: %s", errors)
    else:
        logger.info("Application started successfully on %s:%d",
                    settings.api_host, settings.api_port)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
    )
