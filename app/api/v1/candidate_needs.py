"""候选需求 API。"""

# ruff: noqa: I001
from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, status

from app.models import CandidateNeedStatus
from app.schemas import (
    CandidateNeedCreate,
    CandidateNeedList,
    CandidateNeedRead,
    CandidateNeedStatusLogRead,
    CandidateNeedStatusEnum,
    CandidateNeedStatusUpdate,
    CandidateNeedUpdate,
)
from app.services import candidate_needs
from app.services.candidate_needs import (
    CandidateNeedNotFoundError,
    InvalidStatusTransitionError,
)
from app.services.raw_entries import RawEntryNotFoundError

router = APIRouter(prefix="/candidate-needs", tags=["Candidate Needs"])


@router.get("/", response_model=CandidateNeedList, summary="列出候选需求")
async def list_candidate_needs(
    skip: int = Query(default=0, ge=0, description="跳过的记录数量"),
    limit: int = Query(default=20, ge=1, le=200, description="返回的记录数量"),
    statuses: list[CandidateNeedStatusEnum] | None = Query(
        default=None,
        description="按状态过滤，可多选",
    ),
    search: str | None = Query(default=None, description="关键字搜索"),
    raw_entry_id: int | None = Query(default=None, description="关联的原始条目 ID"),
    synced: bool | None = Query(
        default=None,
        description="按同步状态过滤，true 表示已同步，false 表示未同步",
    ),
) -> CandidateNeedList:
    total, items = candidate_needs.list_needs(
        statuses=_convert_statuses(statuses),
        search=search,
        raw_entry_id=raw_entry_id,
        synced=synced,
        skip=skip,
        limit=limit,
    )
    return CandidateNeedList(
        total=total,
        items=[CandidateNeedRead.model_validate(item) for item in items],
    )


@router.post(
    "/",
    response_model=CandidateNeedRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建候选需求",
)
async def create_candidate_need(payload: CandidateNeedCreate) -> CandidateNeedRead:
    try:
        need = candidate_needs.create_need(
            {
                **payload.model_dump(exclude={"status"}),
                "status": _convert_status(payload.status),
            }
        )
    except RawEntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="关联的原始条目不存在",
        ) from exc
    return CandidateNeedRead.model_validate(need)


@router.get(
    "/{need_id}",
    response_model=CandidateNeedRead,
    summary="候选需求详情",
)
async def get_candidate_need(need_id: int) -> CandidateNeedRead:
    try:
        need = candidate_needs.get_need(need_id)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    return CandidateNeedRead.model_validate(need)


@router.put(
    "/{need_id}",
    response_model=CandidateNeedRead,
    summary="更新候选需求",
)
async def update_candidate_need(need_id: int, payload: CandidateNeedUpdate) -> CandidateNeedRead:
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        status_value = data["status"]
        if status_value is None:
            data.pop("status")
        else:
            data["status"] = _convert_status(status_value)
    try:
        need = candidate_needs.update_need(need_id, data)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    except RawEntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="关联的原始条目不存在",
        ) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return CandidateNeedRead.model_validate(need)


@router.put(
    "/{need_id}/status",
    response_model=CandidateNeedRead,
    summary="更新候选需求状态",
)
async def update_candidate_need_status(
    need_id: int, payload: CandidateNeedStatusUpdate
) -> CandidateNeedRead:
    try:
        need = candidate_needs.update_need_status(need_id, _convert_status(payload.status))
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return CandidateNeedRead.model_validate(need)


@router.delete(
    "/{need_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除候选需求",
)
async def delete_candidate_need(need_id: int) -> None:
    try:
        candidate_needs.delete_need(need_id)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc


@router.get(
    "/{need_id}/status-logs",
    response_model=list[CandidateNeedStatusLogRead],
    summary="候选需求状态流转日志",
)
async def list_candidate_need_status_logs(need_id: int) -> list[CandidateNeedStatusLogRead]:
    try:
        logs = candidate_needs.list_need_status_logs(need_id)
    except CandidateNeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选需求不存在") from exc
    return [CandidateNeedStatusLogRead.model_validate(item) for item in logs]


@router.get("/export", summary="导出候选需求")
async def export_candidate_needs(
    format: str = Query(default="json", pattern="^(json|csv)$", description="导出格式"),
    statuses: list[CandidateNeedStatusEnum] | None = Query(
        default=None,
        description="按状态过滤，可多选",
    ),
    search: str | None = Query(default=None, description="关键字搜索"),
    raw_entry_id: int | None = Query(default=None, description="关联的原始条目 ID"),
    synced: bool | None = Query(
        default=None,
        description="按同步状态过滤，true 表示已同步，false 表示未同步",
    ),
    limit: int | None = Query(default=None, ge=1, le=1000, description="最大导出数量"),
) -> dict:
    needs = candidate_needs.export_needs(
        statuses=_convert_statuses(statuses),
        search=search,
        raw_entry_id=raw_entry_id,
        synced=synced,
        limit=limit,
    )

    if format == "json":
        payload = [CandidateNeedRead.model_validate(item).model_dump(mode="json") for item in needs]
        return {"format": "json", "items": payload}

    buffer = StringIO()
    fieldnames = [
        "id",
        "raw_entry_id",
        "summary",
        "problem_statement",
        "target_users",
        "value_proposition",
        "competition",
        "confidence",
        "rule_score",
        "status",
        "notes",
        "created_at",
        "updated_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for need in needs:
        model = CandidateNeedRead.model_validate(need)
        writer.writerow(
            {
                "id": model.id,
                "raw_entry_id": model.raw_entry_id,
                "summary": model.summary,
                "problem_statement": model.problem_statement or "",
                "target_users": model.target_users or "",
                "value_proposition": model.value_proposition or "",
                "competition": model.competition or "",
                "confidence": model.confidence if model.confidence is not None else "",
                "rule_score": model.rule_score if model.rule_score is not None else "",
                "status": model.status.value,
                "notes": model.notes or "",
                "created_at": model.created_at.isoformat(),
                "updated_at": model.updated_at.isoformat(),
            }
        )
    return {"format": "csv", "content": buffer.getvalue()}


def _convert_status(
    value: CandidateNeedStatusEnum | CandidateNeedStatus | str,
) -> CandidateNeedStatus:
    if isinstance(value, CandidateNeedStatus):
        return value
    if isinstance(value, CandidateNeedStatusEnum):
        raw = value.value
    else:
        raw = value
    return CandidateNeedStatus(raw)


def _convert_statuses(
    values: Iterable[CandidateNeedStatusEnum] | None,
) -> list[CandidateNeedStatus] | None:
    if values is None:
        return None
    return [_convert_status(value) for value in values]
