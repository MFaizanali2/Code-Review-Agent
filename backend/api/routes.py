"""API endpoints for code review."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agent.agent import CodeReviewAgent
from agent.core.react_loop import LoopResult
from backend.api.dependencies import get_agent, get_db
from backend.database import ReviewRecord
from backend.models import (
    Issue,
    ReviewHistoryItem,
    ReviewRequest,
    ReviewResponse,
)
from backend.utils.logger import logger

router = APIRouter()


def _validate_request(request: ReviewRequest) -> None:
    """Validate that request has at least one source (URL or code)."""
    if not request.github_url and not request.code_content:
        raise HTTPException(
            status_code=400,
            detail="Either github_url or code_content is required",
        )


def _build_context_and_input(request: ReviewRequest) -> tuple[dict, str]:
    """Build the context dict and input string from a review request."""
    context: dict = {"analysis_type": request.analysis_type}
    if request.github_url:
        context["github_url"] = request.github_url
        code_input = f"Review code from GitHub: {request.github_url}"
    else:
        code_input = f"Review the following code:\n\n{request.code_content}"
    return context, code_input


def _issues_from_review_record(record: ReviewRecord) -> list[dict]:
    """Parse issues from stored review record."""
    return _parse_issues_str(record.report)


def _parse_issues_str(report: str) -> list[dict]:
    """Parse JSON issues array from a report string."""
    issues: list[dict] = []
    try:
        json_match = re.search(r"\[.*?\]", report, re.DOTALL)
        if json_match:
            issues = json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return issues


def _build_review_record(
    review_id: str,
    request: ReviewRequest,
    issues: list[dict],
    result: LoopResult,
) -> ReviewRecord:
    """Create a ReviewRecord from review results."""
    return ReviewRecord(
        id=review_id,
        code_source="github" if request.github_url else "direct",
        github_url=request.github_url,
        quality_score=_calculate_quality_score(issues),
        total_issues=len(issues),
        critical_issues=len([i for i in issues if i.get("severity") == "CRITICAL"]),
        security_issues=len([i for i in issues if i.get("type") == "Security"]),
        performance_issues=len([i for i in issues if i.get("type") == "Performance"]),
        report=result.final_answer or "",
        timestamp=datetime.now(timezone.utc),
    )


async def _execute_review(
    request: ReviewRequest,
    agent: CodeReviewAgent,
    review_id: str,
    db: Session,
) -> ReviewRecord:
    """Run the review, parse issues, create and persist a ReviewRecord."""
    context, code_input = _build_context_and_input(request)
    result = await agent.review(code_input, context=context)
    issues = _parse_issues(result)
    record = _build_review_record(review_id, request, issues, result)
    db.add(record)
    db.commit()
    return record


@router.post(
    "/review",
    response_model=ReviewResponse,
    summary="Start a code review",
    description="Submit code for review via GitHub URL or direct code content.",
)
async def start_review(
    request: ReviewRequest,
    agent: CodeReviewAgent = Depends(get_agent),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    """Submit code for review and get results synchronously."""
    _validate_request(request)

    try:
        review_id = str(uuid.uuid4())
        record = await _execute_review(request, agent, review_id, db)

        return ReviewResponse(
            status="success",
            review_id=review_id,
            quality_score=record.quality_score,
            total_issues=record.total_issues,
            critical_issues=record.critical_issues,
            security_issues=record.security_issues,
            performance_issues=record.performance_issues,
            issues=[Issue(**i) for i in _issues_from_review_record(record)],
            report=record.report,
            timestamp=record.timestamp,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Review failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/review/{review_id}",
    summary="Get review results",
    description="Retrieve a previously completed review by its ID.",
)
async def get_review(
    review_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Retrieve a review result by ID."""
    review = db.query(ReviewRecord).filter(ReviewRecord.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return {
        "review_id": review.id,
        "quality_score": review.quality_score,
        "total_issues": review.total_issues,
        "report": review.report,
        "timestamp": review.timestamp,
    }


@router.get(
    "/reviews/history",
    response_model=List[ReviewHistoryItem],
    summary="Get review history",
    description="Get the most recent 20 code reviews.",
)
async def get_review_history(
    db: Session = Depends(get_db),
) -> list[ReviewHistoryItem]:
    """Get recent review history."""
    reviews = (
        db.query(ReviewRecord)
        .order_by(ReviewRecord.timestamp.desc())
        .limit(20)
        .all()
    )

    return [
        ReviewHistoryItem(
            review_id=r.id,
            code_source=r.code_source,
            quality_score=r.quality_score,
            total_issues=r.total_issues,
            timestamp=r.timestamp,
        )
        for r in reviews
    ]


@router.post(
    "/review/async",
    summary="Submit async review",
    description="Submit code for asynchronous background review.",
)
async def async_review(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    agent: CodeReviewAgent = Depends(get_agent),
) -> dict:
    """Submit a review to be processed in the background."""
    _validate_request(request)

    review_id = str(uuid.uuid4())

    background_tasks.add_task(
        _process_review_background,
        review_id=review_id,
        request=request,
        agent=agent,
    )

    return {
        "status": "processing",
        "review_id": review_id,
        "message": "Review is being processed in the background",
    }


def _parse_issues(result: LoopResult) -> list[dict]:
    """Parse issues from agent result."""
    issues: list[dict] = []
    try:
        text = result.final_answer or ""
        json_match = re.search(r"\[.*?\]", text, re.DOTALL)
        if json_match:
            issues = json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return issues


def _calculate_quality_score(issues: list[dict]) -> float:
    """Calculate quality score based on issues."""
    if not issues:
        return 10.0

    severity_weights = {"CRITICAL": 3.0, "HIGH": 2.0, "MEDIUM": 1.0, "LOW": 0.5}
    total_weight = sum(
        severity_weights.get(i.get("severity", "LOW"), 0.5) for i in issues
    )
    score = max(1.0, 10.0 - total_weight)
    return round(score, 1)


async def _process_review_background(
    review_id: str,
    request: ReviewRequest,
    agent: CodeReviewAgent,
) -> None:
    """Process a review in the background with its own DB session."""
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        await _execute_review(request, agent, review_id, db)
        logger.info("Background review %s completed successfully", review_id)
    except Exception as e:
        logger.exception("Background review %s failed: %s", review_id, e)
    finally:
        db.close()
