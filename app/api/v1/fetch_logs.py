"""RSS 抓取日志 API。"""

from __future__ import annotations

from app.schemas import FetchLogList, FetchLogRead
from app.services import fetch_logs
from fastapi import APIRouter, Query

router = APIRouter(prefix="/fetch-logs", tags=["Fetch Logs"])


@router.get("/", response_model=FetchLogList, summary="列出抓取日志")
async def list_fetch_logs(
    skip: int = Query(default=0, ge=0, description="跳过的日志数量"),
    limit: int = Query(default=20, ge=1, le=200, description="返回的日志数量"),
    source_id: int | None = Query(default=None, description="按数据源过滤"),
) -> FetchLogList:
    total, items = fetch_logs.list_logs(source_id=source_id, skip=skip, limit=limit)
    return FetchLogList(
        total=total,
        items=[FetchLogRead.model_validate(item) for item in items],
    )
