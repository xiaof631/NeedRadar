"""候选需求相关的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from app.models import CandidateNeedStatus, ExportJobStatus, SyncChannel
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
    rule_score: float | None = Field(default=None, ge=0.0, le=1.0)
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
    rule_score: float | None = Field(default=None, ge=0.0, le=1.0)


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
    rule_score: float | None = Field(default=None, ge=0.0, le=1.0)


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


class SyncChannelEnum(str, Enum):
    """下游同步渠道。"""

    WEBHOOK = SyncChannel.WEBHOOK.value
    MQ = SyncChannel.MQ.value
    EXPORT = SyncChannel.EXPORT.value


class CandidateNeedSyncLogRead(BaseModel):
    """候选需求同步审计日志。"""

    id: int
    need_id: int
    channel: SyncChannelEnum
    status: str
    attempt: int
    message: str | None = None
    metadata: dict[str, Any]
    delivered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateNeedSyncLogList(BaseModel):
    """同步日志列表响应。"""

    total: int
    items: list[CandidateNeedSyncLogRead]


class CandidateNeedExportJobCreate(BaseModel):
    """导出任务创建参数。"""

    format: str = Field(pattern="^(json|csv)$", default="json")
    statuses: list[CandidateNeedStatusEnum] | None = None
    search: str | None = None
    raw_entry_id: int | None = None
    synced: bool | None = None
    limit: int | None = Field(default=None, ge=1, le=5000)


class CandidateNeedExportJobRead(BaseModel):
    """导出任务详情。"""

    id: int
    job_type: str
    format: str
    status: ExportJobStatus
    filters: dict[str, Any]
    record_count: int | None = None
    file_path: str | None = None
    error_message: str | None = None
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CandidateNeedExportJobList(BaseModel):
    """导出任务列表。"""

    total: int
    items: list[CandidateNeedExportJobRead]


