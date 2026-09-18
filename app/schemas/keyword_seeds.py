"""关键词种子相关的序列化模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KeywordSeedRead(BaseModel):
    """关键词种子输出模型。"""

    id: int
    phrase: str
    pattern_kind: str
    occurrence_count: int
    status: str
    search_volume: int | None = None
    keyword_difficulty: int | None = None
    cpc: float | None = None
    competition: str | None = None
    validated_at: datetime | None = None
    validation_error: str | None = None
    opportunity_score: int
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KeywordSeedList(BaseModel):
    """关键词种子分页列表响应。"""

    total: int
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    items: list[KeywordSeedRead]


class KeywordSeedStatusUpdate(BaseModel):
    """更新关键词种子状态。"""

    status: str = Field(..., description="目标状态：shortlisted/dismissed/new")


class KeywordExtractionResult(BaseModel):
    """手动触发抽取的结果。"""

    scanned: int
    created: int
    merged: int


class KeywordValidationResult(BaseModel):
    """批量/单个验证的结果。"""

    skipped: int = 0
    validated: int = 0
    no_volume: int = 0
    errors: int = 0
    reason: str | None = None
