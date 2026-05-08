"""客户雷达 API 模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.models import SourceType
from pydantic import BaseModel, ConfigDict


class CustomerSegmentEnum(str, Enum):
    GOVERNMENT_DOCS = "government_docs"
    REAL_ESTATE_DOCS = "real_estate_docs"
    COMPLIANCE_KYC = "compliance_kyc"
    LEGAL_CONTRACTS = "legal_contracts"
    TRAINING_LMS = "training_lms"
    DOCUMENT_OPS = "document_ops"
    OUTREACH_RESEARCH = "outreach_research"


class RecommendedActionEnum(str, Enum):
    CONTACT_NOW = "contact_now"
    REVIEW_FIRST = "review_first"
    WATCH = "watch"


class CredibilityLevelEnum(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CustomerOpportunityRead(BaseModel):
    id: str
    candidate_need_id: int
    raw_entry_id: int
    title: str
    source_name: str
    source_type: SourceType
    platform: str | None = None
    link: str | None = None
    published_at: datetime | None = None
    customer_segment: CustomerSegmentEnum
    fit_score: int
    credibility_score: int
    credibility_level: CredibilityLevelEnum
    credibility_reasons: list[str]
    risk_flags: list[str]
    recommended_action: RecommendedActionEnum
    pain_summary: str
    product_angle: str
    evidence: list[str]
    matched_signals: list[str]
    budget_signal: str | None = None
    outreach_draft: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerRadarSummaryRead(BaseModel):
    total_candidates: int
    contact_now: int
    review_first: int
    watch: int
    average_fit_score: float
    average_credibility_score: float
    segment_breakdown: dict[str, int]
    source_breakdown: dict[str, int]

    model_config = ConfigDict(from_attributes=True)


class CustomerRadarList(BaseModel):
    total: int
    summary: CustomerRadarSummaryRead
    items: list[CustomerOpportunityRead]
