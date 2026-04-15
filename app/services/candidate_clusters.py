"""候选需求聚类与重复信号聚合。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.db.storage import db
from app.models import CandidateNeed, CandidateNeedStatus, RssSource
import app.services.candidate_needs as candidate_needs

_LATIN_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_CJK_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")


@dataclass(slots=True)
class CandidateNeedCluster:
    """聚合后的候选需求信号簇。"""

    cluster_id: str
    representative_need_id: int
    representative_summary: str
    representative_problem_statement: str | None
    signal_count: int
    source_count: int
    cross_source: bool
    source_names: list[str]
    source_types: list[str]
    need_ids: list[int]
    statuses: list[CandidateNeedStatus]
    avg_confidence: float | None
    avg_rule_score: float | None
    complaint_signal_count: int
    alternative_request_count: int
    reddit_comment_count: int
    priority_score: float
    latest_seen_at: datetime


@dataclass(slots=True)
class _NeedContext:
    need: CandidateNeed
    source_name: str
    source_type: str
    tokens: set[str]
    normalized_summary: str
    tags: set[str]


def summarize_clusters(
    *,
    statuses: tuple[CandidateNeedStatus, ...] | None = None,
    search: str | None = None,
    synced: bool | None = None,
    limit: int = 100,
    min_cluster_size: int = 2,
    similarity_threshold: float = 0.25,
) -> list[CandidateNeedCluster]:
    """基于现有候选需求计算重复信号聚类。"""

    _, needs = candidate_needs.list_needs(
        statuses=statuses,
        search=search,
        synced=synced,
        limit=limit,
    )
    if not needs:
        return []

    raw_entry_cache: dict[int, Any] = {}
    source_cache: dict[int, RssSource | None] = {}
    contexts: list[_NeedContext] = []
    for need in needs:
        raw_entry = raw_entry_cache.get(need.raw_entry_id)
        if raw_entry is None:
            raw_entry = db.get_raw_entry(need.raw_entry_id)
            raw_entry_cache[need.raw_entry_id] = raw_entry
        source_name = "Unknown"
        source_type = "unknown"
        supporting_text = ""
        if raw_entry is not None:
            source = source_cache.get(raw_entry.source_id)
            if source is None:
                source = db.get_source(raw_entry.source_id)
                source_cache[raw_entry.source_id] = source
            if source is not None:
                source_name = source.name
                source_type = source.source_type.value
            supporting_text = " ".join(
                part for part in (raw_entry.title, raw_entry.summary, raw_entry.content) if part
            )
        contexts.append(
            _NeedContext(
                need=need,
                source_name=source_name,
                source_type=source_type,
                tokens=_tokenize(
                    " ".join(
                        part
                        for part in (
                            need.summary,
                            need.problem_statement,
                            need.target_users,
                            need.value_proposition,
                            supporting_text,
                        )
                        if part
                    )
                ),
                normalized_summary=_normalize_text(need.summary),
                tags=set(raw_entry.tags if raw_entry is not None and raw_entry.tags else ()),
            )
        )

    parents = list(range(len(contexts)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left in range(len(contexts)):
        for right in range(left + 1, len(contexts)):
            if _are_similar(contexts[left], contexts[right], threshold=similarity_threshold):
                union(left, right)

    grouped: dict[int, list[_NeedContext]] = {}
    for index, context in enumerate(contexts):
        grouped.setdefault(find(index), []).append(context)

    clusters: list[CandidateNeedCluster] = []
    for members in grouped.values():
        if len(members) < min_cluster_size:
            continue
        clusters.append(_build_cluster(members))

    clusters.sort(
        key=lambda item: (item.priority_score, item.signal_count, item.source_count, item.latest_seen_at),
        reverse=True,
    )
    return clusters


def _are_similar(left: _NeedContext, right: _NeedContext, *, threshold: float) -> bool:
    if left.normalized_summary and left.normalized_summary == right.normalized_summary:
        return True
    if not left.tokens or not right.tokens:
        return False
    overlap = len(left.tokens & right.tokens)
    if overlap == 0:
        return False
    union = len(left.tokens | right.tokens)
    jaccard_similarity = overlap / union
    coverage_similarity = overlap / min(len(left.tokens), len(right.tokens))
    return max(jaccard_similarity, coverage_similarity) >= threshold


def _build_cluster(members: list[_NeedContext]) -> CandidateNeedCluster:
    representative = max(
        members,
        key=lambda item: (
            item.need.rule_score or 0.0,
            item.need.confidence or 0.0,
            item.need.updated_at,
        ),
    )
    source_names = sorted({member.source_name for member in members})
    source_types = sorted({member.source_type for member in members})
    confidences = [member.need.confidence for member in members if member.need.confidence is not None]
    rule_scores = [member.need.rule_score for member in members if member.need.rule_score is not None]
    complaint_signal_count = sum("complaint_signal" in member.tags for member in members)
    alternative_request_count = sum("alternative_request" in member.tags for member in members)
    reddit_comment_count = sum("reddit_comment" in member.tags for member in members)
    latest_seen_at = max(member.need.updated_at for member in members)
    seed = "|".join(str(member.need.id) for member in sorted(members, key=lambda item: item.need.id))
    cluster_id = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    avg_rule_score = round(sum(rule_scores) / len(rule_scores), 4) if rule_scores else None

    return CandidateNeedCluster(
        cluster_id=cluster_id,
        representative_need_id=representative.need.id,
        representative_summary=representative.need.summary,
        representative_problem_statement=representative.need.problem_statement,
        signal_count=len(members),
        source_count=len(source_names),
        cross_source=len(source_names) > 1,
        source_names=source_names,
        source_types=source_types,
        need_ids=[member.need.id for member in sorted(members, key=lambda item: item.need.id)],
        statuses=sorted({member.need.status for member in members}, key=lambda item: item.value),
        avg_confidence=avg_confidence,
        avg_rule_score=avg_rule_score,
        complaint_signal_count=complaint_signal_count,
        alternative_request_count=alternative_request_count,
        reddit_comment_count=reddit_comment_count,
        priority_score=_calculate_priority_score(
            signal_count=len(members),
            source_count=len(source_names),
            avg_confidence=avg_confidence,
            avg_rule_score=avg_rule_score,
            complaint_signal_count=complaint_signal_count,
            alternative_request_count=alternative_request_count,
            reddit_comment_count=reddit_comment_count,
        ),
        latest_seen_at=latest_seen_at,
    )


def _tokenize(text: str) -> set[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return set()
    tokens = {_normalize_latin_token(token) for token in _LATIN_TOKEN_RE.findall(normalized)}
    tokens.update(_CJK_TOKEN_RE.findall(normalized))
    return tokens


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _normalize_latin_token(token: str) -> str:
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def _calculate_priority_score(
    *,
    signal_count: int,
    source_count: int,
    avg_confidence: float | None,
    avg_rule_score: float | None,
    complaint_signal_count: int,
    alternative_request_count: int,
    reddit_comment_count: int,
) -> float:
    signal_strength = min(signal_count / 5, 1.0)
    source_diversity = min(source_count / 3, 1.0)
    avg_conf = avg_confidence or 0.0
    avg_rule = avg_rule_score or 0.0
    signal_tag_strength = min(
        (
            complaint_signal_count * 0.5
            + alternative_request_count * 0.6
            + reddit_comment_count * 0.2
        )
        / max(signal_count, 1),
        1.0,
    )
    score = (
        signal_strength * 0.25
        + source_diversity * 0.2
        + avg_conf * 0.2
        + avg_rule * 0.2
        + signal_tag_strength * 0.15
    )
    return round(min(score, 1.0), 4)
