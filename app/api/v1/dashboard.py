"""仪表盘相关 API。"""

from __future__ import annotations

from app.schemas.dashboard import AlertRead, DashboardMetricsRead
from app.services import alerts as alerts_service
from app.services import dashboard
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics", summary="仪表盘核心指标", response_model=DashboardMetricsRead)
async def get_dashboard_metrics() -> DashboardMetricsRead:
    """返回抓取、筛选与候选需求的聚合指标。"""

    metrics = dashboard.get_dashboard_metrics()
    return DashboardMetricsRead.from_metrics(metrics)


@router.get("/alerts", summary="系统告警", response_model=list[AlertRead])
async def list_dashboard_alerts() -> list[AlertRead]:
    """返回当前需要关注的系统告警。"""

    alerts = alerts_service.generate_system_alerts()
    return [AlertRead.from_alert(alert) for alert in alerts]
