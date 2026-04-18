"""原始条目相关 API。"""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from app.models import RawEntryStatus
from app.schemas import (
    RawEntryBulkStatusUpdate,
    RawEntryList,
    RawEntryRead,
    RawEntryRuleMatch,
    RawEntrySourceTypeEnum,
    RawEntryStatusEnum,
    RawEntryStatusUpdate,
)
from app.services import filter_engine, raw_entries
from fastapi import APIRouter, HTTPException, Query, status

router = APIRouter(prefix="/raw-entries", tags=["Raw Entries"])


@router.get("/", response_model=RawEntryList, summary="分页查询原始条目")
async def list_raw_entries(
    skip: int = Query(default=0, ge=0, description="跳过的记录数量"),
    limit: int = Query(default=20, ge=1, le=200, description="返回的记录数量"),
    source_id: int | None = Query(default=None, description="按数据源过滤"),
    source_type: RawEntrySourceTypeEnum | None = Query(default=None, description="按来源类型过滤"),
    status: RawEntryStatusEnum | None = Query(default=None, description="按状态过滤"),
    search: str | None = Query(default=None, description="标题/摘要关键字"),
    start_published_at: datetime | None = Query(default=None, description="发布时间起始（包含）"),
    end_published_at: datetime | None = Query(default=None, description="发布时间结束（包含）"),
) -> RawEntryList:
    total, items = raw_entries.list_entries(
        source_id=source_id,
        source_type=_convert_source_type(source_type),
        status=_convert_status(status),
        search=search,
        start_published_at=_parse_datetime(start_published_at),
        end_published_at=_parse_datetime(end_published_at),
        skip=skip,
        limit=limit,
    )
    return RawEntryList(total=total, items=[RawEntryRead.model_validate(item) for item in items])


@router.post(
    "/{entry_id}/evaluate",
    response_model=RawEntryRuleMatch,
    summary="评估条目命中规则情况",
)
async def evaluate_raw_entry(
    entry_id: int,
    min_score: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="自定义最低得分阈值",
    ),
) -> RawEntryRuleMatch:
    try:
        entry = raw_entries.get_entry(entry_id)
    except raw_entries.RawEntryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="原始条目不存在") from exc

    result = filter_engine.evaluate_entry(entry, min_score=min_score)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未命中任何筛选规则")

    return RawEntryRuleMatch(
        rule_id=result.rule.id,
        rule_name=result.rule.name,
        score=result.score,
        matched_keywords=list(result.matched_keywords),
        matched_patterns=list(result.matched_patterns),
    )


@router.put("/{entry_id}/status", response_model=RawEntryRead, summary="更新原始条目状态")
async def update_raw_entry_status(entry_id: int, payload: RawEntryStatusUpdate) -> RawEntryRead:
    try:
        entry = raw_entries.update_entry_status(entry_id, _convert_status(payload.status))
    except raw_entries.RawEntryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="原始条目不存在") from exc
    return RawEntryRead.model_validate(entry)


@router.post("/bulk-status", response_model=list[RawEntryRead], summary="批量更新原始条目状态")
async def bulk_update_raw_entry_status(payload: RawEntryBulkStatusUpdate) -> list[RawEntryRead]:
    try:
        entries = raw_entries.bulk_update_status(
            payload.ids,
            _convert_status(payload.status),
        )
    except raw_entries.RawEntryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部分条目不存在") from exc
    return [RawEntryRead.model_validate(entry) for entry in entries]


@router.get("/export", summary="导出原始条目")
async def export_raw_entries(
    format: str = Query(default="json", pattern="^(json|csv)$", description="导出格式"),
    source_id: int | None = Query(default=None, description="按数据源过滤"),
    source_type: RawEntrySourceTypeEnum | None = Query(default=None, description="按来源类型过滤"),
    status: RawEntryStatusEnum | None = Query(default=None, description="按状态过滤"),
    search: str | None = Query(default=None, description="标题/摘要关键字"),
    start_published_at: datetime | None = Query(default=None, description="发布时间起始（包含）"),
    end_published_at: datetime | None = Query(default=None, description="发布时间结束（包含）"),
    limit: int | None = Query(default=None, ge=1, le=1000, description="最大导出数量"),
) -> dict:
    entries = raw_entries.export_entries(
        source_id=source_id,
        source_type=_convert_source_type(source_type),
        status=_convert_status(status),
        search=search,
        start_published_at=_parse_datetime(start_published_at),
        end_published_at=_parse_datetime(end_published_at),
        limit=limit,
    )

    if format == "json":
        payload = [RawEntryRead.model_validate(entry).model_dump(mode="json") for entry in entries]
        return {"format": "json", "items": payload}

    buffer = StringIO()
    fieldnames = [
        "id",
        "source_id",
        "guid",
        "content_hash",
        "title",
        "summary",
        "content",
        "link",
        "published_at",
        "author",
        "tags",
        "status",
        "created_at",
        "updated_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for entry in entries:
        model = RawEntryRead.model_validate(entry)
        writer.writerow(
            {
                "id": model.id,
                "source_id": model.source_id,
                "guid": model.guid,
                "content_hash": model.content_hash or "",
                "title": model.title,
                "summary": model.summary or "",
                "content": model.content or "",
                "link": model.link or "",
                "published_at": model.published_at.isoformat() if model.published_at else "",
                "author": model.author or "",
                "tags": ";".join(model.tags),
                "status": model.status.value,
                "created_at": model.created_at.isoformat(),
                "updated_at": model.updated_at.isoformat(),
            }
        )
    csv_content = buffer.getvalue()
    return {"format": "csv", "content": csv_content}


def _convert_status(
    value: RawEntryStatusEnum | RawEntryStatus | str | None,
) -> RawEntryStatus | None:
    if value is None:
        return None
    if isinstance(value, RawEntryStatus):
        return value
    if isinstance(value, RawEntryStatusEnum):
        raw = value.value
    else:
        raw = value
    return RawEntryStatus(raw)


def _convert_source_type(value: RawEntrySourceTypeEnum | str | None):
    if value is None:
        return None
    raw = value.value if isinstance(value, RawEntrySourceTypeEnum) else value
    from app.models import SourceType

    return SourceType(raw)


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - 参数错误
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="无效的时间格式",
        ) from exc
