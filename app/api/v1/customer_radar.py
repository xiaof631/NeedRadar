"""客户雷达 API。"""

from __future__ import annotations

from app.models import SourceType
from app.schemas.customer_radar import (
    CustomerOpportunityRead,
    CustomerRadarList,
    CustomerRadarSummaryRead,
)
from app.services import customer_radar
from fastapi import APIRouter, Query

router = APIRouter(prefix="/customer-radar", tags=["Customer Radar"])


@router.get("/", response_model=CustomerRadarList, summary="查询 DocReview 客户机会")
async def list_customer_opportunities(
    skip: int = Query(default=0, ge=0, description="跳过的记录数量"),
    limit: int = Query(default=30, ge=1, le=100, description="返回的记录数量"),
    search: str | None = Query(default=None, description="按标题、痛点或来源搜索"),
    source_type: SourceType | None = Query(default=None, description="按来源类型过滤"),
    segment: customer_radar.CustomerSegment | None = Query(
        default=None, description="按客户场景过滤"
    ),
    action: customer_radar.RecommendedAction | None = Query(
        default=None, description="按推荐动作过滤"
    ),
    min_score: int = Query(default=45, ge=0, le=100, description="最低客户匹配分"),
) -> CustomerRadarList:
    result = customer_radar.query_opportunities(
        skip=skip,
        limit=limit,
        search=search,
        source_type=source_type,
        segment=segment,
        action=action,
        min_score=min_score,
    )
    return CustomerRadarList(
        total=result.total,
        summary=CustomerRadarSummaryRead.model_validate(result.summary),
        items=[CustomerOpportunityRead.model_validate(item) for item in result.items],
    )
