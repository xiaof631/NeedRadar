"""筛选规则命中评估逻辑。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from app.models import FilterRule, RawEntry
from app.services import filter_rules


@dataclass(slots=True)
class RuleMatchResult:
    """描述某条规则的匹配情况。"""

    rule: FilterRule
    score: float
    matched_keywords: tuple[str, ...]
    matched_patterns: tuple[str, ...]


def evaluate_entry(
    entry: RawEntry,
    *,
    rules: Sequence[FilterRule] | None = None,
    min_score: float | None = None,
) -> RuleMatchResult | None:
    """对单个原始条目运行启用中的筛选规则并返回最佳命中。"""

    candidates = rules or _load_enabled_rules()
    if not candidates:
        return None

    text = _compose_entry_text(entry)
    best: RuleMatchResult | None = None

    for rule in candidates:
        result = _evaluate_text_with_rule(text, rule)
        if result is None:
            continue
        if result.score < rule.min_score:
            continue
        if min_score is not None and result.score < min_score:
            continue
        if best is None or result.score > best.score:
            best = result
    return best


def _load_enabled_rules() -> list[FilterRule]:
    _, items = filter_rules.list_rules(enabled=True)
    return items


def _compose_entry_text(entry: RawEntry) -> str:
    segments: list[str] = []
    for value in (entry.title, entry.summary, entry.content, entry.author):
        if value:
            segments.append(value)
    if entry.tags:
        segments.extend(entry.tags)
    return "\n".join(segments)


def _evaluate_text_with_rule(text: str, rule: FilterRule) -> RuleMatchResult | None:
    matched_keywords = _match_keywords(text, rule.keywords)
    matched_patterns = _match_patterns(text, rule.patterns)
    score = _calculate_score(
        len(rule.keywords),
        len(matched_keywords),
        len(rule.patterns),
        len(matched_patterns),
    )
    if score == 0.0:
        return None
    return RuleMatchResult(
        rule=rule,
        score=score,
        matched_keywords=matched_keywords,
        matched_patterns=matched_patterns,
    )


def _match_keywords(text: str, keywords: Sequence[str]) -> tuple[str, ...]:
    if not keywords:
        return tuple()
    lowered = text.lower()
    hits = []
    for keyword in keywords:
        if keyword.lower() in lowered:
            hits.append(keyword)
    return tuple(dict.fromkeys(hits))


def _match_patterns(text: str, patterns: Sequence[str]) -> tuple[str, ...]:
    if not patterns:
        return tuple()
    hits: list[str] = []
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                hits.append(pattern)
        except re.error:
            continue
    return tuple(dict.fromkeys(hits))


def _calculate_score(
    total_keywords: int,
    matched_keywords: int,
    total_patterns: int,
    matched_patterns: int,
) -> float:
    components: list[float] = []
    if total_keywords:
        components.append(matched_keywords / total_keywords)
    if total_patterns:
        components.append(matched_patterns / total_patterns)
    if not components:
        return 0.0
    return sum(components) / len(components)
