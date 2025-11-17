"""与下游系统同步候选需求的辅助方法。"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core import metrics
from app.core.logging import get_logger
from app.models import CandidateNeed, SyncChannel
from app.schemas import CandidateNeedRead
from app.services import candidate_needs, mq, sync_audit

logger = get_logger(__name__)


@dataclass(slots=True)
class SyncDeliveryResult:
    """记录单条候选需求同步的结果。"""

    need_id: int
    success: bool
    channel: SyncChannel
    status_code: int | None = None
    error: str | None = None


async def deliver_need_to_webhook(
    need: CandidateNeed,
    *,
    webhook_url: str,
    client: httpx.AsyncClient,
    attempt: int = 1,
) -> SyncDeliveryResult:
    """将候选需求推送至配置的 webhook 并返回执行结果。"""

    payload = CandidateNeedRead.model_validate(need).model_dump(mode="json")
    try:
        response = await client.post(webhook_url, json=payload)
    except httpx.HTTPError as exc:
        candidate_needs.mark_need_sync_failed(need.id, str(exc))
        metrics.record_downstream_delivery(SyncChannel.WEBHOOK.value, "network-error")
        sync_audit.log_sync_attempt(
            need.id,
            channel=SyncChannel.WEBHOOK,
            status="failed",
            attempt=attempt,
            message=str(exc),
        )
        return SyncDeliveryResult(
            need_id=need.id,
            success=False,
            channel=SyncChannel.WEBHOOK,
            status_code=None,
            error=str(exc),
        )

    if 200 <= response.status_code < 300:
        candidate_needs.mark_need_synced(need.id)
        metrics.record_downstream_delivery(SyncChannel.WEBHOOK.value, "success")
        sync_audit.log_sync_attempt(
            need.id,
            channel=SyncChannel.WEBHOOK,
            status="success",
            attempt=attempt,
            metadata={"status_code": response.status_code},
        )
        return SyncDeliveryResult(
            need_id=need.id,
            success=True,
            channel=SyncChannel.WEBHOOK,
            status_code=response.status_code,
            error=None,
        )

    message = f"HTTP {response.status_code}"
    candidate_needs.mark_need_sync_failed(need.id, message)
    metrics.record_downstream_delivery(SyncChannel.WEBHOOK.value, "http-error")
    sync_audit.log_sync_attempt(
        need.id,
        channel=SyncChannel.WEBHOOK,
        status="failed",
        attempt=attempt,
        message=message,
        metadata={"status_code": response.status_code},
    )
    return SyncDeliveryResult(
        need_id=need.id,
        success=False,
        channel=SyncChannel.WEBHOOK,
        status_code=response.status_code,
        error=message,
    )


def publish_need_to_mq(
    need: CandidateNeed,
    *,
    publisher: mq.BaseMQPublisher | None = None,
    attempt: int = 1,
) -> SyncDeliveryResult:
    """将候选需求写入消息队列。"""

    if publisher is None:
        publisher = mq.build_publisher()
    if publisher is None:
        raise RuntimeError("MQ publisher is not configured")

    payload = CandidateNeedRead.model_validate(need).model_dump(mode="json")
    result = publisher.publish(payload)
    if result.success:
        candidate_needs.mark_need_synced(need.id)
        metrics.record_downstream_delivery(SyncChannel.MQ.value, "success")
        sync_audit.log_sync_attempt(
            need.id,
            channel=SyncChannel.MQ,
            status="success",
            attempt=attempt,
            metadata=result.metadata or {},
        )
        return SyncDeliveryResult(
            need_id=need.id,
            success=True,
            channel=SyncChannel.MQ,
            status_code=None,
        )

    message = result.error or "publish-failed"
    candidate_needs.mark_need_sync_failed(need.id, message)
    metrics.record_downstream_delivery(SyncChannel.MQ.value, "error")
    sync_audit.log_sync_attempt(
        need.id,
        channel=SyncChannel.MQ,
        status="failed",
        attempt=attempt,
        message=message,
    )
    logger.warning("downstream.mq.failed", need_id=need.id, error=message)
    return SyncDeliveryResult(
        need_id=need.id,
        success=False,
        channel=SyncChannel.MQ,
        error=message,
    )
