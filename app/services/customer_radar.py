"""DocReview 客户线索自动发现与推荐。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import func, or_, select

from app.db.entities import CandidateNeedEntity, RawEntryEntity, RssSourceEntity
from app.db.session import SessionLocal
from app.models import (
    CandidateNeed,
    CandidateNeedStatus,
    CandidateNeedType,
    RawEntry,
    RawEntryStatus,
    RssSource,
    SourceStatus,
    SourceType,
)


class CustomerSegment(StrEnum):
    GOVERNMENT_DOCS = "government_docs"
    REAL_ESTATE_DOCS = "real_estate_docs"
    COMPLIANCE_KYC = "compliance_kyc"
    LEGAL_CONTRACTS = "legal_contracts"
    TRAINING_LMS = "training_lms"
    DOCUMENT_OPS = "document_ops"
    OUTREACH_RESEARCH = "outreach_research"


class RecommendedAction(StrEnum):
    CONTACT_NOW = "contact_now"
    REVIEW_FIRST = "review_first"
    WATCH = "watch"


class CredibilityLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(slots=True)
class CredibilityAssessment:
    score: int
    level: CredibilityLevel
    reasons: list[str]
    risk_flags: list[str]


@dataclass(slots=True)
class CustomerOpportunity:
    id: str
    candidate_need_id: int
    raw_entry_id: int
    title: str
    source_name: str
    source_type: SourceType
    platform: str | None
    link: str | None
    published_at: datetime | None
    customer_segment: CustomerSegment
    fit_score: int
    credibility_score: int
    credibility_level: CredibilityLevel
    credibility_reasons: list[str]
    risk_flags: list[str]
    recommended_action: RecommendedAction
    pain_summary: str
    product_angle: str
    evidence: list[str]
    matched_signals: list[str]
    budget_signal: str | None
    outreach_draft: str
    created_at: datetime


@dataclass(slots=True)
class CustomerRadarSummary:
    total_candidates: int
    contact_now: int
    review_first: int
    watch: int
    average_fit_score: float
    average_credibility_score: float
    segment_breakdown: dict[str, int]
    source_breakdown: dict[str, int]


@dataclass(slots=True)
class CustomerRadarResult:
    total: int
    summary: CustomerRadarSummary
    items: list[CustomerOpportunity]


_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str], int], ...] = (
    ("pdf_document", re.compile(r"\b(pdf|pdfs|documents|document files?|docx|scan|scanned)\b", re.I), 18),
    ("ocr_extraction", re.compile(r"\b(ocr|extract|extraction|parse|scrap(?:e|ing)|crawl)\b", re.I), 16),
    ("manual_review", re.compile(r"\b(manual|manually|review|validation|validate|inspect|check|copy|paste|data entry|tedious|time consuming)\b", re.I), 18),
    ("structured_output", re.compile(r"\b(metadata|field|fields|structured|json|csv|spreadsheet|google sheets|excel|database)\b", re.I), 12),
    ("workflow_integration", re.compile(r"\b(api|sync|integration|integrate|drive|sharepoint|crm|moodle|lms|erp|export)\b", re.I), 12),
    ("ai_query", re.compile(r"\b(ai query|question answering|searchable|semantic|chat|llm)\b", re.I), 8),
    ("budget", re.compile(r"(\$\s?\d|£\s?\d|€\s?\d|预算|budget)", re.I), 10),
)

_SEGMENT_PATTERNS: tuple[tuple[CustomerSegment, re.Pattern[str], str], ...] = (
    (
        CustomerSegment.GOVERNMENT_DOCS,
        re.compile(r"\b(council|government|public sector|planning application|agenda|minutes|tender|procurement)\b", re.I),
        "政府/公共资料监控与结构化",
    ),
    (
        CustomerSegment.REAL_ESTATE_DOCS,
        re.compile(r"\b(real estate|property|properties|housing|lot number|parcel|planning application|物业|房产|地产)\b", re.I),
        "房产/物业文档匹配与表格同步",
    ),
    (
        CustomerSegment.COMPLIANCE_KYC,
        re.compile(r"\b(kyc|aml|compliance|identity|risk|audit|insurance|financial records|合规|审核)\b", re.I),
        "KYC/合规材料抽取与审核队列",
    ),
    (
        CustomerSegment.LEGAL_CONTRACTS,
        re.compile(r"\b(contract|legal|law|lawmatics|clio|agreement|clause|律师|合同)\b", re.I),
        "合同/律所资料字段抽取与复核",
    ),
    (
        CustomerSegment.TRAINING_LMS,
        re.compile(r"\b(moodle|lms|training|course|completion|grade|certificate|esr|培训|成绩)\b", re.I),
        "培训记录同步与完成状态结构化",
    ),
    (
        CustomerSegment.OUTREACH_RESEARCH,
        re.compile(r"\b(reddit|outreach|lead gen|prospect|linkedin|community|influencer|competitor tracking)\b", re.I),
        "社区/市场线索研究自动化",
    ),
)

_SOURCE_BOOST = {
    SourceType.FREELANCE_MARKETPLACE: 18,
    SourceType.REDDIT: 10,
    SourceType.HACKER_NEWS: 5,
    SourceType.GITHUB_ISSUES: -5,
    SourceType.RSS: -8,
}

_TYPE_BOOST = {
    CandidateNeedType.WORKFLOW_PAIN: 12,
    CandidateNeedType.TOOL_SEEKING: 10,
    CandidateNeedType.FEATURE_GAP: 8,
    CandidateNeedType.MARKET_SIGNAL: 2,
    CandidateNeedType.BUG_REPORT: -10,
}


def query_opportunities(
    *,
    search: str | None = None,
    source_type: SourceType | None = None,
    segment: CustomerSegment | None = None,
    action: RecommendedAction | None = None,
    min_score: int = 45,
    skip: int = 0,
    limit: int = 30,
) -> CustomerRadarResult:
    """从候选需求中实时计算 DocReview 方向的客户机会。"""

    opportunities: list[CustomerOpportunity] = []
    normalized_search = search.lower().strip() if search else None

    for need, entry, source in _iter_candidate_contexts(
        search=normalized_search,
        source_type=source_type,
    ):
        opportunity = _build_opportunity(need, entry, source)
        if opportunity.fit_score < min_score:
            continue
        if segment is not None and opportunity.customer_segment != segment:
            continue
        if action is not None and opportunity.recommended_action != action:
            continue
        if normalized_search and normalized_search not in _search_blob(opportunity, entry).lower():
            continue
        opportunities.append(opportunity)

    opportunities.sort(
        key=lambda item: (
            item.credibility_score,
            item.fit_score,
            1 if item.recommended_action == RecommendedAction.CONTACT_NOW else 0,
            item.published_at or item.created_at,
        ),
        reverse=True,
    )
    total = len(opportunities)
    page_items = opportunities[skip : skip + limit]
    return CustomerRadarResult(
        total=total,
        summary=_summarize(opportunities),
        items=page_items,
    )


def _iter_candidate_contexts(
    *,
    search: str | None = None,
    source_type: SourceType | None = None,
) -> list[tuple[CandidateNeed, RawEntry, RssSource]]:
    """一次性读取客户雷达需要的候选需求上下文，避免每条线索额外查询。"""

    with SessionLocal() as session:
        stmt = (
            select(CandidateNeedEntity, RawEntryEntity, RssSourceEntity)
            .join(RawEntryEntity, CandidateNeedEntity.raw_entry_id == RawEntryEntity.id)
            .join(RssSourceEntity, RawEntryEntity.source_id == RssSourceEntity.id)
            .order_by(CandidateNeedEntity.created_at.desc())
        )
        if source_type is not None:
            stmt = stmt.where(RssSourceEntity.source_type == source_type.value)
        if search:
            keyword = f"%{search}%"
            stmt = stmt.where(
                or_(
                    func.lower(RawEntryEntity.title).like(keyword),
                    func.lower(RawEntryEntity.summary).like(keyword),
                    func.lower(RawEntryEntity.content).like(keyword),
                    func.lower(RssSourceEntity.name).like(keyword),
                    func.lower(CandidateNeedEntity.summary).like(keyword),
                    func.lower(CandidateNeedEntity.problem_statement).like(keyword),
                    func.lower(CandidateNeedEntity.target_users).like(keyword),
                    func.lower(CandidateNeedEntity.value_proposition).like(keyword),
                    func.lower(CandidateNeedEntity.notes).like(keyword),
                )
            )

        rows = session.execute(stmt).all()
        return [
            (
                _candidate_need_from_entity(need_entity),
                _raw_entry_from_entity(entry_entity),
                _source_from_entity(source_entity),
            )
            for need_entity, entry_entity, source_entity in rows
        ]


def _source_from_entity(entity: RssSourceEntity) -> RssSource:
    return RssSource(
        id=entity.id,
        name=entity.name,
        url=entity.url,
        category=entity.category,
        frequency=entity.frequency,
        source_type=SourceType(entity.source_type),
        config=dict(entity.config or {}),
        status=SourceStatus(entity.status),
        last_fetched_at=entity.last_fetched_at,
        etag=entity.etag,
        last_modified=entity.last_modified,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _raw_entry_from_entity(entity: RawEntryEntity) -> RawEntry:
    return RawEntry(
        id=entity.id,
        source_id=entity.source_id,
        guid=entity.guid,
        title=entity.title,
        content_hash=entity.content_hash,
        summary=entity.summary,
        content=entity.content,
        link=entity.link,
        published_at=entity.published_at,
        author=entity.author,
        tags=tuple(entity.tags or []),
        metadata=dict(entity.details or {}),
        status=RawEntryStatus(entity.status),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _candidate_need_from_entity(entity: CandidateNeedEntity) -> CandidateNeed:
    return CandidateNeed(
        id=entity.id,
        raw_entry_id=entity.raw_entry_id,
        summary=entity.summary,
        problem_statement=entity.problem_statement,
        target_users=entity.target_users,
        value_proposition=entity.value_proposition,
        competition=entity.competition,
        candidate_type=CandidateNeedType(entity.candidate_type)
        if entity.candidate_type
        else None,
        review_readiness=entity.review_readiness,
        confidence=entity.confidence,
        rule_score=entity.rule_score,
        status=CandidateNeedStatus(entity.status),
        notes=entity.notes,
        synced_at=entity.synced_at,
        sync_error=entity.sync_error,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _build_opportunity(
    need: CandidateNeed,
    entry: RawEntry,
    source: RssSource,
) -> CustomerOpportunity:
    text = _compose_text(need, entry)
    matched_signals: list[str] = []
    evidence: list[str] = []
    score = 0

    for signal, pattern, points in _SIGNAL_PATTERNS:
        match = pattern.search(text)
        if match:
            matched_signals.append(signal)
            evidence.append(_evidence_snippet(text, match.start()))
            score += points

    segment, segment_angle, segment_points = _classify_segment(text)
    score += segment_points
    score += _SOURCE_BOOST.get(source.source_type, 0)
    if need.candidate_type is not None:
        score += _TYPE_BOOST.get(need.candidate_type, 0)
    score += int((need.review_readiness or 0) * 8)
    score += int((need.rule_score or 0) * 8)

    if _has_budget_signal(entry):
        score += 8
    if not _has_doc_review_intent(text, matched_signals, segment):
        score -= 70
    if segment == CustomerSegment.OUTREACH_RESEARCH:
        score -= 25
    if source.source_type == SourceType.RSS and not _has_strong_direct_intent(text):
        score -= 15
    score = max(0, min(100, score))

    pain_summary = _first_non_empty(
        need.problem_statement,
        need.summary,
        entry.summary,
        entry.title,
    )
    platform = _metadata_string(entry, "platform")
    budget = _metadata_string(entry, "budget") or _extract_budget(entry.summary)
    product_angle = _product_angle(segment, segment_angle)
    credibility = _assess_credibility(
        need=need,
        entry=entry,
        source=source,
        matched_signals=matched_signals,
        text=text,
        budget_signal=budget,
    )
    action = _recommended_action(
        score,
        source.source_type,
        matched_signals,
        credibility.score,
    )

    return CustomerOpportunity(
        id=f"need-{need.id}",
        candidate_need_id=need.id,
        raw_entry_id=entry.id,
        title=entry.title,
        source_name=source.name,
        source_type=source.source_type,
        platform=platform,
        link=entry.link,
        published_at=entry.published_at,
        customer_segment=segment,
        fit_score=score,
        credibility_score=credibility.score,
        credibility_level=credibility.level,
        credibility_reasons=credibility.reasons,
        risk_flags=credibility.risk_flags,
        recommended_action=action,
        pain_summary=_truncate(pain_summary, 320),
        product_angle=product_angle,
        evidence=_unique([_truncate(item, 220) for item in evidence])[:4],
        matched_signals=matched_signals,
        budget_signal=budget,
        outreach_draft=_build_outreach_draft(entry, pain_summary, product_angle),
        created_at=need.created_at,
    )


def _classify_segment(text: str) -> tuple[CustomerSegment, str, int]:
    for segment, pattern, angle in _SEGMENT_PATTERNS:
        if pattern.search(text):
            return segment, angle, 15
    return CustomerSegment.DOCUMENT_OPS, "通用文档抽取、复核与导出", 6


def _recommended_action(
    score: int,
    source_type: SourceType,
    matched_signals: list[str],
    credibility_score: int,
) -> RecommendedAction:
    if (
        score >= 78
        and credibility_score >= 70
        and source_type in {SourceType.FREELANCE_MARKETPLACE, SourceType.REDDIT}
        and "manual_review" in matched_signals
    ):
        return RecommendedAction.CONTACT_NOW
    if score >= 62 and credibility_score >= 50:
        return RecommendedAction.REVIEW_FIRST
    return RecommendedAction.WATCH


def _summarize(items: list[CustomerOpportunity]) -> CustomerRadarSummary:
    segment_breakdown: dict[str, int] = {}
    source_breakdown: dict[str, int] = {}
    for item in items:
        segment_breakdown[item.customer_segment.value] = (
            segment_breakdown.get(item.customer_segment.value, 0) + 1
        )
        source_breakdown[item.source_type.value] = source_breakdown.get(item.source_type.value, 0) + 1

    total = len(items)
    average = round(sum(item.fit_score for item in items) / total, 1) if total else 0.0
    average_credibility = (
        round(sum(item.credibility_score for item in items) / total, 1) if total else 0.0
    )
    return CustomerRadarSummary(
        total_candidates=total,
        contact_now=sum(1 for item in items if item.recommended_action == RecommendedAction.CONTACT_NOW),
        review_first=sum(1 for item in items if item.recommended_action == RecommendedAction.REVIEW_FIRST),
        watch=sum(1 for item in items if item.recommended_action == RecommendedAction.WATCH),
        average_fit_score=average,
        average_credibility_score=average_credibility,
        segment_breakdown=segment_breakdown,
        source_breakdown=source_breakdown,
    )


def _compose_text(need: CandidateNeed, entry: RawEntry) -> str:
    values = [
        entry.title,
        entry.summary,
        entry.content,
        need.summary,
        need.problem_statement,
        need.target_users,
        need.value_proposition,
        " ".join(entry.tags),
        " ".join(str(value) for value in entry.metadata.values() if isinstance(value, (str, int, float))),
    ]
    return " ".join(value for value in values if value)


def _search_blob(opportunity: CustomerOpportunity, entry: RawEntry) -> str:
    return " ".join(
        value
        for value in (
            opportunity.title,
            opportunity.source_name,
            opportunity.platform,
            opportunity.pain_summary,
            opportunity.product_angle,
            entry.summary,
            entry.content,
        )
        if value
    )


def _product_angle(segment: CustomerSegment, label: str) -> str:
    if segment == CustomerSegment.OUTREACH_RESEARCH:
        return "客户雷达：自动发现社区/市场信号、评分并生成半自动联系草稿。"
    return f"DocReview AI：{label}，覆盖抓取、字段抽取、人工复核和导出。"


def _assess_credibility(
    *,
    need: CandidateNeed,
    entry: RawEntry,
    source: RssSource,
    matched_signals: list[str],
    text: str,
    budget_signal: str | None,
) -> CredibilityAssessment:
    score = 35
    reasons: list[str] = []
    risk_flags: list[str] = []

    if source.source_type == SourceType.FREELANCE_MARKETPLACE:
        score += 20
        reasons.append("来自外包/项目平台，通常具备直接购买意图")
    elif source.source_type == SourceType.REDDIT:
        score += 6
        risk_flags.append("社区讨论需要二次确认是否是买方需求")
    elif source.source_type == SourceType.RSS:
        score -= 12
        risk_flags.append("RSS 内容可能是文章或资讯，不一定是客户需求")

    if source.category == "docreview-customer-discovery":
        score += 10
        reasons.append("来自 DocReview 专用高意图来源")

    if _has_buyer_intent(text):
        score += 15
        reasons.append("文本里有明确需求/交付/寻找服务的表达")
    else:
        score -= 10
        risk_flags.append("缺少明确买方意图，需要人工确认")

    if budget_signal:
        score += 12
        reasons.append("出现预算或金额信号")
        amount = _extract_budget_amount(budget_signal)
        if amount is not None:
            if amount >= 100:
                score += 6
                reasons.append("预算达到可验证样品项目门槛")
            elif amount < 20:
                score -= 25
                risk_flags.append("预算极低，更像一次性小任务")
            elif amount < 50:
                score -= 15
                risk_flags.append("预算偏低，可能难以转成产品型客户")
    else:
        risk_flags.append("未看到预算信号")

    if {"pdf_document", "ocr_extraction"}.issubset(matched_signals):
        score += 10
        reasons.append("同时命中文档对象和抽取/解析动作")
    if {"manual_review", "structured_output"}.issubset(matched_signals):
        score += 15
        reasons.append("同时命中人工复核和结构化输出")
    elif "manual_review" in matched_signals or "structured_output" in matched_signals:
        score += 6
    else:
        score -= 15
        risk_flags.append("缺少人工复核或结构化输出信号")

    if "workflow_integration" in matched_signals:
        score += 8
        reasons.append("包含系统集成/同步/导出场景")

    if need.candidate_type in {CandidateNeedType.WORKFLOW_PAIN, CandidateNeedType.TOOL_SEEKING}:
        score += 8
        reasons.append("候选需求类型偏向工作流痛点或找工具")

    if _looks_like_research_or_content(text):
        score -= 25
        risk_flags.append("更像文章、市场讨论或产品验证，不一定是待采购客户")

    if len(text) < 180:
        score -= 8
        risk_flags.append("原始描述较短，证据不足")

    normalized = max(0, min(100, score))
    if normalized >= 75:
        level = CredibilityLevel.HIGH
    elif normalized >= 55:
        level = CredibilityLevel.MEDIUM
    else:
        level = CredibilityLevel.LOW

    return CredibilityAssessment(
        score=normalized,
        level=level,
        reasons=_unique(reasons)[:5],
        risk_flags=_unique(risk_flags)[:5],
    )


def _build_outreach_draft(entry: RawEntry, pain_summary: str, product_angle: str) -> str:
    title = _truncate(entry.title, 110)
    pain = _truncate(pain_summary, 170)
    return (
        f"Hi, I saw your post/project about \"{title}\". "
        f"It looks like the painful part is: {pain}. "
        f"We are prototyping {product_angle} "
        "If useful, I can run a small sample with 5-10 real documents and show the review workflow before any commitment."
    )


def _has_budget_signal(entry: RawEntry) -> bool:
    return bool(_metadata_string(entry, "budget") or _extract_budget(entry.summary) or _extract_budget(entry.content))


def _has_strong_direct_intent(text: str) -> bool:
    return bool(
        re.search(
            r"\b(need|looking for|we require|we are looking|would you pay|manual|manually|pain|tedious|time consuming)\b",
            text,
            flags=re.I,
        )
    )


def _has_buyer_intent(text: str) -> bool:
    return bool(
        re.search(
            r"\b(we need|need someone|looking for|we require|we are looking|seeking|project overview|scope of work|deliverables|required to|freelancer|build|create|develop|预算|需要|寻找|开发|搭建|对接)\b",
            text,
            flags=re.I,
        )
    )


def _looks_like_research_or_content(text: str) -> bool:
    return bool(
        re.search(
            r"\b(blog|tutorial|guide|case study|build saas|high user count|low conversion|would you pay|what is the #1 feature|do i just accept|newsletter|article)\b",
            text,
            flags=re.I,
        )
    )


def _has_doc_review_intent(
    text: str,
    matched_signals: list[str],
    segment: CustomerSegment,
) -> bool:
    if "ocr_extraction" in matched_signals and (
        "pdf_document" in matched_signals
        or "manual_review" in matched_signals
        or "structured_output" in matched_signals
    ):
        return True
    if re.search(
        r"\b(pdf|pdfs|documents|document files?|contract|kyc|council|agenda|minutes|moodle|lms|google drive|sheets)\b.{0,160}\b(extract|scrap(?:e|ing)|crawl|metadata|field|match|sync|export|query|validation|validate)\b",
        text,
        flags=re.I | re.S,
    ):
        return True
    if re.search(
        r"\b(extract|scrap(?:e|ing)|crawl|metadata|field|match|sync|export|query|validation|validate)\b.{0,160}\b(pdf|pdfs|documents|document files?|contract|kyc|council|agenda|minutes|moodle|lms|google drive|sheets)\b",
        text,
        flags=re.I | re.S,
    ):
        return True
    return segment in {
        CustomerSegment.REAL_ESTATE_DOCS,
        CustomerSegment.COMPLIANCE_KYC,
        CustomerSegment.LEGAL_CONTRACTS,
        CustomerSegment.TRAINING_LMS,
    } and "manual_review" in matched_signals


def _metadata_string(entry: RawEntry, key: str) -> str | None:
    value = entry.metadata.get(key)
    return str(value) if isinstance(value, (str, int, float)) and str(value).strip() else None


def _extract_budget(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\$\s?\d[\d,.]*(?:k)?|£\s?\d[\d,.]*(?:k)?|€\s?\d[\d,.]*(?:k)?)", value, re.I)
    return match.group(1) if match else None


def _extract_budget_amount(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"[\$£€]\s?(\d[\d,]*(?:\.\d+)?)(k)?", value, re.I)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    if match.group(2):
        amount *= 1000
    return amount


def _evidence_snippet(text: str, offset: int) -> str:
    start = max(0, offset - 90)
    end = min(len(text), offset + 160)
    return " ".join(text[start:end].split())


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return "未提供明确痛点摘要"


def _truncate(value: str, length: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= length:
        return cleaned
    return f"{cleaned[: length - 1].rstrip()}…"


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
