"""超过时效窗口的未处理线索归档。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.storage import db

STALE_ARCHIVE_REASON = "stale_over_7_days"


@dataclass(frozen=True, slots=True)
class StaleLeadArchiveResult:
    """一次陈旧线索归档的统计结果。"""

    cutoff: datetime
    archived_at: datetime
    raw_entries_archived: int
    candidate_needs_archived: int


def archive_stale_leads(
    *,
    stale_after_days: int = 7,
    now: datetime | None = None,
) -> StaleLeadArchiveResult:
    """归档超过时效且仍未处理的线索；重复执行不会再次修改已归档记录。"""

    if stale_after_days < 1:
        raise ValueError("stale_after_days must be at least 1")
    archived_at = _ensure_utc(now or datetime.now(UTC))
    cutoff = archived_at - timedelta(days=stale_after_days)
    raw_count, candidate_count = db.archive_stale_leads(
        cutoff=cutoff,
        archived_at=archived_at,
        reason=STALE_ARCHIVE_REASON,
    )
    return StaleLeadArchiveResult(
        cutoff=cutoff,
        archived_at=archived_at,
        raw_entries_archived=raw_count,
        candidate_needs_archived=candidate_count,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
