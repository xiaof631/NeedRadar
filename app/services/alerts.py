"""系统运行状态的告警检测逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.db.storage import db
from app.models import FetchStatus, RawEntryStatus, RssSource, SourceStatus


class AlertSeverity(str, Enum):
    """告警严重等级。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(slots=True)
class Alert:
    """系统告警。"""

    code: str
    message: str
    severity: AlertSeverity
    details: dict[str, Any] = field(default_factory=dict)


def generate_system_alerts(
    *,
    fetch_failure_ratio_threshold: float = 0.5,
    fetch_log_window: int = 50,
    pending_entries_threshold: int = 100,
    unsynced_needs_threshold: int = 50,
    stale_source_threshold_minutes: int = 180,
) -> list[Alert]:
    """根据当前数据生成系统告警。"""

    alerts: list[Alert] = []
    alerts.extend(
        alert
        for alert in (
            _check_active_sources(),
            _check_fetch_failures(
                ratio_threshold=fetch_failure_ratio_threshold,
                window=fetch_log_window,
            ),
            _check_stale_sources(threshold_minutes=stale_source_threshold_minutes),
            _check_pending_entries(threshold=pending_entries_threshold),
            _check_unsynced_needs(threshold=unsynced_needs_threshold),
        )
        if alert is not None
    )
    return alerts


def _check_active_sources() -> Alert | None:
    if db.count_sources(status=SourceStatus.ACTIVE) > 0:
        return None
    return Alert(
        code="no_active_sources",
        message="暂无启用的 RSS 源，抓取任务无法执行",
        severity=AlertSeverity.CRITICAL,
    )


def _check_fetch_failures(
    *,
    ratio_threshold: float,
    window: int,
) -> Alert | None:
    logs = db.list_fetch_logs(limit=window)
    if not logs:
        return None

    failures = sum(1 for log in logs if log.status == FetchStatus.FAILURE)
    if failures == 0:
        return None

    ratio = failures / len(logs)
    if ratio < ratio_threshold:
        return None

    severity = AlertSeverity.WARNING
    if ratio >= min(0.9, ratio_threshold + 0.25):
        severity = AlertSeverity.CRITICAL
    return Alert(
        code="fetch_failure_ratio_high",
        message="最近 RSS 抓取失败率过高",
        severity=severity,
        details={
            "window": len(logs),
            "failures": failures,
            "failure_ratio": round(ratio, 2),
        },
    )


def _check_stale_sources(*, threshold_minutes: int) -> Alert | None:
    if threshold_minutes <= 0:
        return None

    active_sources = [
        source for source in db.list_sources() if source.status == SourceStatus.ACTIVE
    ]
    if not active_sources:
        return None

    now = datetime.now(UTC)
    stale_sources: list[tuple[RssSource, float | None]] = []
    for source in active_sources:
        last_fetched = source.last_fetched_at
        if last_fetched is None:
            stale_sources.append((source, None))
            continue
        if last_fetched.tzinfo is None:
            last_fetched = last_fetched.replace(tzinfo=UTC)
        age_minutes = (now - last_fetched).total_seconds() / 60
        if age_minutes >= threshold_minutes:
            stale_sources.append((source, age_minutes))

    if not stale_sources:
        return None

    severity = AlertSeverity.WARNING
    if any(age is None or age >= threshold_minutes * 2 for _, age in stale_sources):
        severity = AlertSeverity.CRITICAL

    return Alert(
        code="rss_sources_stale",
        message="部分 RSS 源长时间未被抓取",
        severity=severity,
        details={
            "threshold_minutes": threshold_minutes,
            "stale_sources": [
                {
                    "source_id": source.id,
                    "name": source.name,
                    "minutes_since_fetch": None
                    if age is None
                    else round(age, 1),
                }
                for source, age in stale_sources
            ],
        },
    )


def _check_pending_entries(*, threshold: int) -> Alert | None:
    pending = db.count_raw_entries(status=RawEntryStatus.PENDING)
    if pending < threshold:
        return None

    severity = AlertSeverity.WARNING if pending < threshold * 2 else AlertSeverity.CRITICAL
    return Alert(
        code="pending_entries_backlog",
        message="待处理的原始内容数量过多",
        severity=severity,
        details={"pending_entries": pending, "threshold": threshold},
    )


def _check_unsynced_needs(*, threshold: int) -> Alert | None:
    unsynced = db.count_candidate_needs(synced=False)
    if unsynced < threshold:
        return None

    severity = AlertSeverity.WARNING if unsynced < threshold * 2 else AlertSeverity.CRITICAL
    return Alert(
        code="unsynced_candidate_needs",
        message="存在大量尚未同步到下游的候选需求",
        severity=severity,
        details={"unsynced": unsynced, "threshold": threshold},
    )
