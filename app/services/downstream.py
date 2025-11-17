"""与下游系统同步候选需求的辅助方法。"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core import metrics
from app.models import CandidateNeed
from app.schemas import CandidateNeedRead
from app.services import candidate_needs


@dataclass(slots=True)
class SyncDeliveryResult:
    """记录单条候选需求同步的结果。"""

    need_id: int
    success: bool
    status_code: int | None = None
    error: str | None = None


async def deliver_need_to_webhook(
    need: CandidateNeed,
    *,
    webhook_url: str,
    client: httpx.AsyncClient,
) -> SyncDeliveryResult:
    """将候选需求推送至配置的 webhook 并返回执行结果。"""

    payload = CandidateNeedRead.model_validate(need).model_dump(mode="json")
    try:
        response = await client.post(webhook_url, json=payload)
    except httpx.HTTPError as exc:
        candidate_needs.mark_need_sync_failed(need.id, str(exc))
        metrics.record_downstream_delivery("network-error")
        return SyncDeliveryResult(
            need_id=need.id,
            success=False,
            status_code=None,
            error=str(exc),
        )

    if 200 <= response.status_code < 300:
        candidate_needs.mark_need_synced(need.id)
        metrics.record_downstream_delivery("success")
        return SyncDeliveryResult(
            need_id=need.id,
            success=True,
            status_code=response.status_code,
            error=None,
        )

    message = f"HTTP {response.status_code}"
    candidate_needs.mark_need_sync_failed(need.id, message)
    metrics.record_downstream_delivery("http-error")
    return SyncDeliveryResult(
        need_id=need.id,
        success=False,
        status_code=response.status_code,
        error=message,
    )
