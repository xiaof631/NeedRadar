"""关键词种子领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class KeywordSeedStatus(StrEnum):
    """关键词种子在验证流程中的状态。"""

    NEW = "new"
    VALIDATED = "validated"
    NO_VOLUME = "no_volume"
    ERROR = "error"
    DISMISSED = "dismissed"
    SHORTLISTED = "shortlisted"


@dataclass(slots=True)
class KeywordSeed:
    """从候选需求文本中抽取的工具型长尾关键词及其证据。"""

    id: int
    phrase: str
    phrase_key: str
    pattern_kind: str
    occurrence_count: int = 1
    first_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: KeywordSeedStatus = KeywordSeedStatus.NEW
    search_volume: int | None = None
    keyword_difficulty: int | None = None
    cpc: float | None = None
    competition: str | None = None
    validated_at: datetime | None = None
    validation_error: str | None = None
    opportunity_score: int = 0
    evidence: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
