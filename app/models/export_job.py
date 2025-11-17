"""导出任务相关数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ExportJobStatus(str, Enum):
    """导出任务的执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class ExportJob:
    """描述一次异步导出任务。"""

    id: int
    job_type: str
    format: str
    status: ExportJobStatus = ExportJobStatus.PENDING
    filters: dict[str, Any] = field(default_factory=dict)
    record_count: int | None = None
    file_path: str | None = None
    error_message: str | None = None
    attempt_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
