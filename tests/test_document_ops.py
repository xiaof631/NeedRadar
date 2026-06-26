from __future__ import annotations

import csv
from pathlib import Path

from app.main import app
from app.services import document_ops
from fastapi.testclient import TestClient

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "document_ops"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_case(case_id: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    case_dir = FIXTURE_ROOT / case_id
    return _read_csv(case_dir / "reference.csv"), _read_csv(case_dir / "invoice.csv")


def _reconcile_case(case_id: str) -> document_ops.DocumentOpsResult:
    reference_rows, invoice_rows = _load_case(case_id)
    return document_ops.reconcile_documents(
        reference_rows=reference_rows,
        invoice_rows=invoice_rows,
    )


def test_document_ops_reconciles_three_fixture_pairs_offline() -> None:
    for case_id in ("case_001", "case_002", "case_003"):
        result = _reconcile_case(case_id)

        assert result.scenario == document_ops.DocumentOpsScenario.CONTRACTOR_INVOICE_RECONCILIATION
        assert result.normalized_reference_items
        assert result.normalized_invoice_items
        assert result.matched_items
        assert result.exceptions
        assert result.confidence_by_match
        assert result.needs_review_items
        assert result.exported_exception_report_csv.startswith("exception_id,type,severity")
        assert result.spike_conclusion.validated


def test_document_ops_flags_missing_price_quantity_and_amount_mismatches() -> None:
    result = _reconcile_case("case_001")

    exception_types = {item.type for item in result.exceptions}
    assert document_ops.DocumentOpsExceptionType.MISSING_REFERENCE_ITEM in exception_types
    assert document_ops.DocumentOpsExceptionType.MISSING_INVOICE_ITEM in exception_types
    assert document_ops.DocumentOpsExceptionType.UNIT_PRICE_MISMATCH in exception_types
    assert document_ops.DocumentOpsExceptionType.QUANTITY_MISMATCH in exception_types
    assert document_ops.DocumentOpsExceptionType.AMOUNT_MISMATCH in exception_types
    assert document_ops.DocumentOpsExceptionType.TOTAL_AMOUNT_MISMATCH in exception_types
    assert all(item.needs_review for item in result.exceptions)


def test_document_ops_reports_missing_fields_as_reviewable_failures() -> None:
    result = document_ops.reconcile_documents(
        reference_rows=[
            {
                "line_id": "D100",
                "description": "Roof access hatch",
                "quantity": "2",
                "unit": "item",
                "unit_price": "500",
                "amount": "1000",
            }
        ],
        invoice_rows=[
            {
                "line_id": "D100",
                "description": "",
                "quantity": "",
                "unit": "item",
                "unit_price": "500",
                "amount": "1000",
            }
        ],
    )

    missing_field = next(
        item
        for item in result.exceptions
        if item.type == document_ops.DocumentOpsExceptionType.MISSING_REQUIRED_FIELD
    )
    assert missing_field.invoice_line_id == "D100"
    assert "description" in (missing_field.actual or "")
    assert any(item.id == missing_field.id for item in result.needs_review_items)


def test_document_ops_export_csv_contains_review_state_and_notes() -> None:
    result = _reconcile_case("case_003")
    exception = result.exceptions[0]
    exception.review_status = document_ops.DocumentOpsReviewStatus.ACCEPTED
    exception.reviewer_note = "Confirmed against revised site instruction."

    csv_payload = document_ops.export_exceptions_csv([exception])

    assert "exception_id,type,severity" in csv_payload
    assert exception.id in csv_payload
    assert "accepted" in csv_payload
    assert "Confirmed against revised site instruction." in csv_payload


def test_document_ops_api_reconcile_and_export_csv() -> None:
    reference_rows, invoice_rows = _load_case("case_001")
    payload = {
        "reference_items": reference_rows,
        "invoice_items": invoice_rows,
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/document-ops/reconcile", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["matched_count"] >= 3
        assert body["exceptions"]
        assert body["confidence_by_match"]
        assert body["spike_conclusion"]["remaining_risks"]

        export_response = client.post(
            "/api/v1/document-ops/exceptions/export.csv",
            json={"exceptions": body["exceptions"]},
        )
        assert export_response.status_code == 200
        assert export_response.text.startswith("exception_id,type,severity")
        assert "missing_reference_item" in export_response.text
