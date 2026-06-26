"""Email follow-up API."""

from __future__ import annotations

from datetime import datetime

from app.schemas.email_followups import (
    EmailFollowUpList,
    EmailFollowUpStatusUpdate,
    EmailFollowUpSummaryRead,
    EmailFollowUpTaskRead,
)
from app.services import email_followups
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/email-followups", tags=["Email Followups"])


@router.get("/", response_model=EmailFollowUpList, summary="List email follow-up tasks")
async def list_email_followups(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=30, ge=1, le=100, description="Number of records to return"),
    source: email_followups.EmailFollowUpSource = Query(
        default=email_followups.EmailFollowUpSource.ALL,
        description="Task source: all, marketplace, customer_radar",
    ),
    status: email_followups.EmailFollowUpStatus | None = Query(
        default=None,
        description="Filter by email follow-up status",
    ),
    min_score: int = Query(default=70, ge=0, le=100, description="Minimum queue score"),
    include_review_first: bool = Query(
        default=True,
        description="Include customer radar items that need manual review first",
    ),
) -> EmailFollowUpList:
    result = email_followups.query_followups(
        skip=skip,
        limit=limit,
        source=source,
        status=status,
        min_score=min_score,
        include_review_first=include_review_first,
    )
    return EmailFollowUpList(
        total=result.total,
        summary=EmailFollowUpSummaryRead.model_validate(result.summary),
        items=[EmailFollowUpTaskRead.model_validate(item) for item in result.items],
    )


@router.get(
    "/{raw_entry_id}",
    response_model=EmailFollowUpTaskRead,
    summary="Get one email follow-up task",
)
async def get_email_followup(raw_entry_id: int) -> EmailFollowUpTaskRead:
    try:
        task = email_followups.get_followup_task(raw_entry_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="email follow-up task not found") from exc
    return EmailFollowUpTaskRead.model_validate(task)


@router.put(
    "/{raw_entry_id}/status",
    response_model=EmailFollowUpTaskRead,
    summary="Update email follow-up status",
)
async def update_email_followup_status(
    raw_entry_id: int,
    payload: EmailFollowUpStatusUpdate,
) -> EmailFollowUpTaskRead:
    try:
        status = email_followups.EmailFollowUpStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsupported email follow-up status") from exc

    next_follow_up_at = None
    if payload.next_follow_up_at:
        try:
            next_follow_up_at = datetime.fromisoformat(payload.next_follow_up_at)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid next follow-up timestamp") from exc

    try:
        task = email_followups.update_followup_status(
            raw_entry_id,
            status=status,
            note=payload.note,
            recipient=payload.recipient,
            gmail_thread_id=payload.gmail_thread_id,
            next_follow_up_at=next_follow_up_at,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="email follow-up task not found") from exc
    return EmailFollowUpTaskRead.model_validate(task)
