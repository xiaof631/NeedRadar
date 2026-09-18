"""关键词种子抽取与搜索量验证。"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core import metrics
from app.core.config import get_settings
from app.db.entities import CandidateNeedEntity, RawEntryEntity, RssSourceEntity
from app.db.session import SessionLocal
from app.db.storage import db
from app.models import KeywordSeed, KeywordSeedStatus
from app.services.keyword_provider import (
    KeywordMetrics,
    KeywordProviderError,
    KeywordRateLimitedError,
    resolve_keyword_provider,
)


class KeywordSeedNotFoundError(Exception):
    """关键词种子不存在。"""


@dataclass(slots=True)
class ExtractionResult:
    """一次种子抽取的统计结果。"""

    scanned: int = 0
    created: int = 0
    merged: int = 0


@dataclass(slots=True)
class ValidationResult:
    """一批关键词验证的统计结果。"""

    skipped: int = 0
    validated: int = 0
    no_volume: int = 0
    errors: int = 0
    reason: str | None = None


@dataclass(slots=True)
class KeywordSeedsResult:
    """关键词种子列表查询结果。"""

    total: int
    status_breakdown: dict[str, int] = field(default_factory=dict)
    items: list[KeywordSeed] = field(default_factory=list)


_EN_WORD = r"[a-z0-9][a-z0-9\-']*"
# 槽位内的分隔符不跨行，避免把标题和正文拼成一个短语。
_EN_SEPARATOR = r"[^\S\n]+"
_EN_PHRASE = rf"{_EN_WORD}(?:{_EN_SEPARATOR}{_EN_WORD}){{0,5}}"
_ZH_TOKEN = r"[\u4e00-\u9fffA-Za-z0-9]"

# 抽取模式：句式名称 -> (正则, 短语模板)。模板占位符对应正则捕获组。
_EXTRACTION_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "convert_to",
        re.compile(
            rf"\b(?:convert|turn|transform)\s+({_EN_PHRASE})\s+(?:in)?to\s+({_EN_PHRASE})",
            re.IGNORECASE,
        ),
        "convert {0} to {1}",
    ),
    (
        "to_converter",
        re.compile(
            rf"\b({_EN_PHRASE})\s+to\s+({_EN_PHRASE})\s+(?:converter|conversion|conversion tool)\b",
            re.IGNORECASE,
        ),
        "{0} to {1} converter",
    ),
    (
        "extract_from",
        re.compile(
            rf"\bextract(?:ing)?\s+({_EN_PHRASE})\s+from\s+({_EN_PHRASE})",
            re.IGNORECASE,
        ),
        "extract {0} from {1}",
    ),
    (
        "extractor",
        re.compile(rf"\b({_EN_PHRASE})\s+(?:extractor|extraction tool)\b", re.IGNORECASE),
        "{0} extractor",
    ),
    (
        "scrape_target",
        # X 至少两个词，避免 "scrape data/api/tool" 这类无检索价值的泛化短语。
        re.compile(
            rf"\b(?:scrape|scraping|crawl|crawling)\s+({_EN_WORD}(?:{_EN_SEPARATOR}{_EN_WORD}){{1,5}})",
            re.IGNORECASE,
        ),
        "scrape {0}",
    ),
    (
        "zh_convert_to",
        re.compile(rf"把?({_ZH_TOKEN}{{1,12}})转(?:换)?成({_ZH_TOKEN}{{1,12}})"),
        "{0}转成{1}",
    ),
    (
        "zh_extract_from",
        re.compile(rf"从({_ZH_TOKEN}{{1,12}}?)(?:之|中)?(?:提)?取({_ZH_TOKEN}{{1,12}})"),
        "从{0}提取{1}",
    ),
)

# 纯功能词组成的槽位没有检索意义（如 "convert it to excel" 的 "it"）。
_EN_FILLER_WORDS = frozenset(
    (
        "a", "an", "the", "my", "our", "your", "their", "his", "her", "its",
        "this", "that", "these", "those", "it", "them", "they", "me", "us",
        "you", "he", "she", "we", "i", "some", "any", "each", "every", "all",
        "one", "new", "other", "another", "there", "here", "then", "now",
        "just", "also", "very", "much", "many", "more", "most", "such", "what",
        "which", "who", "whom", "whose", "when", "where", "why", "how", "do",
        "does", "did", "done", "doing", "be", "been", "being", "am", "is",
        "are", "was", "were", "can", "could", "should", "would", "will",
        "shall", "may", "might", "must", "want", "need", "like", "into",
        "onto", "from", "with", "without", "for", "and", "or", "but", "not",
        "no", "yes", "please", "help", "using", "every", "month", "months",
        "week", "weeks", "day", "days", "year", "years", "weekly", "monthly",
        "daily", "regularly", "again", "automatically", "manually", "fast",
        "quickly", "easily", "today", "tomorrow", "currently", "soon",
        "sometimes", "always", "never", "back", "looking", "find", "finds",
        "know", "knows", "anyone", "someone", "anybody", "best", "good",
        "great", "free", "online", "cheap", "recommend", "recommends",
        "recommendation", "recommendations", "suggest", "suggests",
        "suggestion", "suggestions", "preferably", "preferred", "instead",
        "similar", "alternative",
    )
)
_ZH_FILLER_CHARS = frozenset("的我你他她它们把被和与或在对给让用要会能有是了着过吧呢吗这那个些")
# 中文槽位两端的常见引导/语气字，成串出现时视为噪声。
_ZH_EDGE_TRIM_CHARS = "有没有需想要工具能把个这那对我你他她它们和与或很太就还都只被的"

# 槽位内的介词/连词/关系代词视为短语边界，避免把从句源头吞进关键词。
_EN_BOUNDARY_WORDS = frozenset(
    (
        "to", "from", "with", "without", "into", "onto", "in", "on", "at",
        "by", "of", "per", "via", "using", "for", "and", "or", "but", "that",
        "which", "who", "whom", "when", "where", "while", "so", "if", "then",
        "also", "too",
    )
)

# 每个句式各槽位的截断策略：head 取触发词后的第一段，tail 取贴近后续关键词的最后一段。
_SLOT_STRATEGIES: dict[str, tuple[str, ...]] = {
    "convert_to": ("head", "head"),
    "to_converter": ("tail", "head"),
    "extract_from": ("head", "head"),
    "extractor": ("tail",),
    "scrape_target": ("head",),
}

# 裁剪后槽位最少要保留的实词数，避免退化为泛化短语。
_SLOT_MIN_CONTENT_WORDS: dict[str, int] = {
    "scrape_target": 2,
}

_MIN_PHRASE_LENGTH = 8
_MAX_PHRASE_LENGTH = 80
# 证据条目上限。出现次数按 distinct raw entry 累计，上限只用于防止极端膨胀；
# 达到上限后截断会牺牲幂等性，因此取一个宽松值。
_EVIDENCE_LIMIT = 50
_CONTENT_SCAN_LIMIT = 2000

_WHITESPACE_RE = re.compile(r"\s+")


def extract_phrases(text: str) -> list[tuple[str, str]]:
    """从文本中抽取 (短语, 句式) 列表，同一文本内按短语去重。"""

    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    if not text:
        return results
    for kind, pattern, template in _EXTRACTION_PATTERNS:
        for match in pattern.finditer(text):
            slots = [group.strip() for group in match.groups() if group]
            phrase = _build_phrase(kind, template, slots)
            if phrase is None:
                continue
            key = phrase_key(phrase)
            if key in seen:
                continue
            if not (_MIN_PHRASE_LENGTH <= len(phrase) <= _MAX_PHRASE_LENGTH):
                continue
            seen.add(key)
            results.append((phrase, kind))
    return results


def phrase_key(phrase: str) -> str:
    """短语的归一化去重键。"""

    return _WHITESPACE_RE.sub(" ", phrase.strip()).lower()


def extract_seeds() -> ExtractionResult:
    """扫描全部候选需求并抽取关键词种子，合并进已有种子。"""

    result = ExtractionResult()
    with SessionLocal() as session:
        rows = session.execute(
            select(CandidateNeedEntity, RawEntryEntity, RssSourceEntity)
            .join(RawEntryEntity, CandidateNeedEntity.raw_entry_id == RawEntryEntity.id)
            .join(RssSourceEntity, RawEntryEntity.source_id == RssSourceEntity.id)
        ).all()

    for need_entity, entry_entity, source_entity in rows:
        result.scanned += 1
        content = entry_entity.content or ""
        text = "\n".join(
            part
            for part in (
                entry_entity.title,
                need_entity.summary,
                need_entity.problem_statement,
                need_entity.value_proposition,
                entry_entity.summary,
                content[:_CONTENT_SCAN_LIMIT],
            )
            if part
        )
        evidence = {
            "raw_entry_id": entry_entity.id,
            "candidate_need_id": need_entity.id,
            "title": entry_entity.title,
            "link": entry_entity.link,
            "source_name": source_entity.name,
            "published_at": entry_entity.published_at.isoformat()
            if entry_entity.published_at
            else None,
        }
        for phrase, kind in extract_phrases(text):
            key = phrase_key(phrase)
            existing = db.get_keyword_seed_by_key(key)
            if existing is None:
                db.create_keyword_seed(
                    {
                        "phrase": phrase,
                        "phrase_key": key,
                        "pattern_kind": kind,
                        "occurrence_count": 1,
                        "opportunity_score": _evidence_score(1, [evidence]),
                        "evidence": [evidence],
                    }
                )
                result.created += 1
            elif _merge_evidence(existing, evidence):
                result.merged += 1

    metrics.record_keyword_seed_extraction("created", count=result.created)
    metrics.record_keyword_seed_extraction("merged", count=result.merged)
    return result


async def validate_pending(batch_size: int | None = None) -> ValidationResult:
    """批量验证待处理种子（new/error）的搜索量。"""

    provider = resolve_keyword_provider()
    if provider is None:
        metrics.record_keyword_validation("skipped")
        return ValidationResult(reason="keyword provider not configured")

    settings = get_settings()
    limit = batch_size or settings.keyword_validation_batch_size
    seeds = db.list_keyword_seeds(
        statuses=(KeywordSeedStatus.NEW, KeywordSeedStatus.ERROR),
        limit=limit,
    )
    if not seeds:
        return ValidationResult()

    result = ValidationResult()
    rate_limited = False
    try:
        metrics_map = await provider.fetch_metrics([seed.phrase for seed in seeds])
    except KeywordRateLimitedError as exc:
        # 限流：已完成部分正常写回，未处理的保持待验证状态供下次重试。
        metrics_map = exc.partial
        rate_limited = True
        result.reason = "rate limited by provider; remaining seeds kept pending"
    except KeywordProviderError as exc:
        for seed in seeds:
            _mark_validation_error(seed, str(exc))
        result.errors = len(seeds)
        metrics.record_keyword_validation("error", count=result.errors)
        return result

    for seed in seeds:
        if rate_limited and seed.phrase.lower() not in metrics_map:
            result.skipped += 1
            continue
        keyword_metrics = metrics_map.get(seed.phrase.lower())
        # 无数值的确认（suggest 存在性校验）也算 validated；零搜索量才算无需求。
        has_volume = keyword_metrics is not None and (
            keyword_metrics.search_volume is None or keyword_metrics.search_volume > 0
        )
        if has_volume:
            _apply_metrics(seed, keyword_metrics, status=KeywordSeedStatus.VALIDATED)
            result.validated += 1
            metrics.record_keyword_validation("validated")
        else:
            _apply_metrics(seed, keyword_metrics, status=KeywordSeedStatus.NO_VOLUME)
            result.no_volume += 1
            metrics.record_keyword_validation("no_volume")
    if result.skipped:
        metrics.record_keyword_validation("skipped", count=result.skipped)
    return result


async def validate_seed(seed_id: int) -> KeywordSeed:
    """验证单个种子的搜索量；未配置数据源时抛出 ValueError。"""

    seed = get_seed(seed_id)
    provider = resolve_keyword_provider()
    if provider is None:
        raise ValueError("keyword provider not configured")
    try:
        metrics_map = await provider.fetch_metrics([seed.phrase])
    except KeywordRateLimitedError:
        raise ValueError("keyword provider rate limited; retry later") from None
    except KeywordProviderError as exc:
        _mark_validation_error(seed, str(exc))
        metrics.record_keyword_validation("error")
        return db.get_keyword_seed(seed_id) or seed

    keyword_metrics = metrics_map.get(seed.phrase.lower())
    has_volume = keyword_metrics is not None and (
        keyword_metrics.search_volume is None or keyword_metrics.search_volume > 0
    )
    if has_volume:
        _apply_metrics(seed, keyword_metrics, status=KeywordSeedStatus.VALIDATED)
        metrics.record_keyword_validation("validated")
    else:
        _apply_metrics(seed, keyword_metrics, status=KeywordSeedStatus.NO_VOLUME)
        metrics.record_keyword_validation("no_volume")
    return db.get_keyword_seed(seed_id) or seed


def get_seed(seed_id: int) -> KeywordSeed:
    """按 ID 读取种子。"""

    seed = db.get_keyword_seed(seed_id)
    if seed is None:
        raise KeywordSeedNotFoundError(seed_id)
    return seed


def list_seeds(
    *,
    status: KeywordSeedStatus | None = None,
    search: str | None = None,
    min_volume: int | None = None,
    min_score: int | None = None,
    skip: int = 0,
    limit: int = 30,
) -> KeywordSeedsResult:
    """分页查询种子列表，附带全量状态分布。"""

    total = db.count_keyword_seeds(
        status=status,
        search=search,
        min_volume=min_volume,
        min_score=min_score,
    )
    items = db.list_keyword_seeds(
        status=status,
        search=search,
        min_volume=min_volume,
        min_score=min_score,
        skip=skip,
        limit=limit,
    )
    return KeywordSeedsResult(
        total=total,
        status_breakdown=db.keyword_seed_status_breakdown(),
        items=items,
    )


def update_seed_status(seed_id: int, status: KeywordSeedStatus) -> KeywordSeed:
    """更新种子状态（shortlist/dismiss 等）。"""

    get_seed(seed_id)

    def _apply(model: KeywordSeed) -> None:
        model.status = status

    return db.update_keyword_seed(seed_id, _apply)


def _build_phrase(kind: str, template: str, slots: Sequence[str]) -> str | None:
    expected = template.count("{0}") + template.count("{1}")
    if len(slots) < expected:
        return None
    if kind.startswith("zh_"):
        trimmed_zh = [slot.strip(_ZH_EDGE_TRIM_CHARS) for slot in slots[:expected]]
        if any(not _slot_has_content_zh(slot) for slot in trimmed_zh):
            return None
        phrase = template.format(*trimmed_zh).lower()
    else:
        strategies = _SLOT_STRATEGIES.get(kind, ("head",) * expected)
        trimmed = [
            _trim_filler_edges_en(slot, strategy=strategies[index])
            for index, slot in enumerate(slots[:expected])
        ]
        if any(not _slot_has_content_en(slot) for slot in trimmed):
            return None
        min_words = _SLOT_MIN_CONTENT_WORDS.get(kind, 1)
        if any(_content_word_count(slot) < min_words for slot in trimmed):
            return None
        phrase = template.format(*(slot.lower() for slot in trimmed)).lower()
    return _WHITESPACE_RE.sub(" ", phrase.strip())


def _content_word_count(slot: str) -> int:
    return sum(
        1 for word in slot.split() if word and word.lower() not in _EN_FILLER_WORDS
    )


def _slot_has_content_en(slot: str) -> bool:
    words = [word.strip("' -") for word in slot.split()]
    return any(word and word.lower() not in _EN_FILLER_WORDS for word in words)


def _trim_filler_edges_en(slot: str, *, strategy: str = "head") -> str:
    """按策略在介词/连词处截断槽位，再剔除两端的功能词。"""

    words = [word.strip("' -") for word in slot.split()]
    if strategy == "tail":
        for index in range(len(words) - 1, -1, -1):
            if words[index].lower() in _EN_BOUNDARY_WORDS:
                words = words[index + 1 :]
                break
    else:
        for index, word in enumerate(words):
            if word.lower() in _EN_BOUNDARY_WORDS:
                words = words[:index]
                break
    while words and words[0].lower() in _EN_FILLER_WORDS:
        words.pop(0)
    while words and words[-1].lower() in _EN_FILLER_WORDS:
        words.pop()
    return " ".join(word for word in words if word)


def _slot_has_content_zh(slot: str) -> bool:
    return any(char not in _ZH_FILLER_CHARS for char in slot)


def _merge_evidence(seed: KeywordSeed, evidence: dict[str, Any]) -> bool:
    """将新证据并入种子；同一 raw entry 重复出现时只刷新时间戳。"""

    already_seen = any(
        item.get("raw_entry_id") == evidence["raw_entry_id"] for item in seed.evidence
    )
    next_evidence = [*seed.evidence, evidence] if not already_seen else seed.evidence
    next_count = seed.occurrence_count if already_seen else seed.occurrence_count + 1

    def _apply(model: KeywordSeed) -> None:
        model.occurrence_count = next_count
        model.last_seen_at = datetime.now(UTC)
        model.evidence = next_evidence[:_EVIDENCE_LIMIT]
        model.opportunity_score = _compute_opportunity_score(model)

    db.update_keyword_seed(seed.id, _apply)
    return not already_seen


def _apply_metrics(
    seed: KeywordSeed,
    keyword_metrics: KeywordMetrics | None,
    *,
    status: KeywordSeedStatus,
) -> None:
    def _apply(model: KeywordSeed) -> None:
        if keyword_metrics is not None:
            model.search_volume = keyword_metrics.search_volume
            model.keyword_difficulty = keyword_metrics.keyword_difficulty
            model.cpc = keyword_metrics.cpc
            model.competition = keyword_metrics.competition
        else:
            model.search_volume = 0
            model.keyword_difficulty = None
            model.cpc = None
            model.competition = None
        model.status = status
        model.validated_at = datetime.now(UTC)
        model.validation_error = None
        model.opportunity_score = _compute_opportunity_score(model)

    db.update_keyword_seed(seed.id, _apply)


def _mark_validation_error(seed: KeywordSeed, message: str) -> None:
    def _apply(model: KeywordSeed) -> None:
        model.status = KeywordSeedStatus.ERROR
        model.validated_at = datetime.now(UTC)
        model.validation_error = message[:500]

    db.update_keyword_seed(seed.id, _apply)


def _compute_opportunity_score(seed: KeywordSeed) -> int:
    """证据分（0-50）+ 关键词分（0-50），无搜索量数据时只算证据分。"""

    total = _evidence_score(seed.occurrence_count, seed.evidence) + _keyword_score(seed)
    return max(0, min(100, int(round(total))))


def _evidence_score(occurrence_count: int, evidence: Sequence[dict[str, Any]]) -> int:
    count_part = 18 * math.log2(max(1, occurrence_count) + 1)
    distinct_sources = {
        str(item.get("source_name")) for item in evidence if item.get("source_name")
    }
    source_part = 8 * max(0, len(distinct_sources) - 1)
    return min(50, int(round(count_part + source_part)))


def _keyword_score(seed: KeywordSeed) -> int:
    if seed.search_volume is None:
        # 免费存在性校验确认过是真实搜索词，给基础分使其排在未验证种子之前。
        if seed.competition == "confirmed_by_suggest":
            return 10
        return 0
    volume = seed.search_volume
    if volume >= 10_000:
        volume_part = 40.0
    elif volume >= 1_000:
        volume_part = 32.0
    elif volume >= 100:
        volume_part = 24.0
    elif volume >= 10:
        volume_part = 16.0
    elif volume >= 1:
        volume_part = 8.0
    else:
        volume_part = 0.0
    difficulty_part = 0.0
    if seed.keyword_difficulty is not None:
        difficulty_part = max(0.0, (100 - seed.keyword_difficulty) / 100 * 10)
    return int(round(min(50.0, volume_part + difficulty_part)))
