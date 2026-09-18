"""Keyword seeds API."""

from __future__ import annotations

from app.models import KeywordSeedStatus
from app.schemas.keyword_seeds import (
    KeywordExtractionResult,
    KeywordSeedList,
    KeywordSeedRead,
    KeywordSeedStatusUpdate,
    KeywordValidationResult,
)
from app.services import keyword_seeds
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/keyword-seeds", tags=["Keyword Seeds"])


@router.get("/", response_model=KeywordSeedList, summary="List keyword seeds")
async def list_keyword_seeds(
    status: KeywordSeedStatus | None = Query(default=None, description="Filter by status"),
    search: str | None = Query(default=None, description="Filter by phrase substring"),
    min_volume: int | None = Query(
        default=None, ge=0, description="Minimum search volume"
    ),
    min_score: int | None = Query(
        default=None, ge=0, le=100, description="Minimum opportunity score"
    ),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=30, ge=1, le=200, description="Number of records to return"),
) -> KeywordSeedList:
    result = keyword_seeds.list_seeds(
        status=status,
        search=search,
        min_volume=min_volume,
        min_score=min_score,
        skip=skip,
        limit=limit,
    )
    return KeywordSeedList(
        total=result.total,
        status_breakdown=result.status_breakdown,
        items=[KeywordSeedRead.model_validate(item) for item in result.items],
    )


@router.post(
    "/extract",
    response_model=KeywordExtractionResult,
    status_code=201,
    summary="Extract keyword seeds from candidate needs",
)
async def extract_keyword_seeds() -> KeywordExtractionResult:
    result = keyword_seeds.extract_seeds()
    return KeywordExtractionResult(
        scanned=result.scanned,
        created=result.created,
        merged=result.merged,
    )


@router.post(
    "/validate-pending",
    response_model=KeywordValidationResult,
    summary="Validate pending keyword seeds in batch",
)
async def validate_pending_keyword_seeds(
    batch_size: int | None = Query(
        default=None, ge=1, le=1000, description="Maximum seeds to validate"
    ),
) -> KeywordValidationResult:
    result = await keyword_seeds.validate_pending(batch_size=batch_size)
    return KeywordValidationResult(
        skipped=result.skipped,
        validated=result.validated,
        no_volume=result.no_volume,
        errors=result.errors,
        reason=result.reason,
    )


@router.post(
    "/{seed_id}/validate",
    response_model=KeywordSeedRead,
    summary="Validate one keyword seed",
)
async def validate_keyword_seed(seed_id: int) -> KeywordSeedRead:
    try:
        seed = await keyword_seeds.validate_seed(seed_id)
    except keyword_seeds.KeywordSeedNotFoundError as exc:
        raise HTTPException(status_code=404, detail="keyword seed not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KeywordSeedRead.model_validate(seed)


@router.patch(
    "/{seed_id}",
    response_model=KeywordSeedRead,
    summary="Update keyword seed status",
)
async def update_keyword_seed_status(
    seed_id: int,
    payload: KeywordSeedStatusUpdate,
) -> KeywordSeedRead:
    try:
        status = KeywordSeedStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsupported keyword seed status") from exc

    try:
        seed = keyword_seeds.update_seed_status(seed_id, status)
    except keyword_seeds.KeywordSeedNotFoundError as exc:
        raise HTTPException(status_code=404, detail="keyword seed not found") from exc
    return KeywordSeedRead.model_validate(seed)
