"""原始条目相关的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.models import RawEntryStatus
from pydantic import BaseModel, ConfigDict, Field


class RawEntryStatusEnum(str, Enum):
    """导出给 API 的状态枚举，避免直接暴露 dataclass 枚举实现。"""

    PENDING = RawEntryStatus.PENDING.value
    FILTERED = RawEntryStatus.FILTERED.value
    PROMOTED = RawEntryStatus.PROMOTED.value
    IGNORED = RawEntryStatus.IGNORED.value


class RawEntryRead(BaseModel):
    """原始条目输出模型。"""

    id: int
    source_id: int
    guid: str
    content_hash: str | None = None
    title: str
    summary: str | None = None
    content: str | None = None
    link: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: RawEntryStatusEnum
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RawEntryList(BaseModel):
    """原始条目分页列表响应。"""

    total: int
    items: list[RawEntryRead]


class RawEntryRuleMatch(BaseModel):
    """描述条目与筛选规则匹配结果。"""

    rule_id: int
    rule_name: str
    score: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)
    matched_patterns: list[str] = Field(default_factory=list)


class RawEntryStatusUpdate(BaseModel):
    """单条状态更新请求模型。"""

    status: RawEntryStatusEnum


class RawEntryBulkStatusUpdate(BaseModel):
    """批量状态更新请求模型。"""

    ids: list[int] = Field(..., min_length=1, description="待更新的条目 ID 列表")
    status: RawEntryStatusEnum
