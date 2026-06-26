"""Document Ops reconciliation API schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentOpsScenarioEnum(str, Enum):
    CONTRACTOR_INVOICE_RECONCILIATION = "contractor_invoice_reconciliation"


class DocumentOpsExceptionTypeEnum(str, Enum):
    MISSING_REFERENCE_ITEM = "missing_reference_item"
    MISSING_INVOICE_ITEM = "missing_invoice_item"
    UNIT_PRICE_MISMATCH = "unit_price_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"
    AMOUNT_MISMATCH = "amount_mismatch"
    TOTAL_AMOUNT_MISMATCH = "total_amount_mismatch"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    LOW_CONFIDENCE_MATCH = "low_confidence_match"


class DocumentOpsSeverityEnum(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DocumentOpsReviewStatusEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class DocumentOpsMatchTypeEnum(str, Enum):
    EXACT_LINE_ID = "exact_line_id"
    EXACT_DESCRIPTION = "exact_description"
    FUZZY_DESCRIPTION = "fuzzy_description"


class DocumentOpsLineItemInput(BaseModel):
    line_id: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    source_row: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class DocumentOpsLineItemRead(BaseModel):
    line_id: str
    description: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    source: str
    source_row: int
    normalized_description: str
    raw: dict[str, Any]
    parse_warnings: list[str]

    model_config = ConfigDict(from_attributes=True)


class DocumentOpsExceptionRead(BaseModel):
    id: str
    type: DocumentOpsExceptionTypeEnum
    severity: DocumentOpsSeverityEnum
    message: str
    reference_line_id: str | None = None
    invoice_line_id: str | None = None
    expected: str | None = None
    actual: str | None = None
    difference: float | None = None
    confidence: float
    needs_review: bool
    review_status: DocumentOpsReviewStatusEnum
    reviewer_note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentOpsMatchRead(BaseModel):
    id: str
    reference_item: DocumentOpsLineItemRead
    invoice_item: DocumentOpsLineItemRead
    match_type: DocumentOpsMatchTypeEnum
    confidence: float
    needs_review: bool
    review_status: DocumentOpsReviewStatusEnum
    reviewer_note: str | None = None
    exception_ids: list[str]

    model_config = ConfigDict(from_attributes=True)


class DocumentOpsReviewItemRead(BaseModel):
    id: str
    item_type: str
    reason: str
    confidence: float

    model_config = ConfigDict(from_attributes=True)


class DocumentOpsSummaryRead(BaseModel):
    reference_count: int
    invoice_count: int
    matched_count: int
    exception_count: int
    needs_review_count: int
    reference_total: float
    invoice_total: float
    total_difference: float

    model_config = ConfigDict(from_attributes=True)


class DocumentOpsSpikeConclusionRead(BaseModel):
    feasible: bool
    recommendation: str
    validated: list[str]
    remaining_risks: list[str]

    model_config = ConfigDict(from_attributes=True)


class DocumentOpsReconcileRequest(BaseModel):
    scenario: DocumentOpsScenarioEnum = (
        DocumentOpsScenarioEnum.CONTRACTOR_INVOICE_RECONCILIATION
    )
    reference_items: list[DocumentOpsLineItemInput]
    invoice_items: list[DocumentOpsLineItemInput]


class DocumentOpsReconcileResponse(BaseModel):
    scenario: DocumentOpsScenarioEnum
    normalized_invoice_items: list[DocumentOpsLineItemRead]
    normalized_reference_items: list[DocumentOpsLineItemRead]
    matched_items: list[DocumentOpsMatchRead]
    exceptions: list[DocumentOpsExceptionRead]
    confidence_by_match: dict[str, float]
    needs_review_items: list[DocumentOpsReviewItemRead]
    summary: DocumentOpsSummaryRead
    spike_conclusion: DocumentOpsSpikeConclusionRead
    exported_exception_report_csv: str

    model_config = ConfigDict(from_attributes=True)


class DocumentOpsExceptionExportRequest(BaseModel):
    exceptions: list[DocumentOpsExceptionRead]
