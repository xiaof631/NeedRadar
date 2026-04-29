"""RSS 源管理相关的 API。"""

from __future__ import annotations

from app.models import SourceStatus, SourceType
from app.schemas import (
    FetchResultRead,
    RssSourceCreate,
    RssSourceList,
    RssSourceRead,
    RssSourceUpdate,
)
from app.services import rss_fetcher, rss_sources
from fastapi import APIRouter, HTTPException, Query, status

router = APIRouter(prefix="/rss-sources", tags=["RSS Sources"])


@router.get("/", response_model=RssSourceList, summary="列出 RSS 源")
async def list_rss_sources(
    skip: int = Query(default=0, ge=0, description="跳过的记录数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回的记录数量"),
    status: SourceStatus | None = Query(default=None, description="过滤状态"),
    source_type: SourceType | None = Query(default=None, description="过滤数据源类型"),
    category: str | None = Query(default=None, description="过滤分类"),
    search: str | None = Query(default=None, description="名称模糊搜索"),
) -> RssSourceList:
    total, items = rss_sources.list_sources(
        skip=skip,
        limit=limit,
        status=status,
        source_type=source_type,
        category=category,
        search=search,
    )
    return RssSourceList(
        total=total,
        items=[RssSourceRead.model_validate(item) for item in items],
    )


@router.post(
    "/",
    response_model=RssSourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建 RSS 源",
)
async def create_rss_source(payload: RssSourceCreate) -> RssSourceRead:
    try:
        source = rss_sources.create_source(payload.model_dump(mode="json"))
    except rss_sources.RssSourceAlreadyExistsError as exc:  # pragma: no cover - 防御性
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RSS 源已存在") from exc
    return RssSourceRead.model_validate(source)


@router.get("/{source_id}", response_model=RssSourceRead, summary="获取 RSS 源详情")
async def get_rss_source(source_id: int) -> RssSourceRead:
    try:
        source = rss_sources.get_source(source_id)
    except rss_sources.RssSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS 源不存在") from exc
    return RssSourceRead.model_validate(source)


@router.put("/{source_id}", response_model=RssSourceRead, summary="更新 RSS 源")
async def update_rss_source(source_id: int, payload: RssSourceUpdate) -> RssSourceRead:
    data = payload.model_dump(exclude_unset=True, mode="json")
    try:
        source = rss_sources.update_source(source_id, data)
    except rss_sources.RssSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS 源不存在") from exc
    except rss_sources.RssSourceAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RSS 源 URL 冲突") from exc
    return RssSourceRead.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除 RSS 源")
async def delete_rss_source(source_id: int) -> None:
    try:
        rss_sources.delete_source(source_id)
    except rss_sources.RssSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS 源不存在") from exc


@router.post("/{source_id}/fetch", response_model=FetchResultRead, summary="手动触发抓取")
async def fetch_rss_source_now(source_id: int) -> FetchResultRead:
    try:
        rss_sources.get_source(source_id)
    except rss_sources.RssSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS 源不存在") from exc

    result = await rss_fetcher.fetch_rss_source(source_id)
    return FetchResultRead(
        source_id=result.source_id,
        fetched_entries=result.fetched_entries,
        new_entries=result.new_entries,
        status=result.status,
        error_message=result.error_message,
    )
