"""Document Ops reconciliation spike API."""

from __future__ import annotations

from app.schemas.document_ops import (
    DocumentOpsExceptionExportRequest,
    DocumentOpsReconcileRequest,
    DocumentOpsReconcileResponse,
)
from app.services import document_ops
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/document-ops", tags=["Document Ops"])


@router.post(
    "/reconcile",
    response_model=DocumentOpsReconcileResponse,
    summary="Run a structured Document Ops reconciliation spike",
)
async def reconcile_document_ops(
    payload: DocumentOpsReconcileRequest,
) -> DocumentOpsReconcileResponse:
    result = document_ops.reconcile_documents(
        scenario=document_ops.DocumentOpsScenario(payload.scenario.value),
        reference_rows=[item.model_dump(exclude_none=True) for item in payload.reference_items],
        invoice_rows=[item.model_dump(exclude_none=True) for item in payload.invoice_items],
    )
    return DocumentOpsReconcileResponse.model_validate(result)


@router.post(
    "/exceptions/export.csv",
    response_class=PlainTextResponse,
    summary="Export reviewed Document Ops exceptions as CSV",
)
async def export_document_ops_exceptions(
    payload: DocumentOpsExceptionExportRequest,
) -> PlainTextResponse:
    exceptions = [
        document_ops.DocumentOpsException(
            id=item.id,
            type=document_ops.DocumentOpsExceptionType(item.type.value),
            severity=document_ops.DocumentOpsSeverity(item.severity.value),
            message=item.message,
            reference_line_id=item.reference_line_id,
            invoice_line_id=item.invoice_line_id,
            expected=item.expected,
            actual=item.actual,
            difference=item.difference,
            confidence=item.confidence,
            needs_review=item.needs_review,
            review_status=document_ops.DocumentOpsReviewStatus(item.review_status.value),
            reviewer_note=item.reviewer_note,
        )
        for item in payload.exceptions
    ]
    return PlainTextResponse(
        document_ops.export_exceptions_csv(exceptions),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="document_ops_exceptions.csv"'},
    )
