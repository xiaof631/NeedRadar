"""外包项目线索 API。"""

from __future__ import annotations

from app.schemas import MarketplaceLeadList, MarketplaceLeadRead
from app.services import marketplace_leads
from fastapi import APIRouter, Query

router = APIRouter(prefix="/marketplace-leads", tags=["Marketplace Leads"])


@router.get("/", response_model=MarketplaceLeadList, summary="分页查询外包项目线索")
async def list_marketplace_leads(
    skip: int = Query(default=0, ge=0, description="跳过的记录数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回的记录数量"),
    source_id: int | None = Query(default=None, description="按数据源过滤"),
    search: str | None = Query(default=None, description="按标题或描述关键字搜索"),
    tier: marketplace_leads.MarketplaceLeadTier | None = Query(
        default=None, description="按线索层级过滤"
    ),
) -> MarketplaceLeadList:
    total, items, tier_breakdown = marketplace_leads.list_leads(
        skip=skip,
        limit=limit,
        source_id=source_id,
        search=search,
        tier=tier,
    )
    return MarketplaceLeadList(
        total=total,
        tier_breakdown=tier_breakdown,
        items=[MarketplaceLeadRead.model_validate(item) for item in items],
    )
