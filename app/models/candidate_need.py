"""候选需求相关的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class CandidateNeedStatus(str, Enum):
    """候选需求的状态。"""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_DISCOVERY = "in_discovery"
    COMPLETED = "completed"


@dataclass(slots=True)
class CandidateNeed:
    """候选需求记录。"""

    id: int
    raw_entry_id: int
    summary: str
    problem_statement: str | None = None
    target_users: str | None = None
    value_proposition: str | None = None
    competition: str | None = None
    confidence: float | None = None
    rule_score: float | None = None
    status: CandidateNeedStatus = CandidateNeedStatus.PENDING_REVIEW
    notes: str | None = None
    synced_at: datetime | None = None
    sync_error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        """更新时间戳。"""

        self.updated_at = datetime.now(UTC)


@dataclass(slots=True)
class CandidateNeedStatusLog:
    """记录候选需求状态的流转历史。"""

    id: int
    need_id: int
    from_status: CandidateNeedStatus | None
    to_status: CandidateNeedStatus
    note: str | None = None
    changed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
