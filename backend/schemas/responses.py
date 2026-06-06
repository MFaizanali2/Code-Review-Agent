"""Standardized API response schemas."""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class SuccessResponse(BaseModel):
    message: str
    data: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
