"""Document Ops reconciliation spike service.

The spike deliberately starts from structured rows instead of PDF/OCR input so
the reconciliation behavior can be tested offline and independently from any
extraction provider.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum
from typing import Any


class DocumentOpsScenario(StrEnum):
    CONTRACTOR_INVOICE_RECONCILIATION = "contractor_invoice_reconciliation"


class DocumentOpsExceptionType(StrEnum):
    MISSING_REFERENCE_ITEM = "missing_reference_item"
    MISSING_INVOICE_ITEM = "missing_invoice_item"
    UNIT_PRICE_MISMATCH = "unit_price_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"
    AMOUNT_MISMATCH = "amount_mismatch"
    TOTAL_AMOUNT_MISMATCH = "total_amount_mismatch"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    LOW_CONFIDENCE_MATCH = "low_confidence_match"


class DocumentOpsSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DocumentOpsReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class DocumentOpsMatchType(StrEnum):
    EXACT_LINE_ID = "exact_line_id"
    EXACT_DESCRIPTION = "exact_description"
    FUZZY_DESCRIPTION = "fuzzy_description"


@dataclass(slots=True)
class DocumentOpsLineItem:
    line_id: str
    description: str
    quantity: float | None
    unit: str | None
    unit_price: float | None
    amount: float | None
    source: str
    source_row: int
    normalized_description: str
    raw: dict[str, Any] = field(default_factory=dict)
    parse_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DocumentOpsException:
    id: str
    type: DocumentOpsExceptionType
    severity: DocumentOpsSeverity
    message: str
    reference_line_id: str | None = None
    invoice_line_id: str | None = None
    expected: str | None = None
    actual: str | None = None
    difference: float | None = None
    confidence: float = 1.0
    needs_review: bool = True
    review_status: DocumentOpsReviewStatus = DocumentOpsReviewStatus.PENDING
    reviewer_note: str | None = None


@dataclass(slots=True)
class DocumentOpsMatch:
    id: str
    reference_item: DocumentOpsLineItem
    invoice_item: DocumentOpsLineItem
    match_type: DocumentOpsMatchType
    confidence: float
    needs_review: bool
    review_status: DocumentOpsReviewStatus = DocumentOpsReviewStatus.PENDING
    reviewer_note: str | None = None
    exception_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DocumentOpsReviewItem:
    id: str
    item_type: str
    reason: str
    confidence: float


@dataclass(slots=True)
class DocumentOpsSummary:
    reference_count: int
    invoice_count: int
    matched_count: int
    exception_count: int
    needs_review_count: int
    reference_total: float
    invoice_total: float
    total_difference: float


@dataclass(slots=True)
class DocumentOpsSpikeConclusion:
    feasible: bool
    recommendation: str
    validated: list[str]
    remaining_risks: list[str]


@dataclass(slots=True)
class DocumentOpsResult:
    scenario: DocumentOpsScenario
    normalized_invoice_items: list[DocumentOpsLineItem]
    normalized_reference_items: list[DocumentOpsLineItem]
    matched_items: list[DocumentOpsMatch]
    exceptions: list[DocumentOpsException]
    confidence_by_match: dict[str, float]
    needs_review_items: list[DocumentOpsReviewItem]
    summary: DocumentOpsSummary
    spike_conclusion: DocumentOpsSpikeConclusion
    exported_exception_report_csv: str


_LINE_ID_FIELDS = ("line_id", "item_code", "code", "ref", "reference", "id")
_DESCRIPTION_FIELDS = ("description", "item", "work_item", "scope", "name")
_QUANTITY_FIELDS = ("quantity", "qty", "qnty")
_UNIT_FIELDS = ("unit", "uom", "measure")
_UNIT_PRICE_FIELDS = ("unit_price", "rate", "price")
_AMOUNT_FIELDS = ("amount", "total", "line_total")
_TEXT_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_MONEY_TOLERANCE = 0.01
_QUANTITY_TOLERANCE = 0.0001
_FUZZY_MATCH_THRESHOLD = 0.62
_REVIEW_CONFIDENCE_THRESHOLD = 0.86


def reconcile_documents(
    *,
    reference_rows: Iterable[Mapping[str, Any]],
    invoice_rows: Iterable[Mapping[str, Any]],
    scenario: DocumentOpsScenario = DocumentOpsScenario.CONTRACTOR_INVOICE_RECONCILIATION,
) -> DocumentOpsResult:
    """Normalize and reconcile paired reference/invoice line-item rows."""

    reference_items = normalize_line_items(reference_rows, source="reference")
    invoice_items = normalize_line_items(invoice_rows, source="invoice")

    exceptions: list[DocumentOpsException] = []
    exceptions.extend(_missing_field_exceptions(reference_items + invoice_items))

    matches, matched_reference_ids, matched_invoice_ids = _match_items(reference_items, invoice_items)

    for match in matches:
        match_exceptions = _build_match_exceptions(match, start_index=len(exceptions) + 1)
        match.exception_ids = [item.id for item in match_exceptions]
        if match_exceptions or match.confidence < _REVIEW_CONFIDENCE_THRESHOLD:
            match.needs_review = True
        exceptions.extend(match_exceptions)

    for reference_item in reference_items:
        if reference_item.line_id not in matched_reference_ids:
            exceptions.append(
                _exception(
                    index=len(exceptions) + 1,
                    exception_type=DocumentOpsExceptionType.MISSING_INVOICE_ITEM,
                    severity=DocumentOpsSeverity.MEDIUM,
                    message=f"Reference item '{reference_item.description}' was not found on the invoice.",
                    reference_line_id=reference_item.line_id,
                    expected=_format_amount(reference_item.amount),
                    actual=None,
                    difference=_signed(reference_item.amount),
                    confidence=0.92,
                )
            )

    for invoice_item in invoice_items:
        if invoice_item.line_id not in matched_invoice_ids:
            exceptions.append(
                _exception(
                    index=len(exceptions) + 1,
                    exception_type=DocumentOpsExceptionType.MISSING_REFERENCE_ITEM,
                    severity=DocumentOpsSeverity.HIGH,
                    message=f"Invoice item '{invoice_item.description}' has no reference schedule match.",
                    reference_line_id=None,
                    invoice_line_id=invoice_item.line_id,
                    expected=None,
                    actual=_format_amount(invoice_item.amount),
                    difference=_signed(invoice_item.amount),
                    confidence=0.9,
                )
            )

    total_exception = _build_total_exception(reference_items, invoice_items, len(exceptions) + 1)
    if total_exception is not None:
        exceptions.append(total_exception)

    needs_review_items = _build_needs_review_items(matches, exceptions)
    confidence_by_match = {item.id: item.confidence for item in matches}
    summary = _summarize(reference_items, invoice_items, matches, exceptions, needs_review_items)
    conclusion = _build_spike_conclusion(reference_items, invoice_items, matches, exceptions)

    return DocumentOpsResult(
        scenario=scenario,
        normalized_invoice_items=invoice_items,
        normalized_reference_items=reference_items,
        matched_items=matches,
        exceptions=exceptions,
        confidence_by_match=confidence_by_match,
        needs_review_items=needs_review_items,
        summary=summary,
        spike_conclusion=conclusion,
        exported_exception_report_csv=export_exceptions_csv(exceptions),
    )


def normalize_line_items(
    rows: Iterable[Mapping[str, Any]],
    *,
    source: str,
) -> list[DocumentOpsLineItem]:
    """Normalize line-item fields from common CSV/JSON naming variants."""

    normalized: list[DocumentOpsLineItem] = []
    for index, row in enumerate(rows, start=1):
        row_dict = dict(row)
        line_id = _coerce_text(_first_present(row_dict, _LINE_ID_FIELDS))
        description = _coerce_text(_first_present(row_dict, _DESCRIPTION_FIELDS))
        quantity = _coerce_number(_first_present(row_dict, _QUANTITY_FIELDS))
        unit = _coerce_text(_first_present(row_dict, _UNIT_FIELDS))
        unit_price = _coerce_number(_first_present(row_dict, _UNIT_PRICE_FIELDS))
        amount = _coerce_number(_first_present(row_dict, _AMOUNT_FIELDS))
        warnings = _parse_warnings(
            line_id=line_id,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
        )

        normalized.append(
            DocumentOpsLineItem(
                line_id=line_id or f"{source}-{index:03d}",
                description=description or "(missing description)",
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                amount=amount,
                source=source,
                source_row=index,
                normalized_description=_normalize_description(description or ""),
                raw=row_dict,
                parse_warnings=warnings,
            )
        )
    return normalized


def export_exceptions_csv(exceptions: Iterable[DocumentOpsException]) -> str:
    """Export exceptions to the stable CSV shape used by the review queue."""

    output = io.StringIO()
    fieldnames = [
        "exception_id",
        "type",
        "severity",
        "reference_line_id",
        "invoice_line_id",
        "message",
        "expected",
        "actual",
        "difference",
        "confidence",
        "needs_review",
        "review_status",
        "reviewer_note",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in exceptions:
        writer.writerow(
            {
                "exception_id": item.id,
                "type": item.type.value,
                "severity": item.severity.value,
                "reference_line_id": item.reference_line_id or "",
                "invoice_line_id": item.invoice_line_id or "",
                "message": item.message,
                "expected": item.expected or "",
                "actual": item.actual or "",
                "difference": "" if item.difference is None else _round_money(item.difference),
                "confidence": item.confidence,
                "needs_review": str(item.needs_review).lower(),
                "review_status": item.review_status.value,
                "reviewer_note": item.reviewer_note or "",
            }
        )
    return output.getvalue()


def _match_items(
    reference_items: list[DocumentOpsLineItem],
    invoice_items: list[DocumentOpsLineItem],
) -> tuple[list[DocumentOpsMatch], set[str], set[str]]:
    matches: list[DocumentOpsMatch] = []
    matched_reference_ids: set[str] = set()
    matched_invoice_ids: set[str] = set()

    invoice_by_line_id = {
        _normalize_line_id(item.line_id): item
        for item in invoice_items
        if _normalize_line_id(item.line_id)
    }

    for reference_item in reference_items:
        normalized_line_id = _normalize_line_id(reference_item.line_id)
        invoice_item = invoice_by_line_id.get(normalized_line_id)
        if invoice_item is None or invoice_item.line_id in matched_invoice_ids:
            continue
        match = _make_match(
            reference_item=reference_item,
            invoice_item=invoice_item,
            match_type=DocumentOpsMatchType.EXACT_LINE_ID,
            confidence=0.98,
        )
        matches.append(match)
        matched_reference_ids.add(reference_item.line_id)
        matched_invoice_ids.add(invoice_item.line_id)

    for reference_item in reference_items:
        if reference_item.line_id in matched_reference_ids:
            continue
        best_invoice: DocumentOpsLineItem | None = None
        best_score = 0.0
        for invoice_item in invoice_items:
            if invoice_item.line_id in matched_invoice_ids:
                continue
            score = _description_similarity(
                reference_item.normalized_description,
                invoice_item.normalized_description,
            )
            if score > best_score:
                best_score = score
                best_invoice = invoice_item

        if best_invoice is None or best_score < _FUZZY_MATCH_THRESHOLD:
            continue

        match_type = (
            DocumentOpsMatchType.EXACT_DESCRIPTION
            if best_score >= 0.96
            else DocumentOpsMatchType.FUZZY_DESCRIPTION
        )
        match = _make_match(
            reference_item=reference_item,
            invoice_item=best_invoice,
            match_type=match_type,
            confidence=round(best_score, 2),
        )
        matches.append(match)
        matched_reference_ids.add(reference_item.line_id)
        matched_invoice_ids.add(best_invoice.line_id)

    return matches, matched_reference_ids, matched_invoice_ids


def _make_match(
    *,
    reference_item: DocumentOpsLineItem,
    invoice_item: DocumentOpsLineItem,
    match_type: DocumentOpsMatchType,
    confidence: float,
) -> DocumentOpsMatch:
    return DocumentOpsMatch(
        id=f"match-{reference_item.line_id}-{invoice_item.line_id}",
        reference_item=reference_item,
        invoice_item=invoice_item,
        match_type=match_type,
        confidence=confidence,
        needs_review=confidence < _REVIEW_CONFIDENCE_THRESHOLD,
    )


def _build_match_exceptions(
    match: DocumentOpsMatch,
    *,
    start_index: int,
) -> list[DocumentOpsException]:
    exceptions: list[DocumentOpsException] = []
    reference_item = match.reference_item
    invoice_item = match.invoice_item

    if _has_material_difference(reference_item.unit_price, invoice_item.unit_price, _MONEY_TOLERANCE):
        exceptions.append(
            _exception(
                index=start_index + len(exceptions),
                exception_type=DocumentOpsExceptionType.UNIT_PRICE_MISMATCH,
                severity=DocumentOpsSeverity.HIGH,
                message=f"Unit price differs for '{reference_item.description}'.",
                reference_line_id=reference_item.line_id,
                invoice_line_id=invoice_item.line_id,
                expected=_format_amount(reference_item.unit_price),
                actual=_format_amount(invoice_item.unit_price),
                difference=_difference(invoice_item.unit_price, reference_item.unit_price),
                confidence=match.confidence,
            )
        )

    if _has_material_difference(reference_item.quantity, invoice_item.quantity, _QUANTITY_TOLERANCE):
        exceptions.append(
            _exception(
                index=start_index + len(exceptions),
                exception_type=DocumentOpsExceptionType.QUANTITY_MISMATCH,
                severity=DocumentOpsSeverity.HIGH,
                message=f"Quantity differs for '{reference_item.description}'.",
                reference_line_id=reference_item.line_id,
                invoice_line_id=invoice_item.line_id,
                expected=_format_quantity(reference_item.quantity),
                actual=_format_quantity(invoice_item.quantity),
                difference=_difference(invoice_item.quantity, reference_item.quantity),
                confidence=match.confidence,
            )
        )

    expected_amount = reference_item.amount
    actual_amount = invoice_item.amount
    invoice_calculated_amount = _calculated_amount(invoice_item)
    if invoice_calculated_amount is not None and actual_amount is not None:
        if _has_material_difference(invoice_calculated_amount, actual_amount, _MONEY_TOLERANCE):
            expected_amount = invoice_calculated_amount

    if _has_material_difference(expected_amount, actual_amount, _MONEY_TOLERANCE):
        exceptions.append(
            _exception(
                index=start_index + len(exceptions),
                exception_type=DocumentOpsExceptionType.AMOUNT_MISMATCH,
                severity=DocumentOpsSeverity.MEDIUM,
                message=f"Line amount differs for '{reference_item.description}'.",
                reference_line_id=reference_item.line_id,
                invoice_line_id=invoice_item.line_id,
                expected=_format_amount(expected_amount),
                actual=_format_amount(actual_amount),
                difference=_difference(actual_amount, expected_amount),
                confidence=match.confidence,
            )
        )

    if match.confidence < _REVIEW_CONFIDENCE_THRESHOLD:
        exceptions.append(
            _exception(
                index=start_index + len(exceptions),
                exception_type=DocumentOpsExceptionType.LOW_CONFIDENCE_MATCH,
                severity=DocumentOpsSeverity.LOW,
                message=f"Description match needs review for '{reference_item.description}'.",
                reference_line_id=reference_item.line_id,
                invoice_line_id=invoice_item.line_id,
                expected=reference_item.description,
                actual=invoice_item.description,
                difference=None,
                confidence=match.confidence,
            )
        )

    return exceptions


def _missing_field_exceptions(items: Iterable[DocumentOpsLineItem]) -> list[DocumentOpsException]:
    exceptions: list[DocumentOpsException] = []
    for item in items:
        if not item.parse_warnings:
            continue
        exceptions.append(
            _exception(
                index=len(exceptions) + 1,
                exception_type=DocumentOpsExceptionType.MISSING_REQUIRED_FIELD,
                severity=DocumentOpsSeverity.MEDIUM,
                message=f"{item.source.title()} row {item.source_row} has missing or invalid fields: "
                + ", ".join(item.parse_warnings),
                reference_line_id=item.line_id if item.source == "reference" else None,
                invoice_line_id=item.line_id if item.source == "invoice" else None,
                expected="description, quantity, unit_price, amount",
                actual=", ".join(item.parse_warnings),
                difference=None,
                confidence=1.0,
            )
        )
    return exceptions


def _build_total_exception(
    reference_items: list[DocumentOpsLineItem],
    invoice_items: list[DocumentOpsLineItem],
    index: int,
) -> DocumentOpsException | None:
    reference_total = _sum_amounts(reference_items)
    invoice_total = _sum_amounts(invoice_items)
    if not _has_material_difference(reference_total, invoice_total, _MONEY_TOLERANCE):
        return None
    return _exception(
        index=index,
        exception_type=DocumentOpsExceptionType.TOTAL_AMOUNT_MISMATCH,
        severity=DocumentOpsSeverity.HIGH,
        message="Invoice total does not match the reference schedule total.",
        expected=_format_amount(reference_total),
        actual=_format_amount(invoice_total),
        difference=_difference(invoice_total, reference_total),
        confidence=0.98,
    )


def _build_needs_review_items(
    matches: Iterable[DocumentOpsMatch],
    exceptions: Iterable[DocumentOpsException],
) -> list[DocumentOpsReviewItem]:
    review_items: list[DocumentOpsReviewItem] = []
    for match in matches:
        if match.needs_review:
            reason = "Match has exceptions" if match.exception_ids else "Low confidence match"
            review_items.append(
                DocumentOpsReviewItem(
                    id=match.id,
                    item_type="match",
                    reason=reason,
                    confidence=match.confidence,
                )
            )
    for item in exceptions:
        if item.needs_review:
            review_items.append(
                DocumentOpsReviewItem(
                    id=item.id,
                    item_type="exception",
                    reason=item.message,
                    confidence=item.confidence,
                )
            )
    return review_items


def _summarize(
    reference_items: list[DocumentOpsLineItem],
    invoice_items: list[DocumentOpsLineItem],
    matches: list[DocumentOpsMatch],
    exceptions: list[DocumentOpsException],
    needs_review_items: list[DocumentOpsReviewItem],
) -> DocumentOpsSummary:
    reference_total = _sum_amounts(reference_items)
    invoice_total = _sum_amounts(invoice_items)
    return DocumentOpsSummary(
        reference_count=len(reference_items),
        invoice_count=len(invoice_items),
        matched_count=len(matches),
        exception_count=len(exceptions),
        needs_review_count=len(needs_review_items),
        reference_total=_round_money(reference_total),
        invoice_total=_round_money(invoice_total),
        total_difference=_round_money(invoice_total - reference_total),
    )


def _build_spike_conclusion(
    reference_items: list[DocumentOpsLineItem],
    invoice_items: list[DocumentOpsLineItem],
    matches: list[DocumentOpsMatch],
    exceptions: list[DocumentOpsException],
) -> DocumentOpsSpikeConclusion:
    required_types = {
        DocumentOpsExceptionType.MISSING_REFERENCE_ITEM,
        DocumentOpsExceptionType.UNIT_PRICE_MISMATCH,
        DocumentOpsExceptionType.QUANTITY_MISMATCH,
        DocumentOpsExceptionType.AMOUNT_MISMATCH,
    }
    observed_types = {item.type for item in exceptions}
    matched_enough = bool(reference_items and invoice_items and matches)
    feasible = matched_enough and bool(required_types.intersection(observed_types))
    return DocumentOpsSpikeConclusion(
        feasible=feasible,
        recommendation=(
            "Proceed to the MVP if real customer samples have similar table structure; keep PDF/OCR "
            "extraction as a separate adapter."
            if feasible
            else "Keep this in spike mode until paired samples produce stable matches and exceptions."
        ),
        validated=[
            "offline structured invoice/reference normalization",
            "line-item matching by line id and fuzzy description",
            "exception queue generation with confidence and needs_review flags",
            "CSV exception report export",
        ],
        remaining_risks=[
            "PDF/OCR extraction accuracy is not covered by this spike",
            "description-only matching still needs review on ambiguous line items",
            "real customer schedules may require scenario-specific field aliases",
        ],
    )


def _exception(
    *,
    index: int,
    exception_type: DocumentOpsExceptionType,
    severity: DocumentOpsSeverity,
    message: str,
    reference_line_id: str | None = None,
    invoice_line_id: str | None = None,
    expected: str | None = None,
    actual: str | None = None,
    difference: float | None = None,
    confidence: float = 1.0,
) -> DocumentOpsException:
    return DocumentOpsException(
        id=f"ex-{index:03d}",
        type=exception_type,
        severity=severity,
        message=message,
        reference_line_id=reference_line_id,
        invoice_line_id=invoice_line_id,
        expected=expected,
        actual=actual,
        difference=None if difference is None else _round_money(difference),
        confidence=confidence,
    )


def _first_present(row: Mapping[str, Any], aliases: tuple[str, ...]) -> Any:
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_warnings(
    *,
    line_id: str | None,
    description: str | None,
    quantity: float | None,
    unit_price: float | None,
    amount: float | None,
) -> list[str]:
    warnings: list[str] = []
    if line_id is None:
        warnings.append("line_id")
    if description is None:
        warnings.append("description")
    if quantity is None:
        warnings.append("quantity")
    if unit_price is None:
        warnings.append("unit_price")
    if amount is None:
        warnings.append("amount")
    return warnings


def _normalize_line_id(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_description(value: str) -> str:
    return " ".join(_TEXT_TOKEN_PATTERN.findall(value.lower()))


def _description_similarity(reference: str, invoice: str) -> float:
    if not reference or not invoice:
        return 0.0
    if reference == invoice:
        return 1.0
    ratio = SequenceMatcher(a=reference, b=invoice).ratio()
    reference_tokens = set(reference.split())
    invoice_tokens = set(invoice.split())
    if not reference_tokens or not invoice_tokens:
        return ratio
    overlap = len(reference_tokens & invoice_tokens) / max(len(reference_tokens), len(invoice_tokens))
    return max(ratio, (ratio * 0.6) + (overlap * 0.4))


def _has_material_difference(
    expected: float | None,
    actual: float | None,
    tolerance: float,
) -> bool:
    if expected is None or actual is None:
        return False
    return abs(actual - expected) > tolerance


def _difference(actual: float | None, expected: float | None) -> float | None:
    if actual is None or expected is None:
        return None
    return actual - expected


def _signed(value: float | None) -> float | None:
    if value is None:
        return None
    return value


def _calculated_amount(item: DocumentOpsLineItem) -> float | None:
    if item.quantity is None or item.unit_price is None:
        return None
    return item.quantity * item.unit_price


def _sum_amounts(items: Iterable[DocumentOpsLineItem]) -> float:
    return sum(item.amount or 0.0 for item in items)


def _round_money(value: float) -> float:
    return round(value, 2)


def _format_amount(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{_round_money(value):.2f}"


def _format_quantity(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:g}"
