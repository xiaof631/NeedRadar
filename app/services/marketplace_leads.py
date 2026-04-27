"""外包项目线索查询与状态管理。"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
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


class MarketplaceLeadOutcome(StrEnum):
    WON = "won"
    LOST = "lost"
    NO_RESPONSE = "no_response"
    NOT_FIT = "not_fit"


class MarketplaceBudgetBand(StrEnum):
    LT_1K = "lt_1k"
    ONE_K_TO_FIVE_K = "1k_5k"
    FIVE_K_TO_TWENTY_K = "5k_20k"
    GT_20K = "gt_20k"
    NEGOTIABLE = "negotiable"


class MarketplaceDeliveryScope(StrEnum):
    WEBSITE = "website"
    APP = "app"
    BACKEND = "backend"
    PLUGIN = "plugin"
    AUTOMATION = "automation"
    DATA_TOOL = "data_tool"
    EMBEDDED = "embedded"


class MarketplaceRegion(StrEnum):
    CHINA = "china"
    APAC = "apac"
    EUROPE_AMERICAS = "europe_americas"
    GLOBAL = "global"


@dataclass(slots=True)
class MarketplaceLeadEvent:
    event_type: str
    created_at: datetime
    status_from: str | None = None
    status_to: str | None = None
    outcome_from: str | None = None
    outcome_to: str | None = None
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
    budget_band: MarketplaceBudgetBand | None
    engagement: str | None
    timeline: str | None
    normalized_timeline: str | None
    delivery_scope: MarketplaceDeliveryScope | None
    tech_stack_normalized: list[str]
    location: str | None
    region: MarketplaceRegion | None
    timezone_fit: bool | None
    published_at: datetime | None
    author: str | None
    tags: list[str]
    skills: list[str]
    link: str | None
    lead_kind: MarketplaceLeadKind
    lead_tier: MarketplaceLeadTier
    tier_reason: str
    lead_status: MarketplaceLeadStatus
    lead_outcome: MarketplaceLeadOutcome | None
    outcome_reason_tags: list[str]
    notes: str | None
    next_follow_up_at: datetime | None
    follow_up_reason: str | None
    is_follow_up_overdue: bool
    priority_score: int
    priority_reason: str
    last_action_at: datetime
    lead_events: list[MarketplaceLeadEvent]
    duplicate_count: int
    duplicate_sources: list[str]
    first_seen_at: datetime
    latest_seen_at: datetime
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
class MarketplaceLeadConversionMetric:
    key: str
    label: str
    total: int
    resolved: int
    won: int
    lost: int
    no_response: int
    not_fit: int
    contacted: int
    resolution_rate: float
    win_rate: float


@dataclass(slots=True)
class MarketplaceLeadReminder:
    lead_id: int
    title: str
    source_name: str
    lead_status: MarketplaceLeadStatus
    priority_score: int
    reminder_type: str
    severity: str
    message: str
    last_action_at: datetime
    stale_days: int


@dataclass(slots=True)
class MarketplaceSourceRecommendation:
    source_id: int
    source_name: str
    action: str
    severity: str
    reason: str


@dataclass(slots=True)
class MarketplacePriorityContext:
    source_history: dict[int, MarketplaceLeadSourceMetric]
    now: datetime


@dataclass(slots=True)
class MarketplaceLeadQueryResult:
    total: int
    items: list[MarketplaceLead]
    tier_breakdown: dict[str, int]
    kind_breakdown: dict[str, int]
    status_breakdown: dict[str, int]
    outcome_breakdown: dict[str, int]
    outcome_reason_breakdown: dict[str, int]
    source_breakdown: list[MarketplaceLeadSourceMetric]
    source_conversion_breakdown: list[MarketplaceLeadConversionMetric]
    segment_conversion_breakdown: list[MarketplaceLeadConversionMetric]
    source_recommendations: list[MarketplaceSourceRecommendation]
    todo_breakdown: dict[str, int]
    todo_queue: list[MarketplaceLeadReminder]


@dataclass(slots=True)
class MarketplaceLeadOutcomeBackfillRow:
    lead_id: int
    outcome: MarketplaceLeadOutcome | None
    reason_tags: list[str]
    notes: str | None = None


def list_leads(
    *,
    search: str | None = None,
    source_id: int | None = None,
    tier: MarketplaceLeadTier | None = None,
    lead_kind: MarketplaceLeadKind | None = None,
    budget_band: MarketplaceBudgetBand | None = None,
    delivery_scope: MarketplaceDeliveryScope | None = None,
    tech_stack: str | None = None,
    region: MarketplaceRegion | None = None,
    timezone_fit: bool | None = None,
    reviewable_only: bool = False,
    overdue_only: bool = False,
    lead_status: MarketplaceLeadStatus | None = None,
    lead_outcome: MarketplaceLeadOutcome | None = None,
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
    result = query_leads(
        search=search,
        source_id=source_id,
        tier=tier,
        lead_kind=lead_kind,
        budget_band=budget_band,
        delivery_scope=delivery_scope,
        tech_stack=tech_stack,
        region=region,
        timezone_fit=timezone_fit,
        reviewable_only=reviewable_only,
        overdue_only=overdue_only,
        lead_status=lead_status,
        lead_outcome=lead_outcome,
        skip=skip,
        limit=limit,
    )
    return (
        result.total,
        result.items,
        result.tier_breakdown,
        result.kind_breakdown,
        result.status_breakdown,
        result.source_breakdown,
    )


def query_leads(
    *,
    search: str | None = None,
    source_id: int | None = None,
    tier: MarketplaceLeadTier | None = None,
    lead_kind: MarketplaceLeadKind | None = None,
    budget_band: MarketplaceBudgetBand | None = None,
    delivery_scope: MarketplaceDeliveryScope | None = None,
    tech_stack: str | None = None,
    region: MarketplaceRegion | None = None,
    timezone_fit: bool | None = None,
    reviewable_only: bool = False,
    overdue_only: bool = False,
    lead_status: MarketplaceLeadStatus | None = None,
    lead_outcome: MarketplaceLeadOutcome | None = None,
    skip: int = 0,
    limit: int = 20,
    todo_sort: str = "default",
) -> MarketplaceLeadQueryResult:
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
    outcome_breakdown = _count_outcomes(leads)
    outcome_reason_breakdown = _count_outcome_reasons(leads)
    source_breakdown = _build_source_breakdown(leads)
    source_conversion_breakdown = _build_source_conversion_breakdown(leads)
    segment_conversion_breakdown = _build_segment_conversion_breakdown(leads)
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
    if budget_band is not None:
        leads = [lead for lead in leads if lead.budget_band == budget_band]
    if delivery_scope is not None:
        leads = [lead for lead in leads if lead.delivery_scope == delivery_scope]
    if tech_stack is not None:
        normalized_stack = tech_stack.strip().lower()
        leads = [lead for lead in leads if normalized_stack in lead.tech_stack_normalized]
    if region is not None:
        leads = [lead for lead in leads if lead.region == region]
    if timezone_fit is not None:
        leads = [lead for lead in leads if lead.timezone_fit is timezone_fit]
    if reviewable_only:
        leads = [lead for lead in leads if lead.lead_kind in _REVIEWABLE_LEAD_KINDS]
    if overdue_only:
        leads = [lead for lead in leads if lead.is_follow_up_overdue]
    if lead_status is not None:
        leads = [lead for lead in leads if lead.lead_status == lead_status]
    if lead_outcome is not None:
        leads = [lead for lead in leads if lead.lead_outcome == lead_outcome]
    todo_queue = _build_todo_queue(leads, priority_context.now, todo_sort)
    todo_breakdown = _count_todo_queue(todo_queue)
    source_recommendations = _build_source_recommendations(
        source_breakdown,
        source_conversion_breakdown,
    )
    total = len(leads)
    leads = leads[skip : skip + limit]
    return MarketplaceLeadQueryResult(
        total=total,
        items=leads,
        tier_breakdown=tier_breakdown,
        kind_breakdown=kind_breakdown,
        status_breakdown=status_breakdown,
        outcome_breakdown=outcome_breakdown,
        outcome_reason_breakdown=outcome_reason_breakdown,
        source_breakdown=source_breakdown,
        source_conversion_breakdown=source_conversion_breakdown,
        segment_conversion_breakdown=segment_conversion_breakdown,
        source_recommendations=source_recommendations,
        todo_breakdown=todo_breakdown,
        todo_queue=todo_queue[:8],
    )


def build_retrospective_markdown(*, as_of: datetime | None = None) -> str:
    report_time = _ensure_utc(as_of or datetime.now(UTC))
    result = query_leads(limit=1000)
    recommendations_by_source = {
        item.source_id: item for item in result.source_recommendations
    }
    resolved = sum(
        result.outcome_breakdown.get(key, 0)
        for key in (
            MarketplaceLeadOutcome.WON.value,
            MarketplaceLeadOutcome.LOST.value,
            MarketplaceLeadOutcome.NO_RESPONSE.value,
            MarketplaceLeadOutcome.NOT_FIT.value,
        )
    )
    lines = [
        f"# Marketplace 复盘记录（{report_time.date().isoformat()}）",
        "",
        f"- 生成时间：{report_time.isoformat()}",
        f"- 线索总量：{result.total}",
        f"- 已结案：{resolved}",
        f"- 未结案：{result.outcome_breakdown.get('unresolved', 0)}",
        f"- 待办队列：{result.todo_breakdown.get('total', 0)}",
        "",
        "## 结果概览",
        f"- 成交：{result.outcome_breakdown.get(MarketplaceLeadOutcome.WON.value, 0)}",
        f"- 失败：{result.outcome_breakdown.get(MarketplaceLeadOutcome.LOST.value, 0)}",
        f"- 无回复：{result.outcome_breakdown.get(MarketplaceLeadOutcome.NO_RESPONSE.value, 0)}",
        f"- 不匹配：{result.outcome_breakdown.get(MarketplaceLeadOutcome.NOT_FIT.value, 0)}",
        "",
        "## 来源复盘",
    ]
    for metric in result.source_conversion_breakdown:
        recommendation = recommendations_by_source.get(
            int(metric.key.removeprefix("source:"))
        )
        recommendation_text = (
            f"{_recommendation_action_label(recommendation.action)}；{recommendation.reason}"
            if recommendation is not None
            else "继续观察结果样本"
        )
        lines.append(
            "- "
            f"{metric.label}：总量 {metric.total}，已结案 {metric.resolved}，"
            f"won {metric.won} / lost {metric.lost} / no_response {metric.no_response} / not_fit {metric.not_fit}，"
            f"成交率 {_ratio_to_percent(metric.win_rate)}，建议：{recommendation_text}"
        )

    lines.extend(["", "## 队列与类型复盘"])
    for metric in result.segment_conversion_breakdown:
        lines.append(
            "- "
            f"{metric.label}：总量 {metric.total}，已结案 {metric.resolved}，"
            f"结案率 {_ratio_to_percent(metric.resolution_rate)}，成交率 {_ratio_to_percent(metric.win_rate)}"
        )

    lines.extend(["", "## 高频结果原因"])
    if result.outcome_reason_breakdown:
        for tag, count in list(result.outcome_reason_breakdown.items())[:8]:
            lines.append(f"- `{tag}`：{count}")
    else:
        lines.append("- 暂无结果原因标签。")

    lines.extend(["", "## 本周待办"])
    if result.todo_queue:
        for item in result.todo_queue[:5]:
            lines.append(
                "- "
                f"{item.title}（{item.source_name}，{item.reminder_type}，优先级 {item.priority_score}）"
            )
    else:
        lines.append("- 当前没有新的待办。")

    lines.extend(
        [
            "",
            "## 节奏提醒",
            "- 每周一次来源复盘：更新来源效果、成交率、噪音来源和扩源建议。",
            "- 每两周一次规则复盘：复核高纯度/扩展线索边界，决定收紧或放宽过滤。",
            "- 每次复盘后，把结论同步到 `docs/marketplace-retrospectives/`，并回写来源建议或过滤规则。",
        ]
    )
    return "\n".join(lines)


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


def update_lead_outcome(
    entry_id: int,
    outcome: MarketplaceLeadOutcome | None,
    reason_tags: Iterable[str] | None = None,
) -> MarketplaceLead:
    entry = raw_entries.get_entry(entry_id)
    source = rss_sources.get_source(entry.source_id)
    if source is None or source.source_type != SourceType.FREELANCE_MARKETPLACE:
        raise ValueError("marketplace lead not found")
    normalized_reason_tags = _normalize_reason_tags(reason_tags)

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        previous_outcome = _to_lead_outcome(metadata.get("lead_outcome"))
        previous_reason_tags = _normalize_reason_tags(metadata.get("lead_outcome_reason_tags"))
        if outcome is None:
            metadata.pop("lead_outcome", None)
            metadata.pop("lead_outcome_reason_tags", None)
        else:
            metadata["lead_outcome"] = outcome.value
            metadata.pop("next_follow_up_at", None)
            metadata.pop("follow_up_reason", None)
            if normalized_reason_tags:
                metadata["lead_outcome_reason_tags"] = normalized_reason_tags
            else:
                metadata.pop("lead_outcome_reason_tags", None)
        if previous_outcome != outcome or previous_reason_tags != normalized_reason_tags:
            metadata["lead_events"] = _append_lead_event(
                metadata.get("lead_events"),
                event_type="outcome_updated",
                outcome_from=previous_outcome.value if previous_outcome else None,
                outcome_to=outcome.value if outcome else None,
                note=_stringify_outcome_reason_tags(normalized_reason_tags),
            )
        model.metadata = metadata

    db.update_raw_entry(entry_id, _apply)
    return get_lead(entry_id)


def update_lead_follow_up(
    entry_id: int,
    next_follow_up_at: datetime | None,
    reason: str | None,
) -> MarketplaceLead:
    entry = raw_entries.get_entry(entry_id)
    source = rss_sources.get_source(entry.source_id)
    if source is None or source.source_type != SourceType.FREELANCE_MARKETPLACE:
        raise ValueError("marketplace lead not found")

    normalized_next_follow_up_at = _ensure_utc(next_follow_up_at) if next_follow_up_at else None
    normalized_reason = reason.strip() if isinstance(reason, str) else ""

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        previous_next_follow_up_at = _to_datetime(metadata.get("next_follow_up_at"))
        previous_reason = _to_string(metadata.get("follow_up_reason"))
        if normalized_next_follow_up_at is None:
            metadata.pop("next_follow_up_at", None)
        else:
            metadata["next_follow_up_at"] = normalized_next_follow_up_at.isoformat()
        if normalized_reason:
            metadata["follow_up_reason"] = normalized_reason
        else:
            metadata.pop("follow_up_reason", None)
        if (
            previous_next_follow_up_at != normalized_next_follow_up_at
            or (previous_reason or "") != normalized_reason
        ):
            metadata["lead_events"] = _append_lead_event(
                metadata.get("lead_events"),
                event_type="follow_up_scheduled",
                note=_stringify_follow_up_schedule(normalized_next_follow_up_at, normalized_reason or None),
            )
        model.metadata = metadata

    db.update_raw_entry(entry_id, _apply)
    return get_lead(entry_id)


def bulk_update_lead_outcome(
    entry_ids: Iterable[int],
    outcome: MarketplaceLeadOutcome | None,
    reason_tags: Iterable[str] | None = None,
) -> list[MarketplaceLead]:
    updated: list[MarketplaceLead] = []
    for entry_id in entry_ids:
        updated.append(update_lead_outcome(entry_id, outcome, reason_tags))
    return updated


def backfill_lead_outcomes(
    rows: Iterable[MarketplaceLeadOutcomeBackfillRow],
) -> list[MarketplaceLead]:
    updated: list[MarketplaceLead] = []
    for row in rows:
        lead = update_lead_outcome(row.lead_id, row.outcome, row.reason_tags)
        if row.notes is not None:
            lead = update_lead_notes(row.lead_id, row.notes)
        updated.append(lead)
    return updated


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
    normalized_budget = _normalize_budget(budget, _to_string(metadata.get("engagement")))
    timeline = _to_string(metadata.get("timeline"))
    delivery_scope = _resolve_delivery_scope(item, metadata)
    tech_stack_normalized = _normalize_tech_stack(item, metadata)
    region = _resolve_region(item, metadata)
    lead_events = _to_lead_events(item, metadata)
    last_action_at = max(
        [event.created_at for event in lead_events],
        default=_ensure_utc(item.updated_at),
    )
    follow_up_anchor = _follow_up_anchor(
        lead_events,
        fallback=_ensure_utc(item.created_at),
    )
    lead_status = _to_lead_status(metadata.get("lead_status"))
    lead_outcome = _to_lead_outcome(metadata.get("lead_outcome"))
    next_follow_up_at = _resolve_next_follow_up_at(
        lead_status=lead_status,
        lead_outcome=lead_outcome,
        metadata=metadata,
        last_action_at=follow_up_anchor,
    )
    follow_up_reason = _resolve_follow_up_reason(
        lead_status=lead_status,
        lead_outcome=lead_outcome,
        metadata=metadata,
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
        normalized_budget=normalized_budget,
        budget_band=_resolve_budget_band(budget, normalized_budget),
        engagement=_to_string(metadata.get("engagement")),
        timeline=timeline,
        normalized_timeline=_normalize_timeline(timeline),
        delivery_scope=delivery_scope,
        tech_stack_normalized=tech_stack_normalized,
        location=_to_string(metadata.get("location")),
        region=region,
        timezone_fit=_resolve_timezone_fit(region, _to_string(metadata.get("location"))),
        published_at=item.published_at,
        author=item.author,
        tags=list(item.tags),
        skills=_to_string_list(metadata.get("skills")),
        link=item.link,
        lead_kind=lead_kind,
        lead_tier=lead_tier,
        tier_reason=tier_reason,
        lead_status=lead_status,
        lead_outcome=lead_outcome,
        outcome_reason_tags=_normalize_reason_tags(metadata.get("lead_outcome_reason_tags")),
        notes=_to_string(metadata.get("lead_notes")),
        next_follow_up_at=next_follow_up_at,
        follow_up_reason=follow_up_reason,
        is_follow_up_overdue=_is_follow_up_overdue(
            lead_status=lead_status,
            lead_outcome=lead_outcome,
            next_follow_up_at=next_follow_up_at,
            now=datetime.now(UTC),
        ),
        priority_score=0,
        priority_reason="尚未计算优先级。",
        last_action_at=last_action_at,
        lead_events=lead_events,
        duplicate_count=1,
        duplicate_sources=[source.name],
        first_seen_at=item.created_at,
        latest_seen_at=item.created_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _classify_lead_tier(
    source_name: str,
    item: RawEntry,
    metadata: dict[str, object],
) -> tuple[MarketplaceLeadTier, str]:
    delivery_scope = _resolve_delivery_scope(item, metadata)
    tech_stack_normalized = _normalize_tech_stack(item, metadata)
    region = _resolve_region(item, metadata)
    timezone_fit = _resolve_timezone_fit(region, _to_string(metadata.get("location")))
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
    if (
        delivery_scope
        in {
            MarketplaceDeliveryScope.WEBSITE,
            MarketplaceDeliveryScope.APP,
            MarketplaceDeliveryScope.BACKEND,
            MarketplaceDeliveryScope.PLUGIN,
            MarketplaceDeliveryScope.AUTOMATION,
            MarketplaceDeliveryScope.DATA_TOOL,
        }
        and tech_stack_normalized
        and timezone_fit is not False
    ):
        return (
            MarketplaceLeadTier.HIGH_PURITY,
            "画像字段显示交付范围明确、技术栈清晰且时区可承接，进入高纯度队列。",
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
    next_follow_up_at = _merge_follow_up_at(left.next_follow_up_at, right.next_follow_up_at)
    lead_outcome = representative.lead_outcome or alternate.lead_outcome
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
        budget_band=representative.budget_band or alternate.budget_band,
        engagement=representative.engagement or alternate.engagement,
        timeline=representative.timeline or alternate.timeline,
        normalized_timeline=representative.normalized_timeline or alternate.normalized_timeline,
        delivery_scope=representative.delivery_scope or alternate.delivery_scope,
        tech_stack_normalized=list(
            dict.fromkeys(
                [*representative.tech_stack_normalized, *alternate.tech_stack_normalized]
            )
        ),
        location=representative.location or alternate.location,
        region=representative.region or alternate.region,
        timezone_fit=_merge_timezone_fit(representative.timezone_fit, alternate.timezone_fit),
        published_at=representative.published_at or alternate.published_at,
        author=representative.author or alternate.author,
        tags=list(dict.fromkeys([*representative.tags, *alternate.tags])),
        skills=list(dict.fromkeys([*representative.skills, *alternate.skills])),
        link=representative.link or alternate.link,
        lead_kind=representative.lead_kind,
        lead_tier=representative.lead_tier,
        tier_reason=representative.tier_reason,
        lead_status=status,
        lead_outcome=lead_outcome,
        outcome_reason_tags=list(
            dict.fromkeys([*representative.outcome_reason_tags, *alternate.outcome_reason_tags])
        ),
        notes=representative.notes or alternate.notes,
        next_follow_up_at=next_follow_up_at,
        follow_up_reason=representative.follow_up_reason or alternate.follow_up_reason,
        is_follow_up_overdue=_is_follow_up_overdue(
            lead_status=status,
            lead_outcome=lead_outcome,
            next_follow_up_at=next_follow_up_at,
            now=datetime.now(UTC),
        ),
        priority_score=max(left.priority_score, right.priority_score),
        priority_reason=representative.priority_reason or alternate.priority_reason,
        last_action_at=max(left.last_action_at, right.last_action_at),
        lead_events=_merge_lead_events(left.lead_events, right.lead_events),
        duplicate_count=left.duplicate_count + right.duplicate_count,
        duplicate_sources=duplicate_sources,
        first_seen_at=min(left.first_seen_at, right.first_seen_at),
        latest_seen_at=max(left.latest_seen_at, right.latest_seen_at),
        created_at=min(left.created_at, right.created_at),
        updated_at=max(left.updated_at, right.updated_at),
    )


def _lead_sort_key(lead: MarketplaceLead) -> tuple[int, int, int, int, datetime]:
    return (
        lead.priority_score,
        1 if lead.lead_kind in _REVIEWABLE_LEAD_KINDS else 0,
        1 if lead.lead_tier == MarketplaceLeadTier.HIGH_PURITY else 0,
        _lead_status_rank(lead.lead_status),
        lead.latest_seen_at,
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

    if lead.lead_outcome == MarketplaceLeadOutcome.WON:
        score -= 60
        reasons.append("已成交")
    elif lead.lead_outcome == MarketplaceLeadOutcome.LOST:
        score -= 45
        reasons.append("已失败")
    elif lead.lead_outcome == MarketplaceLeadOutcome.NO_RESPONSE:
        score -= 36
        reasons.append("无回复")
    elif lead.lead_outcome == MarketplaceLeadOutcome.NOT_FIT:
        score -= 40
        reasons.append("不匹配")

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

    if lead.is_follow_up_overdue:
        score += 8
        reasons.append("跟进已超时")

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

    if lead.delivery_scope in {
        MarketplaceDeliveryScope.WEBSITE,
        MarketplaceDeliveryScope.APP,
        MarketplaceDeliveryScope.BACKEND,
        MarketplaceDeliveryScope.PLUGIN,
        MarketplaceDeliveryScope.AUTOMATION,
        MarketplaceDeliveryScope.DATA_TOOL,
    }:
        score += 8
        reasons.append("交付范围匹配")
    elif lead.delivery_scope == MarketplaceDeliveryScope.EMBEDDED:
        score -= 6
        reasons.append("嵌入式项目谨慎评估")

    if lead.budget_band == MarketplaceBudgetBand.LT_1K:
        score -= 6
        reasons.append("预算偏低")
    elif lead.budget_band == MarketplaceBudgetBand.ONE_K_TO_FIVE_K:
        score += 4
        reasons.append("预算带 1k-5k")
    elif lead.budget_band == MarketplaceBudgetBand.FIVE_K_TO_TWENTY_K:
        score += 10
        reasons.append("预算带 5k-20k")
    elif lead.budget_band == MarketplaceBudgetBand.GT_20K:
        score += 6
        reasons.append("高客单预算")
    elif lead.budget_band == MarketplaceBudgetBand.NEGOTIABLE:
        score += 2
        reasons.append("预算可议")

    if lead.timezone_fit is True:
        score += 8
        reasons.append("时区匹配")
    elif lead.timezone_fit is False:
        score -= 10
        reasons.append("时区不匹配")

    if lead.tech_stack_normalized:
        score += min(len(lead.tech_stack_normalized), 3) * 2
        reasons.append("技术栈清晰")

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


def _count_outcomes(leads: list[MarketplaceLead]) -> dict[str, int]:
    breakdown = {outcome.value: 0 for outcome in MarketplaceLeadOutcome}
    breakdown["unresolved"] = 0
    for lead in leads:
        if lead.lead_outcome is None:
            breakdown["unresolved"] += 1
        else:
            breakdown[lead.lead_outcome.value] += 1
    return breakdown


def _count_outcome_reasons(leads: list[MarketplaceLead]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for lead in leads:
        if lead.lead_outcome is None:
            continue
        for reason_tag in lead.outcome_reason_tags:
            breakdown[reason_tag] = breakdown.get(reason_tag, 0) + 1
    return dict(
        sorted(
            breakdown.items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
    )


def _resolve_next_follow_up_at(
    *,
    lead_status: MarketplaceLeadStatus,
    lead_outcome: MarketplaceLeadOutcome | None,
    metadata: dict[str, object],
    last_action_at: datetime,
) -> datetime | None:
    if lead_outcome is not None or lead_status not in {
        MarketplaceLeadStatus.WATCHING,
        MarketplaceLeadStatus.CONTACTED,
    }:
        return None
    explicit = _to_datetime(metadata.get("next_follow_up_at"))
    if explicit is not None:
        return explicit
    if lead_status == MarketplaceLeadStatus.WATCHING:
        return last_action_at + timedelta(days=3)
    return last_action_at + timedelta(days=5)


def _resolve_follow_up_reason(
    *,
    lead_status: MarketplaceLeadStatus,
    lead_outcome: MarketplaceLeadOutcome | None,
    metadata: dict[str, object],
) -> str | None:
    if lead_outcome is not None or lead_status not in {
        MarketplaceLeadStatus.WATCHING,
        MarketplaceLeadStatus.CONTACTED,
    }:
        return None
    explicit = _to_string(metadata.get("follow_up_reason"))
    if explicit:
        return explicit
    if lead_status == MarketplaceLeadStatus.WATCHING:
        return "watching_checkin"
    return "contacted_follow_up"


def _is_follow_up_overdue(
    *,
    lead_status: MarketplaceLeadStatus,
    lead_outcome: MarketplaceLeadOutcome | None,
    next_follow_up_at: datetime | None,
    now: datetime,
) -> bool:
    return (
        lead_outcome is None
        and lead_status in {MarketplaceLeadStatus.WATCHING, MarketplaceLeadStatus.CONTACTED}
        and next_follow_up_at is not None
        and next_follow_up_at <= now
    )


def _append_lead_event(
    raw_events: object,
    *,
    event_type: str,
    status_from: str | None = None,
    status_to: str | None = None,
    outcome_from: str | None = None,
    outcome_to: str | None = None,
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
    if outcome_from:
        event["outcome_from"] = outcome_from
    if outcome_to:
        event["outcome_to"] = outcome_to
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
                outcome_from=_to_string(raw_event.get("outcome_from")),
                outcome_to=_to_string(raw_event.get("outcome_to")),
                note=_to_string(raw_event.get("note")),
            )
        )
    events.sort(key=lambda item: item.created_at, reverse=True)
    return events


def _merge_lead_events(left: list[MarketplaceLeadEvent], right: list[MarketplaceLeadEvent]) -> list[MarketplaceLeadEvent]:
    merged: dict[
        tuple[str, datetime, str | None, str | None, str | None, str | None, str | None],
        MarketplaceLeadEvent,
    ] = {}
    for event in [*left, *right]:
        key = (
            event.event_type,
            event.created_at,
            event.status_from,
            event.status_to,
            event.outcome_from,
            event.outcome_to,
            event.note,
        )
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


def _build_source_conversion_breakdown(
    leads: list[MarketplaceLead],
) -> list[MarketplaceLeadConversionMetric]:
    grouped: dict[tuple[int, str], list[MarketplaceLead]] = {}
    for lead in leads:
        key = (lead.source_id, lead.source_name)
        grouped.setdefault(key, []).append(lead)

    metrics = [
        _build_conversion_metric(
            key=f"source:{source_id}",
            label=source_name,
            leads=items,
        )
        for (source_id, source_name), items in grouped.items()
    ]
    return _sort_conversion_metrics(metrics)


def _build_segment_conversion_breakdown(
    leads: list[MarketplaceLead],
) -> list[MarketplaceLeadConversionMetric]:
    grouped: dict[str, tuple[str, list[MarketplaceLead]]] = {}
    for tier in MarketplaceLeadTier:
        grouped[f"tier:{tier.value}"] = (
            f"queue:{tier.value}",
            [lead for lead in leads if lead.lead_tier == tier],
        )
    for kind in MarketplaceLeadKind:
        grouped[f"kind:{kind.value}"] = (
            f"kind:{kind.value}",
            [lead for lead in leads if lead.lead_kind == kind],
        )

    metrics = [
        _build_conversion_metric(key=key, label=label, leads=items)
        for key, (label, items) in grouped.items()
        if items
    ]
    return _sort_conversion_metrics(metrics)


def _build_conversion_metric(
    *,
    key: str,
    label: str,
    leads: list[MarketplaceLead],
) -> MarketplaceLeadConversionMetric:
    total = len(leads)
    won = sum(1 for lead in leads if lead.lead_outcome == MarketplaceLeadOutcome.WON)
    lost = sum(1 for lead in leads if lead.lead_outcome == MarketplaceLeadOutcome.LOST)
    no_response = sum(1 for lead in leads if lead.lead_outcome == MarketplaceLeadOutcome.NO_RESPONSE)
    not_fit = sum(1 for lead in leads if lead.lead_outcome == MarketplaceLeadOutcome.NOT_FIT)
    contacted = sum(1 for lead in leads if lead.lead_status == MarketplaceLeadStatus.CONTACTED)
    resolved = won + lost + no_response + not_fit
    resolution_rate = round(resolved / total, 4) if total else 0.0
    win_rate = round(won / resolved, 4) if resolved else 0.0
    return MarketplaceLeadConversionMetric(
        key=key,
        label=label,
        total=total,
        resolved=resolved,
        won=won,
        lost=lost,
        no_response=no_response,
        not_fit=not_fit,
        contacted=contacted,
        resolution_rate=resolution_rate,
        win_rate=win_rate,
    )


def _sort_conversion_metrics(
    metrics: list[MarketplaceLeadConversionMetric],
) -> list[MarketplaceLeadConversionMetric]:
    metrics.sort(
        key=lambda item: (
            item.won,
            item.resolved,
            item.contacted,
            item.total,
            item.label,
        ),
        reverse=True,
    )
    return metrics


def _build_todo_queue(leads: list[MarketplaceLead], now: datetime, todo_sort: str = "default") -> list[MarketplaceLeadReminder]:
    reminders: list[MarketplaceLeadReminder] = []
    for lead in leads:
        if (
            lead.lead_kind not in _REVIEWABLE_LEAD_KINDS
            or lead.lead_status == MarketplaceLeadStatus.IGNORED
            or lead.lead_outcome is not None
        ):
            continue
        reminder_anchor = _last_follow_up_at(lead)
        stale_days = max((now - reminder_anchor).days, 0)
        if lead.is_follow_up_overdue and lead.next_follow_up_at is not None:
            overdue_days = max((now - lead.next_follow_up_at).days, 0)
            reminders.append(
                MarketplaceLeadReminder(
                    lead_id=lead.id,
                    title=lead.title,
                    source_name=lead.source_name,
                    lead_status=lead.lead_status,
                    priority_score=lead.priority_score,
                    reminder_type="follow_up_overdue",
                    severity="high" if overdue_days >= 3 else "medium",
                    message=f"下次跟进已超时 {overdue_days} 天，原因：{lead.follow_up_reason or 'scheduled_follow_up'}。",
                    last_action_at=lead.next_follow_up_at,
                    stale_days=overdue_days,
                )
            )
            continue
        if lead.lead_status == MarketplaceLeadStatus.NEW and lead.priority_score >= 85:
            reminders.append(
                MarketplaceLeadReminder(
                    lead_id=lead.id,
                    title=lead.title,
                    source_name=lead.source_name,
                    lead_status=lead.lead_status,
                    priority_score=lead.priority_score,
                    reminder_type="new_high_priority",
                    severity="high",
                    message="高优先级新线索，建议今天查看。",
                    last_action_at=reminder_anchor,
                    stale_days=stale_days,
                )
            )
            continue
        if lead.lead_status == MarketplaceLeadStatus.WATCHING and stale_days >= 3:
            reminders.append(
                MarketplaceLeadReminder(
                    lead_id=lead.id,
                    title=lead.title,
                    source_name=lead.source_name,
                    lead_status=lead.lead_status,
                    priority_score=lead.priority_score,
                    reminder_type="watching_stale",
                    severity="high" if stale_days >= 7 else "medium",
                    message=f"已关注 {stale_days} 天未更新，建议推进下一步。",
                    last_action_at=reminder_anchor,
                    stale_days=stale_days,
                )
            )
            continue
        if lead.lead_status == MarketplaceLeadStatus.CONTACTED and stale_days >= 5:
            reminders.append(
                MarketplaceLeadReminder(
                    lead_id=lead.id,
                    title=lead.title,
                    source_name=lead.source_name,
                    lead_status=lead.lead_status,
                    priority_score=lead.priority_score,
                    reminder_type="contacted_stale",
                    severity="high" if stale_days >= 10 else "medium",
                    message=f"已联系 {stale_days} 天未跟进，建议确认回复。",
                    last_action_at=reminder_anchor,
                    stale_days=stale_days,
                )
            )
    if todo_sort == "newest_first":
        reminders.sort(
            key=lambda item: (0 - _reminder_severity_rank(item.severity), item.last_action_at),
            reverse=True,
        )
    elif todo_sort == "oldest_first":
        reminders.sort(
            key=lambda item: (
                0 - _reminder_severity_rank(item.severity),
                item.stale_days,
                item.last_action_at,
            ),
            reverse=True,
        )
    elif todo_sort == "priority":
        reminders.sort(
            key=lambda item: (
                0 - _reminder_severity_rank(item.severity),
                item.priority_score,
                item.last_action_at,
            ),
            reverse=True,
        )
    else:
        reminders.sort(
            key=lambda item: (
                _reminder_severity_rank(item.severity),
                item.priority_score,
                item.stale_days,
                item.last_action_at,
            ),
            reverse=True,
        )
    return reminders


def _build_source_recommendations(
    metrics: list[MarketplaceLeadSourceMetric],
    conversions: list[MarketplaceLeadConversionMetric],
) -> list[MarketplaceSourceRecommendation]:
    recommendations: list[MarketplaceSourceRecommendation] = []
    conversions_by_source_id: dict[int, MarketplaceLeadConversionMetric] = {}
    for metric in conversions:
        if not metric.key.startswith("source:"):
            continue
        try:
            source_id = int(metric.key.split(":", 1)[1])
        except ValueError:
            continue
        conversions_by_source_id[source_id] = metric

    for item in metrics:
        total = max(item.total, 1)
        high_purity_ratio = item.high_purity / total
        reviewable_ratio = item.reviewable / total
        full_time_ratio = item.full_time_job / total
        conversion = conversions_by_source_id.get(item.source_id)
        resolved = conversion.resolved if conversion is not None else 0
        won = conversion.won if conversion is not None else 0
        no_response = conversion.no_response if conversion is not None else 0
        not_fit = conversion.not_fit if conversion is not None else 0
        contacted = conversion.contacted if conversion is not None else item.contacted
        win_rate = conversion.win_rate if conversion is not None else 0.0

        if item.total >= 2 and full_time_ratio >= 0.5:
            recommendations.append(
                MarketplaceSourceRecommendation(
                    source_id=item.source_id,
                    source_name=item.source_name,
                    action="pause_candidate",
                    severity="high",
                    reason="全职招聘噪音占比过高，建议暂停或大幅收紧过滤规则。",
                )
            )
            continue
        if item.total >= 3 and item.high_purity == 0:
            recommendations.append(
                MarketplaceSourceRecommendation(
                    source_id=item.source_id,
                    source_name=item.source_name,
                    action="pause_candidate",
                    severity="high",
                    reason="连续产出但没有高纯度线索，建议暂停并寻找替代来源。",
                )
            )
            continue
        if resolved >= 2 and won >= 1 and win_rate >= 0.3 and high_purity_ratio >= 0.5:
            recommendations.append(
                MarketplaceSourceRecommendation(
                    source_id=item.source_id,
                    source_name=item.source_name,
                    action="expand_similar",
                    severity="high",
                    reason="已有真实成交且赢单率稳定，值得扩同类平台或关键词。",
                )
            )
            continue
        if resolved >= 2 and won == 0 and (not_fit + no_response) >= resolved:
            action = "pause_candidate" if full_time_ratio >= 0.3 or not_fit >= no_response else "lower_frequency"
            severity = "high" if action == "pause_candidate" else "medium"
            reason = (
                "已有多条结案结果但主要是不匹配，建议暂停并重做来源过滤。"
                if action == "pause_candidate"
                else "已有多条结案结果但多数无回复/失败，建议降频并观察后续样本。"
            )
            recommendations.append(
                MarketplaceSourceRecommendation(
                    source_id=item.source_id,
                    source_name=item.source_name,
                    action=action,
                    severity=severity,
                    reason=reason,
                )
            )
            continue
        if contacted >= 2 and resolved == 0 and high_purity_ratio >= 0.4:
            recommendations.append(
                MarketplaceSourceRecommendation(
                    source_id=item.source_id,
                    source_name=item.source_name,
                    action="needs_outcome_data",
                    severity="medium",
                    reason="已有跟进动作但还缺少结案样本，建议先补结果数据再判断是否扩源。",
                )
            )
            continue
        if item.total >= 3 and reviewable_ratio < 0.6:
            recommendations.append(
                MarketplaceSourceRecommendation(
                    source_id=item.source_id,
                    source_name=item.source_name,
                    action="lower_frequency",
                    severity="medium",
                    reason="可跟进占比偏低，建议降频抓取并继续观察。",
                )
            )
            continue
        if item.high_purity >= 1 and item.reviewable >= 1:
            recommendations.append(
                MarketplaceSourceRecommendation(
                    source_id=item.source_id,
                    source_name=item.source_name,
                    action="keep",
                    severity="medium",
                    reason="当前产出稳定，可继续保留并观察后续转化。",
                )
            )
    recommendations.sort(
        key=lambda item: (_recommendation_severity_rank(item.severity), _recommendation_action_rank(item.action)),
        reverse=True,
    )
    return recommendations[:6]


def _count_todo_queue(reminders: list[MarketplaceLeadReminder]) -> dict[str, int]:
    return {
        "total": len(reminders),
        "high": sum(1 for item in reminders if item.severity == "high"),
        "medium": sum(1 for item in reminders if item.severity == "medium"),
        "new_high_priority": sum(1 for item in reminders if item.reminder_type == "new_high_priority"),
        "watching_stale": sum(1 for item in reminders if item.reminder_type == "watching_stale"),
        "contacted_stale": sum(1 for item in reminders if item.reminder_type == "contacted_stale"),
        "follow_up_overdue": sum(1 for item in reminders if item.reminder_type == "follow_up_overdue"),
    }


def _last_follow_up_at(lead: MarketplaceLead) -> datetime:
    return _follow_up_anchor(lead.lead_events, fallback=lead.last_action_at)


def _follow_up_anchor(events: list[MarketplaceLeadEvent], fallback: datetime) -> datetime:
    follow_up_events = [event.created_at for event in events if event.event_type != "captured"]
    if follow_up_events:
        return max(follow_up_events)
    return fallback


def _reminder_severity_rank(value: str) -> int:
    return {
        "high": 2,
        "medium": 1,
        "low": 0,
    }.get(value, 0)


def _recommendation_severity_rank(value: str) -> int:
    return {
        "high": 2,
        "medium": 1,
        "low": 0,
    }.get(value, 0)


def _recommendation_action_rank(value: str) -> int:
    return {
        "expand_similar": 3,
        "pause_candidate": 3,
        "needs_outcome_data": 2,
        "lower_frequency": 2,
        "keep": 1,
    }.get(value, 0)


def _recommendation_action_label(value: str) -> str:
    return {
        "expand_similar": "扩同类来源",
        "pause_candidate": "建议暂停",
        "needs_outcome_data": "需要补结果数据",
        "lower_frequency": "建议降频",
        "keep": "继续保留",
    }.get(value, value)


def _ratio_to_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _merge_follow_up_at(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _to_lead_status(value: object) -> MarketplaceLeadStatus:
    if value is None:
        return MarketplaceLeadStatus.NEW
    try:
        return MarketplaceLeadStatus(str(value))
    except ValueError:
        return MarketplaceLeadStatus.NEW


def _to_lead_outcome(value: object) -> MarketplaceLeadOutcome | None:
    if value is None:
        return None
    try:
        return MarketplaceLeadOutcome(str(value))
    except ValueError:
        return None


def _to_datetime(value: object) -> datetime | None:
    text = _to_string(value)
    if not text:
        return None
    try:
        return _ensure_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _normalize_reason_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[;,|]", value)
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        raw_items = [str(item) for item in value if item is not None]
    else:
        raw_items = [str(value)]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        cleaned = _NON_WORD_RE.sub("_", item.strip().lower()).strip("_")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _stringify_outcome_reason_tags(reason_tags: list[str]) -> str | None:
    if not reason_tags:
        return None
    return "reasons: " + ", ".join(reason_tags)


def _stringify_follow_up_schedule(next_follow_up_at: datetime | None, reason: str | None) -> str | None:
    if next_follow_up_at is None and not reason:
        return None
    parts: list[str] = []
    if next_follow_up_at is not None:
        parts.append(f"due: {next_follow_up_at.isoformat()}")
    if reason:
        parts.append(f"reason: {reason}")
    return " / ".join(parts)


def _resolve_budget_band(
    raw_budget: str | None,
    normalized_budget: str | None,
) -> MarketplaceBudgetBand | None:
    text = (normalized_budget or raw_budget or "").strip().lower()
    if not text:
        return None
    if text in {"待商议", "面议", "open", "negotiable"}:
        return MarketplaceBudgetBand.NEGOTIABLE

    normalized = text.replace("千", "k")
    values: list[float] = []
    for match in re.finditer(r"(?P<value>\d[\d,.]*)(?P<suffix>k)?", normalized):
        value = float(match.group("value").replace(",", ""))
        if match.group("suffix"):
            value *= 1000
        values.append(value)
    if not values:
        return None

    amount = max(values)
    if "/hr" in normalized:
        amount *= 80

    if amount < 1000:
        return MarketplaceBudgetBand.LT_1K
    if amount <= 5000:
        return MarketplaceBudgetBand.ONE_K_TO_FIVE_K
    if amount <= 20000:
        return MarketplaceBudgetBand.FIVE_K_TO_TWENTY_K
    return MarketplaceBudgetBand.GT_20K


def _resolve_delivery_scope(
    item: RawEntry,
    metadata: dict[str, object],
) -> MarketplaceDeliveryScope | None:
    haystack = _profile_haystack(item, metadata)
    if _contains_any(haystack, _DELIVERY_SCOPE_KEYWORDS[MarketplaceDeliveryScope.EMBEDDED]):
        return MarketplaceDeliveryScope.EMBEDDED
    if _contains_any(haystack, _DELIVERY_SCOPE_KEYWORDS[MarketplaceDeliveryScope.PLUGIN]):
        return MarketplaceDeliveryScope.PLUGIN
    if _contains_any(haystack, _DELIVERY_SCOPE_KEYWORDS[MarketplaceDeliveryScope.AUTOMATION]):
        return MarketplaceDeliveryScope.AUTOMATION
    if _contains_any(haystack, _DELIVERY_SCOPE_KEYWORDS[MarketplaceDeliveryScope.APP]):
        return MarketplaceDeliveryScope.APP
    if _contains_any(haystack, _DELIVERY_SCOPE_KEYWORDS[MarketplaceDeliveryScope.WEBSITE]):
        return MarketplaceDeliveryScope.WEBSITE
    if _contains_any(haystack, _DELIVERY_SCOPE_KEYWORDS[MarketplaceDeliveryScope.BACKEND]):
        return MarketplaceDeliveryScope.BACKEND
    if _contains_any(haystack, _DELIVERY_SCOPE_KEYWORDS[MarketplaceDeliveryScope.DATA_TOOL]):
        return MarketplaceDeliveryScope.DATA_TOOL
    return None


def _normalize_tech_stack(item: RawEntry, metadata: dict[str, object]) -> list[str]:
    haystack = _profile_haystack(item, metadata)
    matched: list[str] = []
    for normalized_name, variants in _TECH_STACK_ALIASES.items():
        if _contains_any(haystack, variants):
            matched.append(normalized_name)
    return matched


def _resolve_region(
    item: RawEntry,
    metadata: dict[str, object],
) -> MarketplaceRegion | None:
    location = " ".join(
        filter(
            None,
            [
                _to_string(metadata.get("location")),
                item.title,
                item.summary or "",
            ],
        )
    ).lower()
    if not location:
        return None
    if _contains_any(location, _GLOBAL_REGION_KEYWORDS):
        return MarketplaceRegion.GLOBAL

    has_china = _contains_any(location, _CHINA_REGION_KEYWORDS)
    has_apac = _contains_any(location, _APAC_REGION_KEYWORDS)
    has_west = _contains_any(location, _EUROPE_AMERICAS_REGION_KEYWORDS)
    if has_china:
        return MarketplaceRegion.CHINA
    if has_apac and has_west:
        return MarketplaceRegion.GLOBAL
    if has_apac:
        return MarketplaceRegion.APAC
    if has_west:
        return MarketplaceRegion.EUROPE_AMERICAS
    return None


def _resolve_timezone_fit(
    region: MarketplaceRegion | None,
    location: str | None,
) -> bool | None:
    if region in {MarketplaceRegion.CHINA, MarketplaceRegion.APAC, MarketplaceRegion.GLOBAL}:
        return True
    if region == MarketplaceRegion.EUROPE_AMERICAS:
        return False
    normalized_location = (location or "").strip().lower()
    if _contains_any(normalized_location, _GLOBAL_REGION_KEYWORDS):
        return True
    return None


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


def _profile_haystack(item: RawEntry, metadata: dict[str, object]) -> str:
    return " ".join(
        filter(
            None,
            [
                item.title.lower(),
                (item.summary or "").lower(),
                (item.content or "").lower(),
                (_to_string(metadata.get("category")) or "").lower(),
                (_to_string(metadata.get("engagement")) or "").lower(),
                (_to_string(metadata.get("location")) or "").lower(),
                " ".join(skill.lower() for skill in _to_string_list(metadata.get("skills"))),
            ],
        )
    )


def _contains_any(haystack: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in haystack for candidate in candidates)


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


def _merge_timezone_fit(left: bool | None, right: bool | None) -> bool | None:
    if left is None:
        return right
    if right is None:
        return left
    return left or right


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

_DELIVERY_SCOPE_KEYWORDS: dict[MarketplaceDeliveryScope, tuple[str, ...]] = {
    MarketplaceDeliveryScope.WEBSITE: (
        "website",
        "web app",
        "web development",
        "landing page",
        "wordpress",
        "cms",
        "webflow",
        "shopify",
        "frontend",
        "网页",
        "网站",
        "官网",
        "商城",
        "hubl",
    ),
    MarketplaceDeliveryScope.APP: (
        "mobile app",
        "mobile",
        "app",
        "ios",
        "android",
        "flutter",
        "react native",
        "小程序",
        "鸿蒙",
    ),
    MarketplaceDeliveryScope.BACKEND: (
        "backend",
        "api",
        "database",
        "postgres",
        "postgresql",
        "mysql",
        "crm",
        "erp",
        "saas",
        "admin dashboard",
        "后台",
        "后端",
        "数据库",
    ),
    MarketplaceDeliveryScope.PLUGIN: (
        "plugin",
        "extension",
        "woocommerce",
        "chrome extension",
        "shopify app",
        "wordpress plugin",
        "插件",
        "扩展",
    ),
    MarketplaceDeliveryScope.AUTOMATION: (
        "automation",
        "workflow",
        "zapier",
        "make.com",
        "n8n",
        "bot",
        "scraper",
        "爬虫",
        "自动化",
        "集成",
    ),
    MarketplaceDeliveryScope.DATA_TOOL: (
        "dashboard",
        "analytics",
        "reporting",
        "etl",
        "data pipeline",
        "data tool",
        "scraping",
        "bi",
        "数据采集",
        "数据分析",
        "报表",
    ),
    MarketplaceDeliveryScope.EMBEDDED: (
        "embedded",
        "firmware",
        "hardware",
        "iot",
        "oem",
        "kiosk",
        "device owner",
        "rk3568",
        "嵌入式",
        "硬件",
    ),
}

_TECH_STACK_ALIASES: dict[str, tuple[str, ...]] = {
    "react": ("react",),
    "nextjs": ("next.js", "nextjs"),
    "vue": ("vue", "vue.js", "vuejs"),
    "angular": ("angular",),
    "typescript": ("typescript",),
    "javascript": ("javascript",),
    "nodejs": ("node.js", "nodejs"),
    "python": ("python",),
    "django": ("django",),
    "fastapi": ("fastapi",),
    "flask": ("flask",),
    "php": ("php",),
    "laravel": ("laravel",),
    "wordpress": ("wordpress", "woocommerce"),
    "java": ("java",),
    "spring": ("spring",),
    "go": ("golang", "grpc"),
    "dotnet": (".net", "c#", "asp.net"),
    "postgres": ("postgres", "postgresql"),
    "mysql": ("mysql",),
    "mongodb": ("mongodb", "mongo"),
    "docker": ("docker",),
    "kubernetes": ("kubernetes", "k8s"),
    "graphql": ("graphql",),
    "android": ("android",),
    "ios": ("ios",),
    "flutter": ("flutter",),
    "react_native": ("react native",),
    "shopify": ("shopify",),
    "webflow": ("webflow",),
    "llm": ("openai", "rag", "langchain", "ai agent"),
}

_CHINA_REGION_KEYWORDS = (
    "china",
    "beijing",
    "shanghai",
    "shenzhen",
    "guangzhou",
    "hangzhou",
    "中国",
    "国内",
    "北京",
    "上海",
    "深圳",
    "广州",
    "杭州",
)

_APAC_REGION_KEYWORDS = (
    "apac",
    "asia",
    "oceania",
    "australia",
    "new zealand",
    "singapore",
    "philippines",
    "india",
    "japan",
    "korea",
    "hong kong",
    "taiwan",
    "malaysia",
    "thailand",
    "vietnam",
)

_EUROPE_AMERICAS_REGION_KEYWORDS = (
    "europe",
    "emea",
    "uk",
    "united kingdom",
    "germany",
    "france",
    "spain",
    "italy",
    "netherlands",
    "portugal",
    "america",
    "americas",
    "usa",
    "us only",
    "united states",
    "canada",
    "latam",
    "latin america",
)

_GLOBAL_REGION_KEYWORDS = (
    "worldwide",
    "global",
    "remote",
    "anywhere",
    "anywhere in the world",
)
