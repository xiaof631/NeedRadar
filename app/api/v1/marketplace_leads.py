"""外包项目线索 API。"""

from __future__ import annotations

from datetime import datetime

from app.schemas import (
    MarketplaceLeadBulkOutcomeUpdate,
    MarketplaceLeadConversionMetricRead,
    MarketplaceLeadEventRead,
    MarketplaceLeadFollowUpUpdate,
    MarketplaceLeadList,
    MarketplaceLeadNotesUpdate,
    MarketplaceLeadOutcomeUpdate,
    MarketplaceLeadRead,
    MarketplaceLeadReminderRead,
    MarketplaceLeadSourceMetricRead,
    MarketplaceLeadStatusUpdate,
)
from app.schemas.marketplace_leads import (
    MarketplaceProposalContentUpdate,
    MarketplaceProposalGenerate,
    MarketplaceProposalPrepare,
    MarketplaceProposalPrepareResult,
    MarketplaceProposalRead,
    MarketplaceProposalStatusUpdate,
    MarketplaceSourceRecommendationRead,
)
from app.services import marketplace_leads, proposal_submissions
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
    opportunity_lane: marketplace_leads.MarketplaceOpportunityLane | None = Query(
        default=None, description="按远程兼职/项目外包通道过滤"
    ),
    communication_burden: marketplace_leads.MarketplaceCommunicationBurden | None = Query(
        default=None, description="按沟通成本过滤"
    ),
    preferred_only: bool = Query(
        default=False, description="仅保留低/中沟通且可快速承接的优先机会"
    ),
    budget_band: marketplace_leads.MarketplaceBudgetBand | None = Query(
        default=None, description="按预算分段过滤"
    ),
    delivery_scope: marketplace_leads.MarketplaceDeliveryScope | None = Query(
        default=None, description="按交付范围过滤"
    ),
    tech_stack: str | None = Query(default=None, description="按归一化技术栈过滤"),
    region: marketplace_leads.MarketplaceRegion | None = Query(
        default=None, description="按地区画像过滤"
    ),
    timezone_fit: bool | None = Query(default=None, description="按时区匹配度过滤"),
    reviewable_only: bool = Query(default=False, description="仅保留项目型与合同型线索"),
    overdue_only: bool = Query(default=False, description="仅保留下次跟进已超时的线索"),
    lead_status: marketplace_leads.MarketplaceLeadStatus | None = Query(
        default=None, description="按跟进状态过滤"
    ),
    lead_outcome: marketplace_leads.MarketplaceLeadOutcome | None = Query(
        default=None, description="按跟进结果过滤"
    ),
    todo_sort: str = Query(
        default="default",
        description="待办排序: default | newest_first | oldest_first | priority",
    ),
) -> MarketplaceLeadList:
    result = marketplace_leads.query_leads(
        skip=skip,
        limit=limit,
        source_id=source_id,
        search=search,
        tier=tier,
        lead_kind=lead_kind,
        opportunity_lane=opportunity_lane,
        communication_burden=communication_burden,
        preferred_only=preferred_only,
        budget_band=budget_band,
        delivery_scope=delivery_scope,
        tech_stack=tech_stack,
        region=region,
        timezone_fit=timezone_fit,
        reviewable_only=reviewable_only,
        overdue_only=overdue_only,
        lead_status=lead_status,
        lead_outcome=lead_outcome,
        todo_sort=todo_sort,
    )
    return MarketplaceLeadList(
        total=result.total,
        tier_breakdown=result.tier_breakdown,
        kind_breakdown=result.kind_breakdown,
        opportunity_lane_breakdown=result.opportunity_lane_breakdown,
        communication_breakdown=result.communication_breakdown,
        status_breakdown=result.status_breakdown,
        outcome_breakdown=result.outcome_breakdown,
        outcome_reason_breakdown=result.outcome_reason_breakdown,
        todo_breakdown=result.todo_breakdown,
        source_breakdown=[
            MarketplaceLeadSourceMetricRead.model_validate(item) for item in result.source_breakdown
        ],
        source_conversion_breakdown=[
            MarketplaceLeadConversionMetricRead.model_validate(item)
            for item in result.source_conversion_breakdown
        ],
        segment_conversion_breakdown=[
            MarketplaceLeadConversionMetricRead.model_validate(item)
            for item in result.segment_conversion_breakdown
        ],
        source_recommendations=[
            MarketplaceSourceRecommendationRead.model_validate(item)
            for item in result.source_recommendations
        ],
        todo_queue=[
            MarketplaceLeadReminderRead.model_validate(item) for item in result.todo_queue
        ],
        items=[_to_marketplace_lead_read(item) for item in result.items],
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
    return _to_marketplace_lead_read(item)


@router.put("/{lead_id}/outcome", response_model=MarketplaceLeadRead, summary="更新外包项目线索结果")
async def update_marketplace_lead_outcome(
    lead_id: int,
    payload: MarketplaceLeadOutcomeUpdate,
) -> MarketplaceLeadRead:
    try:
        outcome = (
            marketplace_leads.MarketplaceLeadOutcome(payload.outcome)
            if payload.outcome is not None
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsupported marketplace lead outcome") from exc
    try:
        item = marketplace_leads.update_lead_outcome(lead_id, outcome, payload.reason_tags)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return _to_marketplace_lead_read(item)


@router.post(
    "/bulk-outcome",
    response_model=list[MarketplaceLeadRead],
    summary="批量更新外包项目线索结果",
)
async def bulk_update_marketplace_lead_outcome(
    payload: MarketplaceLeadBulkOutcomeUpdate,
) -> list[MarketplaceLeadRead]:
    try:
        outcome = (
            marketplace_leads.MarketplaceLeadOutcome(payload.outcome)
            if payload.outcome is not None
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsupported marketplace lead outcome") from exc
    try:
        items = marketplace_leads.bulk_update_lead_outcome(
            payload.ids,
            outcome,
            payload.reason_tags,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return [_to_marketplace_lead_read(item) for item in items]


@router.post(
    "/proposal-drafts/prepare",
    response_model=MarketplaceProposalPrepareResult,
    summary="为高优先级线索批量准备投递草稿",
)
async def prepare_marketplace_proposal_drafts(
    payload: MarketplaceProposalPrepare,
) -> MarketplaceProposalPrepareResult:
    result = proposal_submissions.prepare_proposals(
        limit=payload.limit,
        min_priority_score=payload.min_priority_score,
    )
    return MarketplaceProposalPrepareResult(
        created=result.created,
        skipped=result.skipped,
        items=[MarketplaceProposalRead.model_validate(item) for item in result.items],
    )


@router.get(
    "/{lead_id}/proposal",
    response_model=MarketplaceProposalRead | None,
    summary="获取线索投递草稿",
)
async def get_marketplace_proposal(lead_id: int) -> MarketplaceProposalRead | None:
    try:
        proposal = proposal_submissions.get_proposal(lead_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return MarketplaceProposalRead.model_validate(proposal) if proposal is not None else None


@router.post(
    "/{lead_id}/proposal",
    response_model=MarketplaceProposalRead,
    summary="生成或重新生成线索投递草稿",
)
async def generate_marketplace_proposal(
    lead_id: int,
    payload: MarketplaceProposalGenerate,
) -> MarketplaceProposalRead:
    try:
        proposal = proposal_submissions.generate_proposal(lead_id, force=payload.force)
    except proposal_submissions.InvalidProposalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return MarketplaceProposalRead.model_validate(proposal)


@router.put(
    "/{lead_id}/proposal",
    response_model=MarketplaceProposalRead,
    summary="编辑线索投递草稿",
)
async def edit_marketplace_proposal(
    lead_id: int,
    payload: MarketplaceProposalContentUpdate,
) -> MarketplaceProposalRead:
    try:
        proposal = proposal_submissions.update_proposal_content(
            lead_id,
            proposal_text=payload.proposal_text,
            suggested_price=payload.suggested_price,
            delivery_days=payload.delivery_days,
        )
    except proposal_submissions.InvalidProposalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail="proposal not found") from exc
    return MarketplaceProposalRead.model_validate(proposal)


@router.put(
    "/{lead_id}/proposal/status",
    response_model=MarketplaceProposalRead,
    summary="更新投递草稿状态",
)
async def update_marketplace_proposal_status(
    lead_id: int,
    payload: MarketplaceProposalStatusUpdate,
) -> MarketplaceProposalRead:
    try:
        status = proposal_submissions.ProposalStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsupported proposal status") from exc
    try:
        proposal = proposal_submissions.update_proposal_status(lead_id, status)
    except proposal_submissions.InvalidProposalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail="proposal not found") from exc
    return MarketplaceProposalRead.model_validate(proposal)


@router.get("/{lead_id}", response_model=MarketplaceLeadRead, summary="获取单条外包项目线索详情")
async def get_marketplace_lead(lead_id: int) -> MarketplaceLeadRead:
    try:
        item = marketplace_leads.get_lead(lead_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return _to_marketplace_lead_read(item)


@router.put("/{lead_id}/notes", response_model=MarketplaceLeadRead, summary="更新外包项目线索备注")
async def update_marketplace_lead_notes(
    lead_id: int,
    payload: MarketplaceLeadNotesUpdate,
) -> MarketplaceLeadRead:
    try:
        item = marketplace_leads.update_lead_notes(lead_id, payload.notes)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return _to_marketplace_lead_read(item)


@router.put(
    "/{lead_id}/follow-up",
    response_model=MarketplaceLeadRead,
    summary="更新外包项目线索下次跟进时间",
)
async def update_marketplace_lead_follow_up(
    lead_id: int,
    payload: MarketplaceLeadFollowUpUpdate,
) -> MarketplaceLeadRead:
    next_follow_up_at = None
    if payload.next_follow_up_at:
        try:
            next_follow_up_at = datetime.fromisoformat(payload.next_follow_up_at)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid next follow-up timestamp") from exc
    try:
        item = marketplace_leads.update_lead_follow_up(
            lead_id,
            next_follow_up_at,
            payload.follow_up_reason,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="marketplace lead not found") from exc
    return _to_marketplace_lead_read(item)


def _to_marketplace_lead_read(item: marketplace_leads.MarketplaceLead) -> MarketplaceLeadRead:
    payload = MarketplaceLeadRead.model_validate(item).model_dump()
    payload["lead_events"] = [
        MarketplaceLeadEventRead.model_validate(event).model_dump()
        for event in item.lead_events
    ]
    return MarketplaceLeadRead.model_validate(payload)
