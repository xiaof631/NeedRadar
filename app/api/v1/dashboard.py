"""仪表盘相关 API。"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.dashboard import DashboardMetricsRead
from app.services import dashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics", summary="仪表盘核心指标", response_model=DashboardMetricsRead)
async def get_dashboard_metrics() -> DashboardMetricsRead:
    """返回抓取、筛选与候选需求的聚合指标。"""

    metrics = dashboard.get_dashboard_metrics()
    return DashboardMetricsRead.from_metrics(metrics)
