"""外包项目线索查询与状态管理。"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlsplit

from app.db.storage import db
from app.models import RawEntry, SourceType
from app.services import raw_entries, rss_sources

_NON_WORD_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_USD_RANGE_RE = re.compile(r"^\$(?P<start>\d[\d,.]*)(?P<start_suffix>k)?\s*(?:to|-)\s*\$(?P<end>\d[\d,.]*)(?P<end_suffix>k)?(?P<unit>/hr)?$", re.IGNORECASE)
_USD_SINGLE_RE = re.compile(r"^\$(?P<value>\d[\d,.]*)(?P<suffix>k)?(?P<unit>/hr)?$", re.IGNORECASE)
_CNY_RANGE_RE = re.compile(r"^(?P<start>\d+)千\s*[~\-]\s*(?P<end>\d+)千$")
_CNY_UPPER_RE = re.compile(r"^(?P<value>\d+)千以下$")
_CNY_SINGLE_RE = re.compile(r"^￥(?P<value>\d[\d,]*)$")
_CN_DAY_RE = re.compile(r"(?P<days>\d+)\s*天")
_EN_DAY_RE = re.compile(r"(?P<days>\d+)\s*days?", re.IGNORECASE)
_HOURS_PER_WEEK_RE = re.compile(r"(?P<hours>\d+\s*hrs/wk)", re.IGNORECASE)


class MarketplaceLeadTier(StrEnum):
    HIGH_PURITY = "high_purity"
    EXPANDED = "expanded"


class MarketplaceLeadKind(StrEnum):
    PROJECT = "project"
    CONTRACT_ROLE = "contract_role"
    FULL_TIME_JOB = "full_time_job"


class MarketplaceLeadStatus(StrEnum):
    NEW = "new"
    WATCHING = "watching"
    CONTACTED = "contacted"
    IGNORED = "ignored"


@dataclass(slots=True)
class MarketplaceLeadEvent:
    event_type: str
    created_at: datetime
    status_from: str | None = None
    status_to: str | None = None
    note: str | None = None


@dataclass(slots=True)
class MarketplaceLead:
    id: int
    source_id: int
    source_name: str
    platform: str
    title: str
    summary: str | None
    description: str | None
    category: str | None
    budget: str | None
    normalized_budget: str | None
    engagement: str | None
    timeline: str | None
    normalized_timeline: str | None
    location: str | None
    published_at: datetime | None
    author: str | None
    tags: list[str]
    skills: list[str]
    link: str | None
    lead_kind: MarketplaceLeadKind
    lead_tier: MarketplaceLeadTier
    tier_reason: str
    lead_status: MarketplaceLeadStatus
    notes: str | None
    priority_score: int
    priority_reason: str
    last_action_at: datetime
    lead_events: list[MarketplaceLeadEvent]
    duplicate_count: int
    duplicate_sources: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MarketplaceLeadSourceMetric:
    source_id: int
    source_name: str
    total: int
    high_purity: int
    expanded: int
    reviewable: int
    full_time_job: int
    watching: int
    contacted: int


@dataclass(slots=True)
class MarketplacePriorityContext:
    source_history: dict[int, MarketplaceLeadSourceMetric]
    now: datetime


def list_leads(
    *,
    search: str | None = None,
    source_id: int | None = None,
    tier: MarketplaceLeadTier | None = None,
    lead_kind: MarketplaceLeadKind | None = None,
    reviewable_only: bool = False,
    lead_status: MarketplaceLeadStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[
    int,
    list[MarketplaceLead],
    dict[str, int],
    dict[str, int],
    dict[str, int],
    list[MarketplaceLeadSourceMetric],
]:
    _, items = raw_entries.list_entries(
        source_id=source_id,
        source_type=SourceType.FREELANCE_MARKETPLACE,
        search=search,
        skip=0,
        limit=None,
    )
    leads = _merge_duplicate_leads([_to_marketplace_lead(item) for item in items])
    tier_breakdown = _count_tiers(leads)
    kind_breakdown = _count_kinds(leads)
    status_breakdown = _count_statuses(leads)
    source_breakdown = _build_source_breakdown(leads)
    priority_context = MarketplacePriorityContext(
        source_history={item.source_id: item for item in source_breakdown},
        now=datetime.now(UTC),
    )
    leads = [_with_priority(lead, priority_context) for lead in leads]
    leads.sort(key=_lead_sort_key, reverse=True)
    if tier is not None:
        leads = [lead for lead in leads if lead.lead_tier == tier]
    if lead_kind is not None:
        leads = [lead for lead in leads if lead.lead_kind == lead_kind]
    if reviewable_only:
        leads = [lead for lead in leads if lead.lead_kind in _REVIEWABLE_LEAD_KINDS]
    if lead_status is not None:
        leads = [lead for lead in leads if lead.lead_status == lead_status]
    total = len(leads)
    leads = leads[skip : skip + limit]
    return total, leads, tier_breakdown, kind_breakdown, status_breakdown, source_breakdown


def update_lead_status(entry_id: int, status: MarketplaceLeadStatus) -> MarketplaceLead:
    entry = raw_entries.get_entry(entry_id)
    source = rss_sources.get_source(entry.source_id)
    if source is None or source.source_type != SourceType.FREELANCE_MARKETPLACE:
        raise ValueError("marketplace lead not found")

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        previous_status = _to_lead_status(metadata.get("lead_status"))
        metadata["lead_status"] = status.value
        if previous_status != status:
            metadata["lead_events"] = _append_lead_event(
                metadata.get("lead_events"),
                event_type="status_changed",
                status_from=previous_status.value,
                status_to=status.value,
            )
        model.metadata = metadata

    updated = db.update_raw_entry(entry_id, _apply)
    return _to_marketplace_lead(updated)


def get_lead(entry_id: int) -> MarketplaceLead:
    entry = raw_entries.get_entry(entry_id)
    source = rss_sources.get_source(entry.source_id)
    if source is None or source.source_type != SourceType.FREELANCE_MARKETPLACE:
        raise ValueError("marketplace lead not found")

    _, items, _, _, _, _ = list_leads(limit=1000)
    for item in items:
        if item.id == entry_id:
            return item
    return _to_marketplace_lead(entry)


def update_lead_notes(entry_id: int, notes: str | None) -> MarketplaceLead:
    entry = raw_entries.get_entry(entry_id)
    source = rss_sources.get_source(entry.source_id)
    if source is None or source.source_type != SourceType.FREELANCE_MARKETPLACE:
        raise ValueError("marketplace lead not found")

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        previous_notes = _to_string(metadata.get("lead_notes"))
        cleaned_notes = notes.strip() if isinstance(notes, str) else ""
        if cleaned_notes:
            metadata["lead_notes"] = cleaned_notes
        else:
            metadata.pop("lead_notes", None)
        if cleaned_notes != (previous_notes or ""):
            metadata["lead_events"] = _append_lead_event(
                metadata.get("lead_events"),
                event_type="notes_updated",
                note=cleaned_notes or None,
            )
        model.metadata = metadata

    db.update_raw_entry(entry_id, _apply)
    return get_lead(entry_id)


def _to_marketplace_lead(item: RawEntry) -> MarketplaceLead:
    source = rss_sources.get_source(item.source_id)
    if source is None:
        raise ValueError(f"source #{item.source_id} not found")
    metadata = dict(item.metadata or {})
    lead_kind = _classify_lead_kind(source.name, item, metadata)
    lead_tier, tier_reason = _classify_lead_tier(source.name, item, metadata)
    budget = _to_string(metadata.get("budget"))
    timeline = _to_string(metadata.get("timeline"))
    lead_events = _to_lead_events(item, metadata)
    last_action_at = max(
        [event.created_at for event in lead_events],
        default=_ensure_utc(item.updated_at),
    )
    return MarketplaceLead(
        id=item.id,
        source_id=item.source_id,
        source_name=source.name,
        platform=str(metadata.get("platform") or source.name),
        title=item.title,
        summary=item.summary,
        description=item.content,
        category=_to_string(metadata.get("category")),
        budget=budget,
        normalized_budget=_normalize_budget(budget, _to_string(metadata.get("engagement"))),
        engagement=_to_string(metadata.get("engagement")),
        timeline=timeline,
        normalized_timeline=_normalize_timeline(timeline),
        location=_to_string(metadata.get("location")),
        published_at=item.published_at,
        author=item.author,
        tags=list(item.tags),
        skills=_to_string_list(metadata.get("skills")),
        link=item.link,
        lead_kind=lead_kind,
        lead_tier=lead_tier,
        tier_reason=tier_reason,
        lead_status=_to_lead_status(metadata.get("lead_status")),
        notes=_to_string(metadata.get("lead_notes")),
        priority_score=0,
        priority_reason="尚未计算优先级。",
        last_action_at=last_action_at,
        lead_events=lead_events,
        duplicate_count=1,
        duplicate_sources=[source.name],
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _classify_lead_tier(
    source_name: str,
    item: RawEntry,
    metadata: dict[str, object],
) -> tuple[MarketplaceLeadTier, str]:
    title_haystack = " ".join(
        filter(
            None,
            [
                item.title.lower(),
                (item.summary or "").lower(),
                _to_string(metadata.get("category")) and str(metadata.get("category")).lower(),
            ],
        )
    )
    detail_haystack = " ".join(
        filter(
            None,
            [
                title_haystack,
                " ".join(text.lower() for text in _to_string_list(metadata.get("skills"))),
            ],
        )
    )
    if any(keyword in title_haystack for keyword in _STRONG_HIGH_PURITY_KEYWORDS):
        return (
            MarketplaceLeadTier.HIGH_PURITY,
            "标题直接体现前后端、全栈或 CMS 交付，属于明确的软件开发项目。",
        )
    if any(keyword in detail_haystack for keyword in _EXPANDED_KEYWORDS):
        return (
            MarketplaceLeadTier.EXPANDED,
            "技术实现类项目，适合放入扩展线索而不是默认高纯度队列。",
        )
    if "猪八戒" in source_name:
        return (
            MarketplaceLeadTier.HIGH_PURITY,
            "公开外包平台上的明确软件开发交付项目，可直接进入高纯度队列。",
        )
    if any(keyword in detail_haystack for keyword in _HIGH_PURITY_KEYWORDS):
        return (
            MarketplaceLeadTier.HIGH_PURITY,
            "标题或分类明确指向 Web/App/后台/管理系统交付，适合优先评审。",
        )
    return (
        MarketplaceLeadTier.EXPANDED,
        "仍属于软件实现需求，但更偏技术服务或垂直场景，放入扩展线索观察。",
    )


def _merge_duplicate_leads(leads: list[MarketplaceLead]) -> list[MarketplaceLead]:
    grouped: list[MarketplaceLead] = []
    for lead in leads:
        matching_indexes = [index for index, existing in enumerate(grouped) if _looks_like_duplicate(existing, lead)]
        if not matching_indexes:
            grouped.append(lead)
            continue
        primary_index = matching_indexes[0]
        merged_lead = _merge_lead_pair(grouped[primary_index], lead)
        for index in reversed(matching_indexes[1:]):
            merged_lead = _merge_lead_pair(merged_lead, grouped[index])
            del grouped[index]
        grouped[primary_index] = merged_lead
    merged = grouped
    merged.sort(
        key=lambda item: (
            item.lead_status == MarketplaceLeadStatus.CONTACTED,
            item.lead_status == MarketplaceLeadStatus.WATCHING,
            item.lead_tier == MarketplaceLeadTier.HIGH_PURITY,
            item.published_at or item.created_at,
        ),
        reverse=True,
    )
    return merged


def _merge_lead_pair(left: MarketplaceLead, right: MarketplaceLead) -> MarketplaceLead:
    representative = left
    alternate = right
    if _lead_sort_key(right) > _lead_sort_key(left):
        representative, alternate = right, left
    status = max(left.lead_status, right.lead_status, key=_lead_status_rank)
    duplicate_sources = list(dict.fromkeys([*left.duplicate_sources, *right.duplicate_sources]))
    return MarketplaceLead(
        id=representative.id,
        source_id=representative.source_id,
        source_name=representative.source_name,
        platform=representative.platform,
        title=representative.title,
        summary=representative.summary or alternate.summary,
        description=representative.description or alternate.description,
        category=representative.category or alternate.category,
        budget=representative.budget or alternate.budget,
        normalized_budget=representative.normalized_budget or alternate.normalized_budget,
        engagement=representative.engagement or alternate.engagement,
        timeline=representative.timeline or alternate.timeline,
        normalized_timeline=representative.normalized_timeline or alternate.normalized_timeline,
        location=representative.location or alternate.location,
        published_at=representative.published_at or alternate.published_at,
        author=representative.author or alternate.author,
        tags=list(dict.fromkeys([*representative.tags, *alternate.tags])),
        skills=list(dict.fromkeys([*representative.skills, *alternate.skills])),
        link=representative.link or alternate.link,
        lead_kind=representative.lead_kind,
        lead_tier=representative.lead_tier,
        tier_reason=representative.tier_reason,
        lead_status=status,
        notes=representative.notes or alternate.notes,
        priority_score=max(left.priority_score, right.priority_score),
        priority_reason=representative.priority_reason or alternate.priority_reason,
        last_action_at=max(left.last_action_at, right.last_action_at),
        lead_events=_merge_lead_events(left.lead_events, right.lead_events),
        duplicate_count=left.duplicate_count + right.duplicate_count,
        duplicate_sources=duplicate_sources,
        created_at=min(left.created_at, right.created_at),
        updated_at=max(left.updated_at, right.updated_at),
    )


def _lead_sort_key(lead: MarketplaceLead) -> tuple[int, int, datetime]:
    return (
        lead.priority_score,
        1 if lead.lead_kind in _REVIEWABLE_LEAD_KINDS else 0,
        1 if lead.lead_tier == MarketplaceLeadTier.HIGH_PURITY else 0,
        _lead_status_rank(lead.lead_status),
        lead.published_at or lead.created_at,
    )


def _with_priority(lead: MarketplaceLead, context: MarketplacePriorityContext) -> MarketplaceLead:
    score, reason = _calculate_priority(lead, context)
    return replace(lead, priority_score=score, priority_reason=reason)


def _calculate_priority(lead: MarketplaceLead, context: MarketplacePriorityContext) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []

    if lead.lead_tier == MarketplaceLeadTier.HIGH_PURITY:
        score += 35
        reasons.append("高纯度线索")
    else:
        score += 12
        reasons.append("扩展线索")

    if lead.lead_kind == MarketplaceLeadKind.PROJECT:
        score += 28
        reasons.append("项目型")
    elif lead.lead_kind == MarketplaceLeadKind.CONTRACT_ROLE:
        score += 20
        reasons.append("合同型角色")
    else:
        score -= 18
        reasons.append("全职招聘降权")

    if lead.lead_status == MarketplaceLeadStatus.NEW:
        score += 12
        reasons.append("待处理")
    elif lead.lead_status == MarketplaceLeadStatus.WATCHING:
        score += 6
        reasons.append("已关注")
    elif lead.lead_status == MarketplaceLeadStatus.CONTACTED:
        score -= 10
        reasons.append("已联系")
    else:
        score -= 24
        reasons.append("已忽略")

    published_at = _ensure_utc(lead.published_at or lead.created_at)
    age_days = max((context.now - published_at).days, 0)
    if age_days <= 3:
        score += 14
        reasons.append("最近 3 天发布")
    elif age_days <= 7:
        score += 8
        reasons.append("最近 7 天发布")
    elif age_days <= 14:
        score += 3
        reasons.append("近期发布")

    if lead.duplicate_count > 1:
        score -= min((lead.duplicate_count - 1) * 4, 12)
        reasons.append("重复线索降权")

    source_metric = context.source_history.get(lead.source_id)
    if source_metric and source_metric.total >= 1:
        purity_ratio = source_metric.high_purity / source_metric.total
        if purity_ratio >= 0.7:
            score += 10
            reasons.append("来源高纯度占比高")
        elif purity_ratio >= 0.4:
            score += 5
            reasons.append("来源质量稳定")

    if lead.notes:
        score += 4
        reasons.append("已有备注")

    return score, " / ".join(reasons)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _lead_status_rank(status: MarketplaceLeadStatus) -> int:
    return {
        MarketplaceLeadStatus.IGNORED: 0,
        MarketplaceLeadStatus.NEW: 1,
        MarketplaceLeadStatus.WATCHING: 2,
        MarketplaceLeadStatus.CONTACTED: 3,
    }[status]


def _canonical_lead_key(lead: MarketplaceLead) -> str:
    normalized = _NON_WORD_RE.sub(" ", lead.title.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if lead.normalized_budget:
        return f"{normalized}|{lead.normalized_budget}"
    return normalized


def _looks_like_duplicate(left: MarketplaceLead, right: MarketplaceLead) -> bool:
    left_link = _normalized_link_key(left.link)
    right_link = _normalized_link_key(right.link)
    if left_link and right_link and left_link == right_link:
        return True

    left_author = _normalized_entity_key(left.author)
    right_author = _normalized_entity_key(right.author)
    title_overlap = _title_overlap_ratio(left.title, right.title)
    shared_title_tokens = _shared_title_token_count(left.title, right.title)

    if left_author and right_author and left_author == right_author:
        if title_overlap >= 0.7 and shared_title_tokens >= 2:
            return True

    left_title_key = _title_similarity_key(left.title)
    right_title_key = _title_similarity_key(right.title)
    if left_title_key and left_title_key == right_title_key:
        if left.normalized_budget and right.normalized_budget and left.normalized_budget == right.normalized_budget:
            return True
        left_skill_key = _skill_signature(left.skills)
        right_skill_key = _skill_signature(right.skills)
        left_location = _normalized_entity_key(left.location)
        right_location = _normalized_entity_key(right.location)
        if (
            left_skill_key
            and right_skill_key
            and left_skill_key == right_skill_key
            and (
                (left_location and right_location and left_location == right_location)
                or (left_author and right_author and left_author == right_author)
            )
        ):
            return True

    return False


def _count_tiers(leads: list[MarketplaceLead]) -> dict[str, int]:
    return {
        MarketplaceLeadTier.HIGH_PURITY.value: sum(
            1 for lead in leads if lead.lead_tier == MarketplaceLeadTier.HIGH_PURITY
        ),
        MarketplaceLeadTier.EXPANDED.value: sum(
            1 for lead in leads if lead.lead_tier == MarketplaceLeadTier.EXPANDED
        ),
    }


def _count_kinds(leads: list[MarketplaceLead]) -> dict[str, int]:
    return {
        kind.value: sum(1 for lead in leads if lead.lead_kind == kind)
        for kind in MarketplaceLeadKind
    }


def _count_statuses(leads: list[MarketplaceLead]) -> dict[str, int]:
    return {
        status.value: sum(1 for lead in leads if lead.lead_status == status)
        for status in MarketplaceLeadStatus
    }


def _append_lead_event(
    raw_events: object,
    *,
    event_type: str,
    status_from: str | None = None,
    status_to: str | None = None,
    note: str | None = None,
) -> list[dict[str, object]]:
    events = list(raw_events) if isinstance(raw_events, list) else []
    event: dict[str, object] = {
        "event_type": event_type,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if status_from:
        event["status_from"] = status_from
    if status_to:
        event["status_to"] = status_to
    if note:
        event["note"] = note
    events.append(event)
    return events


def _to_lead_events(item: RawEntry, metadata: dict[str, object]) -> list[MarketplaceLeadEvent]:
    events: list[MarketplaceLeadEvent] = [
        MarketplaceLeadEvent(
            event_type="captured",
            created_at=_ensure_utc(item.created_at),
        )
    ]
    raw_events = metadata.get("lead_events")
    if not isinstance(raw_events, list):
        return events
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            continue
        created_at_text = _to_string(raw_event.get("created_at"))
        if not created_at_text:
            continue
        try:
            created_at = _ensure_utc(datetime.fromisoformat(created_at_text))
        except ValueError:
            continue
        event_type = _to_string(raw_event.get("event_type")) or "updated"
        events.append(
            MarketplaceLeadEvent(
                event_type=event_type,
                created_at=created_at,
                status_from=_to_string(raw_event.get("status_from")),
                status_to=_to_string(raw_event.get("status_to")),
                note=_to_string(raw_event.get("note")),
            )
        )
    events.sort(key=lambda item: item.created_at, reverse=True)
    return events


def _merge_lead_events(left: list[MarketplaceLeadEvent], right: list[MarketplaceLeadEvent]) -> list[MarketplaceLeadEvent]:
    merged: dict[tuple[str, datetime, str | None, str | None, str | None], MarketplaceLeadEvent] = {}
    for event in [*left, *right]:
        key = (event.event_type, event.created_at, event.status_from, event.status_to, event.note)
        merged[key] = event
    return sorted(merged.values(), key=lambda item: item.created_at, reverse=True)


def _build_source_breakdown(leads: list[MarketplaceLead]) -> list[MarketplaceLeadSourceMetric]:
    grouped: dict[tuple[int, str], list[MarketplaceLead]] = {}
    for lead in leads:
        key = (lead.source_id, lead.source_name)
        grouped.setdefault(key, []).append(lead)

    metrics: list[MarketplaceLeadSourceMetric] = []
    for (source_id, source_name), items in grouped.items():
        metrics.append(
            MarketplaceLeadSourceMetric(
                source_id=source_id,
                source_name=source_name,
                total=len(items),
                high_purity=sum(1 for item in items if item.lead_tier == MarketplaceLeadTier.HIGH_PURITY),
                expanded=sum(1 for item in items if item.lead_tier == MarketplaceLeadTier.EXPANDED),
                reviewable=sum(1 for item in items if item.lead_kind in _REVIEWABLE_LEAD_KINDS),
                full_time_job=sum(1 for item in items if item.lead_kind == MarketplaceLeadKind.FULL_TIME_JOB),
                watching=sum(1 for item in items if item.lead_status == MarketplaceLeadStatus.WATCHING),
                contacted=sum(1 for item in items if item.lead_status == MarketplaceLeadStatus.CONTACTED),
            )
        )
    metrics.sort(
        key=lambda item: (item.high_purity, item.reviewable, item.contacted, item.total, item.source_name),
        reverse=True,
    )
    return metrics


def _to_lead_status(value: object) -> MarketplaceLeadStatus:
    if value is None:
        return MarketplaceLeadStatus.NEW
    try:
        return MarketplaceLeadStatus(str(value))
    except ValueError:
        return MarketplaceLeadStatus.NEW


def _normalize_budget(value: str | None, engagement: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    lowered = text.lower()
    if lowered in {"待商议", "面议", "open"}:
        return "Negotiable"
    if match := _USD_RANGE_RE.match(text):
        return (
            f"USD {_expand_number(match.group('start'), match.group('start_suffix'))}"
            f"-{_expand_number(match.group('end'), match.group('end_suffix'))}"
            f"{match.group('unit') or ''}"
        )
    if match := _USD_SINGLE_RE.match(text):
        return f"USD {_expand_number(match.group('value'), match.group('suffix'))}{match.group('unit') or ''}"
    if match := _CNY_RANGE_RE.match(text):
        return f"CNY {match.group('start')}k-{match.group('end')}k"
    if match := _CNY_UPPER_RE.match(text):
        return f"CNY <= {match.group('value')}k"
    if match := _CNY_SINGLE_RE.match(text):
        return f"CNY {match.group('value').replace(',', '')}"
    if engagement == "fixed-price":
        return text
    return text


def _normalize_timeline(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    lowered = text.lower()
    if "ago" in lowered or lowered in {"选标中", "圆满结束", "待商议"}:
        return None
    if "ongoing" in lowered:
        hours = _HOURS_PER_WEEK_RE.search(lowered)
        if hours:
            return f"{hours.group('hours')} · Ongoing"
        return "Ongoing"
    if match := _CN_DAY_RE.search(text):
        return f"{match.group('days')} days"
    if match := _EN_DAY_RE.search(text):
        return f"{match.group('days')} days"
    if match := _HOURS_PER_WEEK_RE.search(text):
        return match.group("hours")
    return text


def _expand_number(value: str, suffix: str | None) -> str:
    if suffix and suffix.lower() == "k":
        base = float(value.replace(",", ""))
        expanded = int(base * 1000)
        return str(expanded)
    cleaned = value.replace(",", "")
    return cleaned


def _to_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, Iterable):
        return []
    values: list[str] = []
    for item in value:
        text = _to_string(item)
        if text:
            values.append(text)
    return values


def _normalized_link_key(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/").lower()
    if not netloc and not path:
        return None
    return f"{netloc}{path}"


def _normalized_entity_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _NON_WORD_RE.sub(" ", value.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized or None


def _title_similarity_key(value: str) -> str:
    tokens = _title_tokens(value)
    return " ".join(tokens)


def _title_tokens(value: str) -> list[str]:
    tokens = [token for token in _NON_WORD_RE.split(value.lower()) if token]
    return [token for token in tokens if token not in _TITLE_STOPWORDS]


def _title_overlap_ratio(left: str, right: str) -> float:
    left_tokens = set(_title_tokens(left))
    right_tokens = set(_title_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _shared_title_token_count(left: str, right: str) -> int:
    return len(set(_title_tokens(left)) & set(_title_tokens(right)))


def _skill_signature(skills: list[str]) -> str | None:
    normalized_skills = {
        token
        for skill in skills
        for token in _NON_WORD_RE.split(skill.lower())
        if token and token not in _SKILL_STOPWORDS
    }
    if len(normalized_skills) < 2:
        return None
    return "|".join(sorted(normalized_skills))


def _diversify_by_source(items: list[MarketplaceLead]) -> list[MarketplaceLead]:
    buckets: dict[int, deque[MarketplaceLead]] = {}
    source_order: list[int] = []
    for item in items:
        if item.source_id not in buckets:
            buckets[item.source_id] = deque()
            source_order.append(item.source_id)
        buckets[item.source_id].append(item)

    diversified: list[MarketplaceLead] = []
    while source_order:
        next_round: list[int] = []
        for source_id in source_order:
            bucket = buckets[source_id]
            if not bucket:
                continue
            diversified.append(bucket.popleft())
            if bucket:
                next_round.append(source_id)
        source_order = next_round
    return diversified


def _classify_lead_kind(
    source_name: str,
    item: RawEntry,
    metadata: dict[str, object],
) -> MarketplaceLeadKind:
    title_haystack = " ".join(
        filter(
            None,
            [
                item.title.lower(),
                (item.summary or "").lower(),
                _to_string(metadata.get("category")) and str(metadata.get("category")).lower(),
            ],
        )
    )
    detail_haystack = " ".join(
        filter(
            None,
            [
                title_haystack,
                (item.content or "").lower(),
                _to_string(metadata.get("engagement")) and str(metadata.get("engagement")).lower(),
            ],
        )
    )
    normalized_source = source_name.lower()
    if any(marker in normalized_source for marker in _PROJECT_SOURCE_MARKERS):
        return MarketplaceLeadKind.PROJECT
    if any(marker in detail_haystack for marker in _FULL_TIME_MARKERS):
        return MarketplaceLeadKind.FULL_TIME_JOB
    if any(marker in detail_haystack for marker in _CONTRACT_ROLE_MARKERS):
        return MarketplaceLeadKind.CONTRACT_ROLE
    if any(marker in detail_haystack for marker in _PROJECT_MARKERS):
        return MarketplaceLeadKind.PROJECT
    return MarketplaceLeadKind.FULL_TIME_JOB


_STRONG_HIGH_PURITY_KEYWORDS = (
    "frontend developer",
    "frontend engineer",
    "backend developer",
    "backend engineer",
    "python developer",
    "software developer",
    "full stack developer",
    "full stack engineer",
    "full-stack developer",
    "full-stack engineer",
    "full-stack web developer",
    "full-stack react",
    "react developer",
    "web developer",
    "react / next.js",
    "react/next.js",
    "wordpress website",
    "cms developer",
    "hubspot cms",
    "quote template",
)

_HIGH_PURITY_KEYWORDS = (
    "小程序",
    "公众号",
    "网站",
    "web",
    "app",
    "frontend",
    "backend",
    "full-stack",
    "full stack",
    "react",
    "next.js",
    "django",
    "angular",
    "wordpress",
    "hubspot",
    "后台",
    "数据库",
    "管理软件",
    "系统",
    "平台",
    "erp",
    "crm",
    "saas",
    "进销存",
)

_EXPANDED_KEYWORDS = (
    "device owner",
    "kiosk",
    "oem",
    "arkit",
    "face mesh",
    "qt",
    "java",
    "mysql",
    "嵌入式",
    "硬件",
    "编译",
    "数字化",
    "识别",
    "rk3568",
)

_PROJECT_SOURCE_MARKERS = (
    "peopleperhour",
    "freelancer",
    "contra featured",
    "猪八戒",
    "软件项目交易网",
)

_CONTRACT_ROLE_MARKERS = (
    "contract",
    "freelance",
    "project-based",
    "hourly-contract",
    "contract-like",
    "b2b",
    "part-time, non-permanent",
    "non-permanent projects",
    "hours per week",
    "hour equivalent",
)

_FULL_TIME_MARKERS = (
    "full-time",
    "full time",
    "employment type: full-time",
    "employment type: full time",
)

_PROJECT_MARKERS = (
    "fixed-price",
    "proposal",
    "proposals",
    "bid",
    "bids",
    "deliverable",
    "交付",
    "选标中",
)

_REVIEWABLE_LEAD_KINDS = (
    MarketplaceLeadKind.PROJECT,
    MarketplaceLeadKind.CONTRACT_ROLE,
)

_TITLE_STOPWORDS = {
    "senior",
    "jr",
    "junior",
    "lead",
    "staff",
    "principal",
    "remote",
    "contract",
    "freelance",
    "role",
}

_SKILL_STOPWORDS = {
    "software",
    "development",
    "engineering",
    "engineer",
    "developer",
    "marketplace",
    "remote",
}
