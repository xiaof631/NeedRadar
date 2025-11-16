"""筛选流程指标相关 API。"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import FilterPerformanceRead
from app.services import filter_metrics

router = APIRouter(prefix="/filter-metrics", tags=["Filter Metrics"])


@router.get("/", summary="获取筛选流程指标", response_model=FilterPerformanceRead)
async def get_filter_metrics() -> FilterPerformanceRead:
    """返回规则筛选和候选需求转化的关键指标。"""

    metrics = filter_metrics.get_filter_performance()
    return FilterPerformanceRead.from_domain(metrics)
