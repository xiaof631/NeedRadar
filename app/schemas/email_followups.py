"""Email follow-up API models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmailDraftRead(BaseModel):
    recipient: str | None = None
    subject: str
    body: str
    source_url: str | None = None
    gmail_query_hint: str | None = None
    codex_handoff: str

    model_config = ConfigDict(from_attributes=True)


class EmailFollowUpEventRead(BaseModel):
    event_type: str
    created_at: datetime
    status_from: str | None = None
    status_to: str | None = None
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EmailFollowUpTaskRead(BaseModel):
    id: str
    raw_entry_id: int
    lead_id: int | None = None
    candidate_need_id: int | None = None
    opportunity_id: str | None = None
    source: str
    title: str
    source_name: str
    platform: str | None = None
    source_url: str | None = None
    priority_score: int
    reason: str
    recommended_action: str
    status: str
    recipient: str | None = None
    next_follow_up_at: datetime | None = None
    last_action_at: datetime
    risk_flags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    draft: EmailDraftRead
    events: list[EmailFollowUpEventRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailFollowUpSummaryRead(BaseModel):
    total: int
    draft_ready: int
    drafted: int
    sent: int
    waiting_reply: int
    no_response: int
    replied: int
    closed: int
    skipped: int
    needs_recipient: int
    overdue: int

    model_config = ConfigDict(from_attributes=True)


class EmailFollowUpList(BaseModel):
    total: int
    summary: EmailFollowUpSummaryRead
    items: list[EmailFollowUpTaskRead]


class EmailFollowUpStatusUpdate(BaseModel):
    status: str
    note: str | None = None
    recipient: str | None = None
    gmail_thread_id: str | None = None
    next_follow_up_at: str | None = None
