"""RSS 抓取日志 API。"""

from __future__ import annotations

from datetime import datetime

from app.models import FetchStatus
from app.schemas import FetchLogList, FetchLogRead
from app.services import fetch_logs
from fastapi import APIRouter, HTTPException, Query, status

router = APIRouter(prefix="/fetch-logs", tags=["Fetch Logs"])


@router.get("/", response_model=FetchLogList, summary="列出抓取日志")
async def list_fetch_logs(
    skip: int = Query(default=0, ge=0, description="跳过的日志数量"),
    limit: int = Query(default=20, ge=1, le=200, description="返回的日志数量"),
    source_id: int | None = Query(default=None, description="按数据源过滤"),
    status: FetchStatus | None = Query(default=None, description="根据抓取状态过滤"),
    start_fetched_at: datetime | None = Query(
        default=None,
        description="抓取开始时间（包含）",
    ),
    end_fetched_at: datetime | None = Query(
        default=None,
        description="抓取结束时间（包含）",
    ),
) -> FetchLogList:
    total, items = fetch_logs.list_logs(
        source_id=source_id,
        status=status,
        start_fetched_at=_parse_datetime(start_fetched_at),
        end_fetched_at=_parse_datetime(end_fetched_at),
        skip=skip,
        limit=limit,
    )
    return FetchLogList(
        total=total,
        items=[FetchLogRead.model_validate(item) for item in items],
    )


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - FastAPI 会处理校验错误
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="无效的时间格式",
        ) from exc
