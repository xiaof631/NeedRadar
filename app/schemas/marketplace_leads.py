"""外包项目线索相关的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    lead_tier: str
    tier_reason: str
    lead_status: str
    duplicate_count: int = 1
    duplicate_sources: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarketplaceLeadList(BaseModel):
    total: int
    tier_breakdown: dict[str, int] = Field(default_factory=dict)
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    items: list[MarketplaceLeadRead]


class MarketplaceLeadStatusUpdate(BaseModel):
    status: str
