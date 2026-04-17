"""外包项目线索 API。"""

from __future__ import annotations

from app.schemas import (
    MarketplaceLeadList,
    MarketplaceLeadNotesUpdate,
    MarketplaceLeadRead,
    MarketplaceLeadSourceMetricRead,
    MarketplaceLeadStatusUpdate,
)
from app.services import marketplace_leads
from fastapi import APIRouter, HTTPException, Query

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
    lead_kind: marketplace_leads.MarketplaceLeadKind | None = Query(
        default=None, description="按线索类型过滤"
    ),
    reviewable_only: bool = Query(default=False, description="仅保留项目型与合同型线索"),
    lead_status: marketplace_leads.MarketplaceLeadStatus | None = Query(
        default=None, description="按跟进状态过滤"
    ),
) -> MarketplaceLeadList:
    total, items, tier_breakdown, kind_breakdown, status_breakdown, source_breakdown = marketplace_leads.list_leads(
        skip=skip,
        limit=limit,
        source_id=source_id,
        search=search,
        tier=tier,
        lead_kind=lead_kind,
        reviewable_only=reviewable_only,
        lead_status=lead_status,
    )
    return MarketplaceLeadList(
        total=total,
        tier_breakdown=tier_breakdown,
        kind_breakdown=kind_breakdown,
        status_breakdown=status_breakdown,
        source_breakdown=[
            MarketplaceLeadSourceMetricRead.model_validate(item) for item in source_breakdown
        ],
        items=[MarketplaceLeadRead.model_validate(item) for item in items],
    )


@router.put("/{lead_id}/status", response_model=MarketplaceLeadRead, summary="更新外包项目线索状态")
async def update_marketplace_lead_status(
    lead_id: int,
    payload: MarketplaceLeadStatusUpdate,
) -> MarketplaceLeadRead:
    try:
        status = marketplace_leads.MarketplaceLeadStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsupported marketplace lead status") from exc
    try:
        item = marketplace_leads.update_lead_status(lead_id, status)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return MarketplaceLeadRead.model_validate(item)


@router.get("/{lead_id}", response_model=MarketplaceLeadRead, summary="获取单条外包项目线索详情")
async def get_marketplace_lead(lead_id: int) -> MarketplaceLeadRead:
    try:
        item = marketplace_leads.get_lead(lead_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return MarketplaceLeadRead.model_validate(item)


@router.put("/{lead_id}/notes", response_model=MarketplaceLeadRead, summary="更新外包项目线索备注")
async def update_marketplace_lead_notes(
    lead_id: int,
    payload: MarketplaceLeadNotesUpdate,
) -> MarketplaceLeadRead:
    try:
        item = marketplace_leads.update_lead_notes(lead_id, payload.notes)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return MarketplaceLeadRead.model_validate(item)
