"""外包项目线索查询。"""

from __future__ import annotations

from collections.abc import Iterable
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.models import RawEntry, SourceType
from app.services import raw_entries, rss_sources


class MarketplaceLeadTier(StrEnum):
    HIGH_PURITY = "high_purity"
    EXPANDED = "expanded"


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
    engagement: str | None
    timeline: str | None
    location: str | None
    published_at: datetime | None
    author: str | None
    tags: list[str]
    skills: list[str]
    link: str | None
    lead_tier: MarketplaceLeadTier
    tier_reason: str
    created_at: datetime
    updated_at: datetime


def list_leads(
    *,
    search: str | None = None,
    source_id: int | None = None,
    tier: MarketplaceLeadTier | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[int, list[MarketplaceLead], dict[str, int]]:
    _, items = raw_entries.list_entries(
        source_id=source_id,
        source_type=SourceType.FREELANCE_MARKETPLACE,
        search=search,
        skip=0,
        limit=None,
    )
    leads = [_to_marketplace_lead(item) for item in items]
    tier_breakdown = _count_tiers(leads)
    if tier is not None:
        leads = [lead for lead in leads if lead.lead_tier == tier]
    if source_id is None:
        leads = _diversify_by_source(leads)
    total = len(leads)
    leads = leads[skip : skip + limit]
    return total, leads, tier_breakdown


def _to_marketplace_lead(item: RawEntry) -> MarketplaceLead:
    source = rss_sources.get_source(item.source_id)
    metadata = dict(item.metadata or {})
    lead_tier, tier_reason = _classify_lead_tier(source.name, item, metadata)
    return MarketplaceLead(
        id=item.id,
        source_id=item.source_id,
        source_name=source.name,
        platform=str(metadata.get("platform") or source.name),
        title=item.title,
        summary=item.summary,
        description=item.content,
        category=_to_string(metadata.get("category")),
        budget=_to_string(metadata.get("budget")),
        engagement=_to_string(metadata.get("engagement")),
        timeline=_to_string(metadata.get("timeline")),
        location=_to_string(metadata.get("location")),
        published_at=item.published_at,
        author=item.author,
        tags=list(item.tags),
        skills=_to_string_list(metadata.get("skills")),
        link=item.link,
        lead_tier=lead_tier,
        tier_reason=tier_reason,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _classify_lead_tier(
    source_name: str,
    item: RawEntry,
    metadata: dict[str, object],
) -> tuple[MarketplaceLeadTier, str]:
    haystack = " ".join(
        filter(
            None,
            [
                item.title.lower(),
                (item.summary or "").lower(),
                _to_string(metadata.get("category")) and str(metadata.get("category")).lower(),
                " ".join(text.lower() for text in _to_string_list(metadata.get("skills"))),
            ],
        )
    )
    if any(keyword in haystack for keyword in _EXPANDED_KEYWORDS):
        return (
            MarketplaceLeadTier.EXPANDED,
            "技术实现类项目，适合放入扩展线索而不是默认高纯度队列。",
        )
    if "猪八戒" in source_name:
        return (
            MarketplaceLeadTier.HIGH_PURITY,
            "公开外包平台上的明确软件开发交付项目，可直接进入高纯度队列。",
        )
    if any(keyword in haystack for keyword in _HIGH_PURITY_KEYWORDS):
        return (
            MarketplaceLeadTier.HIGH_PURITY,
            "标题或分类明确指向 Web/App/后台/管理系统交付，适合优先评审。",
        )
    return (
        MarketplaceLeadTier.EXPANDED,
        "仍属于软件实现需求，但更偏技术服务或垂直场景，放入扩展线索观察。",
    )


def _count_tiers(leads: list[MarketplaceLead]) -> dict[str, int]:
    return {
        MarketplaceLeadTier.HIGH_PURITY.value: sum(
            1 for lead in leads if lead.lead_tier == MarketplaceLeadTier.HIGH_PURITY
        ),
        MarketplaceLeadTier.EXPANDED.value: sum(
            1 for lead in leads if lead.lead_tier == MarketplaceLeadTier.EXPANDED
        ),
    }


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


_HIGH_PURITY_KEYWORDS = (
    "小程序",
    "公众号",
    "网站",
    "web",
    "app",
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
