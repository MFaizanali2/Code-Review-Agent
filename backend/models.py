"""Pydantic models for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    github_url: Optional[str] = Field(None, description="GitHub repository URL")
    code_content: Optional[str] = Field(None, description="Code to review directly")
    analysis_type: str = Field("full", description="Type: full, security, performance")

    model_config = {
        "json_schema_extra": {
            "example": {
                "github_url": "https://github.com/user/repo",
                "analysis_type": "full",
            }
        }
    }


class Issue(BaseModel):
    type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    message: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None


class ReviewResponse(BaseModel):
    status: str
    review_id: str
    quality_score: float
    total_issues: int
    critical_issues: int
    security_issues: int
    performance_issues: int
    issues: List[Issue]
    report: str
    timestamp: datetime


class ReviewHistoryItem(BaseModel):
    review_id: str
    code_source: str
    quality_score: float
    total_issues: int
    timestamp: datetime
