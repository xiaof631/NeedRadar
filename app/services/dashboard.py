"""面向仪表盘的聚合指标。"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.storage import db
from app.models import CandidateNeedStatus, FetchStatus, RawEntryStatus, SourceStatus
"""仪表盘所需的聚合指标。"""


@dataclass(slots=True)
class SourcesSummary:
    """RSS 源数量统计。"""

    total: int
    active: int


@dataclass(slots=True)
class StatusBreakdown:
    """状态分布统计信息。"""

    total: int
    by_status: dict[str, int]


@dataclass(slots=True)
class FetchLogSummary:
    """抓取日志统计。"""

    total: int
    failures: int


@dataclass(slots=True)
class DashboardMetrics:
    """仪表盘展示所需的核心指标。"""

    sources: SourcesSummary
    raw_entries: StatusBreakdown
    candidate_needs: StatusBreakdown
    pending_sync_needs: int
    fetch_logs: FetchLogSummary


def _summarize_sources() -> SourcesSummary:
    return SourcesSummary(
        total=db.count_sources(),
        active=db.count_sources(status=SourceStatus.ACTIVE),
    )


def _count_raw_entries_by_status() -> StatusBreakdown:
    counts: dict[str, int] = {}
    total = 0
    for status in RawEntryStatus:
        value = db.count_raw_entries(status=status)
        counts[status.value] = value
        total += value
    return StatusBreakdown(total=total, by_status=counts)


def _count_candidate_needs_by_status() -> StatusBreakdown:
    counts: dict[str, int] = {}
    total = 0
    for status in CandidateNeedStatus:
        value = db.count_candidate_needs(statuses=(status,))
        counts[status.value] = value
        total += value
    return StatusBreakdown(total=total, by_status=counts)


def _summarize_fetch_logs() -> FetchLogSummary:
    logs = db.list_fetch_logs()
    total = len(logs)
    failures = sum(1 for log in logs if log.status == FetchStatus.FAILURE)
    return FetchLogSummary(total=total, failures=failures)


def get_dashboard_metrics() -> DashboardMetrics:
    """聚合核心指标，供仪表盘及监控调用。"""

    sources = _summarize_sources()
    raw_breakdown = _count_raw_entries_by_status()
    need_breakdown = _count_candidate_needs_by_status()
    pending_sync = db.count_candidate_needs(synced=False)
    fetch_logs = _summarize_fetch_logs()
    return DashboardMetrics(
        sources=sources,
        raw_entries=raw_breakdown,
        candidate_needs=need_breakdown,
        pending_sync_needs=pending_sync,
        fetch_logs=fetch_logs,
    )
