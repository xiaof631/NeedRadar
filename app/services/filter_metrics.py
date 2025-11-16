"""筛选流程指标统计。"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.storage import db
from app.models import RawEntryStatus, RssSource


@dataclass(slots=True)
class SourceFilterStats:
    """单个 RSS 源的筛选表现。"""

    source_id: int
    source_name: str
    total_entries: int
    pending_entries: int
    filtered_entries: int
    promoted_entries: int
    ignored_entries: int
    promotion_rate: float


@dataclass(slots=True)
class FilterPerformance:
    """筛选流程的整体指标。"""

    total_entries: int
    pending_entries: int
    processed_entries: int
    filtered_entries: int
    promoted_entries: int
    ignored_entries: int
    promotion_rate: float
    average_rule_score: float | None
    source_breakdown: list[SourceFilterStats]


def get_filter_performance() -> FilterPerformance:
    """聚合筛选表现指标，便于前端与监控消费。"""

    total_entries = db.count_raw_entries()
    pending_entries = db.count_raw_entries(status=RawEntryStatus.PENDING)
    filtered_entries = db.count_raw_entries(status=RawEntryStatus.FILTERED)
    promoted_entries = db.count_raw_entries(status=RawEntryStatus.PROMOTED)
    ignored_entries = db.count_raw_entries(status=RawEntryStatus.IGNORED)
    processed_entries = max(total_entries - pending_entries, 0)
    promotion_rate = _calculate_rate(promoted_entries, processed_entries)
    average_rule_score = _calculate_average_rule_score()
    breakdown = [_summarize_source(source) for source in db.list_sources()]

    return FilterPerformance(
        total_entries=total_entries,
        pending_entries=pending_entries,
        processed_entries=processed_entries,
        filtered_entries=filtered_entries,
        promoted_entries=promoted_entries,
        ignored_entries=ignored_entries,
        promotion_rate=promotion_rate,
        average_rule_score=average_rule_score,
        source_breakdown=breakdown,
    )


def _summarize_source(source: RssSource) -> SourceFilterStats:
    total_entries = db.count_raw_entries(source_id=source.id)
    pending_entries = db.count_raw_entries(
        source_id=source.id, status=RawEntryStatus.PENDING
    )
    filtered_entries = db.count_raw_entries(
        source_id=source.id, status=RawEntryStatus.FILTERED
    )
    promoted_entries = db.count_raw_entries(
        source_id=source.id, status=RawEntryStatus.PROMOTED
    )
    ignored_entries = db.count_raw_entries(
        source_id=source.id, status=RawEntryStatus.IGNORED
    )
    processed_entries = max(total_entries - pending_entries, 0)
    promotion_rate = _calculate_rate(promoted_entries, processed_entries)

    return SourceFilterStats(
        source_id=source.id,
        source_name=source.name,
        total_entries=total_entries,
        pending_entries=pending_entries,
        filtered_entries=filtered_entries,
        promoted_entries=promoted_entries,
        ignored_entries=ignored_entries,
        promotion_rate=promotion_rate,
    )


def _calculate_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _calculate_average_rule_score() -> float | None:
    needs = db.list_candidate_needs()
    scores = [need.rule_score for need in needs if need.rule_score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 4)
