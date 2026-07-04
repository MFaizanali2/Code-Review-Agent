"""Custom exceptions and error handlers for the API."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ReviewError(Exception):
    """Base exception for review-related errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ReviewNotFoundError(ReviewError):
    """Review not found in database."""

    def __init__(self, review_id: str):
        super().__init__(f"Review not found: {review_id}", status_code=404)


class InvalidRequestError(ReviewError):
    """Invalid request parameters."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


async def review_error_handler(request: Request, exc: ReviewError) -> JSONResponse:
    """Handle ReviewError and return JSON response."""
    logger.error("ReviewError: %s (status=%d)", exc.message, exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register custom error handlers on the FastAPI app."""
    app.add_exception_handler(ReviewError, review_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
