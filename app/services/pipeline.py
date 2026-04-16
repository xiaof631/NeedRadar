"""从原始条目生成候选需求的调度流程。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core import metrics
from app.models import CandidateNeed, RawEntry, RawEntryStatus, RssSource, SourceType
from app.services import candidate_needs, filter_engine, raw_entries, rss_sources
from app.services.llm_client import (
    LLMClient,
    StructuredNeed,
    _sanitize_need_field,
    get_default_llm_client,
)

_TAG_RULE_SCORE_BOOSTS: dict[str, float] = {
    "complaint_signal": 0.08,
    "alternative_request": 0.1,
    "reddit_comment": 0.02,
}
_TAG_CONFIDENCE_BOOSTS: dict[str, float] = {
    "complaint_signal": 0.06,
    "alternative_request": 0.08,
    "reddit_comment": 0.02,
}
_SUMMARY_MAX_LENGTH = 500
_BALANCED_SKIP_TITLE_PATTERNS = (
    re.compile(r"^show hn:", flags=re.IGNORECASE),
    re.compile(r"^ask hn:\s+who needs contributors\b", flags=re.IGNORECASE),
    re.compile(r"^ask hn:\s+what are you working on\b", flags=re.IGNORECASE),
)
_BALANCED_SKIP_TEXT_MARKERS = (
    "[推广]",
    "[酷工作]",
    "招聘",
    "代充",
)
_BALANCED_PRIORITY_MARKERS = (
    "can't",
    "cannot",
    "pain",
    "painful",
    "problem",
    "stuck",
    "down",
    "error",
    "fails",
    "failed",
    "manual",
    "offline",
    "frustrat",
    "求推荐",
    "推荐",
    "替代",
    "崩了",
    "记事本",
    "what standards",
    "which",
    "easiest",
    "what should i do",
)


class EntryNotQualifiedError(Exception):
    """条目未达到筛选要求。"""


class CandidateAlreadyExistsError(Exception):
    """同一条原始内容已存在候选需求。"""

    def __init__(self, need_id: int) -> None:
        super().__init__(f"candidate need #{need_id} already exists")
        self.need_id = need_id


@dataclass(slots=True)
class PromotionResult:
    """记录自动晋升的上下文数据。"""

    entry: RawEntry
    candidate_need: CandidateNeed
    rule_match: filter_engine.RuleMatchResult
    structured_need: StructuredNeed


@dataclass(slots=True)
class PromotionPreview:
    """描述一条待晋升的候选预览。"""

    entry: RawEntry
    source: RssSource
    rule_match: filter_engine.RuleMatchResult


def promote_entry(
    entry_id: int,
    *,
    min_score: float | None = None,
    llm_client: LLMClient | None = None,
) -> PromotionResult:
    """将符合规则的原始条目转化为候选需求。"""

    entry = raw_entries.get_entry(entry_id)
    rule_match = filter_engine.evaluate_entry(entry, min_score=min_score)
    if rule_match is None:
        raise EntryNotQualifiedError

    existing = candidate_needs.get_need_by_raw_entry(entry.id)
    if existing is not None:
        raise CandidateAlreadyExistsError(existing.id)

    client = llm_client or get_default_llm_client()
    structured = client.analyze_entry(entry)
    summary = _normalize_summary(structured.summary) if structured.summary else ""
    if not summary:
        for candidate in (entry.title, entry.summary, entry.content):
            if candidate:
                summary = _normalize_summary(candidate)
            if summary:
                break
    if not summary:
        summary = "自动生成的候选需求"

    rule_score_boost = _signal_boost(entry, _TAG_RULE_SCORE_BOOSTS)
    confidence_boost = _signal_boost(entry, _TAG_CONFIDENCE_BOOSTS)
    need = candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": summary,
            "problem_statement": _normalize_optional_field(structured.problem_statement, summary=summary),
            "target_users": _normalize_optional_field(structured.target_users, summary=summary, max_length=200),
            "value_proposition": _normalize_optional_field(structured.value_proposition, summary=summary),
            "competition": _normalize_optional_field(structured.competition, summary=summary, max_length=120),
            "confidence": min(structured.confidence + confidence_boost, 0.99),
            "rule_score": min(rule_match.score + rule_score_boost, 1.0),
        }
    )
    raw_entries.update_entry_status(entry.id, RawEntryStatus.PROMOTED)
    refreshed = raw_entries.get_entry(entry.id)
    metrics.record_promotion_result("promoted")
    return PromotionResult(
        entry=refreshed,
        candidate_need=need,
        rule_match=rule_match,
        structured_need=structured,
    )


def plan_balanced_promotions(
    *,
    source_types: tuple[SourceType, ...],
    per_source_type: int,
    min_score: float = 0.25,
) -> list[PromotionPreview]:
    """按来源类型挑选一批更适合晋升的待处理条目。"""

    if per_source_type < 1:
        return []

    allowed_source_types = set(source_types)
    previews_by_source_type: dict[SourceType, list[PromotionPreview]] = {
        source_type: [] for source_type in source_types
    }

    for entry in raw_entries.export_entries(status=RawEntryStatus.PENDING):
        source = rss_sources.get_source(entry.source_id)
        if source.source_type not in allowed_source_types:
            continue
        if candidate_needs.get_need_by_raw_entry(entry.id) is not None:
            continue
        rule_match = filter_engine.evaluate_entry(entry, min_score=min_score)
        if rule_match is None:
            continue
        if _should_skip_balanced_promotion(entry, source):
            continue
        previews_by_source_type[source.source_type].append(
            PromotionPreview(entry=entry, source=source, rule_match=rule_match)
        )

    selected: list[PromotionPreview] = []
    for source_type in source_types:
        candidates = previews_by_source_type.get(source_type, [])
        candidates.sort(key=_balanced_preview_sort_key)
        selected.extend(candidates[:per_source_type])
    return selected


def _signal_boost(entry: RawEntry, weights: dict[str, float]) -> float:
    if not entry.tags:
        return 0.0
    unique_tags = set(entry.tags)
    return sum(weight for tag, weight in weights.items() if tag in unique_tags)


def _balanced_preview_sort_key(preview: PromotionPreview) -> tuple[float, float, int]:
    published_at = preview.entry.published_at or datetime.min.replace(tzinfo=UTC)
    priority = preview.rule_match.score + _balanced_priority_bonus(preview.entry)
    return (-priority, -published_at.timestamp(), preview.entry.id)


def _balanced_priority_bonus(entry: RawEntry) -> float:
    text = _compose_entry_text(entry).lower()
    bonus = 0.0
    for marker in _BALANCED_PRIORITY_MARKERS:
        if marker in text:
            bonus += 0.02
    return min(bonus, 0.12)


def _should_skip_balanced_promotion(entry: RawEntry, source: RssSource) -> bool:
    title = entry.title.strip()
    lowered_title = title.lower()
    if any(pattern.search(title) for pattern in _BALANCED_SKIP_TITLE_PATTERNS):
        return True

    text = _compose_entry_text(entry).lower()
    if any(marker in text for marker in _BALANCED_SKIP_TEXT_MARKERS):
        return True

    if source.source_type == SourceType.HACKER_NEWS and lowered_title.startswith("ask hn:"):
        if not any(marker in text for marker in _BALANCED_PRIORITY_MARKERS):
            return True
    return False


def _compose_entry_text(entry: RawEntry) -> str:
    return "\n".join(
        value
        for value in (entry.title, entry.summary, entry.content, entry.author)
        if value
    )


def _normalize_summary(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= _SUMMARY_MAX_LENGTH:
        return text
    return text[: _SUMMARY_MAX_LENGTH - 1].rstrip() + "…"


def _normalize_optional_field(
    value: str | None,
    *,
    summary: str,
    max_length: int = 800,
) -> str | None:
    text = _sanitize_need_field(value, max_length=max_length)
    if not text:
        return None
    if text.lower() == summary.lower():
        return None
    lowered = text.lower()
    if lowered in {"github", "gitlab"}:
        return None
    if lowered.startswith(
        (
            "screenshots",
            "add screenshots",
            "steps to reproduce",
            "expected behavior",
            "additional context",
            "environment",
        )
    ):
        return None
    return text
