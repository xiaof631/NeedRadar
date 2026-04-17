"""外包项目线索相关的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceLeadEventRead(BaseModel):
    event_type: str
    created_at: datetime
    status_from: str | None = None
    status_to: str | None = None
    note: str | None = None

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
    engagement: str | None = None
    timeline: str | None = None
    normalized_timeline: str | None = None
    location: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    link: str | None = None
    lead_kind: str
    lead_tier: str
    tier_reason: str
    lead_status: str
    notes: str | None = None
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


class MarketplaceLeadList(BaseModel):
    total: int
    tier_breakdown: dict[str, int] = Field(default_factory=dict)
    kind_breakdown: dict[str, int] = Field(default_factory=dict)
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    source_breakdown: list[MarketplaceLeadSourceMetricRead] = Field(default_factory=list)
    items: list[MarketplaceLeadRead]


class MarketplaceLeadStatusUpdate(BaseModel):
    status: str


class MarketplaceLeadNotesUpdate(BaseModel):
    notes: str | None = None
