"""从原始条目生成候选需求的调度流程。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from app.core import metrics
from app.models import CandidateNeed, RawEntry, RawEntryStatus
from app.services import candidate_needs, filter_engine, raw_entries
from app.services.llm_client import LLMClient, StructuredNeed, get_default_llm_client

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
            "problem_statement": structured.problem_statement,
            "target_users": structured.target_users,
            "value_proposition": structured.value_proposition,
            "competition": structured.competition,
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


def _signal_boost(entry: RawEntry, weights: dict[str, float]) -> float:
    if not entry.tags:
        return 0.0
    unique_tags = set(entry.tags)
    return sum(weight for tag, weight in weights.items() if tag in unique_tags)


def _normalize_summary(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= _SUMMARY_MAX_LENGTH:
        return text
    return text[: _SUMMARY_MAX_LENGTH - 1].rstrip() + "…"
