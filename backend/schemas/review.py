"""Review request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    github_url: Optional[str] = Field(None, description="GitHub repository URL")
    code_content: Optional[str] = Field(None, description="Code to review directly")
    analysis_type: str = Field("full", description="Type: full, security, performance")


class IssueSchema(BaseModel):
    type: str
    severity: str
    message: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None


class ReviewResult(BaseModel):
    status: str
    review_id: str
    quality_score: float
    total_issues: int
    critical_issues: int
    security_issues: int
    performance_issues: int
    issues: List[IssueSchema]
    report: str
    timestamp: datetime
