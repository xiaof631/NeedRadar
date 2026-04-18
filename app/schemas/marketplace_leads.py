"""外包项目线索相关的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceLeadEventRead(BaseModel):
    event_type: str
    created_at: datetime
    status_from: str | None = None
    status_to: str | None = None
    outcome_from: str | None = None
    outcome_to: str | None = None
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MarketplaceLeadReminderRead(BaseModel):
    lead_id: int
    title: str
    source_name: str
    lead_status: str
    priority_score: int
    reminder_type: str
    severity: str
    message: str
    last_action_at: datetime
    stale_days: int

    model_config = ConfigDict(from_attributes=True)


class MarketplaceSourceRecommendationRead(BaseModel):
    source_id: int
    source_name: str
    action: str
    severity: str
    reason: str

    model_config = ConfigDict(from_attributes=True)


class MarketplaceLeadRead(BaseModel):
    id: int
    source_id: int
    source_name: str
    platform: str
    title: str
    summary: str | None = None
    description: str | None = None
    category: str | None = None
    budget: str | None = None
    normalized_budget: str | None = None
    budget_band: str | None = None
    engagement: str | None = None
    timeline: str | None = None
    normalized_timeline: str | None = None
    delivery_scope: str | None = None
    tech_stack_normalized: list[str] = Field(default_factory=list)
    location: str | None = None
    region: str | None = None
    timezone_fit: bool | None = None
    published_at: datetime | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    link: str | None = None
    lead_kind: str
    lead_tier: str
    tier_reason: str
    lead_status: str
    lead_outcome: str | None = None
    outcome_reason_tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    next_follow_up_at: datetime | None = None
    follow_up_reason: str | None = None
    is_follow_up_overdue: bool = False
    priority_score: int
    priority_reason: str
    duplicate_count: int = 1
    duplicate_sources: list[str] = Field(default_factory=list)
    last_action_at: datetime
    lead_events: list[MarketplaceLeadEventRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarketplaceLeadSourceMetricRead(BaseModel):
    source_id: int
    source_name: str
    total: int
    high_purity: int
    expanded: int
    reviewable: int
    full_time_job: int
    watching: int
    contacted: int

    model_config = ConfigDict(from_attributes=True)


class MarketplaceLeadConversionMetricRead(BaseModel):
    key: str
    label: str
    total: int
    resolved: int
    won: int
    lost: int
    no_response: int
    not_fit: int
    contacted: int
    resolution_rate: float
    win_rate: float

    model_config = ConfigDict(from_attributes=True)


class MarketplaceLeadList(BaseModel):
    total: int
    tier_breakdown: dict[str, int] = Field(default_factory=dict)
    kind_breakdown: dict[str, int] = Field(default_factory=dict)
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    outcome_breakdown: dict[str, int] = Field(default_factory=dict)
    outcome_reason_breakdown: dict[str, int] = Field(default_factory=dict)
    todo_breakdown: dict[str, int] = Field(default_factory=dict)
    source_breakdown: list[MarketplaceLeadSourceMetricRead] = Field(default_factory=list)
    source_conversion_breakdown: list[MarketplaceLeadConversionMetricRead] = Field(
        default_factory=list
    )
    segment_conversion_breakdown: list[MarketplaceLeadConversionMetricRead] = Field(
        default_factory=list
    )
    source_recommendations: list[MarketplaceSourceRecommendationRead] = Field(default_factory=list)
    todo_queue: list[MarketplaceLeadReminderRead] = Field(default_factory=list)
    items: list[MarketplaceLeadRead]


class MarketplaceLeadStatusUpdate(BaseModel):
    status: str


class MarketplaceLeadOutcomeUpdate(BaseModel):
    outcome: str | None = None
    reason_tags: list[str] = Field(default_factory=list)


class MarketplaceLeadBulkOutcomeUpdate(BaseModel):
    ids: list[int] = Field(min_length=1)
    outcome: str | None = None
    reason_tags: list[str] = Field(default_factory=list)


class MarketplaceLeadNotesUpdate(BaseModel):
    notes: str | None = None


class MarketplaceLeadFollowUpUpdate(BaseModel):
    next_follow_up_at: str | None = None
    follow_up_reason: str | None = None
