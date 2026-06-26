"""v1 版本 API 路由。"""

from app.api.v1 import (
    candidate_needs,
    customer_radar,
    dashboard,
    email_followups,
    fetch_logs,
    filter_metrics,
    filter_rules,
    marketplace_leads,
    raw_entries,
    rss_sources,
)
from fastapi import APIRouter

router = APIRouter()
router.include_router(rss_sources.router)
router.include_router(marketplace_leads.router)
router.include_router(raw_entries.router)
router.include_router(filter_rules.router)
router.include_router(filter_metrics.router)
router.include_router(candidate_needs.router)
router.include_router(customer_radar.router)
router.include_router(email_followups.router)
router.include_router(fetch_logs.router)
router.include_router(dashboard.router)


@router.get("/ping", summary="基础连通性测试")
async def ping() -> dict[str, str]:
    """用于 API 版本的连通性测试。"""

    return {"message": "pong"}
