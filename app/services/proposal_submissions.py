"""Safe, review-first proposal preparation for marketplace leads.

This module deliberately stops before an external platform submission. It prepares
an auditable draft, lets the user approve it, and records a submission only after
the user confirms that the platform action has completed.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, overload

from app.db.storage import db
from app.models import RawEntry
from app.services import marketplace_leads, raw_entries, rss_sources

_METADATA_KEY = "proposal_submission"
_WHITESPACE_RE = re.compile(r"\s+")
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


class ProposalStatus(StrEnum):
    DRAFT_READY = "draft_ready"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    REPLIED = "replied"
    INTERVIEW = "interview"
    WON = "won"
    LOST = "lost"
    SKIPPED = "skipped"


class InvalidProposalTransition(ValueError):
    """Raised when a proposal status transition would corrupt the funnel."""


@dataclass(frozen=True, slots=True)
class OfferProfile:
    id: str
    name_zh: str
    name_en: str
    keywords: tuple[str, ...]
    capabilities_zh: tuple[str, ...]
    capabilities_en: tuple[str, ...]
    price_usd: str
    price_cny: str
    delivery_days: str


@dataclass(slots=True)
class ProposalSubmission:
    lead_id: int
    status: ProposalStatus
    offer_id: str
    offer_name: str
    language: str
    application_type: str
    chinese_brief: str
    communication_burden: str
    communication_reasons: list[str]
    fit_score: int
    matched_capabilities: list[str]
    risk_flags: list[str]
    suggested_price: str
    delivery_days: str
    proposal_text: str
    questions: list[str]
    source_url: str | None
    submission_mode: str
    can_auto_submit: bool
    requires_manual_confirmation: bool
    generated_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None


@dataclass(slots=True)
class ProposalPreparationResult:
    created: int
    skipped: int
    items: list[ProposalSubmission]


_OFFERS: tuple[OfferProfile, ...] = (
    OfferProfile(
        id="document_data_automation",
        name_zh="文档与数据自动化",
        name_en="Document and data automation",
        keywords=(
            "pdf", "excel", "ocr", "table", "spreadsheet", "data extraction",
            "extract", "rename", "document", "表格", "文档", "提取", "识别",
        ),
        capabilities_zh=("Python 批处理", "PDF/Excel 结构化提取", "OCR 与数据校验", "可复现交付脚本"),
        capabilities_en=("Python batch processing", "PDF/Excel extraction", "OCR and validation", "reproducible delivery tooling"),
        price_usd="$180–$800",
        price_cny="¥1,200–¥5,800",
        delivery_days="1–5",
    ),
    OfferProfile(
        id="crawler_repair",
        name_zh="爬虫修复与采集自动化",
        name_en="Crawler repair and collection automation",
        keywords=(
            "crawler", "scraper", "scraping", "selenium", "beautifulsoup", "playwright",
            "crawl", "spider", "爬虫", "采集", "抓取", "反爬",
        ),
        capabilities_zh=("Python 爬虫诊断", "动态页面采集", "下载与解析流水线", "失败重试和日志"),
        capabilities_en=("Python crawler diagnostics", "dynamic-page extraction", "download and parsing pipelines", "retries and observability"),
        price_usd="$250–$900",
        price_cny="¥1,800–¥6,500",
        delivery_days="2–5",
    ),
    OfferProfile(
        id="api_middleware",
        name_zh="API 与中间件集成",
        name_en="API and middleware integration",
        keywords=(
            "api", "rest", "xml", "webhook", "middleware", "integration", "connector",
            "sync", "接口", "中间件", "集成", "同步", "对接",
        ),
        capabilities_zh=("REST/API 对接", "XML/JSON 转换", "鉴权与幂等", "Docker 化部署"),
        capabilities_en=("REST/API integration", "XML/JSON transformation", "authentication and idempotency", "Dockerized delivery"),
        price_usd="$600–$2,000",
        price_cny="¥4,500–¥15,000",
        delivery_days="5–10",
    ),
    OfferProfile(
        id="business_system",
        name_zh="企业管理后台与业务系统",
        name_en="Internal admin and business systems",
        keywords=(
            "dashboard", "admin", "management system", "crm", "erp", "workflow", "portal",
            "后台", "管理系统", "业务系统", "工作流", "看板", "平台",
        ),
        capabilities_zh=("Vue/React 管理前端", "FastAPI/Node 后端", "PostgreSQL 数据模型", "Docker 部署"),
        capabilities_en=("Vue/React admin frontend", "FastAPI/Node backend", "PostgreSQL data modeling", "Docker deployment"),
        price_usd="$1,200–$4,000",
        price_cny="¥8,000–¥28,000",
        delivery_days="7–20",
    ),
    OfferProfile(
        id="mobile_mvp",
        name_zh="移动端 MVP",
        name_en="Mobile MVP",
        keywords=(
            "ios", "android", "mobile", "flutter", "react native", "harmonyos", "app",
            "移动端", "小程序", "鸿蒙", "安卓", "应用",
        ),
        capabilities_zh=("iOS/鸿蒙端实现", "移动端 API 集成", "MVP 范围拆分", "打包与交付检查"),
        capabilities_en=("iOS/HarmonyOS implementation", "mobile API integration", "MVP scoping", "packaging and delivery checks"),
        price_usd="$1,000–$4,500",
        price_cny="¥7,000–¥32,000",
        delivery_days="7–25",
    ),
    OfferProfile(
        id="web_ai_automation",
        name_zh="Web 与 AI 自动化应用",
        name_en="Web and AI automation application",
        keywords=(
            "react", "vue", "next.js", "nextjs", "frontend", "website", "web app", "llm",
            "agent", "automation", "网页", "网站", "前端", "自动化", "智能体",
        ),
        capabilities_zh=("Vue/React 前端", "Python/FastAPI 服务", "LLM/Agent 工作流", "自动化测试与部署"),
        capabilities_en=("Vue/React frontend", "Python/FastAPI services", "LLM/agent workflows", "automated testing and deployment"),
        price_usd="$600–$2,500",
        price_cny="¥4,000–¥18,000",
        delivery_days="5–15",
    ),
)

_ALLOWED_TRANSITIONS: dict[ProposalStatus, set[ProposalStatus]] = {
    ProposalStatus.DRAFT_READY: {ProposalStatus.APPROVED, ProposalStatus.SKIPPED},
    ProposalStatus.APPROVED: {
        ProposalStatus.DRAFT_READY,
        ProposalStatus.SUBMITTED,
        ProposalStatus.SKIPPED,
    },
    ProposalStatus.SUBMITTED: {
        ProposalStatus.REPLIED,
        ProposalStatus.INTERVIEW,
        ProposalStatus.WON,
        ProposalStatus.LOST,
    },
    ProposalStatus.REPLIED: {
        ProposalStatus.INTERVIEW,
        ProposalStatus.WON,
        ProposalStatus.LOST,
    },
    ProposalStatus.INTERVIEW: {ProposalStatus.WON, ProposalStatus.LOST},
    ProposalStatus.WON: set(),
    ProposalStatus.LOST: set(),
    ProposalStatus.SKIPPED: {ProposalStatus.DRAFT_READY},
}


def get_proposal(lead_id: int) -> ProposalSubmission | None:
    entry = _get_marketplace_entry(lead_id)
    raw = (entry.metadata or {}).get(_METADATA_KEY)
    return _proposal_from_metadata(lead_id, raw)


def generate_proposal(lead_id: int, *, force: bool = False) -> ProposalSubmission:
    entry = _get_marketplace_entry(lead_id)
    existing = _proposal_from_metadata(lead_id, (entry.metadata or {}).get(_METADATA_KEY))
    if existing is not None and not force:
        return existing
    if existing is not None and existing.status not in {
        ProposalStatus.DRAFT_READY,
        ProposalStatus.APPROVED,
        ProposalStatus.SKIPPED,
    }:
        raise InvalidProposalTransition("submitted proposals cannot be regenerated")

    lead = marketplace_leads.get_lead(lead_id)
    proposal = _build_proposal(lead)
    now = datetime.now(UTC)

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        metadata[_METADATA_KEY] = _proposal_to_metadata(proposal)
        metadata["lead_events"] = _append_event(
            metadata.get("lead_events"),
            "proposal_regenerated" if existing is not None else "proposal_generated",
            f"{proposal.offer_name} · fit {proposal.fit_score}",
            now,
        )
        model.metadata = metadata

    db.update_raw_entry(lead_id, _apply)
    return get_proposal(lead_id) or proposal


def prepare_proposals(
    *,
    limit: int = 5,
    min_priority_score: int = 65,
) -> ProposalPreparationResult:
    result = marketplace_leads.query_leads(
        skip=0,
        limit=500,
        reviewable_only=True,
        todo_sort="priority",
    )
    created: list[ProposalSubmission] = []
    skipped = 0
    for lead in result.items:
        if len(created) >= limit:
            break
        if lead.priority_score < min_priority_score or not _eligible_for_preparation(lead):
            skipped += 1
            continue
        existing = get_proposal(lead.id)
        if existing is not None:
            skipped += 1
            continue
        proposal = _build_proposal(lead)
        if (
            {
                "high_compliance",
                "anti_bot_evasion",
                "high_communication",
                "live_interview",
                "rights_circumvention",
            }
            & set(proposal.risk_flags)
            or proposal.fit_score < 55
        ):
            skipped += 1
            continue
        created.append(generate_proposal(lead.id))
    return ProposalPreparationResult(created=len(created), skipped=skipped, items=created)


def update_proposal_status(lead_id: int, status: ProposalStatus) -> ProposalSubmission:
    entry = _get_marketplace_entry(lead_id)
    current = _proposal_from_metadata(lead_id, (entry.metadata or {}).get(_METADATA_KEY))
    if current is None:
        raise KeyError(lead_id)
    if status == current.status:
        return current
    if status not in _ALLOWED_TRANSITIONS[current.status]:
        raise InvalidProposalTransition(f"cannot move proposal from {current.status} to {status}")

    now = datetime.now(UTC)

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        raw = dict(metadata.get(_METADATA_KEY) or {})
        raw["status"] = status.value
        raw["updated_at"] = now.isoformat()
        if status == ProposalStatus.SUBMITTED:
            raw["submitted_at"] = now.isoformat()
            previous_lead_status = str(metadata.get("lead_status") or "new")
            metadata["lead_status"] = marketplace_leads.MarketplaceLeadStatus.CONTACTED.value
            metadata["next_follow_up_at"] = (now + timedelta(days=3)).isoformat()
            metadata["follow_up_reason"] = "proposal_sent"
            metadata["lead_events"] = _append_event(
                metadata.get("lead_events"),
                "status_changed",
                None,
                now,
                status_from=previous_lead_status,
                status_to=marketplace_leads.MarketplaceLeadStatus.CONTACTED.value,
            )
            metadata["lead_events"] = _append_event(
                metadata.get("lead_events"),
                "follow_up_scheduled",
                "proposal_sent",
                now,
            )
        elif status in {ProposalStatus.WON, ProposalStatus.LOST}:
            outcome = (
                marketplace_leads.MarketplaceLeadOutcome.WON
                if status == ProposalStatus.WON
                else marketplace_leads.MarketplaceLeadOutcome.LOST
            )
            previous_outcome = metadata.get("lead_outcome")
            metadata["lead_outcome"] = outcome.value
            metadata.pop("next_follow_up_at", None)
            metadata.pop("follow_up_reason", None)
            metadata["lead_events"] = _append_event(
                metadata.get("lead_events"),
                "outcome_updated",
                "proposal_funnel",
                now,
                outcome_from=str(previous_outcome) if previous_outcome else None,
                outcome_to=outcome.value,
            )
        metadata[_METADATA_KEY] = raw
        metadata["lead_events"] = _append_event(
            metadata.get("lead_events"),
            "proposal_status_changed",
            f"{current.status.value} -> {status.value}",
            now,
        )
        model.metadata = metadata

    db.update_raw_entry(lead_id, _apply)
    return get_proposal(lead_id) or current


def update_proposal_content(
    lead_id: int,
    *,
    proposal_text: str,
    suggested_price: str | None = None,
    delivery_days: str | None = None,
) -> ProposalSubmission:
    entry = _get_marketplace_entry(lead_id)
    current = _proposal_from_metadata(lead_id, (entry.metadata or {}).get(_METADATA_KEY))
    if current is None:
        raise KeyError(lead_id)
    if current.status in {
        ProposalStatus.SUBMITTED,
        ProposalStatus.REPLIED,
        ProposalStatus.INTERVIEW,
        ProposalStatus.WON,
        ProposalStatus.LOST,
    }:
        raise InvalidProposalTransition("submitted proposals cannot be edited")
    cleaned_text = proposal_text.strip()
    if not cleaned_text:
        raise ValueError("proposal text cannot be empty")
    now = datetime.now(UTC)

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        raw = dict(metadata.get(_METADATA_KEY) or {})
        raw["proposal_text"] = cleaned_text
        if suggested_price is not None and suggested_price.strip():
            raw["suggested_price"] = suggested_price.strip()
        if delivery_days is not None and delivery_days.strip():
            raw["delivery_days"] = delivery_days.strip()
        raw["status"] = ProposalStatus.DRAFT_READY.value
        raw["updated_at"] = now.isoformat()
        metadata[_METADATA_KEY] = raw
        metadata["lead_events"] = _append_event(
            metadata.get("lead_events"),
            "proposal_edited",
            "approval reset" if current.status == ProposalStatus.APPROVED else None,
            now,
        )
        model.metadata = metadata

    db.update_raw_entry(lead_id, _apply)
    return get_proposal(lead_id) or current


def _build_proposal(lead: marketplace_leads.MarketplaceLead) -> ProposalSubmission:
    haystack = _lead_haystack(lead)
    language = "zh" if len(_CHINESE_RE.findall(haystack)) >= 4 else "en"
    offer, matched_keywords = _match_offer(haystack)
    risk_flags = _risk_flags(lead, haystack)
    capabilities = list(offer.capabilities_zh if language == "zh" else offer.capabilities_en)
    fit_score = min(95, 52 + min(len(matched_keywords), 5) * 8 + (8 if lead.lead_tier.value == "high_purity" else 0))
    if risk_flags:
        fit_score = max(25, fit_score - min(20, len(risk_flags) * 5))
    price = offer.price_cny if language == "zh" else offer.price_usd
    questions = _questions(language, risk_flags)
    proposal_text = _proposal_text(
        lead=lead,
        offer=offer,
        language=language,
        capabilities=capabilities,
        price=price,
        questions=questions,
    )
    now = datetime.now(UTC)
    return ProposalSubmission(
        lead_id=lead.id,
        status=ProposalStatus.DRAFT_READY,
        offer_id=offer.id,
        offer_name=offer.name_zh if language == "zh" else offer.name_en,
        language=language,
        application_type=(
            "remote_part_time_application"
            if lead.opportunity_lane
            == marketplace_leads.MarketplaceOpportunityLane.REMOTE_PART_TIME
            else "project_proposal"
        ),
        chinese_brief=lead.decision_summary_zh,
        communication_burden=lead.communication_burden.value,
        communication_reasons=list(lead.communication_reasons),
        fit_score=fit_score,
        matched_capabilities=capabilities,
        risk_flags=risk_flags,
        suggested_price=price,
        delivery_days=offer.delivery_days,
        proposal_text=proposal_text,
        questions=questions,
        source_url=lead.link,
        submission_mode="manual_platform" if lead.link else "manual_review",
        can_auto_submit=False,
        requires_manual_confirmation=True,
        generated_at=now,
        updated_at=now,
    )


def _match_offer(haystack: str) -> tuple[OfferProfile, list[str]]:
    ranked: list[tuple[int, int, OfferProfile, list[str]]] = []
    for index, offer in enumerate(_OFFERS):
        matches = [keyword for keyword in offer.keywords if keyword.lower() in haystack]
        ranked.append((len(matches), -index, offer, matches))
    _, _, selected, matches = max(ranked, key=lambda item: (item[0], item[1]))
    return selected, matches


def _proposal_text(
    *,
    lead: marketplace_leads.MarketplaceLead,
    offer: OfferProfile,
    language: str,
    capabilities: list[str],
    price: str,
    questions: list[str],
) -> str:
    scope = _compact_text(lead.description or lead.summary or lead.title, 180)
    if (
        lead.opportunity_lane
        == marketplace_leads.MarketplaceOpportunityLane.REMOTE_PART_TIME
    ):
        workload = lead.weekly_hours or "a mutually agreed weekly capacity"
        if language == "zh":
            return "\n".join(
                [
                    f"你好，我认真看了《{lead.title}》这份远程兼职需求。",
                    f"我理解主要工作是：{scope}",
                    "",
                    f"这与我的“{offer.name_zh}”能力匹配，可覆盖：{'、'.join(capabilities)}。",
                    "我更适合通过文字异步同步进度，并按可验收的小任务持续交付。",
                    "",
                    "建议先从一个小型付费任务开始：",
                    "1. 明确首个任务、输入输出和验收标准；",
                    "2. 交付可运行结果、源码和简短说明；",
                    "3. 双方确认协作节奏后，再安排后续每周任务。",
                    "",
                    f"职位中提到的工时：{workload}。具体每周投入和报价可在任务范围明确后确认。",
                    "开始前我需要确认：" + "；".join(questions) + "。",
                ]
            )
        return "\n".join(
            [
                f"Hi, I reviewed the remote part-time opportunity for “{lead.title}”.",
                f"My understanding of the main work is: {scope}",
                "",
                f"This matches my {offer.name_en.lower()} experience, including {', '.join(capabilities)}.",
                "I work well with written, asynchronous updates and small, verifiable deliverables.",
                "",
                "I suggest starting with one small paid task:",
                "1. Confirm the first task, expected output, and acceptance criteria;",
                "2. Deliver a working result, source code, and concise documentation;",
                "3. Agree on the ongoing weekly workflow after the first delivery is accepted.",
                "",
                f"The listed workload is {workload}. We can confirm weekly capacity and rate after clarifying the task scope.",
                "Before starting, I would like to confirm " + "; ".join(questions) + ".",
            ]
        )
    if language == "zh":
        return "\n".join(
            [
                f"你好，我认真看了《{lead.title}》的需求。",
                f"我理解当前核心范围是：{scope}",
                "",
                f"这类项目与我的“{offer.name_zh}”交付能力匹配，可直接覆盖：{'、'.join(capabilities)}。",
                "",
                "建议按三个步骤交付：",
                "1. 用真实或脱敏样例确认输入、输出和异常边界；",
                "2. 先交付可运行版本及结果样例，再根据反馈修正；",
                "3. 完成批量验证，并交付源码、运行说明和验收清单。",
                "",
                f"预计周期：{offer.delivery_days} 个工作日；建议报价：{price}（确认完整范围后锁定）。",
                "开始前我需要确认：" + "；".join(questions) + "。",
                "如果方便，可以先给我一个脱敏样例，我会先说明实现路径和验收方式。",
            ]
        )
    return "\n".join(
        [
            f"Hi, I reviewed the requirements for “{lead.title}”.",
            f"My understanding of the core scope is: {scope}",
            "",
            f"This is a strong match for my {offer.name_en.lower()} delivery capability, including {', '.join(capabilities)}.",
            "",
            "I suggest delivering it in three steps:",
            "1. Confirm the input, expected output, and edge cases with a representative sample.",
            "2. Deliver a working version and sample results for early feedback.",
            "3. Run batch validation and hand over source code, run instructions, and an acceptance checklist.",
            "",
            f"Estimated delivery: {offer.delivery_days} business days. Suggested budget: {price}, finalized after scope confirmation.",
            "Before starting, I would confirm: " + "; ".join(questions) + ".",
            "If you can share a sanitized sample, I can first outline the implementation and acceptance approach.",
        ]
    )


def _questions(language: str, risk_flags: list[str]) -> list[str]:
    if language == "zh":
        questions = ["是否有代表性样例与明确验收结果", "目标运行环境和交付形式", "截止时间与优先级"]
        if "high_compliance" in risk_flags or "sensitive_data" in risk_flags:
            questions.append("数据是否可脱敏并在客户环境内处理")
        return questions
    questions = [
        "whether a representative sample and acceptance output are available",
        "the target runtime and preferred delivery format",
        "the deadline and priority order",
    ]
    if "high_compliance" in risk_flags or "sensitive_data" in risk_flags:
        questions.append("whether data can be sanitized and processed inside the client environment")
    return questions


def _risk_flags(lead: marketplace_leads.MarketplaceLead, haystack: str) -> list[str]:
    flags: list[str] = []
    if any(term in haystack for term in ("hipaa", "phi", "baa", "gdpr", "医疗数据", "患者", "隐私数据")):
        flags.append("high_compliance")
    if any(term in haystack for term in ("patient", "personal data", "confidential", "敏感", "隐私", "身份证")):
        flags.append("sensitive_data")
    if not lead.link:
        flags.append("missing_source_link")
    if lead.budget_band == marketplace_leads.MarketplaceBudgetBand.LT_1K:
        flags.append("low_budget")
    if not lead.description and not lead.summary:
        flags.append("unclear_scope")
    if any(term in haystack for term in ("copy-paste", "copy paste", "data entry", "复制粘贴", "数据录入")):
        flags.append("low_value_manual")
    if any(
        term in haystack
        for term in (
            "evade bot",
            "evade basic bot",
            "bypass bot",
            "bypass captcha",
            "rotating fingerprints",
            "proxy pools",
            "规避反爬",
            "绕过验证码",
            "指纹池",
        )
    ):
        flags.append("anti_bot_evasion")
    if any(
        term in haystack
        for term in marketplace_leads._DISALLOWED_SCOPE_MARKERS
    ):
        flags.append("rights_circumvention")
    if (
        lead.communication_burden
        == marketplace_leads.MarketplaceCommunicationBurden.HIGH
    ):
        flags.append("high_communication")
    if lead.requires_live_interview:
        flags.append("live_interview")
    return flags


def _eligible_for_preparation(lead: marketplace_leads.MarketplaceLead) -> bool:
    latest_seen_at = lead.latest_seen_at
    if latest_seen_at.tzinfo is None:
        latest_seen_at = latest_seen_at.replace(tzinfo=UTC)
    haystack = _lead_haystack(lead)
    blocked_terms = (
        "copy-paste",
        "copy paste",
        "data entry",
        "复制粘贴",
        "数据录入",
        "evade bot",
        "evade basic bot",
        "bypass bot",
        "bypass captcha",
        "rotating fingerprints",
        "proxy pools",
        "规避反爬",
        "绕过验证码",
        "指纹池",
        *marketplace_leads._DISALLOWED_SCOPE_MARKERS,
        *marketplace_leads._LOW_VALUE_OR_RISKY_MARKERS,
    )
    return (
        lead.link is not None
        and latest_seen_at >= datetime.now(UTC) - timedelta(days=14)
        and not any(term in haystack for term in blocked_terms)
        and lead.lead_kind
        in {
            marketplace_leads.MarketplaceLeadKind.PROJECT,
            marketplace_leads.MarketplaceLeadKind.CONTRACT_ROLE,
        }
        and lead.opportunity_lane
        in {
            marketplace_leads.MarketplaceOpportunityLane.PROJECT_OUTSOURCING,
            marketplace_leads.MarketplaceOpportunityLane.REMOTE_PART_TIME,
        }
        and lead.communication_burden
        != marketplace_leads.MarketplaceCommunicationBurden.HIGH
        and not lead.requires_live_interview
        and lead.lead_status
        not in {
            marketplace_leads.MarketplaceLeadStatus.CONTACTED,
            marketplace_leads.MarketplaceLeadStatus.IGNORED,
            marketplace_leads.MarketplaceLeadStatus.ARCHIVED,
        }
        and lead.lead_outcome is None
    )


def _lead_haystack(lead: marketplace_leads.MarketplaceLead) -> str:
    return " ".join(
        [
            lead.title,
            lead.summary or "",
            lead.description or "",
            lead.category or "",
            " ".join(lead.tags),
            " ".join(lead.skills),
            " ".join(lead.tech_stack_normalized),
        ]
    ).lower()


def _get_marketplace_entry(lead_id: int) -> RawEntry:
    entry = raw_entries.get_entry(lead_id)
    source = rss_sources.get_source(entry.source_id)
    if source is None or source.source_type.value != "freelance_marketplace":
        raise ValueError("marketplace lead not found")
    return entry


def _proposal_to_metadata(proposal: ProposalSubmission) -> dict[str, Any]:
    payload = asdict(proposal)
    payload["status"] = proposal.status.value
    for key in ("generated_at", "updated_at", "submitted_at"):
        value = payload.get(key)
        payload[key] = value.isoformat() if isinstance(value, datetime) else None
    return payload


def _proposal_from_metadata(lead_id: int, raw: object) -> ProposalSubmission | None:
    if not isinstance(raw, dict):
        return None
    try:
        return ProposalSubmission(
            lead_id=lead_id,
            status=ProposalStatus(str(raw["status"])),
            offer_id=str(raw["offer_id"]),
            offer_name=str(raw["offer_name"]),
            language=str(raw.get("language") or "zh"),
            application_type=str(raw.get("application_type") or "project_proposal"),
            chinese_brief=str(raw.get("chinese_brief") or ""),
            communication_burden=str(raw.get("communication_burden") or "unknown"),
            communication_reasons=_string_list(raw.get("communication_reasons")),
            fit_score=int(raw.get("fit_score") or 0),
            matched_capabilities=_string_list(raw.get("matched_capabilities")),
            risk_flags=_string_list(raw.get("risk_flags")),
            suggested_price=str(raw.get("suggested_price") or ""),
            delivery_days=str(raw.get("delivery_days") or ""),
            proposal_text=str(raw.get("proposal_text") or ""),
            questions=_string_list(raw.get("questions")),
            source_url=str(raw["source_url"]) if raw.get("source_url") else None,
            submission_mode=str(raw.get("submission_mode") or "manual_review"),
            can_auto_submit=bool(raw.get("can_auto_submit", False)),
            requires_manual_confirmation=bool(raw.get("requires_manual_confirmation", True)),
            generated_at=_parse_datetime(raw.get("generated_at")),
            updated_at=_parse_datetime(raw.get("updated_at")),
            submitted_at=_parse_datetime(raw.get("submitted_at"), required=False),
        )
    except (KeyError, TypeError, ValueError):
        return None


@overload
def _parse_datetime(value: object, *, required: Literal[True] = True) -> datetime: ...


@overload
def _parse_datetime(value: object, *, required: Literal[False]) -> datetime | None: ...


def _parse_datetime(value: object, *, required: bool = True) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    if required:
        raise ValueError("missing datetime")
    return None


def _append_event(
    raw_events: object,
    event_type: str,
    note: str | None,
    created_at: datetime,
    *,
    status_from: str | None = None,
    status_to: str | None = None,
    outcome_from: str | None = None,
    outcome_to: str | None = None,
) -> list[dict[str, object]]:
    events = list(raw_events) if isinstance(raw_events, list) else []
    event: dict[str, object] = {"event_type": event_type, "created_at": created_at.isoformat()}
    for key, value in (
        ("note", note),
        ("status_from", status_from),
        ("status_to", status_to),
        ("outcome_from", outcome_from),
        ("outcome_to", outcome_to),
    ):
        if value:
            event[key] = value
    events.append(event)
    return events


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _compact_text(value: str, limit: int) -> str:
    compact = _WHITESPACE_RE.sub(" ", value).strip()
    return compact if len(compact) <= limit else f"{compact[: limit - 1].rstrip()}…"
