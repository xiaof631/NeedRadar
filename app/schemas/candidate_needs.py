"""候选需求相关的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.models import CandidateNeedStatus
from pydantic import BaseModel, ConfigDict, Field


class CandidateNeedStatusEnum(str, Enum):
    """候选需求状态枚举。"""

    PENDING_REVIEW = CandidateNeedStatus.PENDING_REVIEW.value
    APPROVED = CandidateNeedStatus.APPROVED.value
    REJECTED = CandidateNeedStatus.REJECTED.value
    IN_DISCOVERY = CandidateNeedStatus.IN_DISCOVERY.value
    COMPLETED = CandidateNeedStatus.COMPLETED.value


class CandidateNeedRead(BaseModel):
    """候选需求输出模型。"""

    id: int
    raw_entry_id: int
    summary: str
    problem_statement: str | None = None
    target_users: str | None = None
    value_proposition: str | None = None
    competition: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: CandidateNeedStatusEnum
    notes: str | None = None
    synced_at: datetime | None = None
    sync_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateNeedList(BaseModel):
    """候选需求分页结果。"""

    total: int
    items: list[CandidateNeedRead]


class CandidateNeedCreate(BaseModel):
    """候选需求创建请求。"""

    raw_entry_id: int
    summary: str = Field(..., min_length=1)
    problem_statement: str | None = None
    target_users: str | None = None
    value_proposition: str | None = None
    competition: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: CandidateNeedStatusEnum = CandidateNeedStatusEnum.PENDING_REVIEW
    notes: str | None = None


class CandidateNeedUpdate(BaseModel):
    """候选需求更新请求。"""

    raw_entry_id: int | None = None
    summary: str | None = Field(default=None, min_length=1)
    problem_statement: str | None = None
    target_users: str | None = None
    value_proposition: str | None = None
    competition: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: CandidateNeedStatusEnum | None = None
    notes: str | None = None


class CandidateNeedStatusUpdate(BaseModel):
    """候选需求状态更新。"""

    status: CandidateNeedStatusEnum


class CandidateNeedStatusLogRead(BaseModel):
    """候选需求状态流转日志。"""

    id: int
    need_id: int
    from_status: CandidateNeedStatusEnum | None = None
    to_status: CandidateNeedStatusEnum
    note: str | None = None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


