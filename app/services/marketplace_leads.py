"""外包项目线索查询与状态管理。"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

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


class MarketplaceLeadStatus(StrEnum):
    NEW = "new"
    WATCHING = "watching"
    CONTACTED = "contacted"
    IGNORED = "ignored"


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
    lead_tier: MarketplaceLeadTier
    tier_reason: str
    lead_status: MarketplaceLeadStatus
    duplicate_count: int
    duplicate_sources: list[str]
    created_at: datetime
    updated_at: datetime


def list_leads(
    *,
    search: str | None = None,
    source_id: int | None = None,
    tier: MarketplaceLeadTier | None = None,
    lead_status: MarketplaceLeadStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[int, list[MarketplaceLead], dict[str, int], dict[str, int]]:
    _, items = raw_entries.list_entries(
        source_id=source_id,
        source_type=SourceType.FREELANCE_MARKETPLACE,
        search=search,
        skip=0,
        limit=None,
    )
    leads = _merge_duplicate_leads([_to_marketplace_lead(item) for item in items])
    tier_breakdown = _count_tiers(leads)
    status_breakdown = _count_statuses(leads)
    if tier is not None:
        leads = [lead for lead in leads if lead.lead_tier == tier]
    if lead_status is not None:
        leads = [lead for lead in leads if lead.lead_status == lead_status]
    if source_id is None:
        leads = _diversify_by_source(leads)
    total = len(leads)
    leads = leads[skip : skip + limit]
    return total, leads, tier_breakdown, status_breakdown


def update_lead_status(entry_id: int, status: MarketplaceLeadStatus) -> MarketplaceLead:
    entry = raw_entries.get_entry(entry_id)
    source = rss_sources.get_source(entry.source_id)
    if source is None or source.source_type != SourceType.FREELANCE_MARKETPLACE:
        raise ValueError("marketplace lead not found")

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        metadata["lead_status"] = status.value
        model.metadata = metadata

    updated = db.update_raw_entry(entry_id, _apply)
    return _to_marketplace_lead(updated)


def _to_marketplace_lead(item: RawEntry) -> MarketplaceLead:
    source = rss_sources.get_source(item.source_id)
    if source is None:
        raise ValueError(f"source #{item.source_id} not found")
    metadata = dict(item.metadata or {})
    lead_tier, tier_reason = _classify_lead_tier(source.name, item, metadata)
    budget = _to_string(metadata.get("budget"))
    timeline = _to_string(metadata.get("timeline"))
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
        lead_tier=lead_tier,
        tier_reason=tier_reason,
        lead_status=_to_lead_status(metadata.get("lead_status")),
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
    grouped: dict[str, MarketplaceLead] = {}
    for lead in leads:
        key = _canonical_lead_key(lead)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = lead
            continue
        grouped[key] = _merge_lead_pair(existing, lead)
    merged = list(grouped.values())
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
        lead_tier=representative.lead_tier,
        tier_reason=representative.tier_reason,
        lead_status=status,
        duplicate_count=left.duplicate_count + right.duplicate_count,
        duplicate_sources=duplicate_sources,
        created_at=min(left.created_at, right.created_at),
        updated_at=max(left.updated_at, right.updated_at),
    )


def _lead_sort_key(lead: MarketplaceLead) -> tuple[int, int, datetime]:
    return (
        1 if lead.lead_tier == MarketplaceLeadTier.HIGH_PURITY else 0,
        _lead_status_rank(lead.lead_status),
        lead.published_at or lead.created_at,
    )


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


def _count_tiers(leads: list[MarketplaceLead]) -> dict[str, int]:
    return {
        MarketplaceLeadTier.HIGH_PURITY.value: sum(
            1 for lead in leads if lead.lead_tier == MarketplaceLeadTier.HIGH_PURITY
        ),
        MarketplaceLeadTier.EXPANDED.value: sum(
            1 for lead in leads if lead.lead_tier == MarketplaceLeadTier.EXPANDED
        ),
    }


def _count_statuses(leads: list[MarketplaceLead]) -> dict[str, int]:
    return {
        status.value: sum(1 for lead in leads if lead.lead_status == status)
        for status in MarketplaceLeadStatus
    }


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


_STRONG_HIGH_PURITY_KEYWORDS = (
    "frontend developer",
    "backend developer",
    "full stack developer",
    "full-stack developer",
    "full-stack web developer",
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
